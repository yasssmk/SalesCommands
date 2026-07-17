# backend/tests/bi/test_endpoint.py
"""
Endpoint tests for the BI API (GET /bi/kpi/<key>/ and POST /bi/kpi/batch/).

The KPI `scope` is a USER INPUT at the API boundary, so the security focus is:
  - a scalar KPI respects mine scope (cross-user) and tenant isolation
    (cross-tenant) — the endpoint plumbs apply_role_scope correctly;
  - scope is BOUNDED by the caller's role: an individual cannot request a
    scope wider than their tier grants (403), while a manager can (contrast
    proves the bound is role-based, not hard-coded);
  - unknown key -> 404, missing compute_fn param -> 400;
  - batch runs N definitions in one round-trip with PER-ITEM errors and a cap.

Uses sales_quotas KPIs for the scope-bound tests because that module's read
scope differs by tier (individual='mine', manager='team').
"""

import uuid
from datetime import date

import pytest
from rest_framework.test import APIClient

# Re-use the production-shaped auth/tenant fixtures. `_jwt_only_no_csrf` is an
# autouse fixture; importing it here activates it for this module.
from tests.signals.conftest import (  # noqa: F401
    _jwt_only_no_csrf,
    api,
    authenticate,
    user_a,
    user_b,
    authed_api_a,
)


# The KPI registry is a module-level singleton; test_registry.py clears it in
# teardown. These tests hit the LIVE registry through HTTP, so ensure it is
# populated regardless of test order (load_all is idempotent).
@pytest.fixture(autouse=True)
def _ensure_registry_loaded():
    from app_modules.bi.definitions import load_all
    load_all()
    yield


# --- local fixtures: a manager on tenant A + a second individual -------------
@pytest.fixture
def role_manager_a(db, client_account_a):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account_a, name='Manager',
        is_admin=False, is_manager=True, is_individual=False,
        read=True, write=True, modify=True, can_delete=True,
    )


@pytest.fixture
def manager_a(db, client_account_a, role_manager_a):
    from end_users.models import User
    return User.objects.create(
        email='mgr-a@tenant-a.test', client_account=client_account_a,
        role=role_manager_a, is_active=True,
    )


@pytest.fixture
def authed_api_manager_a(authenticate, manager_a, client_account_a):
    """Independent APIClient authenticated as a MANAGER on tenant A."""
    client = APIClient(enforce_csrf_checks=False)
    authenticate(client, manager_a, client_account_a.id)
    return client


@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='rep-a2@tenant-a.test', client_account=client_account_a,
        role=role_individual_a, is_active=True,
    )


@pytest.fixture
def restricted_kpi():
    """A throwaway KPI on scope_module='teams' — the only ENABLED module whose
    read scope is tier-restricted (individual='mine', manager='client'). Lets us
    exercise the role-based scope bound honestly: every module the shipping KPIs
    use is read='client' for all tiers (or disabled), so the bound never yields
    403 for them by design — it only bites where the module's read policy
    actually restricts the tier. Registered then unregistered per test."""
    from django.db.models import Count
    from end_users.models import Team
    from app_modules.bi import registry
    from app_modules.bi.registry import KPIDefinition
    from app_modules.bi.types import OutputShape

    kpi = KPIDefinition(
        key='_test_teams_count', label='Test teams count', scope_module='teams',
        source=lambda: Team.objects.all(), aggregation=Count('id'),
        period_field='created_at', output_shape=OutputShape.SCALAR,
    )
    registry.register(kpi)
    yield kpi
    registry._REGISTRY.pop(kpi.key, None)


# --- data helpers ------------------------------------------------------------
def _mk_account(owner, client_account, name='Corp'):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_activity(owner, account, client_account, title='Act'):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title=title, activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
        account=account, owner=owner, scheduled_date=date(2026, 7, 15),
    )
    a.save(user=owner, client_id=client_account.id)
    return a


# =============================================================================
# POSITIVE — scalar KPI, mine scope (cross-user) and tenant isolation
# =============================================================================
@pytest.mark.django_db
def test_scalar_mine_counts_only_callers_records(
    authed_api_a, user_a, user_a2, client_account_a
):
    """mine scope through the endpoint returns only the caller's records.

    Each activity sits on an account owned by its own owner, so C6
    account-owner inheritance does not leak the other rep's activity in.
    """
    acc_a = _mk_account(user_a, client_account_a, 'A Corp')
    acc_other = _mk_account(user_a2, client_account_a, 'Other Corp')
    _mk_activity(user_a, acc_a, client_account_a, 'mine')
    _mk_activity(user_a2, acc_other, client_account_a, 'not mine')

    resp = authed_api_a.get('/bi/kpi/leads_activities_created/?scope=mine&period=all')

    assert resp.status_code == 200
    data = resp.data['data']
    assert data['key'] == 'leads_activities_created'
    assert data['scope'] == 'mine'
    assert data['shape'] == 'scalar'
    assert data['value'] == 1  # only the caller's activity, not user_a2's


@pytest.mark.django_db
def test_scalar_isolates_across_tenants(
    authed_api_a, user_a, client_account_a, user_b, client_account_b
):
    """A tenant-A caller never counts a tenant-B record, even at client scope."""
    acc_a = _mk_account(user_a, client_account_a, 'A Corp')
    acc_b = _mk_account(user_b, client_account_b, 'B Corp')
    _mk_activity(user_a, acc_a, client_account_a, 'A act')
    _mk_activity(user_b, acc_b, client_account_b, 'B act')

    resp = authed_api_a.get('/bi/kpi/leads_activities_created/?scope=client&period=all')

    assert resp.status_code == 200
    assert resp.data['data']['value'] == 1  # tenant A only


