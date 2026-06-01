# app_modules/signals/constants.py
"""
Constants for the Signals module.

Defines all TextChoices enums used across signal models and cluster
aggregation logic.

Lifecycle / cross-cutting:
  SignalStatus   — lifecycle states shared by all signal types
  SignalSource   — how / where a signal originated
  SignalCategory — high-level commercial category (optional tagging)

Model-specific:
  PeopleRole       — stakeholder role for PeopleSignal
  InfluenceLevel   — stakeholder influence level for PeopleSignal
  SignalWhat       — domain axis for canonical-keyed signals
                     (PainSignal, ObjectiveSignal, ImpactSignal).
                     First component of the canonical_key.
  SignalDimension  — friction / outcome axis for canonical-keyed signals.
                     Second component of the canonical_key.
  ScopeLevel       — organisational scope of the evidence
                     (BUSINESS / DEPARTMENT / PERSONAL). Used by
                     PainSignal, ObjectiveSignal, and ImpactSignal.
  UsageScope       — organisational usage scope of a tool for TechStackSignal
                     (TEAM / DEPARTMENT / COMPANY / UNKNOWN). Drives the
                     conditional usage_department requirement.
  ImpactType       — nature of an Impact observation (FINANCIAL, TIME,
                     PRODUCTIVITY, REVENUE, RISK, CUSTOMER, HUMAN,
                     STRATEGIC, METRIC). Used by ImpactSignal.
  HumanImpactType  — optional human dimension of an Impact (FRUSTRATION,
                     OVERLOAD, STRESS, DEMOTIVATION, CONFLICT). Used by
                     ImpactSignal when impact_type=HUMAN — typically
                     emitted at PERSONAL scope. Renamed from the legacy
                     HumanImpact enum; the DB values are strictly identical.

Cluster aggregation:
  SignalClusterType — enumeration of signal types that support clustering
  FreshnessStatus   — age-based freshness of a cluster
  PriorityBucket    — coarse priority label derived from a numeric score

Thresholds (cluster aggregation):
  FRESHNESS_FRESH_DAYS   — upper bound (exclusive) of FRESH status
  FRESHNESS_DORMANT_DAYS — upper bound (exclusive) of DORMANT status
  PRIORITY_HIGH_THRESHOLD   — minimum score for HIGH bucket
  PRIORITY_MEDIUM_THRESHOLD — minimum score for MEDIUM bucket

Removed vs. previous versions:
  - SignalStatus.MERGED   (merge operation removed from the module)
  - QualificationField    (replaced by dedicated structured models)
  - TechStackField        (replaced by rich fields on TechStackSignal)
  - PainCategory          (replaced by the canonical pair
                           SignalWhat × SignalDimension)
  - PainLevel             (replaced by ScopeLevel — Pain is now a pure
                           diagnosis)
  - TechCategory          (replaced by FK to TechCatalog — categorisation
                           moves out of the signal into the tenant-level
                           tech master catalog)
  - Satisfaction          (dropped — qualitative feel of a tool was rarely
                           used and noisy. Replaced by structured lifecycle
                           stats on the TechStack cluster: usage_start_year,
                           renewal_date, cost_description, is_discontinued)

The canonical_key format follows the same pattern across all
canonical-axes signal types:
  - PainSignal:      "pain:<SignalWhat>:<SignalDimension>"
  - ObjectiveSignal: "objective:<SignalWhat>:<SignalDimension>"
  - ImpactSignal:    "impact:<SignalWhat>:<SignalDimension>"

Enum values (DB strings) are strictly unchanged — only Python class
names change.
"""



from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# SIGNAL STATUS
# =============================================================================

class SignalStatus(models.TextChoices):
    """
    Lifecycle states shared by all signal types.

    PENDING   — created by LLM extraction, awaiting rep validation
    VALIDATED — approved by the rep (or created manually via MANUAL source)
    REJECTED  — dismissed by the rep; kept for audit trail, never deleted
    """
    PENDING   = 'PENDING',   _('Pending')
    VALIDATED = 'VALIDATED', _('Validated')
    REJECTED  = 'REJECTED',  _('Rejected')


