# backend/tests/ai_pipelines/test_contact_lifecycle_workflow.py
"""
Sprint « Cycle de vie des contacts », étape 8 — the COMPLETE next step <->
people workflow, by the real endpoints (reduced scope: no stakeholder ->
contact conversion, no role confirmation, no « Involved in »).

Only the LLM is fake (FakeProvider / patch_active_provider of this
package's conftest); no service is mocked. Chain:
  1. a SUCCESSFUL campaign activity analysed (People + a Pain) and a 2nd
     activity of the same campaign_account analysed (a Pain)
     — POST /module-ai-pipelines/activity-extraction/run/;
  2. « Start Decision Cycle » — POST /module-activities/create-with-entities/;
     the signals of the whole sequence take the born DC;
  3. the People validated by resolve — POST /module-signals/people/{id}/resolve/:
     contact shortcut (Paul X), Create from a first name (Marc), Link to an
     existing stakeholder (Marc Durand -> Marc);
  4. a next step of the DC citing a stakeholder linked to a contact (Paul X)
     AND a non-converted one (Marc) — the DC activity analysed;
  5. GET /module-signals/next-steps/{id}/cited-contacts/ proposes both;
  6. ✓ Create in MEETING — POST /module-activities/ as the drawer sends it:
     contact_ids + stakeholder_ids; the server's defaults: the step = the
     suggested one (in the DC), the date = the scheduled date;
  7. ✓ Create in TASK: the names in the description (the drawer's rule,
     activityDefaultsFromNextStep), no participant required, the due date,
     the step = the origin activity's (no suggested step).
The participants and the description are composed by the drawer (the
server never adds a contact — next_step_materialization.py); this test
sends them as the drawer does, from cited-contacts.
Builders reused from tests/signals/test_signal_cycle_attachment.py.
"""

import json

import pytest

from app_modules.signals.constants import PeopleRole, SignalStatus
from tests.signals.test_signal_cycle_attachment import (
    _campaign_account,
    _prospect_activity,
    _start_decision_cycle,
)


pytestmark = pytest.mark.django_db

EXTRACT_URL = '/module-ai-pipelines/activity-extraction/run/'

CAMPAIGN_TRANSCRIPT = (
    'Lea Prospect: Paul X, our CFO, signs the budget. '
    'Lea Prospect: Marc runs the project day to day. '
    'Lea Prospect: Marc Durand will join the next workshop. '
    'Lea Prospect: Our reporting takes 3 weeks.'
)
SECOND_TRANSCRIPT = 'Hugo Prospect: Our reporting takes 3 weeks, it hurts.'
DC_TRANSCRIPT = (
    'Paul X: Let us hold a workshop with Marc on the business case. '
    'Paul X: Marc should also send the data export.'
)

PAIN_REPLY = json.dumps({
    'pains': [{
        'what': 'OPS', 'dimension': 'TIME', 'scope_level': 'BUSINESS',
        'target_department': None, 'summary': 'Reporting takes 3 weeks',
        'source_quote': 'Our reporting takes 3 weeks', 'confidence': 0.9,
        'is_inferred': False,
    }],
    'impacts': [],
})


def _person(full_name, quote):
    return {
        'full_name': full_name, 'job_title': None, 'role': PeopleRole.CHAMPION.value,
        'influence': 'MEDIUM', 'department': None, 'notes': '',
        'source_quote': quote, 'confidence': 0.9, 'is_inferred': False,
    }


PEOPLE_REPLY = json.dumps({'signals': [
    _person('Paul X', 'Paul X, our CFO, signs the budget'),
    _person('Marc', 'Marc runs the project day to day'),
    _person('Marc Durand', 'Marc Durand will join the next workshop'),
]})

NEXT_STEPS_REPLY = json.dumps({'signals': [
    {
        'suggested_title': 'Business case workshop', 'suggested_activity_type': 'MEETING',
        'suggested_due_date': '2026-12-10', 'suggested_decision_step': 'S3',
        'suggested_people_names': ['Paul X', 'Marc'],
        'source_quote': 'Let us hold a workshop with Marc on the business case',
        'confidence': 0.9, 'is_inferred': False,
    },
    {
        'suggested_title': 'Send the data export', 'suggested_activity_type': 'TASK',
        'suggested_due_date': '2026-12-12',
        'suggested_people_names': ['Paul X', 'Marc'],
        'source_quote': 'Marc should also send the data export',
        'confidence': 0.9, 'is_inferred': False,
    },
]})


def _analyse(api, activity, transcript):
    r = api.post(EXTRACT_URL, {'activity_id': str(activity.id), 'transcript': transcript},
                 format='json')
    assert r.status_code == 200, r.content
    return r.json()


def _resolve(api, people, body):
    r = api.post(f'/module-signals/people/{people.id}/resolve/', body, format='json')
    assert r.status_code == 200, r.content


def _create_activity(api, body):
    r = api.post('/module-activities/', body, format='json')
    assert r.status_code == 201, r.content
    from app_modules.activities.models import Activity
    return Activity.objects.get(next_step_signal_id=body['next_step_signal_id'])


