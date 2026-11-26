# backend/tests/ai_pipelines/test_prep_call_access.py
"""
Sprint 2 Game Plan — sub-step G3: who may generate a Game Plan, and on which
activity.

Before: POST /module-ai-pipelines/prep-call/run/ only checked the tenant and
the activity type (CALL / MEETING / DEMO, else a 400 —
prep_call_serializer.py:74-77). Any user of the tenant could generate on any
activity, COMPLETED / CANCELLED included, with or without a cycle or a
campaign; an EMAIL / a LinkedIn message was refused with a 400.

Now:
  * PERMISSION (a real 403): ai_pipelines/services/game_plan_access.py
    can_run_game_plan — same tenant, then an admin or a manager (tenant-wide),
    the owner of the activity's cycle, or the owner of the activity. Reuses
    can_run_deal_health and is_manager_or_admin, not a copy of them.
  * BUSINESS RULES (200 + an INFO code, never a 400): game_plan_blocked_reason
    — the type is neither a plan type nor a message type
    (PREP_CALL_TYPE_NOT_ELIGIBLE), the activity is terminal — not in
    activities.constants.NON_TERMINAL_STATUSES (PREP_CALL_ACTIVITY_CLOSED),
    neither a campaign nor a cycle (PREP_CALL_NO_CAMPAIGN_NO_DC). Nothing is
    run, nothing written.
  * EMAIL / LINKEDIN are accepted in message mode (output_kind MESSAGE).
  * GET by-activity stays readable on COMPLETED / CANCELLED.
  * The activity detail serves `can_run_game_plan` and
    `game_plan_blocked_reason` (the decision_cycles/serializers.py
    can_run_deal_health pattern).

Real path: POST prep-call/run/, GET prep-call/by-activity/<id>/ and GET
/module-activities/<id>/, real view and pipeline, fake LLM provider.

DB: Postgres.
"""

import json