# =============================================================================
# SIGNAL SOURCE
# =============================================================================

class SignalSource(models.TextChoices):
    """
    Origin of a signal.

    Used to drive auto-validation logic in BaseSignal.save() and to
    communicate provenance to the rep and to LLM prompts.

    MANUAL            — entered directly by the rep after a conversation
                        → status forced to VALIDATED by BaseSignal.save()
    LLM_EXTRACTED     — extracted from a transcript by LLM
                        → status starts PENDING, rep must validate
                        → may still carry a source_activity when the LLM
                           processed a known CRM activity transcript
    LLM_MODIFIED      — extracted by LLM then edited by the rep before
                        validation; original value preserved in original_value
    EXTERNAL_RESEARCH — sourced from outside a CRM conversation
                        (e.g. LinkedIn lookup, internet research, LLM analysis
                        of public data); source_activity will be null
    """
    MANUAL            = 'MANUAL',            _('Manual entry')
    LLM_EXTRACTED     = 'LLM_EXTRACTED',     _('LLM extracted')
    LLM_MODIFIED      = 'LLM_MODIFIED',      _('LLM modified')
    EXTERNAL_RESEARCH = 'EXTERNAL_RESEARCH', _('External research')


# =============================================================================
# SIGNAL CATEGORY
# =============================================================================

class SignalCategory(models.TextChoices):
    """
    High-level commercial category of the signal.

    Optional tag applied to any signal type for filtering and grouping.
    Does not drive any business logic — purely descriptive.

    ECONOMIC  — budget, costs, financial constraints
    TIME      — timeline, urgency, deadlines
    FRICTION  — blockers, risks, objections
    RISK      — deal risk, compliance, legal exposure
    STRATEGIC — strategic fit, executive alignment
    PEOPLE    — stakeholders, roles, relationships
    PROCESS   — buying process, decision criteria, workflows
    """
    ECONOMIC  = 'ECONOMIC',  _('Economic')
    TIME      = 'TIME',      _('Time')
    FRICTION  = 'FRICTION',  _('Friction')
    RISK      = 'RISK',      _('Risk')
    STRATEGIC = 'STRATEGIC', _('Strategic')
    PEOPLE    = 'PEOPLE',    _('People')
    PROCESS   = 'PROCESS',   _('Process')


# =============================================================================
# PEOPLE SIGNAL — enums
# =============================================================================

class PeopleRole(models.TextChoices):
    """
    Stakeholder role observed in a PeopleSignal.

    Represents the commercial or organisational role the target contact
    plays in the buying process at the account.

    DECISION_MAKER  — has formal authority to sign off the deal
    ECONOMIC_BUYER  — controls the budget (may differ from decision maker)
    CHAMPION        — internal advocate for the solution
    BLOCKER         — actively opposing or slowing the deal
    END_USER        — will use the product day-to-day
    PROCUREMENT     — owns the vendor / contract management process
    INFLUENCER      — shapes opinions without formal authority
    """
    DECISION_MAKER  = 'DECISION_MAKER',  _('Decision Maker')
    ECONOMIC_BUYER  = 'ECONOMIC_BUYER',  _('Economic Buyer')
    CHAMPION        = 'CHAMPION',        _('Champion')
    BLOCKER         = 'BLOCKER',         _('Blocker')
    END_USER        = 'END_USER',        _('End User')
    PROCUREMENT     = 'PROCUREMENT',     _('Procurement')
    INFLUENCER      = 'INFLUENCER',      _('Influencer')


class InfluenceLevel(models.TextChoices):
    """
    Perceived influence level of the stakeholder in PeopleSignal.

    Optional qualifier on top of PeopleRole to communicate how much
    weight this person carries in the buying decision.
    """
    HIGH   = 'HIGH',   _('High')
    MEDIUM = 'MEDIUM', _('Medium')
    LOW    = 'LOW',    _('Low')


