# app_modules/signals/services/signal_priority_service.py
"""
SignalPriorityService — cluster priority scoring.

Computes a 0-100 priority score for a signal cluster and maps it to a
coarse bucket (HIGH / MEDIUM / LOW).

Supported signal types:
  - Pain      — compute_pain_priority_score()
  - Objective — compute_objective_priority_score()
  - Impact    — compute_impact_priority_score()
  - TechStack — compute_techstack_priority_score()

Each type has its own weights dict because the priority inputs differ:
  - Pain is scored on corroboration + breadth + freshness + max
    scope_level (direct field on PainSignal).
  - Objective is scored on corroboration + breadth + freshness + max
    scope_level (direct field on ObjectiveSignal) + target_date
    proximity. Pain has no equivalent temporal-urgency factor.
  - Impact is scored on corroboration + breadth + freshness + max
    scope_level (direct field on ImpactSignal). Identical axes to
    Pain — observation-level metadata (impact_type, metric_text,
    human_impact) is deliberately NOT consumed by the scorer; see
    IMPACT_PRIORITY_WEIGHTS docstring for the rationale.
  - TechStack is scored on corroboration + breadth + freshness +
    catalog flags + cross-references with Pain clusters + renewal
    proximity + discontinuation penalty.

Pain, Objective, and Impact share an intentionally identical shape on
the common axes (corroboration, breadth, freshness, scope_level). The
only differences:
  - Objective adds a target_date proximity bonus (temporal urgency).
  - Pain and Impact have no Objective- or TechStack-specific bonuses.

Design choices
--------------
1. Module-level functions, not a class
   Priority is pure arithmetic — no state, no ORM, no side effects.
   A module keeps the surface minimal and makes the weights dicts the
   obvious entry point for tuning.

2. Weights centralized at the top
   PAIN_PRIORITY_WEIGHTS, OBJECTIVE_PRIORITY_WEIGHTS,
   IMPACT_PRIORITY_WEIGHTS, and TECHSTACK_PRIORITY_WEIGHTS are the
   single sources of truth for "what matters" in each cluster type.
   Product can retune any dict in one place without touching the
   formulas — and unit tests can assert formulas independently of
   the weights.

3. Bucket thresholds live in constants.py, not here
   The "how the score becomes a label" policy is a UI concern tuned by
   product, separate from "how the score is built". The bucket
   resolution function (bucket_from_score) is shared across signal
   types — same thresholds apply uniformly.

4. Bounded, deterministic, cheap
   Every score is clamped to [0, 100]. Single dict lookup + a handful
   of arithmetic operations per score. Safe to call inline for every
   cluster in a list endpoint response.

ScopeLevel input contract
-------------------------
Pain, Objective, and Impact all consume `max_scope_level` (ScopeLevel
value or None) from the cluster stats dict. The same key, the same
enum, the same scoring sub-dict shape. The cluster service is
responsible for computing this value across each cluster's VALIDATED
members.
"""

from ..constants import (
    FreshnessStatus,
    PriorityBucket,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
    ScopeLevel,
)


# =============================================================================
# WEIGHTS — PAIN CLUSTER
# =============================================================================
#
# Tunable by product. Adjust values here to change the relative influence
# of each factor. The score is computed as a weighted sum, clamped to
# [0, 100].
#
# Factor definitions:
#
#   corroboration_per_confirmation
#     Flat weight per VALIDATED signal in the cluster, with
#     confirmation_count capped at `corroboration_cap`. Models the
#     "persistence" signal — the same pain mentioned again by anyone
#     counts as additional evidence.
#
#   width_per_distinct_contact
#     Flat weight per distinct source contact. Models the "breadth"
#     signal — a pain reported by 3 different people is stronger than
#     the same person repeating it 3 times.
#
#   freshness
#     Bonus based on the most recent VALIDATED signal's age:
#       FRESH   → freshness.FRESH
#       DORMANT → freshness.DORMANT
#       STALE   → freshness.STALE
#
#   scope_level_bonus
#     Bonus based on the highest ScopeLevel observed across the
#     cluster's VALIDATED members (read directly from
#     PainSignal.scope_level):
#       BUSINESS   → scope_level_bonus.BUSINESS
#       DEPARTMENT → scope_level_bonus.DEPARTMENT
#       PERSONAL   → scope_level_bonus.PERSONAL
#     Identical shape and weights as Objective's scope_level_bonus —
#     the two signal types share the same scoring axis.
#
# All weights are integers. Non-integer weights would not break anything
# but keeping them integers makes the clamped score human-readable.
# =============================================================================

