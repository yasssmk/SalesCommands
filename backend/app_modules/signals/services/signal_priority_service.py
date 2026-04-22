# app_modules/signals/services/signal_priority_service.py
"""
SignalPriorityService — cluster priority scoring.

Computes a 0-100 priority score for a signal cluster and maps it to a
coarse bucket (HIGH / MEDIUM / LOW).

Design choices
--------------
1. Module-level functions, not a class
   Priority is pure arithmetic — no state, no ORM, no side effects.
   A module keeps the surface minimal and makes the weights dict the
   obvious entry point for tuning.

2. Weights centralized at the top
   PAIN_PRIORITY_WEIGHTS is the single source of truth for "what matters
   in a Pain cluster". Product can retune the weights in one place
   without touching the formula — and any future SignalClusterService
   unit test can assert the score formula independently of the weights.

3. Bucket thresholds live in constants.py, not here
   The "how the score becomes a label" policy is a UI concern tuned by
   product, separate from "how the score is built". Both can evolve
   independently.

4. Bounded, deterministic, cheap
   Score is clamped to [0, 100]. Single dict lookup + a handful of
   arithmetic operations. Safe to call inline for every cluster in a
   list endpoint response.
"""

from ..constants import (
    FreshnessStatus,
    ImpactLevel,
    PriorityBucket,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
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
#   human_impact_bonus
#     Additive bonus if at least one child PainImpact carries a
#     human_impact enum value (FRUSTRATION / OVERLOAD / ...). Signals
#     an emotional stake that typically moves deals faster.
#
#   level_bonus
#     Bonus based on the highest ImpactLevel observed across the
#     cluster's PainImpacts:
#       BUSINESS   → level_bonus.BUSINESS
#       DEPARTMENT → level_bonus.DEPARTMENT
#       PERSONAL   → level_bonus.PERSONAL
#
#   metric_bonus
#     Additive bonus if at least one child PainImpact carries a
#     non-empty `metric` field (e.g. "120k$/year", "15h/week"). Signals
#     quantified evidence, which is the strongest proof.
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

    'human_impact_bonus': 15,

    'level_bonus': {
        ImpactLevel.BUSINESS:   15,
        ImpactLevel.DEPARTMENT: 10,
        ImpactLevel.PERSONAL:   5,
    },

    'metric_bonus': 10,
}


# =============================================================================
# SCORE COMPUTATION
# =============================================================================

def compute_pain_priority_score(cluster_stats: dict) -> int:
    """
    Compute a 0-100 priority score for a Pain cluster.

    Args:
        cluster_stats: A dict produced by SignalClusterService with the
            following keys (all keys must be present — the service is
            responsible for populating them, even with zero / None
            defaults):

              - confirmation_count         (int >= 0)
              - distinct_contacts_count    (int >= 0)
              - freshness_status           (FreshnessStatus value or None)
              - has_human_impact           (bool)
              - max_impact_level           (ImpactLevel value or None)
              - has_metric                 (bool)

    Returns:
        int in [0, 100] — the priority score.

    Notes:
        Missing or None values for the categorical inputs
        (freshness_status, max_impact_level) contribute 0 to the score,
        which is the safe default for clusters that have no VALIDATED
        signal yet or no PainImpact attached.
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

    # --- Human impact attached ---
    if cluster_stats.get('has_human_impact'):
        score += weights['human_impact_bonus']

    # --- Max impact level observed ---
    level = cluster_stats.get('max_impact_level')
    if level is not None:
        score += weights['level_bonus'].get(level, 0)

    # --- Metric attached ---
    if cluster_stats.get('has_metric'):
        score += weights['metric_bonus']

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