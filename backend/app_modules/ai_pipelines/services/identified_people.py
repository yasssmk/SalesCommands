# app_modules/ai_pipelines/services/identified_people.py
"""
The persons ALREADY identified in an activity's deal (People stage).

Single source of the "already identified" set, shared by:
  * the context layer (prompts/transcript_signals/context.py), which lists
    them to the LLM with the instruction not to emit them again;
  * the extractor (services/transcript_signal_extractor.py), which drops any
    People candidate whose identity matches one of them -- the server-side
    safety net, since the LLM does not always follow the instruction.

Set = the non-REJECTED (VALIDATED + PENDING) PeopleSignals of the activity's
decision_cycle, scoped on the activity's tenant AND account. An activity
without a decision cycle (campaign context) has no deal: empty set.
"""


__all__ = ['identified_people_in_deal']


def identified_people_in_deal(activity):
    """
    Returns:
        QuerySet[PeopleSignal] | list -- ordered created_at, id, with the
        contact / department preloaded; [] when the activity has no DC.
    """
    if not activity.decision_cycle_id:
        return []

    from app_modules.signals.constants import SignalStatus
    from app_modules.signals.models import PeopleSignal

    return (
        PeopleSignal.objects
        .filter(
            client_id=activity.client_id,
            account_id=activity.account_id,
            decision_cycle_id=activity.decision_cycle_id,
        )
        .exclude(status=SignalStatus.REJECTED)
        .select_related('target_contact', 'target_department')
        .order_by('created_at', 'id')
    )
