# backend/tests/bi/test_kpi_todo_team_by_owner.py
"""
KPI — Todo / team open activities by OWNER (the manager view's per-person todo).

Proves the declared KPI (app_modules/bi/definitions/activities.py):
- it is registered as a standard BREAKDOWN pipeline dimensioned by 'owner'
  (the architecture test: per-person is ONE declaration, no bespoke compute);
- under team scope a manager gets one bucket per team member (owner id -> open
  count), and an outsider's activity is excluded (positive + negative scope);
- cross-tenant isolation: a tenant-B activity is never counted;
- dimension_labels resolves the (already scoped) owner ids to display names in
  one query, with an email fallback when no name is set.
"""

import pytest
from django.core.cache import cache

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import todo_team_by_owner
from app_modules.bi.types import OutputShape
from permissions.compat import AuthContext


def _ctx(user, client_account):
    return AuthContext(user_id=str(user.id), client_id=str(client_account.id),
                       is_authenticated=True)


def _mk_user(email, client_account, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=client_account,
                               role=role, is_active=True, **extra)


def _mk_account(name, owner, client_account):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_act(owner, account, client_account, status=ActivityStatus.PLANNED):
    a = Activity(title='t', activity_type=ActivityType.CALL, status=status,
                 account=account, owner=owner)
    a.save(user=owner, client_id=client_account.id)
    return a


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    yield todo_team_by_owner
    registry.clear()


@pytest.fixture
def manager(db, client_account_a, role_individual_a):
    # Role flags are irrelevant to apply_role_scope (it uses auth_ctx + Team.manager).
    return _mk_user('mgr@a.test', client_account_a, role_individual_a)


@pytest.fixture
def team_x(db, client_account_a, manager):
    from end_users.models import Team
    return Team.objects.create(name='Team X', client_account=client_account_a, manager=manager)


@pytest.fixture
def member1(db, client_account_a, role_individual_a, team_x):
    return _mk_user('alice@a.test', client_account_a, role_individual_a,
                    first_name='Alice', last_name='Martin', team=team_x)


@pytest.fixture
def member2(db, client_account_a, role_individual_a, team_x):
    # No name set -> label resolver must fall back to email.
    return _mk_user('bob@a.test', client_account_a, role_individual_a, team=team_x)


@pytest.mark.django_db
def test_kpi_registered_as_owner_breakdown(kpi):
    assert registry.get('todo_team_by_owner') is kpi
    assert kpi.output_shape is OutputShape.BREAKDOWN
    assert kpi.dimension == 'owner'
    assert kpi.allowed_scopes == ('team', 'client')
    assert kpi.scope_module == 'activities'
    assert callable(kpi.dimension_labels)


@pytest.mark.django_db
def test_team_scope_breaks_down_by_owner_excludes_outsider(
    kpi, manager, member1, member2, client_account_a, role_individual_a
):
    acc1 = _mk_account('M1 Corp', member1, client_account_a)
    acc2 = _mk_account('M2 Corp', member2, client_account_a)
    _mk_act(member1, acc1, client_account_a)                       # member1: 2 open
    _mk_act(member1, acc1, client_account_a)
    _mk_act(member2, acc2, client_account_a)                       # member2: 1 open
    _mk_act(member1, acc1, client_account_a, status=ActivityStatus.COMPLETED)  # not a todo

    # An outsider (not in the manager's team) — must be excluded from team scope.
    outsider = _mk_user('out@a.test', client_account_a, role_individual_a)
    acc_o = _mk_account('Out Corp', outsider, client_account_a)
    _mk_act(outsider, acc_o, client_account_a)

    res = cached_run(kpi, _ctx(manager, client_account_a), scope='team')

    assert res.shape is OutputShape.BREAKDOWN
    assert res.value == {member1.id: 2, member2.id: 1}   # by owner, outsider absent, COMPLETED absent


@pytest.mark.django_db
def test_team_by_owner_includes_c6_sdr_bucket_on_member_account(
    kpi, manager, member1, client_account_a, role_individual_a
):
    """C6 expansion (team): a NON-member SDR's open activity on a MEMBER's account
    now enters team scope, bucketed under the SDR. The manager roster is built
    from this breakdown, so it expands to the SDR automatically — no drop, no
    orphan owner (the outsider-on-own-account case above still stays out)."""
    acc = _mk_account('M1 Corp', member1, client_account_a)
    _mk_act(member1, acc, client_account_a)                             # member1: 1 owned
    sdr = _mk_user('sdr-c6@a.test', client_account_a, role_individual_a)  # NOT a member
    _mk_act(sdr, acc, client_account_a)                                # C6 on member's account
    _mk_act(sdr, acc, client_account_a)

    res = cached_run(kpi, _ctx(manager, client_account_a), scope='team')
    # member1's own bucket + an SDR bucket via C6 (the SDR is the account's worker)
    assert res.value == {member1.id: 1, sdr.id: 2}
    # the label resolver covers the SDR too -> the roster/filter options expand
    labels = kpi.dimension_labels(list(res.value.keys()))
    assert sdr.id in labels


@pytest.mark.django_db
def test_cross_tenant_isolation(
    kpi, manager, member1, client_account_a, client_account_b, role_individual_b
):
    acc1 = _mk_account('M1 Corp', member1, client_account_a)
    _mk_act(member1, acc1, client_account_a)

    # Tenant B activity — must never be counted for a tenant-A manager.
    user_b = _mk_user('rep-b@b.test', client_account_b, role_individual_b)
    acc_b = _mk_account('B Corp', user_b, client_account_b)
    _mk_act(user_b, acc_b, client_account_b)

    res = cached_run(kpi, _ctx(manager, client_account_a), scope='team')

    assert res.value == {member1.id: 1}
    assert user_b.id not in res.value


@pytest.mark.django_db
def test_dimension_labels_resolves_names_with_email_fallback(
    kpi, member1, member2
):
    labels = kpi.dimension_labels([member1.id, member2.id])
    assert labels[member1.id] == 'Alice Martin'   # first + last
    assert labels[member2.id] == 'bob@a.test'      # no name -> email fallback