PAIN_PRIORITY_WEIGHTS = {
    'corroboration_per_confirmation': 15,
    'corroboration_cap':              5,

    'width_per_distinct_contact':     10,

    'freshness': {
        FreshnessStatus.FRESH:   20,
        FreshnessStatus.DORMANT: 10,
        FreshnessStatus.STALE:   0,
    },

    'scope_level_bonus': {
        ScopeLevel.BUSINESS:   15,
        ScopeLevel.DEPARTMENT: 10,
        ScopeLevel.PERSONAL:   5,
    },
}

# =============================================================================
# WEIGHTS — OBJECTIVE CLUSTER
# =============================================================================
#
# Aligned with PAIN_PRIORITY_WEIGHTS on every shared axis (corroboration,
# breadth, freshness, scope_level_bonus). The single Objective-specific
# addition is:
#
#   target_date_proximity_bonus
#     Additive bonus when at least one VALIDATED member has a
#     target_date within OBJECTIVE_TARGET_DATE_SOON_DAYS from today.
#     Captures the temporal-urgency dimension that distinguishes
#     objectives (which have a deadline) from pains (which do not).
#
# Pain has no equivalent temporal-urgency factor — pains are not
# scheduled.
#
# Product-tunable in a single place — the scoring function reads
# everything from this dict.
# =============================================================================

# Target-date proximity thresholds (in days, inclusive upper bound).
# An objective with target_date within OBJECTIVE_TARGET_DATE_SOON_DAYS
# gets the full proximity bonus. Objectives with a target_date further
# out — or no target_date at all — get 0.
OBJECTIVE_TARGET_DATE_SOON_DAYS = 90

OBJECTIVE_PRIORITY_WEIGHTS = {
    # Corroboration: multiple VALIDATED signals confirming the same
    # canonical_key = stronger objective. Same shape as Pain.
    'corroboration_per_confirmation': 15,
    'corroboration_cap':              5,

    # Breadth: distinct source contacts raising the same objective.
    # Uncapped — breadth matters.
    'width_per_distinct_contact':     10,

    # Recency of the last VALIDATED observation.
    'freshness': {
        FreshnessStatus.FRESH:   20,
        FreshnessStatus.DORMANT: 10,
        FreshnessStatus.STALE:   0,
    },

    # Organisational scope observed across the cluster's members.
    # Keyed by ObjectiveSignal.scope_level directly. Identical shape
    # and weights as PAIN_PRIORITY_WEIGHTS['scope_level_bonus'] — the
    # two signal types share this axis.
    'scope_level_bonus': {
        ScopeLevel.BUSINESS:   15,
        ScopeLevel.DEPARTMENT: 10,
        ScopeLevel.PERSONAL:   5,
    },

    # Urgency bonus when at least one member has a target_date within
    # OBJECTIVE_TARGET_DATE_SOON_DAYS from today.
    'target_date_proximity_bonus': 10,
}

