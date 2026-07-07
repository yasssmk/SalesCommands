# app_modules/signals/services/signal_priority_service.py
"""
SignalPriorityService — cluster priority scoring.

Computes a 0-100 priority score for a signal cluster and maps it to a
coarse bucket (HIGH / MEDIUM / LOW).

Supported signal types:
  - Pain      — compute_pain_priority_score()
  - Objective — compute_objective_priority_score()
  - Impact    — compute_impact_priority_score()

(TechStack is NOT clustered — product decision — and therefore has no
priority scorer here.)

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

Pain, Objective, and Impact share an intentionally identical shape on
the common axes (corroboration, breadth, freshness, scope_level). The
only difference:
  - Objective adds a target_date proximity bonus (temporal urgency).

Design choices
--------------
1. Module-level functions, not a class
   Priority is pure arithmetic — no state, no ORM, no side effects.
   A module keeps the surface minimal and makes the weights dicts the
   obvious entry point for tuning.

2. Weights centralized at the top
   PAIN_PRIORITY_WEIGHTS, OBJECTIVE_PRIORITY_WEIGHTS, and
   IMPACT_PRIORITY_WEIGHTS are the
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