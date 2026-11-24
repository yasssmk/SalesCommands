# backend/tests/activities/test_create_with_entities_fk_tenant.py
"""
F1 (TD-246, sprint 2 Game Plan — sub-step S1): the FKs received by
POST /module-activities/create-with-entities/ are resolved INSIDE the tenant,
and on the activity's ACCOUNT, through the central helper core/tenant_fk.py.

Before: `decision_cycle_id`, `decision_step_id` and `source_activity_id` were
read raw from the payload (activities/services/activity_creation_service.py
:137-139); the only check — « the step belongs to the cycle » — had no tenant.
Tenant A could create its activity INSIDE the decision cycle of tenant B (the
activity then appears in B's cycle), or point it at B's activity as its source.

Now, through the real endpoint (two tenants, conftest fixtures):
  * an id of another tenant and an unknown id give the SAME 400
    OBJECT_NOT_FOUND (no existence oracle), and nothing is created;
  * an id of the same tenant but of ANOTHER account gives 400 INVALID_ACCOUNT;
  * the legitimate path (cycle + step + source of the account) is unchanged.

DB: Postgres.
"""

import uuid

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from core.error_messages import ContactErrorMessages, CoreErrorMessages
from tests.signals.test_signal_cycle_attachment import _cycle

pytestmark = pytest.mark.django_db

_URL = '/module-activities/create-with-entities/'
OBJECT_NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)
INVALID_ACCOUNT = str(ContactErrorMessages.INVALID_ACCOUNT)


# =============================================================================
# HELPERS
# =============================================================================

def _participant(account):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='Pat', last_name='Participant')
    c.save(client_id=account.client_id)
    return str(c.id)


def _activity(account, user, title='Earlier call'):
    a = Activity(title=title, activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, account=account, owner=user)
    a.save(user=user, client_id=account.client_id)
    return a


def _second_account(client_account, user):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(company_name='Initech', has_buying_decision=True)
    acc.save(user=user, client_id=client_account.id)
    return acc


def _post(api, account, **fk):
    payload = {
        'activity': {
            'title': 'Discovery call',
            'activity_type': ActivityType.CALL,
            'status': ActivityStatus.PLANNED,
            'account_id': str(account.id),
            'contact_ids': [_participant(account)],
            'scheduled_date': '2026-12-01',
            **fk,
        },
        'inline_contact': None, 'inline_cycle': None, 'inline_step_stage': None,
    }
    return api.post(_URL, payload, format='json')


def _created(title='Discovery call'):
    return Activity.objects.filter(title=title)


def _assert_not_found(resp):
    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
    assert OBJECT_NOT_FOUND in resp.content.decode(), resp.content


def _assert_same_refusal(unknown, foreign):
    """Same status, same body: an unknown id and a foreign id are not told apart."""
    _assert_not_found(foreign)
    assert unknown.status_code == foreign.status_code, (unknown.content, foreign.content)
    assert unknown.content == foreign.content, (
        'existence oracle:\n'
        f'  unknown -> {unknown.content!r}\n  foreign -> {foreign.content!r}'
    )


# =============================================================================
# ANOTHER TENANT — refused, nothing written, no existence oracle
# =============================================================================

def test_cycle_and_step_of_another_tenant_are_refused(
    authed_api_a, account, other_tenant_account, user_b,
):
    foreign = _cycle(other_tenant_account, user_b, name='Globex deal')

    resp = _post(authed_api_a, account,
                 decision_cycle_id=str(foreign.id),
                 decision_step_id=str(foreign.qualification.id))

    _assert_not_found(resp)
    assert not _created().exists()
    assert not Activity.objects.filter(decision_cycle=foreign).exists()


def test_unknown_cycle_and_cycle_of_another_tenant_give_the_same_answer(
    authed_api_a, account, other_tenant_account, user_b,
):
    foreign = _cycle(other_tenant_account, user_b, name='Globex deal')

    unknown = _post(authed_api_a, account,
                    decision_cycle_id=str(uuid.uuid4()),
                    decision_step_id=str(uuid.uuid4()))
    foreign_resp = _post(authed_api_a, account,
                         decision_cycle_id=str(foreign.id),
                         decision_step_id=str(foreign.qualification.id))

    _assert_same_refusal(unknown, foreign_resp)


