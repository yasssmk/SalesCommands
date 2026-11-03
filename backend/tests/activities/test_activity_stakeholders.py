# backend/tests/activities/test_activity_stakeholders.py
"""
Sprint « Cycle de vie des contacts », étape 7 (2) -- the NON-converted
stakeholders of the activity's DC take part in an activity
(Activity.stakeholders), written by the three user paths (stakeholder_ids)
and read back (stakeholders_detail: display_name, department, not linked).

  * accepted: the stakeholders of the activity's DC whose contact is NULL;
    any other one (another DC, a converted one, no DC) -> standard refusal;
  * a stakeholder IS a participant (PEOPLE_ACTIVITY_TYPES minimum);
  * the contacts come with `is_reachable` (email OR phone, non-empty — the
    Contact.filter_reachable presence logic), computed server-side.

Real paths: POST /module-activities/, PATCH /module-activities/{id}/,
POST /module-activities/create-with-entities/, GET /module-activities/{id}/.
"""

import pytest
from rest_framework import status


pytestmark = pytest.mark.django_db

URL = '/module-activities/'


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.constants import PipelineStep
    from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    step = DecisionStep(cycle=dc, name='Qualification', stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=user, client_id=account.client_id)
    dc.step = step
    return dc


def _contact(account, user, first='Jane', last='Doe', **fields):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last, **fields)
    c.save(user=user, client_id=account.client_id)
    return c


def _stakeholder(cycle, user, **fields):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, **fields)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _payload(account, cycle=None, activity_type='MEETING', contact_ids=(), stakeholder_ids=()):
    body = {
        'title': 'Workshop', 'activity_type': activity_type, 'status': 'PLANNED',
        'account_id': str(account.id), 'scheduled_date': '2026-11-20',
        'contact_ids': [str(c) for c in contact_ids],
        'stakeholder_ids': [str(s) for s in stakeholder_ids],
    }
    if cycle:
        body['decision_cycle_id'] = str(cycle.id)
        body['decision_step_id'] = str(cycle.step.id)
    return body


def _detail(api, pk):
    r = api.get(f'{URL}{pk}/')
    assert r.status_code == 200, r.content
    return r.json()['data']


# =============================================================================
# WRITE
# =============================================================================

def test_post_a_meeting_with_a_not_linked_stakeholder_only(authed_api_a, account, user_a):
    from app_modules.core_modules.models import StandardDepartment
    sales, _ = StandardDepartment.objects.get_or_create(name='Sales')
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    finance = _stakeholder(cycle, user_a, department=sales)
    r = authed_api_a.post(URL, _payload(account, cycle, stakeholder_ids=[marc.id, finance.id]),
                          format='json')
    assert r.status_code == status.HTTP_201_CREATED, r.content
    data = _detail(authed_api_a, r.json()['data']['id'])
    rows = {s['id']: s for s in data['stakeholders_detail']}
    assert rows[str(marc.id)]['display_name'] == 'Marc'
    assert rows[str(marc.id)]['is_linked'] is False
    assert rows[str(finance.id)]['department']['id'] == sales.id
    assert data['contacts_detail'] == []


