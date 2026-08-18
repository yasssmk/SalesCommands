# backend/tests/bi/test_kpi_quota.py
"""
KPI 8 — User quota attainment (must-have).

current (computed on app_modules) / fixed target, per target_type, over the
quota period. Proves:
- value per target_type (meetings count; closed_won $),
- unsupported target_type (leads_accepted) -> None / metric_not_available,
- SECURITY scope: a user sees their OWN quota, NOT another user's; a manager
  sees a team member's quota; an unrelated user's quota is out of scope,
- query-bounded (assertNumQueries 2: quota fetch + one aggregate).
"""

from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from tests.deal_value_helpers import give_deal_value
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.quotas import quota_attainment
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext


PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 12, 31)
IN_PERIOD = date(2026, 6, 1)


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_quota(user, ca, target_type='meetings', target=10):
    from end_users.models import SalesQuota
    q = SalesQuota(user=user, name=f'Q-{user.email}', target_type=target_type,
                   target_value=target, recurrence_type='annual', fiscal_year=2026,
                   period_number=1, period_start=PERIOD_START, period_end=PERIOD_END)
    q.save()
    return q


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_meeting(owner, account, ca, when=IN_PERIOD):
    a = Activity(title='m', activity_type=ActivityType.MEETING,
                 status=ActivityStatus.COMPLETED, account=account, owner=owner,
                 scheduled_date=when)
    a.save(user=owner, client_id=ca.id)
    return a


def _mk_won_cycle(owner, account, ca, value, name='dc', when=IN_PERIOD):
    c = DecisionCycle(account=account, owner=owner, name=name,
                      outcome=CycleOutcome.WON, outcome_date=when)
    c.save(user=owner, client_id=ca.id)
    # TD-75: quota values sum the derived product roll-up, not estimated_value.
    give_deal_value(c, value, user=owner)
    return c


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield quota_attainment
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_registered(kpi):
    assert registry.get('quota_attainment') is kpi
    assert kpi.compute_fn is not None


@pytest.mark.django_db
class TestValue:

    def test_meetings_attainment(self, kpi, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a, target_type='meetings', target=10)
        acc = _mk_account('A', user_a, client_account_a)
        for _ in range(3):
            _mk_meeting(user_a, acc, client_account_a)
        # a meeting outside the period must not count
        _mk_meeting(user_a, acc, client_account_a, when=date(2025, 6, 1))

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'quota_id': str(q.id)})
        assert res.meta['current'] == 3.0
        assert res.meta['target'] == 10.0
        assert res.value == 30.0

    def test_closed_won_attainment(self, kpi, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a, target_type='closed_won', target=1000)
        acc1 = _mk_account('A1', user_a, client_account_a)
        acc2 = _mk_account('A2', user_a, client_account_a)
        _mk_won_cycle(user_a, acc1, client_account_a, value=300, name='dc1')
        _mk_won_cycle(user_a, acc2, client_account_a, value=200, name='dc2')

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'quota_id': str(q.id)})
        assert res.meta['current'] == 500.0
        assert res.value == 50.0

    def test_unsupported_target_type_not_available(self, kpi, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a, target_type='leads_accepted', target=5)
        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'quota_id': str(q.id)})
        assert res.value is None
        assert res.meta['reason'] == 'metric_not_available'


@pytest.mark.django_db
class TestScopeSecurity:

    def test_user_sees_own_not_others(self, kpi, user_a, user_b, client_account_a):
        qa = _mk_quota(user_a, client_account_a)
        qb = _mk_quota(user_b, client_account_a)

        # own quota -> computed
        own = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'quota_id': str(qa.id)})
        assert own.value == 0.0  # no meetings yet, but accessible

        # another user's quota -> NOT accessible (personal data)
        other = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                           params={'quota_id': str(qb.id)})
        assert other.value is None
        assert other.meta['reason'] == 'out_of_scope_or_missing'

    def test_manager_team_sees_member_quota(self, kpi, client_account_a, role_individual_a):
        from end_users.models import User, Team
        manager = _mk_user('mgr@a.test', client_account_a, role_individual_a)
        team = Team.objects.create(name='T', client_account=client_account_a, manager=manager)
        member = _mk_user('member@a.test', client_account_a, role_individual_a)
        member.team = team
        member.save()
        outsider = _mk_user('out@a.test', client_account_a, role_individual_a)

        q_member = _mk_quota(member, client_account_a, target_type='meetings', target=10)
        acc = _mk_account('A', member, client_account_a)
        _mk_meeting(member, acc, client_account_a)
        _mk_meeting(member, acc, client_account_a)
        q_outsider = _mk_quota(outsider, client_account_a)

        # manager (team scope) sees the member's quota, computed on member data
        res = cached_run(kpi, _ctx(manager, client_account_a), scope='team',
                         params={'quota_id': str(q_member.id)})
        assert res.value == 20.0  # 2 / 10

        # ...but not an unrelated user's quota
        res_out = cached_run(kpi, _ctx(manager, client_account_a), scope='team',
                             params={'quota_id': str(q_outsider.id)})
        assert res_out.value is None
        assert res_out.meta['reason'] == 'out_of_scope_or_missing'


@pytest.mark.django_db
class TestQueryBound:

    def test_bounded(self, kpi, user_a, client_account_a, django_assert_num_queries):
        q = _mk_quota(user_a, client_account_a, target_type='meetings', target=10)
        acc = _mk_account('A', user_a, client_account_a)
        for _ in range(4):
            _mk_meeting(user_a, acc, client_account_a)
        # quota fetch + meetings count = 2
        with django_assert_num_queries(2):
            res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                             params={'quota_id': str(q.id)})
            _ = res.value