# =============================================================================
# WEIGHTS — IMPACT CLUSTER
# =============================================================================
#
# Identical to PAIN_PRIORITY_WEIGHTS on every axis (corroboration,
# breadth, freshness, scope_level_bonus). Impact is scored on the
# same evidence-of-stake axes as Pain — what differs between the two
# signal types is what the observation describes (a diagnosed problem
# vs. a quantified consequence), not how it should be prioritised at
# the cluster level.
#
# Why observation-level metadata is NOT consumed by the scorer
# ------------------------------------------------------------
# ImpactSignal carries three observation-level axes — impact_type
# (FINANCIAL / TIME / HUMAN / ...), metric_text (free-text quantified
# value), and human_impact (FRUSTRATION / OVERLOAD / ...) — that
# describe the FLAVOUR of an individual observation. Two ImpactSignal
# rows sharing the same canonical_key on the same account can carry
# different impact_types (e.g. one FINANCIAL "30k€/mo lost", one
# HUMAN "team frustrated") and they coexist legitimately in the
# same cluster.
#
# Scoring the cluster on aggregated observation flavour would be
# misleading: it would reward diversity of evidence categories
# rather than strength of evidence at that (what × dimension × account)
# slot. Corroboration count, distinct contacts, freshness, and the
# organisational scope at which the impact lands are the right
# cluster-level evidence dimensions — and they are exactly what we
# score on.
#
# Product-tunable in a single place — the scoring function reads
# everything from this dict.
# =============================================================================

IMPACT_PRIORITY_WEIGHTS = {
    'corroboration_per_confirmation': 15,
    'corroboration_cap':              5,

    'width_per_distinct_contact':     10,

    'freshness': {
        FreshnessStatus.FRESH:   20,
        FreshnessStatus.DORMANT: 10,
        FreshnessStatus.STALE:   0,
    },

    'scope_level_bonus': {
        ScopeLevel.BUSINESS:   15,
        ScopeLevel.DEPARTMENT: 10,
        ScopeLevel.PERSONAL:   5,
    },
}

# =============================================================================
# WEIGHTS — TECHSTACK CLUSTER
# =============================================================================
#
# TechStack priority differs structurally from Pain, Objective, and
# Impact. The three canonical-axes signal types share corroboration +
# breadth + freshness + scope_level (with Objective adding target_date
# proximity). TechStack discards the scope_level axis entirely — a
# tool does not have a "scope at which it is felt" — and brings its
# own signals of relevance:
#     * cross-references with Pain clusters (a tool that hurts is hot)
#     * catalog flags (competitor / integration target)
#     * renewal-date proximity (a contract about to expire is hot)
#     * discontinuation (a tool being phased out is cold)
#
# Score interpretation
# --------------------
#   ≥ 70  HIGH    — actionable: open replacement / integration play
#   40–69 MEDIUM  — worth tracking, mention in next call prep
#   < 40  LOW     — informational, no immediate action
#
# Discontinuation penalty
# -----------------------
# `is_discontinued` carries a strong negative weight (-50) because a
# tool the account is dropping is the exact opposite of an opportunity
# — it is a closed door. The penalty can drop the score below 0 before
# clamping; this is intentional, the cluster ends up firmly in the LOW
# bucket regardless of other signals.
#
# Product-tunable in a single place — the scoring function reads
# everything from this dict.
# =============================================================================

TECHSTACK_PRIORITY_WEIGHTS = {
    # Corroboration: multiple VALIDATED signals confirming the same tool
    # at the account = stronger evidence the tool is genuinely in use.
    # Same shape as Pain/Objective.
    'corroboration_per_confirmation': 15,
    'corroboration_cap':              5,

    # Breadth: distinct contacts mentioning the tool. Uncapped — every
    # extra independent voice strengthens the signal.
    'width_per_distinct_contact':     10,

    # Departmental breadth: distinct departments using the tool.
    # Uncapped — multi-department adoption is a strong relevance signal
    # for sales conversations (every department touched is a potential
    # replacement / integration angle). Smaller weight than contacts
    # because departments are typically fewer in number.
    'width_per_distinct_department':  5,

    # Recency of the last VALIDATED observation. Same shape as
    # Pain/Objective for consistency.
    'freshness': {
        FreshnessStatus.FRESH:   20,
        FreshnessStatus.DORMANT: 10,
        FreshnessStatus.STALE:   0,
    },

    # Cross-reference with Pain clusters — when the tool is also called
    # out as a problem source on the account, urgency multiplies.
    # Capped at 3 to avoid runaway scores when a tool is referenced by
    # many pain clusters (e.g. a generic CRM that everyone complains
    # about — relevance is real but already saturated at 3+).
    'related_pain_per_cluster':  15,
    'related_pain_cap':          3,

    # Catalog flags — these come from TechCatalog entry attributes
    # (is_competitor / is_integration_target). They are the strongest
    # commercial-relevance signals on a TechStack cluster.
    'is_competitor_bonus':         25,
    'is_integration_target_bonus': 10,

    # Renewal proximity — a contract within
    # TECHSTACK_RENEWAL_SOON_DAYS from today is a sharp commercial
    # window. Same magnitude as Objective's target-date proximity but
    # expressed differently in the data (renewal_date vs target_date).
    'renewal_soon_bonus': 20,

    # Discontinuation penalty — see header for rationale.
    'is_discontinued_penalty': -50,
}

