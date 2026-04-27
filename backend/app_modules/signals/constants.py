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
  PeopleRole      — stakeholder role for PeopleSignal
  InfluenceLevel  — stakeholder influence level for PeopleSignal
  SignalWhat      — domain axis for canonical-keyed signals (Pain, and
                    Objective once Wave B ships). First component of the
                    canonical_key.
  SignalDimension — friction / outcome axis for canonical-keyed signals.
                    Second component of the canonical_key.
  HumanImpact     — orthogonal human impact axis for PainImpact (optional,
                    only meaningful at PERSONAL scope level)
  ScopeLevel      — organisational scope of the evidence
                    (BUSINESS / DEPARTMENT / PERSONAL). Used by PainImpact
                    today; will also drive ObjectiveSignal scope once the
                    Objective port lands (Wave B).
  TechCategory    — technology category for TechStackSignal
  Satisfaction    — satisfaction level for TechStackSignal

Cluster aggregation (Sprint 2):
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
  - PainLevel             (replaced by ScopeLevel on PainImpact — Pain is
                           now a pure diagnosis, scope lives on PainImpact)

Renamed in Wave A (backend refactor prep for the Objective port):
  - PainWhat      → SignalWhat       (shared across Pain and Objective)
  - PainDimension → SignalDimension  (shared across Pain and Objective)
  - ImpactLevel   → ScopeLevel       (shared across PainImpact and — Wave B —
                                      ObjectiveSignal)

Dropped in Wave A:
  - GoalLevel — superseded by the shared ScopeLevel. Objective will
                adopt ScopeLevel during the Wave B port.

The canonical_key format is unchanged:
  - PainSignal:      "pain:<SignalWhat>:<SignalDimension>"
  - ObjectiveSignal: "objective:<SignalWhat>:<SignalDimension>"  (Wave B)

Enum values (DB strings) are strictly unchanged by Wave A — only the
Python class names change.
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
# SIGNAL CANONICAL AXES — enums  (shared by Pain and Objective)
# =============================================================================
#
# Canonical-keyed signals are anchored on two orthogonal axes that
# together form the canonical_key used to group observations on an account:
#
#     canonical_key = "<signal_type>:<SignalWhat>:<SignalDimension>"
#
# Examples:
#     "pain:OPS:TIME"
#     "objective:GROWTH:COST"   (Wave B — not yet emitted)
#
# SignalWhat      — the domain of the signal (what area of the business it affects)
# SignalDimension — the friction or outcome experienced in that domain
#
# 5 × 5 = 25 possible canonical slots — enough expressiveness to describe any
# B2B pain or objective without fragmenting the cluster space.
#
# Impact-level data (BUSINESS / DEPARTMENT / PERSONAL scope, metrics,
# human consequences) lives on PainImpact — a separate model attached to
# PainSignal. See the PainImpact docstring for details. ScopeLevel and
# HumanImpact (below) describe the PainImpact side of the picture.
# =============================================================================


class SignalWhat(models.TextChoices):
    """
    Domain axis of a canonical-keyed signal — what area of the business
    is affected.

    First component of the canonical_key: "<type>:<what>:<dimension>".

    Used by:
      - PainSignal.what          (today)
      - ObjectiveSignal.what     (Wave B)

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
      - PainSignal.dimension         (today)
      - ObjectiveSignal.dimension    (Wave B)

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


class HumanImpact(models.TextChoices):
    """
    Personal consequence on an individual — the human side of a pain.

    Used on PainImpact at PERSONAL scope level (optional). Not part of
    any canonical_key. When set, the parent PainImpact must have
    level=ScopeLevel.PERSONAL and a non-null impacted_contact
    (enforced in PainImpact.clean()).

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
# SCOPE LEVEL — enum  (shared by PainImpact and — Wave B — Objective)
# =============================================================================

class ScopeLevel(models.TextChoices):
    """
    Organisational scope level — the three mutually-exclusive angles
    under which evidence (or a goal) can be anchored.

    Used by:
      - PainImpact.level              — scope of a documented pain impact
      - ObjectiveSignal.goal_level    — scope of an objective (Wave B)

    On PainImpact, each level drives conditional field requirements
    (see PainImpact.clean()) and maps to a distinct sales question:

      BUSINESS   — "How much does it cost the company overall?"
                   CFO-level evidence. metric + notes.
      DEPARTMENT — "Which department pays the price?"
                   VP-level evidence. impacted_department + metric + notes.
      PERSONAL   — "Who personally bears this pain?"
                   Champion-level evidence. impacted_contact + metric (opt)
                   + human_impact (opt) + notes.

    On ObjectiveSignal (Wave B), the same three levels describe at which
    layer of the organisation the objective applies.
    """
    BUSINESS   = 'BUSINESS',   _('Business')
    DEPARTMENT = 'DEPARTMENT', _('Department')
    PERSONAL   = 'PERSONAL',   _('Personal')