def test_step_of_another_tenant_is_refused_on_an_own_cycle(
    authed_api_a, account, user_a, other_tenant_account, user_b,
):
    own = _cycle(account, user_a)
    foreign = _cycle(other_tenant_account, user_b, name='Globex deal')

    unknown = _post(authed_api_a, account,
                    decision_cycle_id=str(own.id),
                    decision_step_id=str(uuid.uuid4()))
    foreign_resp = _post(authed_api_a, account,
                         decision_cycle_id=str(own.id),
                         decision_step_id=str(foreign.qualification.id))

    _assert_same_refusal(unknown, foreign_resp)
    assert not _created().exists()


def test_source_activity_of_another_tenant_is_refused(
    authed_api_a, account, other_tenant_account, user_b,
):
    foreign = _activity(other_tenant_account, user_b)

    unknown = _post(authed_api_a, account, source_activity_id=str(uuid.uuid4()))
    foreign_resp = _post(authed_api_a, account, source_activity_id=str(foreign.id))

    _assert_same_refusal(unknown, foreign_resp)
    assert not Activity.objects.filter(source_activity=foreign).exists()


# =============================================================================
# SAME TENANT, ANOTHER ACCOUNT — refused (INVALID_ACCOUNT)
# =============================================================================

def test_cycle_of_another_account_is_refused(
    authed_api_a, account, user_a, client_account_a,
):
    other = _second_account(client_account_a, user_a)
    cycle = _cycle(other, user_a, name='Initech deal')

    resp = _post(authed_api_a, account,
                 decision_cycle_id=str(cycle.id),
                 decision_step_id=str(cycle.qualification.id))

    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
    assert INVALID_ACCOUNT in resp.content.decode(), resp.content
    assert not Activity.objects.filter(decision_cycle=cycle).exists()


def test_cycle_of_another_account_alone_is_refused_by_its_own_check(
    authed_api_a, account, user_a, client_account_a,
):
    """The cycle's account check stands on its own (no step to catch it)."""
    other = _second_account(client_account_a, user_a)
    cycle = _cycle(other, user_a, name='Initech deal')

    resp = _post(authed_api_a, account, decision_cycle_id=str(cycle.id))

    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
    assert INVALID_ACCOUNT in resp.content.decode(), resp.content
    assert not Activity.objects.filter(decision_cycle=cycle).exists()


def test_step_of_another_account_is_refused(
    authed_api_a, account, user_a, client_account_a,
):
    other = _second_account(client_account_a, user_a)
    cycle = _cycle(other, user_a, name='Initech deal')

    resp = _post(authed_api_a, account, decision_step_id=str(cycle.qualification.id))

    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
    assert INVALID_ACCOUNT in resp.content.decode(), resp.content
    assert not _created().exists()


def test_source_activity_of_another_account_is_refused(
    authed_api_a, account, user_a, client_account_a,
):
    other = _second_account(client_account_a, user_a)
    source = _activity(other, user_a)

    resp = _post(authed_api_a, account, source_activity_id=str(source.id))

    assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
    assert INVALID_ACCOUNT in resp.content.decode(), resp.content
    assert not Activity.objects.filter(source_activity=source).exists()


# =============================================================================
# NON-REGRESSION — the legitimate path
# =============================================================================

def test_own_cycle_step_and_source_are_accepted(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    source = _activity(account, user_a)

    resp = _post(authed_api_a, account,
                 decision_cycle_id=str(cycle.id),
                 decision_step_id=str(cycle.qualification.id),
                 source_activity_id=str(source.id))

    assert resp.status_code == status.HTTP_201_CREATED, resp.content
    created = _created().get()
    assert created.decision_cycle_id == cycle.id
    assert created.decision_step_id == cycle.qualification.id
    assert created.source_activity_id == source.id