# =============================================================================
# SIGNAL CANONICAL AXES — enums  (shared by Pain, Objective and Impact)
# =============================================================================
#
# Canonical-keyed signals are anchored on two orthogonal axes that
# together form the canonical_key used to group observations on an account:
#
#     canonical_key = "<signal_type>:<SignalWhat>:<SignalDimension>"
#
# Examples:
#     "pain:OPS:TIME"
#     "objective:GROWTH:COST"
#
# SignalWhat      — the domain of the signal (what area of the business it affects)
# SignalDimension — the friction or outcome experienced in that domain
#
# 5 × 5 = 25 possible canonical slots — enough expressiveness to describe any
# B2B pain or objective without fragmenting the cluster space.
#
# Impact-level data (BUSINESS / DEPARTMENT / PERSONAL scope, metrics,
# human consequences) lives on ImpactSignal — a first-class signal type.
# ScopeLevel and HumanImpactType (below) describe the ImpactSignal side
# of the picture.
# =============================================================================


class SignalWhat(models.TextChoices):
    """
    Domain axis of a canonical-keyed signal — what area of the business
    is affected.

    First component of the canonical_key: "<type>:<what>:<dimension>".

    Used by:
      - PainSignal.what          
      - ObjectiveSignal.what
      - ImpactSignal.what     

    OPS    — operations, processes, execution bottlenecks
    TECH   — technology, systems, technical debt, integrations
    DATA   — data quality, reporting, visibility, analytics
    PEOPLE — org design, roles, skills, hiring, retention
    GROWTH — revenue, pipeline, acquisition, retention motion
    """
    OPS    = 'OPS',    _('Operations / Process')
    TECH   = 'TECH',   _('Technology / System')
    DATA   = 'DATA',   _('Data / Visibility')
    PEOPLE = 'PEOPLE', _('People / Org')
    GROWTH = 'GROWTH', _('Growth / Revenue')


class SignalDimension(models.TextChoices):
    """
    Friction / outcome axis of a canonical-keyed signal.

    Second component of the canonical_key: "<type>:<what>:<dimension>".

    Used by:
      - PainSignal.dimension         
      - ObjectiveSignal.dimension
      - ImpactSignal.dimension   

    TIME    — slowness, latency, time spent, speed constraints
    COST    — budget overruns, financial waste, cost pressure
    QUALITY — errors, inaccuracy, poor output, rework
    SCALE   — capacity limits, volume constraints, bottlenecks at scale
    RISK    — compliance, security, regulatory exposure, legal risk
    """
    TIME    = 'TIME',    _('Time / Speed')
    COST    = 'COST',    _('Cost / Budget')
    QUALITY = 'QUALITY', _('Quality / Accuracy')
    SCALE   = 'SCALE',   _('Scale / Capacity')
    RISK    = 'RISK',    _('Risk / Compliance')


class HumanImpactType(models.TextChoices):
    """
    Optional human dimension of an ImpactSignal — the personal
    consequence on an individual.

    Used on ImpactSignal when impact_type=HUMAN (and occasionally on
    other impact_types when relevant). Typically emitted at PERSONAL
    or DEPARTMENT scope.

    FRUSTRATION  — ongoing irritation, annoyance, dissatisfaction
    OVERLOAD     — workload pressure, too much to handle
    STRESS       — anxiety, tension, mental strain
    DEMOTIVATION — disengagement, loss of drive, apathy
    CONFLICT     — interpersonal tension, disputes, friction with peers
    """
    FRUSTRATION  = 'FRUSTRATION',  _('Frustration')
    OVERLOAD     = 'OVERLOAD',     _('Overload')
    STRESS       = 'STRESS',       _('Stress / Anxiety')
    DEMOTIVATION = 'DEMOTIVATION', _('Demotivation')
    CONFLICT     = 'CONFLICT',     _('Conflict')


# =============================================================================
# IMPACT TYPE — enum
# =============================================================================