# =============================================================================
# SCORE COMPUTATION
# =============================================================================

def compute_pain_priority_score(cluster_stats: dict) -> int:
    """
    Compute a 0-100 priority score for a Pain cluster.

    Aligned with compute_objective_priority_score on every shared
    axis (corroboration + breadth + freshness + scope_level_bonus).
    Pain has no temporal-urgency equivalent — pains are not scheduled
    — so there is no target-date factor here.

    Args:
        cluster_stats: A dict produced by SignalClusterService with the
            following keys (all keys expected — the service populates
            zero / None defaults):

              - confirmation_count         (int >= 0)
              - distinct_contacts_count    (int >= 0)
              - freshness_status           (FreshnessStatus value or None)
              - max_scope_level            (ScopeLevel value or None) —
                                            highest observed scope across
                                            the cluster's VALIDATED
                                            members, read directly from
                                            PainSignal.scope_level

    Returns:
        int in [0, 100] — the priority score.

    Notes:
        Missing or None values for the categorical inputs
        (freshness_status, max_scope_level) contribute 0 to the score,
        which is the safe default for clusters that have no VALIDATED
        signal yet.
    """
    weights = PAIN_PRIORITY_WEIGHTS
    score = 0

    # --- Corroboration: count × weight, capped ---
    confirmation_count = int(cluster_stats.get('confirmation_count', 0) or 0)
    corroboration = min(confirmation_count, weights['corroboration_cap'])
    score += corroboration * weights['corroboration_per_confirmation']

    # --- Breadth: distinct contacts × weight (uncapped — breadth matters) ---
    distinct_contacts = int(cluster_stats.get('distinct_contacts_count', 0) or 0)
    score += distinct_contacts * weights['width_per_distinct_contact']

    # --- Freshness bonus ---
    freshness = cluster_stats.get('freshness_status')
    if freshness is not None:
        score += weights['freshness'].get(freshness, 0)

    # --- Scope level observed ---
    scope = cluster_stats.get('max_scope_level')
    if scope is not None:
        score += weights['scope_level_bonus'].get(scope, 0)

    # Clamp to [0, 100]
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score

