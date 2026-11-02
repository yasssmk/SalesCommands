# app_modules/decision_cycles/services/stakeholder_service.py
"""
Stakeholders of a decision cycle -- sprint « Cycle de vie des contacts »,
étape 3 (backend preparation for the Activity flow).

attach_signal(ps, stakeholder): affiliate a PeopleSignal (an observation) to
a DC stakeholder (the person). The signal is never merged nor modified
otherwise (règle doublons). The FIRST affiliated role becomes the
stakeholder's current_signal; a later one leaves it unchanged (the
"rôle à confirmer" choice and set_current / convert / readiness belong to
the DC sprint -- TD).
"""

from django.core.exceptions import ValidationError
from django.db import transaction


@transaction.atomic
def attach_signal(people_signal, stakeholder):
    """
    Affiliate `people_signal` to `stakeholder`.

    Args:
        people_signal: a PeopleSignal of the stakeholder's decision cycle.
        stakeholder:   a Stakeholder.

    Returns:
        The stakeholder (current_signal set on the first affiliation).

    Raises:
        ValidationError: different tenant, or the signal is not on the
        stakeholder's decision cycle.
    """
    from app_modules.signals.models import PeopleSignal

    if people_signal.client_id != stakeholder.client_id:
        raise ValidationError('The signal and the stakeholder belong to different tenants.')
    if people_signal.decision_cycle_id != stakeholder.decision_cycle_id:
        raise ValidationError("The signal is not on the stakeholder's decision cycle.")

    PeopleSignal.objects.filter(pk=people_signal.pk).update(stakeholder=stakeholder)
    people_signal.stakeholder = stakeholder

    if stakeholder.current_signal_id is None:
        stakeholder.current_signal = people_signal
        stakeholder.save(update_fields=['current_signal', 'updated_at'])
    return stakeholder