class ImpactType(models.TextChoices):
    """
    Nature of an ImpactSignal observation.

    Required field on ImpactSignal — every impact observation must
    declare which kind of consequence or proof it represents. Not
    part of canonical_key (which is built from what × dimension);
    impact_type is an orthogonal axis that documents the FLAVOUR of
    the impact, separate from the business area (what) and friction
    axis (dimension).

    Used by:
      - ImpactSignal.impact_type

    Values:
      FINANCIAL     — direct monetary consequence (cost overrun,
                       opportunity cost in currency terms).
                       Example: "30k€/month lost on inefficient onboarding"
      TIME          — time-based consequence (hours, days, weeks
                       consumed or wasted).
                       Example: "Managers spend 5h/week on manual reports"
      PRODUCTIVITY  — output efficiency loss (tasks per period,
                       throughput drop).
                       Example: "Sales reps close 30% fewer deals due to
                       data quality"
      REVENUE       — revenue-side consequence (sales lost, deals
                       blocked, missed opportunities).
                       Example: "We lost 4 deals last quarter because of X"
      RISK          — exposure to compliance, security, legal, or
                       operational risk.
                       Example: "GDPR audit risk because of unverified
                       data lineage"
      CUSTOMER      — customer-facing consequence (churn, NPS drop,
                       complaints, satisfaction loss).
                       Example: "Customer churn at 15%"
      HUMAN         — qualitative human consequence (frustration,
                       overload, stress). Typically pairs with a
                       non-null human_impact field on the same
                       ImpactSignal.
                       Example: "Team is frustrated by reporting delays"
      STRATEGIC     — strategic alignment consequence (loss of focus,
                       priority drift, executive misalignment).
                       Example: "Engineering bandwidth pulled away from
                       product roadmap"
      METRIC        — raw quantified observation without a clear
                       business-impact classification. Captures
                       evidence the LLM extracted as a number but
                       could not categorise further — typically
                       refined by the rep at validation time.
                       Example: "Team of 50 people"
    """
    FINANCIAL    = 'FINANCIAL',    _('Financial impact')
    TIME         = 'TIME',         _('Time impact')
    PRODUCTIVITY = 'PRODUCTIVITY', _('Productivity impact')
    REVENUE      = 'REVENUE',      _('Revenue impact')
    RISK         = 'RISK',         _('Risk impact')
    CUSTOMER     = 'CUSTOMER',     _('Customer impact')
    HUMAN        = 'HUMAN',        _('Human impact')
    STRATEGIC    = 'STRATEGIC',    _('Strategic impact')
    METRIC       = 'METRIC',       _('Raw metric')


# =============================================================================
# SCOPE LEVEL — enum
# =============================================================================

class ScopeLevel(models.TextChoices):
    """
    Organisational scope level — the three mutually-exclusive layers
    under which evidence (a pain, a goal, or an impact) is anchored.

    Used by:
      - PainSignal.scope_level        — scope at which a pain is felt
      - ObjectiveSignal.scope_level   — scope at which an objective applies
      - ImpactSignal.scope_level      — scope at which an impact is measured

    The three levels map to a sales question:
      BUSINESS   — "How does this apply to the company overall?"
                   CFO-level framing.
      DEPARTMENT — "Which department does this concern?"
                   VP / team-lead framing.
      PERSONAL   — "Which individual is involved?"
                   Champion-level framing.

    Conditional logic per signal type:
      PainSignal   — default BUSINESS; no conditional FK requirement.
                     Purely descriptive.
      ObjectiveSignal — drives conditional target requirements
                     (PERSONAL → target_contact, DEPARTMENT →
                     target_department, BUSINESS → neither). See
                     ObjectiveSignal.clean().
      ImpactSignal — purely descriptive; no conditional FK requirement.
                     Documents the layer at which the rep observed the
                     impact (e.g. "30k€/mo" at BUSINESS, "5h/week per
                     AE" at PERSONAL).
    """
    BUSINESS   = 'BUSINESS',   _('Business')
    DEPARTMENT = 'DEPARTMENT', _('Department')
    PERSONAL   = 'PERSONAL',   _('Personal')


