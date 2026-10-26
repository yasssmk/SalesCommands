# app_modules/activities/services/activity_participants.py
"""
The DEDUCED participants of an activity (Sprint Next steps 5.8a, PO decision
B2) -- read-only, no schema change, the ">= 1 contact" rule untouched:

  1. the activity's own contacts (ParticipantSource.CONTACT), then
  2. the People (suggested_people) of the next steps that CREATED the activity
     (Activity.next_step_signal) or are LINKED to it
     (NextStepSignal.attached_activity -> attached_next_step_signals),
     REJECTED People excluded (ParticipantSource.NEXT_STEP).

Deduplicated by identity: a People linked to a contact already listed is not
repeated (the contact stands for it); a People reached through two next steps
appears once. People are ordered by name.

Reads the relations directly (a few queries), never an annotation or a
prefetch: the detail endpoint's get_object() refetches the row without the
retrieve select_related (lesson 4).
"""

from django.db.models import Q

from app_modules.signals.constants import SignalStatus

from ..constants import ParticipantSource


def get_activity_participants(activity):
    """[{'source', 'contact': Contact | None, 'people': PeopleSignal | None}]"""
    from app_modules.signals.models import NextStepSignal, PeopleSignal

    contacts = list(activity.contacts.select_related('standard_department'))
    participants = [
        {'source': ParticipantSource.CONTACT, 'contact': c, 'people': None}
        for c in contacts
    ]
    seen_contacts = {c.id for c in contacts}

    next_steps = Q(attached_activity_id=activity.id)
    if activity.next_step_signal_id:
        next_steps |= Q(id=activity.next_step_signal_id)
    next_step_ids = NextStepSignal.objects.filter(
        next_steps, client_id=activity.client_id,
    ).values('id')

    people = (
        PeopleSignal.objects
        .filter(next_step_signals__in=next_step_ids, client_id=activity.client_id)
        .exclude(status=SignalStatus.REJECTED)
        .select_related('target_contact__standard_department')
        .distinct()
        .order_by('full_name', 'id')
    )
    for p in people:
        if p.target_contact_id:
            if p.target_contact_id in seen_contacts:
                continue
            seen_contacts.add(p.target_contact_id)
        participants.append({
            'source': ParticipantSource.NEXT_STEP,
            'contact': p.target_contact,
            'people': p,
        })
    return participants
