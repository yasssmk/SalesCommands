# backend/tests/bi/test_kpi_territory.py
"""
KPI 4 — Territory coverage % (custom compute_fn, parameterized by territory).

Proves:
- coverage = touched-with-response / total territory accounts (num/denom),
- period filtering (only responses in the window count),
- scope is negative-safe: another owner's territory is NOT visible (the
  compute_fn scopes via apply_role_scope on Territory),
- params['territory_id'] is in the cache key (two territories -> two keys),
- the compute is query-bounded (assertNumQueries ~3, no per-account N+1).
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.activities.constants import ActivityStatus, ActivityType, ActivityOutcome
from app_modules.activities.models import Activity
from app_modules.territories.models import Territory
from app_modules.bi import registry
from app_modules.bi.cache import cached_run, build_kpi_cache_key
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.territory import territory_coverage
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.bi.types import Period
from permissions.compat import AuthContext


TODAY = timezone.now().date()
PERIOD = Period(start=TODAY - timedelta(days=30), end=TODAY)


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca, classification=AccountClassification.SMB):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner, classification=classification)
    acc.save(user=owner, client_id=ca.id)
    return acc


_terr_seq = 0


def _mk_territory(owner, ca, filter_definition):
    global _terr_seq
    _terr_seq += 1
    t = Territory(name=f'T{_terr_seq}', type='ACCOUNT', owner=owner,
                  filter_definition=filter_definition)
    t.save(user=owner, client_id=ca.id)
    return t


def _touch(account, owner, ca, when=None, outcome=ActivityOutcome.SUCCESSFUL):
    """An activity carrying a response (outcome set) on the account."""
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=outcome,
                 account=account, owner=owner, scheduled_date=when or TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _no_response_activity(account, owner, ca):
    """An activity with NO outcome -> not a 'touch with response'."""
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.PLANNED, account=account, owner=owner,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
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
    yield territory_coverage
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('rep-b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_registered_as_custom_compute(kpi):
    assert registry.get('territory_coverage') is kpi
    assert kpi.compute_fn is not None
    assert kpi.source is None  # custom-compute KPI: no standard source


@pytest.mark.django_db
class TestCoverageValue:

    def test_coverage_ratio(self, kpi, user_a, client_account_a):
        terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
        # 4 SMB accounts in the territory
        a1 = _mk_account('SMB1', user_a, client_account_a)
        a2 = _mk_account('SMB2', user_a, client_account_a)
        a3 = _mk_account('SMB3', user_a, client_account_a)
        _mk_account('SMB4', user_a, client_account_a)
        # 1 ENTERPRISE account -> NOT in the territory (denominator excludes)
        _mk_account('ENT', user_a, client_account_a, classification=AccountClassification.ENTERPRISE)

        # touched-with-response: a1, a2. a3 has an activity but NO outcome. a4 none.
        _touch(a1, user_a, client_account_a)
        _touch(a2, user_a, client_account_a)
        _no_response_activity(a3, user_a, client_account_a)

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         period=PERIOD, params={'territory_id': str(terr.id)})
        assert res.value == 50.0                       # 2 / 4
        assert res.meta['numerator'] == 2
        assert res.meta['denominator'] == 4

    def test_response_outside_period_not_counted(self, kpi, user_a, client_account_a):
        terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
        a1 = _mk_account('SMB1', user_a, client_account_a)
        a2 = _mk_account('SMB2', user_a, client_account_a)
        _touch(a1, user_a, client_account_a, when=TODAY)                         # in period
        _touch(a2, user_a, client_account_a, when=TODAY - timedelta(days=400))   # out of period

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         period=PERIOD, params={'territory_id': str(terr.id)})
        assert res.meta == {'numerator': 1, 'denominator': 2, 'territory_id': str(terr.id)}
        assert res.value == 50.0


@pytest.mark.django_db
class TestScope:

    def test_other_owners_territory_not_visible(self, kpi, user_a, user_b, client_account_a):
        terr_b = _mk_territory(user_b, client_account_a, {'classification': 'SMB'})
        _mk_account('SMB1', user_b, client_account_a)

        # user_a asks for user_b's territory under mine -> not in scope -> None
        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         period=PERIOD, params={'territory_id': str(terr_b.id)})
        assert res.value is None
        assert res.meta['reason'] == 'out_of_scope_or_missing'

        # the owner sees it
        res_b = cached_run(kpi, _ctx(user_b, client_account_a), scope='mine',
                           period=PERIOD, params={'territory_id': str(terr_b.id)})
        assert res_b.value == 0.0  # 1 account, none touched
        assert res_b.meta['denominator'] == 1


@pytest.mark.django_db
class TestCacheKeyAndQueries:

    def test_territory_id_distinguishes_cache_keys(self, kpi, user_a, client_account_a):
        t1 = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
        t2 = _mk_territory(user_a, client_account_a, {'classification': 'ENTERPRISE'})
        ctx = _ctx(user_a, client_account_a)
        k1 = build_kpi_cache_key(kpi, ctx, 'mine', PERIOD, {'territory_id': str(t1.id)})
        k2 = build_kpi_cache_key(kpi, ctx, 'mine', PERIOD, {'territory_id': str(t2.id)})
        assert k1 != k2

    def test_query_bounded_no_n_plus_one(self, kpi, user_a, client_account_a,
                                         django_assert_num_queries):
        terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
        for i in range(6):  # many accounts -> would explode if per-account
            acc = _mk_account(f'SMB{i}', user_a, client_account_a)
            _touch(acc, user_a, client_account_a)

        ctx = _ctx(user_a, client_account_a)
        # cold cache; explicit period (no fiscal lookup). Territory fetch +
        # denominator count + numerator count = 3 queries, independent of #accounts.
        with django_assert_num_queries(3):
            res = cached_run(kpi, ctx, scope='mine', period=PERIOD,
                             params={'territory_id': str(terr.id)})
            _ = res.value
