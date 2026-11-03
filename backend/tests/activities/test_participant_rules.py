# backend/tests/activities/test_participant_rules.py
"""
Sprint « Cycle de vie des contacts », étape 7 (1) -- ONE participant rule for
every user path (activities/services/participant_rules.py):

  * PEOPLE_ACTIVITY_TYPES = MEETING / CALL / EMAIL / DEMO (activities/
    constants.py, mirrored in frontend/src/utils/activityTypes.js);
  * the FINAL type in it  => at least one participant;
    any other type (TASK, LINKEDIN, OTHER)  => no minimum;
  * applied by the POST, the PATCH (also when only the TYPE changes, without
    contact_ids) and create-with-entities;
  * Meeting -> Task keeps the participants;
  * the contacts of an activity belong to its account on every path
    (create-with-entities filtered on the tenant only before).
System exception: the campaign generation (campaign_execution_service.py
491-512) does not go through these paths.

Real paths: POST /module-activities/, PATCH /module-activities/{id}/,
POST /module-activities/create-with-entities/.
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db

URL = '/module-activities/'
WITH_ENTITIES = '/module-activities/create-with-entities/'


def _contact(account, user, first='Jane', last='Doe'):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last)
    c.save(user=user, client_id=account.client_id)
    return c


def _payload(account, activity_type, contact_ids=None, **extra):
    body = {
        'title': 'Follow-up', 'activity_type': activity_type, 'status': ActivityStatus.PLANNED,
        'account_id': str(account.id), 'scheduled_date': '2026-11-20',
    }
    if contact_ids is not None:
        body['contact_ids'] = [str(c) for c in contact_ids]
    body.update(extra)
    return body


def _post(api, body):
    return api.post(URL, body, format='json')


def _error(r):
    return r.content.decode().lower()


def test_the_constant():
    from app_modules.activities.constants import PEOPLE_ACTIVITY_TYPES
    assert PEOPLE_ACTIVITY_TYPES == frozenset({
        ActivityType.MEETING, ActivityType.CALL, ActivityType.EMAIL, ActivityType.DEMO,
    })


# =============================================================================
# POST
# =============================================================================

@pytest.mark.parametrize('activity_type', ['TASK', 'LINKEDIN', 'OTHER'])
def test_post_a_type_without_people_needs_no_participant(authed_api_a, account, activity_type):
    r = _post(authed_api_a, _payload(account, activity_type))
    assert r.status_code == status.HTTP_201_CREATED, r.content


@pytest.mark.parametrize('activity_type', ['MEETING', 'CALL', 'EMAIL', 'DEMO'])
def test_post_a_people_type_needs_a_participant(authed_api_a, account, activity_type):
    r = _post(authed_api_a, _payload(account, activity_type, contact_ids=[]))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'participant' in _error(r)


def test_post_a_meeting_with_a_contact(authed_api_a, account, user_a):
    jane = _contact(account, user_a)
    r = _post(authed_api_a, _payload(account, 'MEETING', contact_ids=[jane.id]))
    assert r.status_code == status.HTTP_201_CREATED, r.content


# =============================================================================
# PATCH -- the FINAL type decides, also when only the type changes
# =============================================================================

def _task(api, account):
    r = _post(api, _payload(account, 'TASK'))
    assert r.status_code == 201, r.content
    return r.json()['data']['id']


def test_patch_task_to_meeting_without_participant_is_refused(authed_api_a, account):
    pk = _task(authed_api_a, account)
    r = authed_api_a.patch(f'{URL}{pk}/', {'activity_type': 'MEETING'}, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'participant' in _error(r)


def test_patch_meeting_to_task_keeps_the_participants(authed_api_a, account, user_a):
    from app_modules.activities.models import Activity
    jane = _contact(account, user_a)
    pk = _post(authed_api_a, _payload(account, 'MEETING', contact_ids=[jane.id])).json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'activity_type': 'TASK'}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    assert list(Activity.objects.get(pk=pk).contacts.values_list('id', flat=True)) == [jane.id]


def test_patch_emptying_the_contacts_of_a_task_is_allowed(authed_api_a, account, user_a):
    jane = _contact(account, user_a)
    pk = _post(authed_api_a, _payload(account, 'TASK', contact_ids=[jane.id])).json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'contact_ids': []}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content


def test_patch_emptying_the_contacts_of_a_meeting_is_refused(authed_api_a, account, user_a):
    jane = _contact(account, user_a)
    pk = _post(authed_api_a, _payload(account, 'MEETING', contact_ids=[jane.id])).json()['data']['id']
    r = authed_api_a.patch(f'{URL}{pk}/', {'contact_ids': []}, format='json')
    assert r.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# create-with-entities
# =============================================================================

def _with_entities(api, activity, inline_contact=None):
    return api.post(WITH_ENTITIES, {
        'activity': activity, 'inline_contact': inline_contact,
        'inline_cycle': None, 'inline_step_stage': None,
    }, format='json')


def test_with_entities_a_meeting_without_participant_is_refused(authed_api_a, account):
    r = _with_entities(authed_api_a, _payload(account, 'MEETING', contact_ids=[]))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'participant' in _error(r)


def test_with_entities_the_inline_contact_is_a_participant(authed_api_a, account):
    r = _with_entities(
        authed_api_a, _payload(account, 'MEETING', contact_ids=[]),
        inline_contact={'first_name': 'Isabelle', 'last_name': 'Roux'},
    )
    assert r.status_code in (200, 201), r.content


def test_with_entities_a_task_needs_no_participant(authed_api_a, account):
    r = _with_entities(authed_api_a, _payload(account, 'TASK', contact_ids=[]))
    assert r.status_code in (200, 201), r.content


def test_with_entities_a_contact_of_another_account_is_refused(
    authed_api_a, account, user_a, client_account_a,
):
    from app_modules.accounts.models import CompanyAccount
    other = CompanyAccount(company_name='Other Co', has_buying_decision=True)
    other.save(user=user_a, client_id=client_account_a.id)
    stranger = _contact(other, user_a, 'Eve', 'Else')
    r = _with_entities(authed_api_a, _payload(account, 'MEETING', contact_ids=[stranger.id]))
    assert r.status_code == status.HTTP_400_BAD_REQUEST
