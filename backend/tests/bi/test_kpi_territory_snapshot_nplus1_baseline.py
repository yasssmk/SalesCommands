# backend/tests/bi/test_kpi_territory_snapshot_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil territory (MESURE, aucun fix).

GET /bi/kpi/territory_progress_by_team/?scope=team was measured at 7.44s cold vs
~441ms warm. The KPI (bi/definitions/territory.py:134-195, compute_fn :210) READS
the materialised snapshot columns and GROUP BYs them (:161-166), but LAZILY
refreshes stale snapshots on read: refresh_stale_snapshots
(territory.py:154 -> territories/services/snapshot.py:74), bounded by
SNAPSHOT_REFRESH_BUDGET = 50 (snapshot.py:43).

Cost of one stale snapshot (snapshot.py:86-87, :105-113): 1 locked SELECT + a
bulk UPDATE per refresh CALL, plus **2 COUNTs per refreshed row** — the coverage
denominator + numerator (compute_territory_coverage_counts, coverage.py:41 & :48).
Staleness is TIME-based, not write-based: a snapshot is refreshed when never
computed, older than the 2h TTL (SNAPSHOT_TTL_SECONDS, snapshot.py:38), or from a
different period (_stale_q, snapshot.py:65-71 ; models.py:110-114).

So COLD (many stale) = a burst of 2 COUNTs per stale territory (capped at 50);
WARM (all fresh) = one empty refresh SELECT + one GROUP BY. This module GRAVES
those two numbers, the per-snapshot cost (2 COUNTs), and proves the cold/warm gap
that is the 7.44s vs 441ms.

Cache neutralised (DummyCache) so we measure the real cold refresh cost.
DB: Postgres.
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.accounts.models import AccountClassification, CompanyAccount
from app_modules.activities.constants import ActivityOutcome, ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.territory import territory_progress_by_team
from app_modules.territories.models import Territory
from app_modules.territories.services.snapshot import SNAPSHOT_REFRESH_BUDGET
from permissions.compat import AuthContext

TODAY = timezone.now().date()

# Volume: more territories than the refresh budget, so COLD saturates the cap and
# the 50-bound is exercised (the PO's mass-staleness case). All share one filter
# so each territory's 2 coverage COUNTs run over a real, non-trivial account set.
N_TERRITORIES = SNAPSHOT_REFRESH_BUDGET + 5   # 55 > budget 50
N_ACCOUNTS = 20
N_TOUCHED = 12
# Two stale counts (both < budget) to prove the per-snapshot slope is 2 COUNTs.
K_LOW = 5
K_HIGH = 25

_seq = 0


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True, **extra)


def _mk_team(name, ca, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner, classification=AccountClassification.SMB)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_territory(owner, ca):
    global _seq
    _seq += 1
    t = Territory(name=f'T{_seq}', type='ACCOUNT', owner=owner,
                  filter_definition={'classification': 'SMB'})
    t.save(user=owner, client_id=ca.id)
    return t


def _touch(account, owner, ca):
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=ActivityOutcome.SUCCESSFUL,
                 account=account, owner=owner, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)


@pytest.fixture(autouse=True)
def _registry_and_cold_cache(db, settings):
    load_all()
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
    }
    cache.clear()
    yield
    cache.clear()
    registry.clear()


@pytest.fixture
def org(db, client_account_a, role_individual_a):
    ca = client_account_a
    mgr = _mk_user('t-mgr@a.test', ca, role_individual_a)
    amer = _mk_team('AMER', ca, manager=mgr)
    rep = _mk_user('t-amer@a.test', ca, role_individual_a, team=amer)

    # One shared SMB account pool (a territory filter matches accounts tenant-wide),
    # so every territory's 2 coverage COUNTs run over N_ACCOUNTS real rows.
    for i in range(N_ACCOUNTS):
        acc = _mk_account(f'acc{i}', rep, ca)
        if i < N_TOUCHED:
            _touch(acc, rep, ca)

    territories = [_mk_territory(rep, ca) for _ in range(N_TERRITORIES)]
    return {'ca': ca, 'mgr': mgr, 'amer': amer, 'rep': rep, 'territories': territories}


