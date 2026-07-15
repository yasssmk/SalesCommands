# backend/tests/bi/test_team_todo_list.py
"""
GET /bi/todo/team/ — the MANAGER view's team todo ROWS.

This endpoint serves the "team filter" need: a manager narrows the team todo to
one team's subtree (and drills into one person). It reads the SAME population as
the todo_team_by_owner COUNT KPI (build_team_todo_population: open activities,
role-scoped, NO personal invited-accepted union), so:

- the team filter never widens past the manager's managed hierarchy — filtering
  on a team OUTSIDE the hierarchy (get_team_member_ids ∩ role scope) yields ZERO
  rows (NEGATIVE), while a team INSIDE it returns that team's rows (POSITIVE),
  and a parent team includes its sub-teams (HIERARCHICAL);
- a person's row count via the owner filter equals their bucket in
  todo_team_by_owner (PARITY);
- scope isolates: an out-of-hierarchy owner and another tenant never appear
  (SCOPE NEGATIVE — cross-user + cross-tenant);
- the manager's OWN accepted invitation is NOT in the rows (this is the team's
  owned work, not the manager's personal inbox — the reason we do NOT reuse
  build_todo_population).

Hierarchy under test (tenant A):
    EMEA  (manager = mgr)
      └── France       (member: fra)
    Sales US  (separate root, NOT managed by mgr; member: us)
"""

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import TODO_STATUSES, todo_team_by_owner
from app_modules.notifications.models import (
    NotificationCategory, NotificationResponseStatus,
)
from app_modules.notifications.services import NotificationService
from permissions.compat import AuthContext

from tests.signals.conftest import (  # noqa: F401
    _jwt_only_no_csrf,
    api,
    authenticate,
)


TODAY = timezone.now().date()


@pytest.fixture(autouse=True)
def _flush_and_load(db):
    load_all()
    cache.clear()
    yield
    cache.clear()
    registry.clear()


# --- factories ---------------------------------------------------------------

def _mk_user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True, **extra)


def _mk_team(name, ca, manager=None, parent=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca,
                               manager=manager, parent_team=parent)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_act(owner, account, ca, status=ActivityStatus.PLANNED, due=None):
    a = Activity(title='t', activity_type=ActivityType.CALL, status=status,
                 account=account, owner=owner, due_date=due or TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _rows(client, scope='team', team=None, owner=None):
    url = f'/bi/todo/team/?scope={scope}'
    if team:
        url += f'&team={team}'
    if owner:
        url += f'&owner={owner}'
    resp = client.get(url)
    assert resp.status_code == 200, resp.data
    return resp.data['data']


# --- hierarchy fixture -------------------------------------------------------

@pytest.fixture
def org(db, client_account_a, role_individual_a):
    """The EMEA/France + Sales US hierarchy, with one member per leaf and their
    accounts. Role flags are irrelevant to apply_role_scope (it keys on
    Team.manager); activities read = 'client' for every tier, so scope='team' is
    always within the caller's max scope — apply_role_scope does the bounding."""
    mgr = _mk_user('mgr@a.test', client_account_a, role_individual_a)
    emea = _mk_team('EMEA', client_account_a, manager=mgr)
    france = _mk_team('France', client_account_a, parent=emea)
    sales_us = _mk_team('Sales US', client_account_a)  # separate root, mgr does NOT manage it

    fra = _mk_user('fra@a.test', client_account_a, role_individual_a,
                   first_name='Fabien', last_name='Roux', team=france)
    us = _mk_user('us@a.test', client_account_a, role_individual_a,
                  first_name='Uma', last_name='Stone', team=sales_us)

    return {
        'mgr': mgr, 'emea': emea, 'france': france, 'sales_us': sales_us,
        'fra': fra, 'us': us,
        'fra_acc': _mk_account('Fra Corp', fra, client_account_a),
        'us_acc': _mk_account('US Corp', us, client_account_a),
    }


@pytest.fixture
def as_mgr(api, authenticate, org, client_account_a):  # noqa: F811
    authenticate(api, org['mgr'], client_account_a.id)
    return api


# --- tests -------------------------------------------------------------------

@pytest.mark.django_db
def test_negative_out_of_hierarchy_team_yields_zero(as_mgr, org, client_account_a):
    """NEGATIVE: EMEA manager filtering on Sales US (outside the hierarchy) gets
    ZERO rows — the team's members are not in the manager's role scope, so the
    intersection is empty."""
    _mk_act(org['us'], org['us_acc'], client_account_a)  # a real Sales US todo

    data = _rows(as_mgr, team=str(org['sales_us'].id))
    assert data['count'] == 0
    assert data['results'] == []


@pytest.mark.django_db
def test_positive_in_hierarchy_team_returns_its_rows(as_mgr, org, client_account_a):
    """POSITIVE: EMEA manager filtering on France (a sub-team) gets the France
    member's todo."""
    act = _mk_act(org['fra'], org['fra_acc'], client_account_a)

    data = _rows(as_mgr, team=str(org['france'].id))
    ids = {r['id'] for r in data['results']}
    assert ids == {str(act.id)}


@pytest.mark.django_db
def test_hierarchical_parent_team_includes_subteams(as_mgr, org, client_account_a):
    """HIERARCHICAL: filtering on EMEA (the parent) includes the France
    sub-team's rows — descendants are expanded."""
    act = _mk_act(org['fra'], org['fra_acc'], client_account_a)  # France member, under EMEA

    data = _rows(as_mgr, team=str(org['emea'].id))
    ids = {r['id'] for r in data['results']}
    assert str(act.id) in ids


@pytest.mark.django_db
def test_parity_owner_rows_equal_kpi_bucket(as_mgr, org, client_account_a):
    """PARITY: for each owner, len(rows via owner filter) == that owner's bucket
    in the todo_team_by_owner COUNT KPI — same population, same scope."""
    # Give the France member some todos and a COMPLETED (non-todo) decoy.
    _mk_act(org['fra'], org['fra_acc'], client_account_a)
    _mk_act(org['fra'], org['fra_acc'], client_account_a)
    _mk_act(org['fra'], org['fra_acc'], client_account_a, status=ActivityStatus.COMPLETED)

    counts = cached_run(todo_team_by_owner, _ctx(org['mgr'], client_account_a),
                        scope='team').value
    assert counts.get(org['fra'].id) == 2  # sanity: COMPLETED excluded

    for owner_id, expected in counts.items():
        data = _rows(as_mgr, owner=str(owner_id))
        assert data['count'] == expected
        assert len(data['results']) == expected


@pytest.mark.django_db
def test_scope_negative_cross_user_and_cross_tenant(
    as_mgr, org, client_account_a, client_account_b, role_individual_b
):
    """SCOPE NEGATIVE: with NO team filter (pure role scope), an out-of-hierarchy
    owner (Sales US) and another tenant's owner never appear."""
    fra_act = _mk_act(org['fra'], org['fra_acc'], client_account_a)   # in scope
    _mk_act(org['us'], org['us_acc'], client_account_a)               # cross-user, out of hierarchy

    # Cross-tenant: a tenant-B rep's todo must never surface for a tenant-A mgr.
    user_b = _mk_user('rep-b@b.test', client_account_b, role_individual_b)
    acc_b = _mk_account('B Corp', user_b, client_account_b)
    _mk_act(user_b, acc_b, client_account_b)

    data = _rows(as_mgr)  # scope=team, no narrowing
    ids = {r['id'] for r in data['results']}
    assert ids == {str(fra_act.id)}  # only the managed hierarchy, tenant A


@pytest.mark.django_db
def test_manager_personal_accepted_invitation_absent(as_mgr, org, client_account_a):
    """NO PERSONAL INVITATION: an activity the manager was INVITED to and
    ACCEPTED — owned by someone OUTSIDE the hierarchy — is NOT in the team rows.
    This is the guard against reusing build_todo_population: were it used, this
    row would leak in via the personal invited-accepted union."""
    invited = _mk_act(org['us'], org['us_acc'], client_account_a)  # owned by Sales US (outsider)
    invited.invited_users.add(org['mgr'])
    n = NotificationService.emit(
        client_id=client_account_a.id, recipient=org['mgr'], actor=org['us'],
        category=NotificationCategory.ACTIVITY_INVITATION,
        title='inv', related_object_type='activity', related_object_id=invited.id,
    )
    n.response_status = NotificationResponseStatus.ACCEPTED
    n.save(user=org['mgr'])

    data = _rows(as_mgr)  # scope=team, no narrowing
    ids = {r['id'] for r in data['results']}
    assert str(invited.id) not in ids
    assert data['count'] == 0


@pytest.mark.django_db
def test_population_uses_shared_todo_statuses_constant(as_mgr, org, client_account_a):
    """GUARDRAIL: the endpoint's population is bounded by the SAME TODO_STATUSES
    constant as todo_team_by_owner — only PLANNED/ON_HOLD are todos. A COMPLETED
    activity (a status NOT in TODO_STATUSES) is excluded."""
    assert ActivityStatus.COMPLETED not in TODO_STATUSES  # premise of the check
    _mk_act(org['fra'], org['fra_acc'], client_account_a, status=ActivityStatus.PLANNED)
    _mk_act(org['fra'], org['fra_acc'], client_account_a, status=ActivityStatus.ON_HOLD)
    _mk_act(org['fra'], org['fra_acc'], client_account_a, status=ActivityStatus.COMPLETED)

    data = _rows(as_mgr, team=str(org['france'].id))
    assert data['count'] == 2  # the two TODO_STATUSES rows; COMPLETED excluded
