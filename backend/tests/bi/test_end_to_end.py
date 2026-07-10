# backend/tests/bi/test_end_to_end.py
"""
Palier 1 exit criterion — the BI architecture validated end-to-end, à vide.

ONE named scenario walks all four architecture stages against a single fixture
KPIDefinition, proving they compose:

    1. REGISTRY     — a KPI is declared and introspectable.
    2. COMPUTE+SCOPE— run() aggregates at the DB level, scoped by role, and the
                      C6 account-owner inheritance flows through the whole chain.
    3. CACHE        — a warm identical call is a hit (0 DB queries).
    4. INVALIDATION — a write to a source model busts the cache; the next call
                      recomputes.

This is both the documented "architecture validated empty" milestone and a
regression canary: touch any stage (scope callable, compute, cache key, or
invalidation wiring) and this test moves. Requires Redis.
"""

import pytest
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape, KPIResult
from app_modules.bi.signals import cache_invalidation as ci
from core.cache_utils import _is_redis_backend
from permissions.compat import AuthContext


# --- helpers ---------------------------------------------------------------

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


E2E_TAG = 'bi_e2e_kpi_tag'
E2E_KEY = 'e2e_open_activities'


def _make_e2e_kpi():
    """A representative KPI: count of activities, scoped by role, invalidated
    when an Activity is written."""
    return KPIDefinition(
        key=E2E_KEY,
        label='E2E open activities',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.SCALAR,
        allowed_scopes=('mine', 'team', 'client'),
        cache_tags=(E2E_TAG,),
        invalidation_sources=('module_activities.Activity',),
    )


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def bi_stack(db):
    """Register the fixture KPI and wire its invalidation — the full stack."""
    registry.clear()
    kpi = registry.register(_make_e2e_kpi())
    ci.connect_invalidation_receivers()
    yield kpi
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.mark.django_db
class TestBIArchitectureEndToEnd:

    def test_registry_to_invalidation_full_flow(
        self, bi_stack, client_account_a, role_individual_a,
        django_assert_num_queries, django_capture_on_commit_callbacks,
    ):
        # --- actors -------------------------------------------------------
        ae = _mk_user('ae@a.test', client_account_a, role_individual_a)       # account owner
        sdr = _mk_user('sdr@a.test', client_account_a, role_individual_a)     # works AE's account
        other = _mk_user('other@a.test', client_account_a, role_individual_a) # own account only

        account_ae = _mk_account('AE Corp', ae, client_account_a)
        account_other = _mk_account('Other Corp', other, client_account_a)

        _mk_activity(ae, account_ae, client_account_a)      # AE's own
        _mk_activity(sdr, account_ae, client_account_a)     # SDR on AE's account -> C6 for AE
        _mk_activity(other, account_other, client_account_a)  # other rep's own -> NOT AE's

        ae_ctx = _ctx(ae, client_account_a)

        # === STAGE 1 — REGISTRY ==========================================
        assert registry.get(E2E_KEY) is bi_stack
        assert E2E_KEY in registry.keys()

        # === STAGE 2 — COMPUTE + ROLE SCOPE (incl. C6) ===================
        r1 = cached_run(bi_stack, ae_ctx, scope='mine')
        assert isinstance(r1, KPIResult)
        assert r1.shape is OutputShape.SCALAR
        # AE sees: own activity + SDR's activity on AE's account (C6). NOT the
        # other rep's activity on their own account.
        assert r1.value == 2

        # negative scope: the other rep, under mine, sees only their own.
        assert cached_run(bi_stack, _ctx(other, client_account_a), scope='mine').value == 1

        # === STAGE 3 — CACHE (warm hit, 0 DB queries) ====================
        with django_assert_num_queries(0):
            hit = cached_run(bi_stack, ae_ctx, scope='mine')
        assert hit.value == 2  # served from cache

        # === STAGE 4 — INVALIDATION (write busts, next call recomputes) ==
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            _mk_activity(sdr, account_ae, client_account_a)  # another SDR activity on AE's account
        assert callbacks, "a write to a source model must schedule an invalidation"

        r2 = cached_run(bi_stack, ae_ctx, scope='mine')
        assert r2.value == 3  # recomputed (would still be 2 if the cache weren't busted)
