# backend/tests/bi/test_kpi_batch_dc_cycle_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil batch KPI (MESURE, aucun fix).

POST /bi/kpi/batch/ runs its specs in a SEQUENTIAL loop
(``app_modules/bi/views.py:173`` ``for spec in specs`` -> ``compute_kpi:177``
-> ``cached_run:111``), with no mutualisation between specs. When the Home fires
one ``dc_cycle_state`` spec per visible decision cycle, each spec re-runs
``_cycle_state`` (``bi/definitions/decision_cycles.py:122-182``) from scratch:
``cycles.prefetch_related('steps__activities').filter(id=cycle_id).first()``
(``:138``) = 3 queries per cycle (cycle row + steps prefetch + activities
prefetch); ``get_bulk_summaries([cycle])`` (``:145``) adds 0 (prefetched data).

GARDE-FOU POST-FIX. Le batch groupe desormais les specs dc_cycle_state par
(scope, periode) et les calcule en UN passage : ``_cycle_state_bulk`` fait un seul
``DecisionCycle.objects.filter(id__in=[...]).prefetch_related('steps__activities')``
(3 requetes) + ``CycleAggregationService.get_bulk_summaries`` (0), et
``dc_cycle_state`` passe a ``default_period='all'`` (plus de requete ClientAccount
fiscale par spec). Le cout des dc_cycle_state est donc CONSTANT (~3), independant
du nombre de cycles.

ROUGE (avant fix, commit c8775ff) -> VERT (apres regroupement) :
  3  dc_cycle_state : 12 -> 3
  11 dc_cycle_state : 44 -> 3
  pente : 4/cycle -> 0/cycle
Casser le groupage (retomber sur la boucle par spec) fait REMONTER ces nombres et
echouer ce test — c'est sa non-vacuite.

CACHE NEUTRALISE : DummyCache pendant la mesure -> chaque spec est FROID (jamais
un hit Redis). On mesure le cout reel du batch.

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep

# authed_api_a authenticates as user_a on tenant A (same real JWT setup the BI
# endpoint tests use); client_account_a / role_individual_a come via bi/conftest.
from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    user_a,
    authed_api_a,
)

TODAY = timezone.now().date()
FUTURE = TODAY + timedelta(days=30)
STAGES = [
    PipelineStep.QUALIFICATION,
    PipelineStep.TECHNICAL_FIT,
    PipelineStep.SOLUTION_VALIDATION,
    PipelineStep.BUSINESS_CASE,
    PipelineStep.CLOSING,
]

# Batch sizes: 11 = the PO's observed case; 3 = a lower point to prove the slope.
CYCLES_HIGH = 11
CYCLES_LOW = 3

_seq = 0


@pytest.fixture(autouse=True)
def _registry_and_cold_cache(db, settings):
    """Populate the live KPI registry (the endpoint reads it) and force a cold
    cache (DummyCache) so every spec is computed, never served from Redis."""
    from app_modules.bi.definitions import load_all

    load_all()
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
    }
    cache.clear()
    yield
    cache.clear()


def _mk_full_cycle(user, ca):
    """A realistic decision cycle: 5 pipeline steps, each with an activity, so
    the steps__activities prefetch actually loads rows (step 0 completed, step 1
    planned -> a genuine IN_PROGRESS cycle)."""
    global _seq
    _seq += 1
    acc = CompanyAccount(
        company_name=f"Acc{_seq}", has_buying_decision=True, account_owner=user
    )
    acc.save(user=user, client_id=ca.id)

    cycle = DecisionCycle(account=acc, owner=user, name=f"dc{_seq}")
    cycle.save(user=user, client_id=ca.id)

    steps = []
    for order, stage in enumerate(STAGES):
        step = DecisionStep(cycle=cycle, stage=stage, order=order, name=str(stage))
        step.save(user=user, client_id=ca.id)
        steps.append(step)

    def _act(step, status, scheduled):
        a = Activity(
            title="a", activity_type=ActivityType.CALL, status=status,
            account=acc, owner=user, decision_cycle=cycle,
            decision_step=step, scheduled_date=scheduled,
        )
        a.save(user=user, client_id=ca.id)

    _act(steps[0], ActivityStatus.COMPLETED, TODAY)
    _act(steps[1], ActivityStatus.PLANNED, FUTURE)
    return cycle


@pytest.mark.django_db
class TestBatchDcCycleStateRedBaseline:
    """Measures, does not fix. Prints the starting numbers and locks the slope."""

    def _measure_batch(self, authed_api_a, cycles):
        body = {
            "requests": [
                {"key": "dc_cycle_state", "scope": "mine",
                 "params": {"cycle_id": str(c.id)}}
                for c in cycles
            ]
        }
        cache.clear()  # explicit cold intent (a no-op under DummyCache).
        with CaptureQueriesContext(connection) as cap:
            resp = authed_api_a.post("/bi/kpi/batch/", body, format="json")
        assert resp.status_code == 200, resp.content
        results = resp.data["data"]["results"]
        assert len(results) == len(cycles)
        # Every spec ran to a value (owned by user_a, scope mine) — not an error.
        assert all("value" in r for r in results), results
        return len(cap.captured_queries)

    def test_batch_query_count_and_slope(self, authed_api_a, user_a, client_account_a):
        cycles_high = [_mk_full_cycle(user_a, client_account_a) for _ in range(CYCLES_HIGH)]
        cycles_low = [_mk_full_cycle(user_a, client_account_a) for _ in range(CYCLES_LOW)]

        q_high = self._measure_batch(authed_api_a, cycles_high)
        q_low = self._measure_batch(authed_api_a, cycles_low)
        per_cycle = (q_high - q_low) / (CYCLES_HIGH - CYCLES_LOW)

        # ---- THE NUMBERS (printed; run with `pytest -s` to see it) ----
        print("\n" + "=" * 60)
        print("BATCH dc_cycle_state SQL queries — grouped guard (cold cache)")
        print("=" * 60)
        print(f"  {CYCLES_LOW:>3} dc_cycle_state specs : {q_low} queries")
        print(f"  {CYCLES_HIGH:>3} dc_cycle_state specs : {q_high} queries")
        print(f"  slope                    : {per_cycle:.2f} queries / cycle")
        print("=" * 60 + "\n")

        # ---- THE GREEN, locked. dc_cycle_state specs are grouped into ONE shared
        # query set (filter id__in + steps/activities prefetch = 3), so the cost is
        # CONSTANT regardless of the cycle count: 3 cycles = 3, 11 cycles = 3, slope
        # 0. Breaking the grouping (per-spec loop) makes these climb back to 12/44
        # and fails the test. ----
        assert q_low == 3, f"3-cycle batch expected 3 queries, got {q_low}"
        assert q_high == 3, f"11-cycle batch expected 3 queries, got {q_high}"
        assert per_cycle == 0.0, f"slope expected 0.0 q/cycle, got {per_cycle}"