# =============================================================================
# TECH STACK SIGNAL — enums
# =============================================================================

class UsageScope(models.TextChoices):
    """
    Organisational usage scope of a tool observed at an account.

    Drives the conditional usage_department requirement on TechStackSignal:
      usage_scope = DEPARTMENT → usage_department REQUIRED
      usage_scope ∈ {TEAM, COMPANY, UNKNOWN} → usage_department FORBIDDEN

    TEAM       — used by a single team within a department
                 (granularity finer than department; usage_department
                 not specified because the team is not a first-class
                 entity in the platform)
    DEPARTMENT — used by a specific department; usage_department FK
                 must be set (StandardDepartment)
    COMPANY    — used company-wide across multiple departments
    UNKNOWN    — scope was discussed but not clarified, or not yet known.
                 Safe default for early-stage observations.

    INDIVIDUAL is intentionally NOT a value — single-user usage is captured
    through notes / source_quote on the signal itself, not promoted to a
    canonical scope.
    """
    TEAM       = 'TEAM',       _('Team')
    DEPARTMENT = 'DEPARTMENT', _('Department')
    COMPANY    = 'COMPANY',    _('Company-wide')
    UNKNOWN    = 'UNKNOWN',    _('Unknown')

# =============================================================================
# SIGNAL CLUSTER AGGREGATION — enums and thresholds 
# =============================================================================
#
# Clusters aggregate signals sharing the same canonical_key on a given account.
# The enums below describe cluster-level attributes (freshness, priority)
# that are computed on read — never stored on signal rows.
#
# Pain, Objective, Impact and Tech Stack signals are all clustered today.
# SignalClusterType is intentionally extensible so future signal types can
# plug in without introducing a second enum.
# =============================================================================


class SignalClusterType(models.TextChoices):
    """
    Signal types that support cluster aggregation.

    PAIN, OBJECTIVE, TECH_STACK, and IMPACT all produce real clusters
    today. The enum stays open-ended so that future signal types can
    plug into the same SignalClusterArchival table without a schema
    change.

    The string values intentionally match the keys used in
    SignalDataService._SIGNAL_TYPE_MAP (pain / objective / tech_stack /
    impact) so the same identifier travels through all layers.

    Cluster identity per type:
      pain       — "pain:<SignalWhat>:<SignalDimension>"
      objective  — "objective:<SignalWhat>:<SignalDimension>"
      tech_stack — "techstack:<TechCatalog.id>"
      impact     — "impact:<SignalWhat>:<SignalDimension>"
    """
    PAIN       = 'pain',       _('Pain')
    OBJECTIVE  = 'objective',  _('Objective')
    TECH_STACK = 'tech_stack', _('Tech Stack')
    IMPACT     = 'impact',     _('Impact')


class FreshnessStatus(models.TextChoices):
    """
    Age-based freshness of a signal cluster.

    Computed on read from the most recent VALIDATED signal's creation date.
    Never stored.

    FRESH   — last VALIDATED observation is younger than
              FRESHNESS_FRESH_DAYS (default 30).
    DORMANT — last VALIDATED observation is between
              FRESHNESS_FRESH_DAYS and FRESHNESS_DORMANT_DAYS (default 30–90).
    STALE   — last VALIDATED observation is older than
              FRESHNESS_DORMANT_DAYS (default 90).

    Exception enforced by SignalClusterService:
      If at least one member signal references a decision cycle that is
      still active (outcome IS NULL or outcome = ON_HOLD), the cluster is
      never STALE — it is clamped to DORMANT at worst. Rationale: as long
      as a deal is alive (even paused), its associated pain is not stale.
    """
    FRESH   = 'FRESH',   _('Fresh')
    DORMANT = 'DORMANT', _('Dormant')
    STALE   = 'STALE',   _('Stale')


