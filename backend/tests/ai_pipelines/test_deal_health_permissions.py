# backend/tests/ai_pipelines/test_deal_health_permissions.py
"""
Sprint « Deal health v2 », sub-step 6b — who may RUN a deal health (PO
decision n° 6): an admin, a manager, or the owner of the decision cycle.
Nobody else. Reading the snapshots does not change.

ONE central predicate (decision_cycles/services/deal_health_access.py
can_run_deal_health), enforced by the run endpoint (the standard permission
refusal, 403) and served read-only on the cycle payloads the front reads
(detail and by-account) so the UI never offers an impossible action.

Real path: POST /module-ai-pipelines/deal-health/run/ and GET
/decision_cycles/{id}/ + /decision_cycles/by-account/{account}/, real JWT
role flags (the authenticate helper of tests/signals/conftest.py).

  (a) a rep who does NOT own the cycle → refused (permission), no LLM call;
  (b) the owner, a manager, an admin → allowed;
  (c) a user of another tenant → refused, no LLM call;
  (d) the cycle payloads carry can_run_deal_health, right for each case.
"""

import copy
import json

import pytest

from core.error_messages import CoreErrorMessages

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'


# =============================================================================
# The people of tenant A (cycle.owner is user_a, a rep)
# =============================================================================

def _role(client_account, name, *, is_admin=False, is_manager=False):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account, name=name,
        is_admin=is_admin, is_manager=is_manager,
        is_individual=not (is_admin or is_manager),
        read=True, write=True, modify=True, can_delete=True,
    )


def _user(client_account, email, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=client_account,
                               role=role, is_active=True)


@pytest.fixture
def other_rep(client_account_a, role_individual_a):
    return _user(client_account_a, 'other-rep@tenant-a.test', role_individual_a)


@pytest.fixture
def manager(client_account_a):
    return _user(client_account_a, 'manager@tenant-a.test',
                 _role(client_account_a, 'DH Manager', is_manager=True))


@pytest.fixture
def admin(client_account_a):
    return _user(client_account_a, 'admin@tenant-a.test',
                 _role(client_account_a, 'DH Admin', is_admin=True))


def _as(authenticate, user, tenant_id):
    from rest_framework.test import APIClient
    client = APIClient()
    authenticate(client, user, tenant_id)
    return client


def _run(client, cycle):
    return client.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    return patch_active_provider


def _calls(provider):
    return len(provider.calls_for('deal_health'))


# =============================================================================
# (a) / (c) — refused
# =============================================================================

def test_a_a_rep_who_does_not_own_the_cycle_is_refused(
    authenticate, client_account_a, cycle, other_rep, provider,
):
    resp = _run(_as(authenticate, other_rep, client_account_a.id), cycle)

    assert resp.status_code == 403, resp.content
    assert str(CoreErrorMessages.PERMISSION_DENIED) in json.dumps(resp.data)
    assert _calls(provider) == 0


def test_c_a_user_of_another_tenant_is_refused(authed_api_b, cycle, provider):
    resp = _run(authed_api_b, cycle)

    assert resp.status_code in (400, 403, 404), resp.content
    assert _calls(provider) == 0


# =============================================================================
# (b) — the owner, a manager, an admin
# =============================================================================

@pytest.mark.parametrize('who', ['owner', 'manager', 'admin'])
def test_b_the_owner_a_manager_and_an_admin_may_run(
    request, authenticate, client_account_a, cycle, user_a, provider, who,
):
    user = {'owner': user_a}.get(who) or request.getfixturevalue(who)

    resp = _run(_as(authenticate, user, client_account_a.id), cycle)

    assert resp.status_code == 201, resp.content
    assert _calls(provider) == 1


# =============================================================================
# (d) — the right, served on the cycle payloads the front reads
# =============================================================================

@pytest.mark.parametrize('who, expected', [
    ('owner', True), ('manager', True), ('admin', True), ('other_rep', False),
])
def test_d_the_cycle_payloads_carry_can_run_deal_health(
    request, authenticate, client_account_a, cycle, user_a, who, expected,
):
    user = {'owner': user_a}.get(who) or request.getfixturevalue(who)
    client = _as(authenticate, user, client_account_a.id)

    detail = client.get(f'/decision_cycles/{cycle.id}/')
    assert detail.status_code == 200, detail.content
    assert detail.data['data']['can_run_deal_health'] is expected

    # The DC workspace reads its cycle from the by-account payload.
    listing = client.get(f'/decision_cycles/by-account/{cycle.account_id}/')
    assert listing.status_code == 200, listing.content
    [row] = [r for r in listing.data['data']['results'] if r['id'] == str(cycle.id)]
    assert row['can_run_deal_health'] is expected


def test_d_another_tenant_does_not_even_see_the_cycle(authed_api_b, cycle):
    assert authed_api_b.get(f'/decision_cycles/{cycle.id}/').status_code == 404