# =============================================================================
# TECH STACK SIGNAL — enums
# =============================================================================

class TechCategory(models.TextChoices):
    """
    Technology category for TechStackSignal.

    Classifies the type of tool or platform the account is using.
    Used for filtering and LLM prompt grouping.

    CRM           — customer relationship management
    ERP           — enterprise resource planning
    BI            — business intelligence / analytics
    HR            — human resources / HCM
    MARKETING     — marketing automation, email, ads
    SECURITY      — cybersecurity, IAM, compliance tools
    CLOUD         — cloud infrastructure, IaaS, PaaS
    COLLABORATION — communication, project management, productivity
    FINANCE       — accounting, FP&A, expense management
    OTHER         — tools that do not fit the above categories
    """
    CRM           = 'CRM',           _('CRM')
    ERP           = 'ERP',           _('ERP')
    BI            = 'BI',            _('BI & Analytics')
    HR            = 'HR',            _('HR & People')
    MARKETING     = 'MARKETING',     _('Marketing')
    SECURITY      = 'SECURITY',      _('Security')
    CLOUD         = 'CLOUD',         _('Cloud Infrastructure')
    COLLABORATION = 'COLLABORATION', _('Collaboration')
    FINANCE       = 'FINANCE',       _('Finance')
    OTHER         = 'OTHER',         _('Other')


class Satisfaction(models.TextChoices):
    """
    Rep-assessed satisfaction level of the account with a tool in TechStackSignal.

    Based on what was expressed during the conversation — not a formal score.
    UNKNOWN is the safe default when satisfaction was not discussed.

    HIGH    — account is satisfied or positive about the tool
    MEDIUM  — mixed feelings, some concerns raised
    LOW     — clear dissatisfaction or frustration expressed
    UNKNOWN — satisfaction was not discussed or is unclear
    """
    HIGH    = 'HIGH',    _('High')
    MEDIUM  = 'MEDIUM',  _('Medium')
    LOW     = 'LOW',     _('Low')
    UNKNOWN = 'UNKNOWN', _('Unknown')

# =============================================================================
# SIGNAL CLUSTER AGGREGATION — enums and thresholds (Sprint 2)
# =============================================================================
#
# Clusters aggregate signals sharing the same canonical_key on a given account.
# The enums below describe cluster-level attributes (freshness, priority)
# that are computed on read — never stored on signal rows.
#
# Only PainSignal is actively clustered today. SignalClusterType is
# intentionally extensible so later waves can add Objective / TechStack
# clustering without introducing a second enum.
# =============================================================================


class SignalClusterType(models.TextChoices):
    """
    Signal types that support cluster aggregation.

    In the current sprint only PAIN is actively aggregated. PEOPLE,
    OBJECTIVE, and TECH_STACK are reserved — kept in the enum so the
    same SignalClusterArchival table can serve them without a schema
    change when their respective waves ship.

    The string values intentionally match the keys used in
    SignalDataService._SIGNAL_TYPE_MAP (people / pain / objective /
    tech_stack) so the same identifier travels through all layers.
    """
    PAIN       = 'pain',       _('Pain')
    PEOPLE     = 'people',     _('People')       # reserved — not aggregated yet
    OBJECTIVE  = 'objective',  _('Objective')    # reserved — activates in Wave B
    TECH_STACK = 'tech_stack', _('Tech Stack')   # reserved — not aggregated yet


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
#   - Validating a People signal does not affect Pain cluster stats
#     (clusters are computed from Pain signals + PainImpact only).
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
#   PeopleSignal                 ✓            ✗
#   PainSignal                   ✓            ✓  (cluster member)
#   ObjectiveSignal              ✓            ✗
#   TechStackSignal              ✓            ✗
#   PainImpact                   ✓            ✓  (cluster stats pivot)
#   SignalClusterArchival        ✗            ✓  (archival-only)
# =============================================================================

# Shared namespace for list / detail / filtered signal caches.
# Any write on a concrete signal type (People / Pain / Objective /
# TechStack) invalidates this tag. PainImpact writes also invalidate
# it because impacts are rendered inline in PainSignal detail reads.
SIGNALS_CACHE_TAG = 'signals'

# Dedicated namespace for cluster list / detail responses.
# Writes that do NOT change cluster content (e.g. validating a People
# signal) must not bust this tag — that is the whole point of the split.
#
# Invalidated on:
#   - PainSignal create/update/delete        (cluster membership changes)
#   - PainImpact create/update/delete        (cluster aggregated stats
#                                              change: human_impacts,
#                                              metrics, max_impact_level,
#                                              impacted_contacts_count)
#   - SignalClusterArchival create/update    (archive / unarchive toggle
#                                              — affects include_archived
#                                              filtering in list views)
SIGNAL_CLUSTERS_CACHE_TAG = 'signal_clusters'