def _run(org):
    return cached_run(territory_progress_by_team, _ctx(org['mgr'], org['ca']), scope='team')


def _prime_all_fresh(org):
    # Each read refreshes up to the budget; two passes cover 55 with budget 50.
    for _ in range(3):
        _run(org)


def _mark_stale(org, n):
    """Force exactly ``n`` snapshots stale (computed_at = NULL), the rest fresh."""
    ids = [t.id for t in org['territories'][:n]]
    Territory.objects.filter(id__in=ids).update(coverage_computed_at=None)


def _measure(org):
    cache.clear()
    with CaptureQueriesContext(connection) as cap:
        _ = _run(org).value
    return len(cap.captured_queries)


@pytest.mark.django_db
class TestTerritorySnapshotRedBaseline:
    """Measures, does not fix. Prints the cold/warm numbers and the per-snapshot cost."""

    def test_cold_vs_warm_and_per_snapshot_cost(self, org):
        # WARM: all snapshots fresh -> one empty refresh SELECT + one GROUP BY.
        _prime_all_fresh(org)
        warm = _measure(org)

        # COLD, budget-saturated: force ALL stale -> the read refreshes exactly
        # SNAPSHOT_REFRESH_BUDGET rows (the cap), each paying 2 COUNTs.
        _prime_all_fresh(org)
        _mark_stale(org, N_TERRITORIES)
        cold_capped = _measure(org)
        refreshed_now = Territory.objects.filter(coverage_computed_at__isnull=False).count()

        # PER-SNAPSHOT slope: K_LOW vs K_HIGH stale (both under the budget) ->
        # the query delta is 2 per extra stale territory (the 2 coverage COUNTs).
        _prime_all_fresh(org)
        _mark_stale(org, K_LOW)
        cold_k_low = _measure(org)
        _prime_all_fresh(org)
        _mark_stale(org, K_HIGH)
        cold_k_high = _measure(org)
        per_snapshot = (cold_k_high - cold_k_low) / (K_HIGH - K_LOW)

        # ---- THE RED (printed; run with `pytest -s` to see it) ----
        print("\n" + "=" * 64)
        print("RED BASELINE — territory_progress_by_team SQL queries (scope=team)")
        print("=" * 64)
        print(f"  WARM (all {N_TERRITORIES} snapshots fresh)      : {warm} queries")
        print(f"  COLD ({N_TERRITORIES} stale, budget {SNAPSHOT_REFRESH_BUDGET}) : {cold_capped} queries"
              f"  ({refreshed_now} refreshed)")
        print(f"  COLD, {K_LOW:>2} stale                        : {cold_k_low} queries")
        print(f"  COLD, {K_HIGH:>2} stale                        : {cold_k_high} queries")
        print(f"  per-snapshot cost                    : {per_snapshot:.2f} queries / stale territory")
        print("=" * 64)
        print(f"  cold/warm gap (budget-saturated)     : {cold_capped - warm} extra queries\n")

        # ---- Proofs ----
        # Refresh is budget-capped, not per-territory unbounded.
        assert refreshed_now == SNAPSHOT_REFRESH_BUDGET, (
            f"expected {SNAPSHOT_REFRESH_BUDGET} refreshed (budget), got {refreshed_now}"
        )
        # Each stale territory costs exactly its 2 coverage COUNTs.
        assert per_snapshot == 2.0, f"per-snapshot cost expected 2.0, got {per_snapshot}"
        # Cold is far heavier than warm — the 7.44s vs 441ms in query terms.
        assert cold_capped >= warm + 2 * SNAPSHOT_REFRESH_BUDGET, (
            f"cold {cold_capped} not >= warm {warm} + 2*budget"
        )
        # Warm is a small constant (no per-territory work).
        assert warm <= 15, f"warm baseline unexpectedly high: {warm}"
