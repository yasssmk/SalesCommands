# app_modules/ai_pipelines/services/game_plan_freshness.py
"""
The Game Plan's banner predicate — sprint 2 Game Plan, G14 (backend only;
the display comes with the Activity UI step).

    game_plan_freshness(activity) -> deal_health_freshness(its cycle) | None

« New information since the last deal health » shown BEFORE an activity's
first Game Plan, so the rep may re-run the deal health first. NO second
logic: it IS the deal health's freshness (services/deal_health_freshness.py)
— the same `applies` (an open cycle, a declared step >= TECHNICAL_FIT) and
the same reasons, those of THE predicate the deal health's run guard reads
(DealHealthEvidenceBuilder.new_info_reasons, S7). Hence the invariant:
banner on (applies and has_new_info) => a deal-health re-run is accepted.

None — nothing to show — for an activity without decision cycle (a campaign
activity outside a cycle: its light diagnostic is the Game Plan's own
campaign_diagnostic, G8 / G10).
"""

from .deal_health_freshness import deal_health_freshness


__all__ = ['game_plan_freshness']


def game_plan_freshness(activity):
    """See the module docstring."""
    if not activity.decision_cycle_id:
        return None
    return deal_health_freshness(activity.decision_cycle)