def compute_objective_priority_score(cluster_stats: dict) -> int:
    """
    Compute a 0-100 priority score for an Objective cluster.

    Tuned differently from Pain (see OBJECTIVE_PRIORITY_WEIGHTS
    docstring for rationale):
      - corroboration + breadth + freshness behave like Pain
      - scope_level_bonus reads the directly-stored scope_level
        on ObjectiveSignal
      - no human_impact / metric bonuses (Pain-only concepts)
      - target_date_proximity_bonus adds urgency when the deadline
        is close (within OBJECTIVE_TARGET_DATE_SOON_DAYS)

    Args:
        cluster_stats: A dict produced by SignalClusterService with
            the following keys (all keys expected — the service
            populates zero / None defaults):

              - confirmation_count         (int >= 0)
              - distinct_contacts_count    (int >= 0)
              - freshness_status           (FreshnessStatus or None)
              - max_scope_level            (ScopeLevel or None) —
                                            highest observed scope across
                                            the cluster's VALIDATED members
              - has_target_date_soon       (bool) — True if at least
                                            one member's target_date is
                                            within the proximity window

    Returns:
        int in [0, 100] — the priority score.

    Notes:
        Missing or None values for the categorical inputs
        (freshness_status, max_scope_level) contribute 0 — safe
        default for clusters with no VALIDATED signal yet or no
        explicit scope observation.
    """
    weights = OBJECTIVE_PRIORITY_WEIGHTS
    score = 0

    # --- Corroboration: count × weight, capped ---
    confirmation_count = int(cluster_stats.get('confirmation_count', 0) or 0)
    corroboration = min(confirmation_count, weights['corroboration_cap'])
    score += corroboration * weights['corroboration_per_confirmation']

    # --- Breadth: distinct contacts × weight (uncapped) ---
    distinct_contacts = int(cluster_stats.get('distinct_contacts_count', 0) or 0)
    score += distinct_contacts * weights['width_per_distinct_contact']

    # --- Freshness bonus ---
    freshness = cluster_stats.get('freshness_status')
    if freshness is not None:
        score += weights['freshness'].get(freshness, 0)

    # --- Scope level observed ---
    scope = cluster_stats.get('max_scope_level')
    if scope is not None:
        score += weights['scope_level_bonus'].get(scope, 0)

    # --- Target date proximity ---
    if cluster_stats.get('has_target_date_soon'):
        score += weights['target_date_proximity_bonus']

    # Clamp to [0, 100]
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score

# =============================================================================
# IMPACT PRIORITY
# =============================================================================

def compute_impact_priority_score(cluster_stats: dict) -> int:
    """
    Compute a 0-100 priority score for an Impact cluster.

    Aligned with compute_pain_priority_score on every axis
    (corroboration + breadth + freshness + scope_level_bonus). Impact
    has no temporal-urgency equivalent — impacts are observed states,
    not scheduled outcomes — so there is no target-date factor here.

    Observation-level metadata (impact_type, metric_text, human_impact)
    is deliberately not consumed by this scorer. See
    IMPACT_PRIORITY_WEIGHTS docstring for the rationale.

    Args:
        cluster_stats: A dict produced by SignalClusterService with the
            following keys (all keys expected — the service populates
            zero / None defaults):

              - confirmation_count         (int >= 0)
              - distinct_contacts_count    (int >= 0)
              - freshness_status           (FreshnessStatus value or None)
              - max_scope_level            (ScopeLevel value or None) —
                                            highest observed scope across
                                            the cluster's VALIDATED
                                            members, read directly from
                                            ImpactSignal.scope_level

    Returns:
        int in [0, 100] — the priority score.

    Notes:
        Missing or None values for the categorical inputs
        (freshness_status, max_scope_level) contribute 0 to the score,
        which is the safe default for clusters that have no VALIDATED
        signal yet.
    """
    weights = IMPACT_PRIORITY_WEIGHTS
    score = 0

    # --- Corroboration: count × weight, capped ---
    confirmation_count = int(cluster_stats.get('confirmation_count', 0) or 0)
    corroboration = min(confirmation_count, weights['corroboration_cap'])
    score += corroboration * weights['corroboration_per_confirmation']

    # --- Breadth: distinct contacts × weight (uncapped — breadth matters) ---
    distinct_contacts = int(cluster_stats.get('distinct_contacts_count', 0) or 0)
    score += distinct_contacts * weights['width_per_distinct_contact']

    # --- Freshness bonus ---
    freshness = cluster_stats.get('freshness_status')
    if freshness is not None:
        score += weights['freshness'].get(freshness, 0)

    # --- Scope level observed ---
    scope = cluster_stats.get('max_scope_level')
    if scope is not None:
        score += weights['scope_level_bonus'].get(scope, 0)

    # Clamp to [0, 100]
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score

# =============================================================================
# TECHSTACK PRIORITY
# =============================================================================