# =============================================================================
# SECURITY — scope is bounded by the caller's role (THE sprint security point)
# =============================================================================
@pytest.mark.django_db
def test_individual_cannot_request_scope_beyond_tier(authed_api_a, restricted_kpi):
    """teams read for an individual is 'mine'; requesting 'team' -> 403.

    The scope bound runs BEFORE compute, so no data is needed."""
    resp = authed_api_a.get('/bi/kpi/_test_teams_count/?scope=team')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_manager_may_request_team_scope(authed_api_manager_a, restricted_kpi):
    """Same request as the individual case, but a manager's teams read scope is
    'client', so the bound passes and the KPI computes (200). The 403-vs-200
    contrast on the identical request proves the bound is role-based."""
    resp = authed_api_manager_a.get('/bi/kpi/_test_teams_count/?scope=team&period=all')
    assert resp.status_code == 200
    assert resp.data['data']['shape'] == 'scalar'


# =============================================================================
# ERROR MAPPING — unknown key -> 404, missing param -> 400
# =============================================================================
@pytest.mark.django_db
def test_unknown_key_returns_404(authed_api_a):
    resp = authed_api_a.get('/bi/kpi/does_not_exist/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_missing_compute_fn_param_returns_400(authed_api_a):
    """quota_attainment at mine scope is allowed for an individual, but the
    compute_fn requires quota_id -> ValueError -> 400."""
    resp = authed_api_a.get('/bi/kpi/quota_attainment/?scope=mine')
    assert resp.status_code == 400


# =============================================================================
# BATCH — N in one round-trip, per-item errors, cap
# =============================================================================
@pytest.mark.django_db
def test_batch_runs_all_with_per_item_errors(
    authed_api_a, user_a, client_account_a, restricted_kpi
):
    acc_a = _mk_account(user_a, client_account_a, 'A Corp')
    _mk_activity(user_a, acc_a, client_account_a, 'a')

    body = {'requests': [
        {'key': 'leads_activities_created', 'scope': 'mine', 'period': 'all'},  # ok
        {'key': 'does_not_exist'},                                              # 404 item
        {'key': '_test_teams_count', 'scope': 'team'},                          # 403 item (individual)
    ]}
    resp = authed_api_a.post('/bi/kpi/batch/', body, format='json')

    assert resp.status_code == 200
    results = resp.data['data']['results']
    assert len(results) == 3
    assert results[0]['value'] == 1            # first ran to a value
    assert results[1]['status'] == 404         # unknown key, per-item
    assert results[1]['key'] == 'does_not_exist'
    assert results[2]['status'] == 403         # scope exceeded, per-item — batch not failed


@pytest.mark.django_db
def test_batch_rejects_oversized_request(authed_api_a):
    body = {'requests': [{'key': 'leads_activities_created'} for _ in range(21)]}
    resp = authed_api_a.post('/bi/kpi/batch/', body, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_batch_requires_requests_list(authed_api_a):
    resp = authed_api_a.post('/bi/kpi/batch/', {'nope': 1}, format='json')
    assert resp.status_code == 400


# =============================================================================
# END-TO-END — owner breakdown + server-side labels through the real endpoint
# =============================================================================
@pytest.mark.django_db
def test_todo_team_by_owner_returns_owner_breakdown_with_labels(
    authed_api_manager_a, manager_a, client_account_a, role_individual_a
):
    from end_users.models import Team, User

    team = Team.objects.create(name='TX', client_account=client_account_a, manager=manager_a)
    member = User.objects.create(
        email='alice@a.test', client_account=client_account_a, role=role_individual_a,
        is_active=True, first_name='Alice', last_name='Martin', team=team,
    )
    acc = _mk_account(member, client_account_a, 'M Corp')
    _mk_activity(member, acc, client_account_a, 'a1')
    _mk_activity(member, acc, client_account_a, 'a2')

    resp = authed_api_manager_a.get('/bi/kpi/todo_team_by_owner/?scope=team&period=all')

    assert resp.status_code == 200
    data = resp.data['data']
    assert data['shape'] == 'breakdown'
    assert data['value'] == {str(member.id): 2}                     # by owner, JSON-safe keys
    assert data['meta']['labels'] == {str(member.id): 'Alice Martin'}  # resolved server-side


# =============================================================================
# UNIT — serialize_result locks the breakdown/label form (no DB)
# =============================================================================
def test_serialize_result_stringifies_breakdown_keys_and_resolves_labels():
    from app_modules.bi.presentation import serialize_result
    from app_modules.bi.types import KPIResult, OutputShape

    uid = uuid.uuid4()
    result = KPIResult(key='x', shape=OutputShape.BREAKDOWN, value={uid: 3}, scope='team')

    seen = {}

    class _Def:
        dimension = 'owner'
        def dimension_labels(self, ids):
            seen['ids'] = ids           # resolver gets the RAW, already-scoped ids
            return {uid: 'Jane Doe'}

    out = serialize_result(result, _Def())

    assert seen['ids'] == [uid]                    # only the ids present in the breakdown
    assert out['value'] == {str(uid): 3}           # JSON-safe string keys
    assert out['meta']['labels'] == {str(uid): 'Jane Doe'}
