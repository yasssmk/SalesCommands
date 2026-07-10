# backend/tests/bi/test_invalidation.py
"""
Tests for registry-driven BI cache invalidation (bi/signals/cache_invalidation.py).

Still "à vide": a fixture KPIDefinition whose invalidation_sources include the
Activity model and whose cache_tags are a BI-specific namespace. We prove the
acceptance criterion:

    hit -> write a source model -> the KPI's tag is bumped on commit ->
    the cached entry is stale -> the next call is a MISS and recomputes.

Requires Redis (tag-version invalidation is Redis-only; the test env runs a
local redis-server).
"""

import pytest
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run, build_kpi_cache_key
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape
from app_modules.bi.signals import cache_invalidation as ci
from core.cache_utils import _is_redis_backend, get_tag_version
from permissions.compat import AuthContext


# =============================================================================
# Helpers / fixtures
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


BI_TAG = 'bi_fixture_kpi_tag'


def _kpi():
    return KPIDefinition(
        key='fixture_invalidated_count',
        label='Fixture invalidated count',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.SCALAR,
        cache_tags=(BI_TAG,),
        invalidation_sources=('module_activities.Activity',),
    )


@pytest.fixture
def wired_kpi(db):
    """Register the fixture KPI and connect the BI invalidation receivers."""
    registry.clear()
    kpi = _kpi()
    registry.register(kpi)
    ci.connect_invalidation_receivers()
    yield kpi
    ci.disconnect_invalidation_receivers()
    registry.clear()


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


def test_env_uses_redis():
    assert _is_redis_backend(), "BI invalidation tests require the Redis backend"


# =============================================================================
# The map is derived from the registry
# =============================================================================

@pytest.mark.django_db
def test_model_tag_map_from_registry(wired_kpi):
    mapping = ci.build_model_tag_map()
    assert mapping == {'module_activities.Activity': frozenset({BI_TAG})}


# =============================================================================
# hit -> write -> miss (the acceptance criterion)
# =============================================================================

@pytest.mark.django_db
class TestWriteBustsCache:

    def test_write_source_model_busts_and_recomputes(
        self, wired_kpi, user_a, account_a, client_account_a,
        django_assert_num_queries, django_capture_on_commit_callbacks,
    ):
        ctx = _ctx(user_a, client_account_a)
        _mk_activity(user_a, account_a, client_account_a)  # 1 activity

        # warm
        r1 = cached_run(wired_kpi, ctx, scope='mine')
        assert r1.value == 1

        # identical call before any write -> HIT (0 DB queries)
        with django_assert_num_queries(0):
            r_hit = cached_run(wired_kpi, ctx, scope='mine')
        assert r_hit.value == 1

        # WRITE a source-model row; execute the on_commit invalidation callbacks
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            _mk_activity(user_a, account_a, client_account_a)  # 2nd activity
        assert callbacks, "expected an on_commit invalidation callback"

        # next call -> the tag was bumped -> key changed -> MISS -> recompute
        r2 = cached_run(wired_kpi, ctx, scope='mine')
        assert r2.value == 2  # would still be 1 if the stale entry were served

    def test_tag_version_and_key_change_on_write(
        self, wired_kpi, user_a, account_a, client_account_a,
        django_capture_on_commit_callbacks,
    ):
        ctx = _ctx(user_a, client_account_a)
        _mk_activity(user_a, account_a, client_account_a)

        v_before = get_tag_version(client_account_a.id, BI_TAG)
        key_before = build_kpi_cache_key(wired_kpi, ctx, 'mine', None)

        with django_capture_on_commit_callbacks(execute=True):
            _mk_activity(user_a, account_a, client_account_a)

        v_after = get_tag_version(client_account_a.id, BI_TAG)
        key_after = build_kpi_cache_key(wired_kpi, ctx, 'mine', None)

        assert v_after > v_before          # the write bumped the KPI's tag
        assert key_after != key_before     # so the cache key moved

    def test_delete_also_busts(
        self, wired_kpi, user_a, account_a, client_account_a,
        django_capture_on_commit_callbacks,
    ):
        ctx = _ctx(user_a, client_account_a)
        a1 = _mk_activity(user_a, account_a, client_account_a)
        _mk_activity(user_a, account_a, client_account_a)

        r1 = cached_run(wired_kpi, ctx, scope='mine')
        assert r1.value == 2

        with django_capture_on_commit_callbacks(execute=True):
            a1.delete()

        r2 = cached_run(wired_kpi, ctx, scope='mine')
        assert r2.value == 1  # recomputed after delete busted the cache


# =============================================================================
# Suppression guard
# =============================================================================

@pytest.mark.django_db
def test_signals_disabled_suppresses_bump(
    wired_kpi, user_a, account_a, client_account_a,
    django_capture_on_commit_callbacks,
):
    from core.cache_utils import disable_signals
    ctx = _ctx(user_a, client_account_a)
    _mk_activity(user_a, account_a, client_account_a)
    v_before = get_tag_version(client_account_a.id, BI_TAG)

    with disable_signals():
        with django_capture_on_commit_callbacks(execute=True):
            _mk_activity(user_a, account_a, client_account_a)

    v_after = get_tag_version(client_account_a.id, BI_TAG)
    assert v_after == v_before  # bump suppressed while signals disabled
