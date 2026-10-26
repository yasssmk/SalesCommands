# backend/tests/activities/test_activity_participants.py
"""
Sprint Next steps 5.8a (PO decision B2) -- `participants` on GET
/module-activities/{id}/: the activity's DEDUCED participants, read-only:

  * the activity's contacts (source CONTACT), then
  * the People (suggested_people) of the next steps that CREATED it
    (Activity.next_step_signal) or are LINKED to it
    (NextStepSignal.attached_activity -> attached_next_step_signals),
    source NEXT_STEP;
  * deduplicated by identity: a People linked to a contact already present
    appears once (as that contact); the same People through two next steps
    appears once; a REJECTED People is not a participant;
  * no schema change; the ">= 1 contact" rule is untouched (contacts are the
    activity's own, unchanged).

Lesson 4: the detail endpoint's get_object() refetches the row without the
retrieve relations -- the field reads directly, never an annotation.
"""

import pytest

from app_modules.activities.constants import ActivityStatus, ActivityType, ParticipantSource
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db


def _contact(account, user, first, last, job=''):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last, job_title=job)
    c.save(user=user, client_id=account.client_id)
    return c


def _cycle(account, user):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name='Deal Acme', is_active=True)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _activity(account, user, title, cycle, **extra):
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
                 account=account, owner=user, decision_cycle=cycle, **extra)
    a.save(user=user, client_id=account.client_id)
    return a


def _people(account, cycle, user, full_name, contact=None, rejected=False):
    """A People of the DC: MANUAL (VALIDATED at create), or an extracted one
    then rejected (an LLM signal starts PENDING)."""
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=account, decision_cycle=cycle, role=PeopleRole.UNKNOWN,
                     full_name=full_name, target_contact=contact,
                     source=SignalSource.LLM_EXTRACTED if rejected else SignalSource.MANUAL)
    p.save(user=user, client_id=account.client_id)
    if rejected:
        PeopleSignal.objects.filter(id=p.id).update(status=SignalStatus.REJECTED)
    return p


def _next_step(account, user, source_activity, people, **extra):
    from app_modules.signals.models import NextStepSignal
    ns = NextStepSignal(account=account, source_activity=source_activity,
                        suggested_title='Security review', suggested_activity_type=ActivityType.MEETING,
                        source=SignalSource.LLM_EXTRACTED, confidence=0.8, **extra)
    ns.save(user=user, client_id=account.client_id)
    ns.suggested_people.set(people)
    return ns


def _participants(authed_api, activity):
    response = authed_api.get(f'/module-activities/{activity.id}/')
    assert response.status_code == 200, response.content
    return response.json()['data']['participants']


def _names(participants):
    return [
        (p['source'],
         (p['contact'] or {}).get('full_name') or (p['people'] or {}).get('full_name'))
        for p in participants
    ]


@pytest.fixture
def deal(account, user_a):
    """A DC atelier (the conversation) and its people."""
    dc = _cycle(account, user_a)
    atelier = _activity(account, user_a, 'Atelier', dc)
    thomas = _contact(account, user_a, 'Thomas', 'Lefèvre', 'CTO')
    laurent = _contact(account, user_a, 'Laurent', 'Dubois', 'CISO')
    return {
        'dc': dc, 'atelier': atelier, 'thomas': thomas, 'laurent': laurent,
        'p_thomas': _people(account, dc, user_a, 'Thomas Lefèvre', thomas),
        'p_karim': _people(account, dc, user_a, 'Karim Benali'),
        'p_laurent': _people(account, dc, user_a, 'Laurent Dubois', laurent),
        'p_rejected': _people(account, dc, user_a, 'Rejected Person', rejected=True),
    }


def test_contacts_only_without_next_step(authed_api_a, account, user_a, deal):
    review = _activity(account, user_a, 'Security review', deal['dc'])
    review.contacts.add(deal['thomas'])
    assert _names(_participants(authed_api_a, review)) == [
        (ParticipantSource.CONTACT, 'Thomas Lefèvre')]


def test_people_of_the_next_steps_that_created_or_are_linked_to_it(
    authed_api_a, account, user_a, deal,
):
    created_from = _next_step(account, user_a, deal['atelier'],
                              [deal['p_thomas'], deal['p_karim']])
    review = _activity(account, user_a, 'Security review', deal['dc'],
                       next_step_signal=created_from)
    review.contacts.add(deal['thomas'])
    _next_step(account, user_a, deal['atelier'],
               [deal['p_laurent'], deal['p_karim'], deal['p_rejected']],
               attached_activity=review)

    participants = _participants(authed_api_a, review)
    assert _names(participants) == [
        (ParticipantSource.CONTACT, 'Thomas Lefèvre'),   # P_thomas: same identity, once
        (ParticipantSource.NEXT_STEP, 'Karim Benali'),   # two next steps, once
        (ParticipantSource.NEXT_STEP, 'Laurent Dubois'),  # a People with a contact not on it
    ]                                                     # the REJECTED People is absent
    karim = participants[1]
    assert karim['contact'] is None
    assert karim['people']['id'] == str(deal['p_karim'].id)
    laurent = participants[2]
    assert laurent['contact']['id'] == str(deal['laurent'].id)
    assert laurent['people']['id'] == str(deal['p_laurent'].id)


def test_the_contacts_of_the_activity_are_unchanged(authed_api_a, account, user_a, deal):
    created_from = _next_step(account, user_a, deal['atelier'], [deal['p_karim']])
    review = _activity(account, user_a, 'Security review', deal['dc'],
                       next_step_signal=created_from)
    review.contacts.add(deal['thomas'])
    data = authed_api_a.get(f'/module-activities/{review.id}/').json()['data']
    assert [c['id'] for c in data['contacts_detail']] == [str(deal['thomas'].id)]


def test_not_on_the_list_endpoint(authed_api_a, account, user_a, deal):
    response = authed_api_a.get('/module-activities/')
    assert response.status_code == 200, response.content
    body = response.json()
    rows = body.get('data', body)
    rows = rows.get('results', rows) if isinstance(rows, dict) else rows
    assert rows and all('participants' not in r for r in rows)


def test_the_people_of_the_next_step_it_was_created_from_alone(authed_api_a, account, user_a, deal):
    created_from = _next_step(account, user_a, deal['atelier'], [deal['p_karim']])
    review = _activity(account, user_a, 'Security review', deal['dc'],
                       next_step_signal=created_from)
    review.contacts.add(deal['thomas'])
    assert _names(_participants(authed_api_a, review)) == [
        (ParticipantSource.CONTACT, 'Thomas Lefèvre'),
        (ParticipantSource.NEXT_STEP, 'Karim Benali'),
    ]


def test_the_people_of_a_linked_next_step_alone(authed_api_a, account, user_a, deal):
    review = _activity(account, user_a, 'Security review', deal['dc'])
    review.contacts.add(deal['thomas'])
    _next_step(account, user_a, deal['atelier'], [deal['p_laurent']], attached_activity=review)
    assert _names(_participants(authed_api_a, review)) == [
        (ParticipantSource.CONTACT, 'Thomas Lefèvre'),
        (ParticipantSource.NEXT_STEP, 'Laurent Dubois'),
    ]