@pytest.mark.parametrize('case', ['other_cycle', 'linked', 'no_cycle'])
def test_post_refuses_a_stakeholder_out_of_scope(authed_api_a, account, user_a, case):
    cycle = _cycle(account, user_a)
    if case == 'other_cycle':
        s = _stakeholder(_cycle(account, user_a, 'Other'), user_a, full_name='Marc')
        body = _payload(account, cycle, stakeholder_ids=[s.id])
    elif case == 'linked':
        s = _stakeholder(cycle, user_a, contact=_contact(account, user_a))
        body = _payload(account, cycle, stakeholder_ids=[s.id])
    else:
        s = _stakeholder(cycle, user_a, full_name='Marc')
        body = _payload(account, None, stakeholder_ids=[s.id])
    # A valid contact satisfies the minimum: the refusal is the stakeholder's.
    body['contact_ids'] = [str(_contact(account, user_a, 'Valid', 'Contact').id)]
    r = authed_api_a.post(URL, body, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'not contacts yet' in r.content.decode().lower()


def test_patch_task_to_meeting_with_a_stakeholder(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    pk = authed_api_a.post(URL, _payload(account, cycle, activity_type='TASK'),
                           format='json').json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'activity_type': 'MEETING',
                                           'stakeholder_ids': [str(marc.id)]}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    assert [s['id'] for s in _detail(authed_api_a, pk)['stakeholders_detail']] == [str(marc.id)]


def test_patch_removing_the_only_stakeholder_of_a_meeting_is_refused(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    pk = authed_api_a.post(URL, _payload(account, cycle, stakeholder_ids=[marc.id]),
                           format='json').json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'stakeholder_ids': []}, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST


def test_with_entities_a_meeting_with_a_stakeholder(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    r = authed_api_a.post(f'{URL}create-with-entities/', {
        'activity': _payload(account, cycle, stakeholder_ids=[marc.id]),
        'inline_contact': None, 'inline_cycle': None, 'inline_step_stage': None,
    }, format='json')
    assert r.status_code in (200, 201), r.content
    from app_modules.activities.models import Activity
    a = Activity.objects.get(title='Workshop')
    assert list(a.stakeholders.values_list('id', flat=True)) == [marc.id]


def test_a_campaign_activity_locks_its_stakeholders(authed_api_a, account, user_a):
    import datetime
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign
    today = datetime.date.today()
    camp = Campaign(name='C', campaign_type=CampaignType.OUTBOUND, owner=user_a,
                    planned_start_date=today, planned_end_date=today + datetime.timedelta(days=9))
    camp.save(user=user_a, client_id=account.client_id)
    a = Activity(title='Camp call', activity_type='CALL', status='PLANNED', account=account,
                 owner=user_a, campaign=camp, scheduled_date=today)
    a.save(user=user_a, client_id=account.client_id)
    r = authed_api_a.patch(f'{URL}{a.id}/', {'stakeholder_ids': []}, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# READ -- contacts reachable (email OR phone)
# =============================================================================

def test_contacts_carry_is_reachable(authed_api_a, account, user_a):
    mail = _contact(account, user_a, 'Mail', 'Only', email='m@x.io')
    phone = _contact(account, user_a, 'Phone', 'Only', phone_number='+33612345678')
    none = _contact(account, user_a, 'No', 'Way')
    linkedin = _contact(account, user_a, 'Link', 'Only', linkedin='https://linkedin.com/in/x')
    pk = authed_api_a.post(URL, _payload(account, contact_ids=[mail.id, phone.id, none.id, linkedin.id]),
                           format='json').json()['data']['id']
    reach = {c['id']: c['is_reachable'] for c in _detail(authed_api_a, pk)['contacts_detail']}
    assert reach == {str(mail.id): True, str(phone.id): True,
                     str(none.id): False, str(linkedin.id): False}


def test_stakeholders_carry_is_reachable_a_non_converted_one_never_is(authed_api_a, account, user_a):
    """8b-2: the « No email or phone » alert covers EVERY participant — a
    non-converted stakeholder has no email nor phone: is_reachable False,
    computed server-side on stakeholders_detail (and on the DC stakeholders
    endpoint, the same serializer: a converted one reads its contact)."""
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    pk = authed_api_a.post(URL, _payload(account, cycle, stakeholder_ids=[marc.id]),
                           format='json').json()['data']['id']
    rows = _detail(authed_api_a, pk)['stakeholders_detail']
    assert [(r['id'], r['is_reachable']) for r in rows] == [(str(marc.id), False)]
    mail = _contact(account, user_a, 'Mail', 'Only', email='m@x.io')
    paul = _stakeholder(cycle, user_a, contact=mail)
    listed = {r['id']: r['is_reachable'] for r in
              authed_api_a.get(f'/decision_cycles/{cycle.id}/stakeholders/').json()['data']}
    assert listed == {str(marc.id): False, str(paul.id): True}


def test_changing_the_cycle_drops_the_stakeholders_of_the_old_one(authed_api_a, account, user_a):
    """A stakeholder belongs to ONE cycle: an activity moved to another cycle
    (without stakeholder_ids) keeps its contacts, loses the old cycle's
    stakeholders."""
    a_cycle, b_cycle = _cycle(account, user_a, 'A'), _cycle(account, user_a, 'B')
    marc = _stakeholder(a_cycle, user_a, full_name='Marc')
    jane = _contact(account, user_a)
    pk = authed_api_a.post(URL, _payload(account, a_cycle, contact_ids=[jane.id],
                                         stakeholder_ids=[marc.id]), format='json').json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'decision_cycle_id': str(b_cycle.id),
                                           'decision_step_id': str(b_cycle.step.id)}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    data = _detail(authed_api_a, pk)
    assert data['stakeholders_detail'] == []
    assert [c['id'] for c in data['contacts_detail']] == [str(jane.id)]
