# backend/tests/bi/test_cache.py
"""
Tests for the BI cache layer (app_modules/bi/cache.py).

Still "à vide": a fixture KPIDefinition over Activity. We prove:
- a warm second identical call is a HIT (0 DB queries) and returns the value,
- the key encodes tenant + user + scope + period (no collisions across them),
- a tag-version bump changes the key (reuses the existing invalidation
  mechanism; the receiver wiring itself is palier 1e),
- non-Redis backends bypass the cache cleanly (compute fresh each time).

These require Redis (the test env runs a local redis-server).
"""

import pytest
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import cache as bi_cache
from app_modules.bi import compute
from app_modules.bi.cache import cached_run, build_kpi_cache_key
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape, Period
from core.cache_utils import _is_redis_backend, invalidate_tag
from permissions.compat import AuthContext


# =============================================================================
# Helpers
# =============================================================================

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


def _mk_activity(owner, account, client_account):
    a = Activity(title='act', activity_type=ActivityType.CALL,
                 status=ActivityStatus.PLANNED, account=account, owner=owner,
                 scheduled_date=timezone.now().date())
    a.save(user=owner, client_id=client_account.id)
    return a


def _kpi(cache_tags=('activities',)):
    return KPIDefinition(
        key='fixture_cached_count',
        label='Fixture cached count',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.SCALAR,
        cache_tags=cache_tags,
    )


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@tenant-a.test', client_account_a, role_individual_a)


@pytest.fixture
def account_a(db, client_account_a, user_a):
    return _mk_account('Acct A', user_a, client_account_a)


# Guard: the suite assumes Redis is active (test env starts redis-server).
def test_env_uses_redis():
    assert _is_redis_backend(), "BI cache hit tests require the Redis backend"


# =============================================================================
# HIT — the acceptance criterion
# =============================================================================

@pytest.mark.django_db
class TestCacheHit:

    def test_second_identical_call_is_hit_zero_queries(
        self, user_a, account_a, client_account_a, django_assert_num_queries
    ):
        for _ in range(3):
            _mk_activity(user_a, account_a, client_account_a)
        ctx = _ctx(user_a, client_account_a)
        kpi = _kpi()

        # First call warms the cache (computes).
        first = cached_run(kpi, ctx, scope='mine')
        assert first.value == 3

        # Second identical call must be served from cache: 0 DB queries.
        with django_assert_num_queries(0):
            second = cached_run(kpi, ctx, scope='mine')
        assert second.value == 3

    def test_different_scope_is_a_miss(self, user_a, account_a, client_account_a):
        for _ in range(2):
            _mk_activity(user_a, account_a, client_account_a)
        ctx = _ctx(user_a, client_account_a)
        kpi = _kpi()

        mine = cached_run(kpi, ctx, scope='mine')
        client = cached_run(kpi, ctx, scope='client')  # different key -> own compute
        assert mine.value == 2 and client.value == 2
        # distinct cache keys
        assert build_kpi_cache_key(kpi, ctx, 'mine', None) != \
               build_kpi_cache_key(kpi, ctx, 'client', None)


# =============================================================================
# KEY COMPOSITION — no collisions across tenant / user / scope / period
# =============================================================================

@pytest.mark.django_db
class TestKeyComposition:

    def test_keys_distinct_across_dimensions(
        self, client_account_a, client_account_b, role_individual_a, role_individual_b
    ):
        ua = _mk_user('u-a@a.test', client_account_a, role_individual_a)
        ua2 = _mk_user('u-a2@a.test', client_account_a, role_individual_a)
        ub = _mk_user('u-b@b.test', client_account_b, role_individual_b)
        kpi = _kpi()

        ctx_a = _ctx(ua, client_account_a)
        base = build_kpi_cache_key(kpi, ctx_a, 'mine', None)

        # different USER -> different key
        assert build_kpi_cache_key(kpi, _ctx(ua2, client_account_a), 'mine', None) != base
        # different TENANT -> different key
        assert build_kpi_cache_key(kpi, _ctx(ub, client_account_b), 'mine', None) != base
        # different SCOPE -> different key
        assert build_kpi_cache_key(kpi, ctx_a, 'team', None) != base
        # different PERIOD -> different key
        p1 = Period(start=None, end=None)
        p2 = Period(start='2026-01-01', end='2026-12-31')
        assert build_kpi_cache_key(kpi, ctx_a, 'mine', p2) != \
               build_kpi_cache_key(kpi, ctx_a, 'mine', p1)

    def test_tag_bump_changes_key(self, client_account_a, role_individual_a):
        ua = _mk_user('u-a@a.test', client_account_a, role_individual_a)
        ctx = _ctx(ua, client_account_a)
        kpi = _kpi(cache_tags=('activities',))

        before = build_kpi_cache_key(kpi, ctx, 'mine', None)
        invalidate_tag(client_account_a.id, 'activities')  # bump the tag version
        after = build_kpi_cache_key(kpi, ctx, 'mine', None)
        assert before != after  # stale entry can never be hit again


# =============================================================================
# NON-REDIS — clean bypass (compute fresh, no caching)
# =============================================================================

@pytest.mark.django_db
class TestNonRedisBypass:

    def test_bypass_computes_each_time(self, user_a, account_a, client_account_a, monkeypatch):
        _mk_activity(user_a, account_a, client_account_a)
        ctx = _ctx(user_a, client_account_a)
        kpi = _kpi()

        calls = {'n': 0}
        real_run = compute.run

        def spy(*a, **kw):
            calls['n'] += 1
            return real_run(*a, **kw)

        monkeypatch.setattr(compute, 'run', spy)
        # Force the non-Redis path.
        monkeypatch.setattr(bi_cache, '_is_redis_backend', lambda: False)

        cached_run(kpi, ctx, scope='mine')
        cached_run(kpi, ctx, scope='mine')
        # No caching on bypass: producer ran both times.
        assert calls['n'] == 2