class PriorityBucket(models.TextChoices):
    """
    Coarse priority label for a cluster, derived from a numeric score.

    The underlying score (0–100) is exposed in the API for debugging but
    the UI only displays the bucket. Thresholds are tunable via
    PRIORITY_HIGH_THRESHOLD and PRIORITY_MEDIUM_THRESHOLD.

    HIGH   — score >= PRIORITY_HIGH_THRESHOLD     (default 70)
    MEDIUM — PRIORITY_MEDIUM_THRESHOLD <= score < PRIORITY_HIGH_THRESHOLD
             (default 40–69)
    LOW    — score < PRIORITY_MEDIUM_THRESHOLD    (default < 40)
    """
    HIGH   = 'HIGH',   _('High')
    MEDIUM = 'MEDIUM', _('Medium')
    LOW    = 'LOW',    _('Low')


# -----------------------------------------------------------------------------
# Freshness thresholds (days)
# -----------------------------------------------------------------------------
# A cluster is FRESH while its most recent VALIDATED signal is newer than
# FRESHNESS_FRESH_DAYS. It becomes DORMANT once older, and STALE past
# FRESHNESS_DORMANT_DAYS — subject to the active-DC exception described on
# FreshnessStatus.
#
# These constants are the single source of truth — adjust here to retune
# the freshness policy without touching service code.
# -----------------------------------------------------------------------------

FRESHNESS_FRESH_DAYS   = 30
FRESHNESS_DORMANT_DAYS = 90


# -----------------------------------------------------------------------------
# Priority bucket thresholds
# -----------------------------------------------------------------------------
# Score buckets applied by SignalPriorityService.bucket_from_score().
# The priority score itself is computed by compute_pain_priority_score()
# using the PAIN_PRIORITY_WEIGHTS dict (see services/signal_priority_service.py).
#
# Kept here (not in the service module) so product can tune the bucket
# cutoffs without opening the priority calculation — separation of concerns
# between "how the score is built" and "how the score is labelled".
# -----------------------------------------------------------------------------

PRIORITY_HIGH_THRESHOLD   = 70
PRIORITY_MEDIUM_THRESHOLD = 40
TECHSTACK_RENEWAL_SOON_DAYS = 90

# =============================================================================
# CACHE TAGS
# =============================================================================
#
# Redis cache namespaces used by the Signals module.
#
# Rationale for two separate tags
# -------------------------------
# A single 'signals' tag would force full cache invalidation on every
# write. That is wasteful because:
#
#   - Validating an Objective signal does not affect cluster stats
#     (clusters are busted only by Pain and Impact writes).
#   - Archiving a cluster does not change any signal data, only its
#     visibility in cluster listings.
#
# Splitting into two tags gives each surface a precise invalidation
# contract. See cache_invalidation.py (safety-net signals) and the
# ViewSet _invalidate_* helpers (immediate post-write invalidation).
#
# Invalidation matrix
# -------------------
#
#   Write on                  signals   signal_clusters
#   ---------------------    -------   ---------------
#   PainSignal                   ✓            ✓  (cluster member)
#   ObjectiveSignal              ✓            ✗
#   ImpactSignal                 ✓            ✓  (cluster member)
#   TechStackSignal              ✓            ✗
#   BlockerSignal                ✓            ✗  (non-clustering)
#   NextStepSignal               ✓            ✗  (non-clustering)
#   SignalClusterArchival        ✗            ✓  (archival-only)
# =============================================================================

# Shared namespace for list / detail / filtered signal caches.
# Any write on a concrete signal type (Pain / Objective / Impact /
# TechStack) invalidates this tag.
SIGNALS_CACHE_TAG = 'signals'

# Dedicated namespace for cluster list / detail responses.
# Writes that do NOT change cluster content (e.g. validating an Objective
# signal) must not bust this tag — that is the whole point of the split.
#
# Invalidated on:
#   - PainSignal create/update/delete        (cluster membership changes)
#   - ImpactSignal create/update/delete      (cluster membership changes)
#   - SignalClusterArchival create/update    (archive / unarchive toggle
#                                              — affects include_archived
#                                              filtering in list views)
SIGNAL_CLUSTERS_CACHE_TAG = 'signal_clusters'