def compute_techstack_priority_score(cluster_stats: dict) -> int:
    """
    Compute a 0-100 priority score for a TechStack cluster.

    Tuned differently from Pain and Objective (see
    TECHSTACK_PRIORITY_WEIGHTS docstring for rationale):
      - corroboration + breadth + freshness behave like Pain/Objective
      - distinct departments contribute a separate (smaller) breadth bonus
      - related Pain clusters add a major bonus, capped to avoid runaway
        scores
      - catalog flags (is_competitor / is_integration_target) add static
        bonuses — these are the strongest commercial-relevance signals
      - renewal proximity adds an urgency bonus
      - is_discontinued is a strong NEGATIVE penalty: a tool being
        phased out is a closed door, not an opportunity

    Args:
        cluster_stats: dict produced by SignalClusterService._build_techstack_cluster.
            All keys expected — the service populates zero / False / None
            defaults for fields that don't apply:
              - confirmation_count           (int >= 0)
              - distinct_contacts_count      (int >= 0)
              - distinct_departments_count   (int >= 0)
              - related_pain_count           (int >= 0) — number of
                                                          Pain clusters
                                                          referencing the
                                                          same TechCatalog
                                                          entry
              - is_competitor                (bool)
              - is_integration_target        (bool)
              - has_renewal_soon             (bool)
              - is_discontinued              (bool)
              - freshness_status             (FreshnessStatus or None)

    Returns:
        int in [0, 100] — the priority score, clamped.

    Notes:
        Missing or None values for the categorical inputs
        (freshness_status) contribute 0 — safe default for clusters
        with no VALIDATED signal yet. The discontinuation penalty can
        drive the un-clamped score below 0; clamping then lifts it back
        to 0, which lands the cluster firmly in the LOW bucket.
    """
    weights = TECHSTACK_PRIORITY_WEIGHTS
    score = 0

    # --- Corroboration: count × weight, capped ---
    confirmation_count = int(cluster_stats.get('confirmation_count', 0) or 0)
    corroboration = min(confirmation_count, weights['corroboration_cap'])
    score += corroboration * weights['corroboration_per_confirmation']

    # --- Breadth: distinct contacts × weight (uncapped) ---
    distinct_contacts = int(cluster_stats.get('distinct_contacts_count', 0) or 0)
    score += distinct_contacts * weights['width_per_distinct_contact']

    # --- Breadth: distinct departments × weight (uncapped, smaller) ---
    distinct_departments = int(cluster_stats.get('distinct_departments_count', 0) or 0)
    score += distinct_departments * weights['width_per_distinct_department']

    # --- Freshness bonus ---
    freshness = cluster_stats.get('freshness_status')
    if freshness is not None:
        score += weights['freshness'].get(freshness, 0)

    # --- Cross-reference with Pain clusters (capped) ---
    related_pain_count = int(cluster_stats.get('related_pain_count', 0) or 0)
    related_pain = min(related_pain_count, weights['related_pain_cap'])
    score += related_pain * weights['related_pain_per_cluster']

    # --- Catalog flag bonuses (additive, both can apply) ---
    if cluster_stats.get('is_competitor'):
        score += weights['is_competitor_bonus']
    if cluster_stats.get('is_integration_target'):
        score += weights['is_integration_target_bonus']

    # --- Renewal urgency ---
    if cluster_stats.get('has_renewal_soon'):
        score += weights['renewal_soon_bonus']

    # --- Discontinuation penalty (can push score below 0) ---
    if cluster_stats.get('is_discontinued'):
        score += weights['is_discontinued_penalty']

    # Clamp to [0, 100]
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score


# =============================================================================
# BUCKET RESOLUTION
# =============================================================================

def bucket_from_score(score: int) -> str:
    """
    Map a numeric priority score to a coarse PriorityBucket.

    Thresholds live in core constants so product can tune the policy
    without touching the scoring formula.

    Args:
        score: int in [0, 100].

    Returns:
        One of PriorityBucket values ('HIGH', 'MEDIUM', 'LOW').
    """
    if score >= PRIORITY_HIGH_THRESHOLD:
        return PriorityBucket.HIGH
    if score >= PRIORITY_MEDIUM_THRESHOLD:
        return PriorityBucket.MEDIUM
    return PriorityBucket.LOW