import pytest
from rest_framework.test import APIClient

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import (
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE,
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE,
)
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import TODAY, _cycle


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    """Another rep of tenant A — owns nothing here."""
    from end_users.models import User
    return User.objects.create(email='rep2-a@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def manager_a(db, client_account_a):
    from end_users.models import User, UserRole
    role = UserRole.objects.create(client_account=client_account_a, name='Manager',
                                   is_admin=False, is_manager=True, is_individual=False,
                                   read=True, write=True, modify=True, can_delete=True)
    return User.objects.create(email='manager-a@tenant-a.test', client_account=client_account_a,
                               role=role, is_active=True)


@pytest.fixture
def as_user(authenticate, client_account_a):
    def _client(user):
        client = APIClient(enforce_csrf_checks=False)
        authenticate(client, user, client_account_a.id)
        return client
    return _client


@pytest.fixture
def cycle(account, user_a2):
    """A cycle owned by user_a2 (NOT the activity's owner)."""
    return _cycle(account, user_a2)


def _activity(account, owner, *, cycle=None, activity_type=ActivityType.CALL,
              status=ActivityStatus.PLANNED, campaign=None):
    a = Activity(title='Discovery', activity_type=activity_type, status=status,
                 account=account, owner=owner, decision_cycle=cycle, campaign=campaign,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=account.client_id)
    return a


def _post(client, activity):
    return client.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')


def _nothing_ran(activity):
    assert not AIPipelineRun.objects.filter(source_activity=activity).exists()
    assert not PrepCallSnapshot.objects.filter(activity=activity).exists()


def _assert_info(resp, code):
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body['success'] is True
    assert body['code'] == code
    assert body['message']
    assert body['data']['run'] is None and body['data']['snapshot'] is None


# =============================================================================
# PERMISSION — a real 403
# =============================================================================

def test_a_rep_who_owns_neither_the_activity_nor_the_cycle_is_refused(
    as_user, account, user_a, manager_a, provider, client_account_a,
):
    from end_users.models import User
    stranger = User.objects.create(email='rep3-a@tenant-a.test', client_account=client_account_a,
                                   role=user_a.role, is_active=True)
    cycle = _cycle(account, user_a)                    # owned by user_a
    activity = _activity(account, user_a, cycle=cycle)  # owned by user_a

    resp = _post(as_user(stranger), activity)

    assert resp.status_code == 403, resp.content
    _nothing_ran(activity)


@pytest.mark.parametrize('who', ['activity_owner', 'cycle_owner', 'manager'])
def test_the_activity_owner_the_cycle_owner_and_a_manager_may_generate(
    who, as_user, account, user_a, user_a2, manager_a, cycle, provider,
):
    activity = _activity(account, user_a, cycle=cycle)   # activity: user_a, cycle: user_a2
    requester = {'activity_owner': user_a, 'cycle_owner': user_a2, 'manager': manager_a}[who]

    resp = _post(as_user(requester), activity)

    assert resp.status_code == 201, resp.content


def test_without_a_cycle_a_manager_passes_the_permission_and_a_stranger_does_not(
    as_user, account, user_a, user_a2, manager_a, provider,
):
    """No cycle (so no can_run_deal_health): the manager branch of
    can_run_game_plan — the permission passes, the business rule answers."""
    activity = _activity(account, user_a)               # neither cycle nor campaign

    assert _post(as_user(user_a2), activity).status_code == 403
    _assert_info(_post(as_user(manager_a), activity), PREP_CALL_NO_CAMPAIGN_NO_DC_CODE)
    _assert_info(_post(as_user(user_a), activity), PREP_CALL_NO_CAMPAIGN_NO_DC_CODE)


# =============================================================================
# BUSINESS RULES — 200 + an INFO code, nothing run
# =============================================================================

@pytest.mark.parametrize('status', [ActivityStatus.COMPLETED, ActivityStatus.CANCELLED])
def test_a_terminal_activity_is_an_info(status, as_user, account, user_a, cycle, provider):
    activity = _activity(account, user_a, cycle=cycle, status=status)

    resp = _post(as_user(user_a), activity)

    _assert_info(resp, PREP_CALL_ACTIVITY_CLOSED_CODE)
    _nothing_ran(activity)


def test_an_activity_without_campaign_nor_cycle_is_an_info(as_user, account, user_a, provider):
    activity = _activity(account, user_a)

    resp = _post(as_user(user_a), activity)

    _assert_info(resp, PREP_CALL_NO_CAMPAIGN_NO_DC_CODE)
    _nothing_ran(activity)


def test_a_type_without_game_plan_is_an_info(as_user, account, user_a, cycle, provider):
    activity = _activity(account, user_a, cycle=cycle, activity_type=ActivityType.TASK)

    resp = _post(as_user(user_a), activity)

    _assert_info(resp, PREP_CALL_TYPE_NOT_ELIGIBLE_CODE)
    _nothing_ran(activity)


# =============================================================================
# EMAIL / LINKEDIN — accepted, message mode
# =============================================================================

@pytest.mark.parametrize('activity_type', [ActivityType.EMAIL, ActivityType.LINKEDIN])
def test_an_email_or_a_linkedin_message_is_accepted_in_message_mode(
    activity_type, as_user, account, user_a, cycle, provider,
):
    activity = _activity(account, user_a, cycle=cycle, activity_type=activity_type)

    resp = _post(as_user(user_a), activity)

    assert resp.status_code == 201, resp.content
    assert PrepCallSnapshot.objects.get(activity=activity).output_kind == 'MESSAGE'


def test_a_call_is_a_plan(as_user, account, user_a, cycle, provider):
    activity = _activity(account, user_a, cycle=cycle)

    assert _post(as_user(user_a), activity).status_code == 201
    assert PrepCallSnapshot.objects.get(activity=activity).output_kind == 'PLAN'


# =============================================================================
# READ — still readable once the activity is over
# =============================================================================

@pytest.mark.parametrize('status', [ActivityStatus.COMPLETED, ActivityStatus.CANCELLED])
def test_the_game_plan_stays_readable_on_a_terminal_activity(
    status, as_user, account, user_a, cycle, provider,
):
    activity = _activity(account, user_a, cycle=cycle)
    client = as_user(user_a)
    assert _post(client, activity).status_code == 201
    Activity.objects.filter(pk=activity.pk).update(status=status)

    resp = client.get(f'/module-ai-pipelines/prep-call/by-activity/{activity.id}/')

    assert resp.status_code == 200, resp.content
    assert resp.json()['data']['brief'] == _VALID_BRIEF


# =============================================================================
# THE ACTIVITY DETAIL — served for the front
# =============================================================================

def test_the_activity_detail_serves_the_access_and_the_reason(
    as_user, account, user_a, cycle, client_account_a,
):
    from end_users.models import User
    stranger = User.objects.create(email='rep4-a@tenant-a.test', client_account=client_account_a,
                                   role=user_a.role, is_active=True)
    open_call = _activity(account, user_a, cycle=cycle)
    done_call = _activity(account, user_a, cycle=cycle, status=ActivityStatus.COMPLETED)

    def detail(user, activity):
        resp = as_user(user).get(f'/module-activities/{activity.id}/')
        assert resp.status_code == 200, resp.content
        body = resp.json()
        return body.get('data', body)

    owner_view = detail(user_a, open_call)
    assert owner_view['can_run_game_plan'] is True
    assert owner_view['game_plan_blocked_reason'] is None
    assert detail(user_a, done_call)['game_plan_blocked_reason'] == PREP_CALL_ACTIVITY_CLOSED_CODE
    assert detail(stranger, open_call)['can_run_game_plan'] is False