def test_the_complete_next_step_people_workflow(authed_api_a, account, user_a, patch_active_provider):
    from app_modules.contacts.models import Contact
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import NextStepSignal, PainSignal, PeopleSignal

    fake = patch_active_provider
    paul = Contact(account=account, first_name='Paul', last_name='X')
    paul.save(user=user_a, client_id=account.client_id)

    # ---- 1. the campaign sequence, analysed --------------------------------
    ca = _campaign_account(account, user_a)
    campaign_call = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL', position=1)
    second_call = _prospect_activity(ca, user_a, 'Hugo', position=1)
    fake.replies = {'pain_impact': PAIN_REPLY, 'people': PEOPLE_REPLY}
    _analyse(authed_api_a, campaign_call, CAMPAIGN_TRANSCRIPT)
    fake.replies = {'pain_impact': PAIN_REPLY}
    _analyse(authed_api_a, second_call, SECOND_TRANSCRIPT)
    people = {p.full_name: p for p in PeopleSignal.objects.filter(source_activity=campaign_call)}
    assert set(people) == {'Paul X', 'Marc', 'Marc Durand'}
    assert PainSignal.objects.filter(source_activity=second_call).count() == 1

    # ---- 2. « Start Decision Cycle »: the whole sequence takes the DC ------
    dc = _start_decision_cycle(authed_api_a, campaign_call)
    assert dc is not None
    r = authed_api_a.get('/module-signals/all/', {
        'decision_cycle_id': str(dc.id), 'signal_type': ['pain', 'people'], 'page_size': 100,
    })
    assert r.status_code == 200, r.content
    listed = {str(row['id']) for row in r.json().get('results', r.json())}
    sequence = [*PainSignal.objects.filter(source_activity__in=[campaign_call, second_call]),
                *people.values()]
    assert len(sequence) == 5
    # every signal of the sequence — the 2nd activity's Pain included — in the DC
    assert {str(x.id) for x in sequence} <= listed

    # ---- 3. the People validated by resolve --------------------------------
    _resolve(authed_api_a, people['Paul X'], {'contact_id': str(paul.id)})          # contact shortcut
    _resolve(authed_api_a, people['Marc'], {'create': {'full_name': 'Marc'}})       # first name only
    marc = Stakeholder.objects.get(decision_cycle=dc, full_name='Marc', contact__isnull=True)
    _resolve(authed_api_a, people['Marc Durand'], {'stakeholder_id': str(marc.id)})  # link
    paul_st = Stakeholder.objects.get(decision_cycle=dc, contact=paul)
    for p in people.values():
        p.refresh_from_db()
        assert p.status == SignalStatus.VALIDATED
    assert people['Paul X'].stakeholder_id == paul_st.id
    assert people['Marc'].stakeholder_id == marc.id == people['Marc Durand'].stakeholder_id

    # ---- 4. a next step of the DC citing both kinds of people --------------
    from app_modules.activities.models import Activity
    dc_activity = Activity.objects.get(source_activity=campaign_call)
    origin_step = dc_activity.decision_step
    suggested_step = dc.steps.get(order=3)
    assert origin_step is not None and origin_step.id != suggested_step.id
    fake.replies = {'next_steps': NEXT_STEPS_REPLY}
    _analyse(authed_api_a, dc_activity, DC_TRANSCRIPT)
    meeting_ns = NextStepSignal.objects.get(source_activity=dc_activity, suggested_activity_type='MEETING')
    task_ns = NextStepSignal.objects.get(source_activity=dc_activity, suggested_activity_type='TASK')
    assert meeting_ns.suggested_decision_step_id == suggested_step.id
    assert task_ns.suggested_decision_step_id is None

    # ---- 5. cited-contacts proposes both -----------------------------------
    r = authed_api_a.get(f'/module-signals/next-steps/{meeting_ns.id}/cited-contacts/')
    assert r.status_code == 200, r.content
    cited = {c['name']: c for c in r.json()['data']['cited']}
    assert cited['Paul X']['contact']['id'] == str(paul.id)
    assert cited['Marc']['contact'] is None
    assert cited['Marc']['stakeholder']['id'] == str(marc.id)

    # ---- 6. ✓ Create in MEETING (the drawer's payload, from cited-contacts) -
    meeting = _create_activity(authed_api_a, {
        'title': meeting_ns.suggested_title, 'activity_type': 'MEETING', 'status': 'PLANNED',
        'account_id': str(account.id),
        'contact_ids': [cited['Paul X']['contact']['id']],
        'stakeholder_ids': [cited['Marc']['stakeholder']['id']],
        'next_step_signal_id': str(meeting_ns.id),
    })
    assert list(meeting.contacts.values_list('id', flat=True)) == [paul.id]
    assert list(meeting.stakeholders.values_list('id', flat=True)) == [marc.id]
    assert meeting.decision_cycle_id == dc.id
    assert meeting.decision_step_id == suggested_step.id          # suggested, in the DC
    assert str(meeting.scheduled_date) == '2026-12-10' and meeting.due_date is None

    # ---- 7. ✓ Create in TASK: names in the description, nobody required ----
    task = _create_activity(authed_api_a, {
        'title': task_ns.suggested_title, 'activity_type': 'TASK', 'status': 'PLANNED',
        'account_id': str(account.id),
        'description': 'Mentioned: Paul X, Marc',
        'contact_ids': [], 'stakeholder_ids': [],
        'next_step_signal_id': str(task_ns.id),
    })
    assert task.contacts.count() == 0 and task.stakeholders.count() == 0
    assert task.description == 'Mentioned: Paul X, Marc'
    assert str(task.due_date) == '2026-12-12' and task.scheduled_date is None
    assert task.decision_step_id == origin_step.id                 # no suggested step
    for ns in (meeting_ns, task_ns):
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED
