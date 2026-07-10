# backend/tests/bi/test_kpi_todo.py
"""
KPI 1 — Todo / my activities, bucketed by due-ness.

Proves the declared KPI (app_modules/bi/definitions/activities.py):
- open activities (PLANNED / ON_HOLD) bucket correctly into
  overdue / today / upcoming on COALESCE(due_date, scheduled_date),
- non-open activities are excluded,
- scope is positive AND negative (a rep does not see another rep's todos; an
  account owner sees, via C6, open work created by someone else on their
  account).

The "accepted invitations" half is intentionally OFF (C2 / Palier 3).
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import todo_my_activities, TodoBucket
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.bi.types import OutputShape
from permissions.compat import AuthContext


TODAY = timezone.now().date()


def _ctx(user, client_account):
    return AuthContext(user_id=str(user.id), client_id=str(client_account.id),
                       is_authenticated=True)


def _mk_user(email, client_account, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=client_account,
                               role=role, is_active=True)


def _mk_account(name, owner, client_account):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_act(owner, account, client_account, status=ActivityStatus.PLANNED,
            due=None, sched=None):
    a = Activity(title='t', activity_type=ActivityType.CALL, status=status,
                 account=account, owner=owner, due_date=due, scheduled_date=sched)
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
    ci.connect_invalidation_receivers()
    yield todo_my_activities
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def account_a(db, client_account_a, user_a):
    return _mk_account('A Corp', user_a, client_account_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('rep-b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_kpi_registered(kpi):
    assert registry.get('todo_my_activities') is kpi
    assert kpi.output_shape is OutputShape.BREAKDOWN
    assert kpi.dimension == 'due_bucket'


@pytest.mark.django_db
class TestBuckets:

    def test_buckets_and_status_filter(self, kpi, user_a, account_a, client_account_a):
        # overdue x2 (one via due_date, one via scheduled_date fallback)
        _mk_act(user_a, account_a, client_account_a, due=TODAY - timedelta(days=2))
        _mk_act(user_a, account_a, client_account_a, sched=TODAY - timedelta(days=1))  # coalesce
        # today x1
        _mk_act(user_a, account_a, client_account_a, due=TODAY)
        # upcoming x1 (ON_HOLD counts as open)
        _mk_act(user_a, account_a, client_account_a,
                status=ActivityStatus.ON_HOLD, due=TODAY + timedelta(days=3))
        # excluded: COMPLETED is not a todo
        _mk_act(user_a, account_a, client_account_a,
                status=ActivityStatus.COMPLETED, due=TODAY)

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine')
        assert res.shape is OutputShape.BREAKDOWN
        assert res.value == {
            TodoBucket.OVERDUE: 2,
            TodoBucket.TODAY: 1,
            TodoBucket.UPCOMING: 1,
        }


@pytest.mark.django_db
class TestScope:

    def test_mine_excludes_other_rep(self, kpi, user_a, account_a, user_b, client_account_a):
        _mk_act(user_a, account_a, client_account_a, due=TODAY)  # mine
        account_b = _mk_account('B Corp', user_b, client_account_a)
        _mk_act(user_b, account_b, client_account_a, due=TODAY)  # other rep's own

        mine_a = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine')
        assert mine_a.value == {TodoBucket.TODAY: 1}

        mine_b = cached_run(kpi, _ctx(user_b, client_account_a), scope='mine')
        assert mine_b.value == {TodoBucket.TODAY: 1}
        # totals confirm no leakage across reps
        assert sum(mine_a.value.values()) == 1

    def test_c6_account_owner_sees_others_work_on_their_account(
        self, kpi, user_a, account_a, user_b, client_account_a
    ):
        """user_a owns account_a; an activity created by user_b on it must show
        in user_a's todo (C6), bucketed normally."""
        _mk_act(user_b, account_a, client_account_a, due=TODAY + timedelta(days=1))

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine')
        assert res.value == {TodoBucket.UPCOMING: 1}
