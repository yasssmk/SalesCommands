# backend/tests/bi/test_kpi_batch_dc_cycle_grouped.py
"""
Correctness of the grouped dc_cycle_state batch path (the perf fix keeps behaviour
byte-identical).

Covers:
- EQUIVALENCE: each cycle's grouped-batch result equals the per-spec single
  endpoint result (grouped path == per-spec path), for 11 realistic cycles.
- ORDER: a batch interleaving dc_cycle_state with another KPI reassembles
  results[i] <-> requests[i] across the group boundary.
- STRICT PARITY: a dc_cycle_state spec missing cycle_id yields that item's 400
  (same as the per-spec path), while its neighbours still return 200 in order.
- NON-REGRESSION: a non-grouped KPI in a mixed batch returns the same value it
  returns alone.

Cache neutralised (DummyCache) so the grouped path is exercised cold.
DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep

from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    user_a,
    authed_api_a,
)

TODAY = timezone.now().date()
FUTURE = TODAY + timedelta(days=30)
STAGES = [PipelineStep.QUALIFICATION, PipelineStep.TECHNICAL_FIT,
          PipelineStep.SOLUTION_VALIDATION, PipelineStep.BUSINESS_CASE, PipelineStep.CLOSING]

# The non-grouped KPI used to interleave / prove non-regression: a standard
# BREAKDOWN on the same module, no params, period-agnostic when asked with 'all'.
OTHER_KEY = "dc_cycles_by_outcome"

_seq = 0


@pytest.fixture(autouse=True)
def _registry_and_cold_cache(db, settings):
    from app_modules.bi.definitions import load_all

    load_all()
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
    }
    cache.clear()
    yield
    cache.clear()


def _mk_cycle(user, ca, *, stalled=False):
    """A realistic cycle: 5 steps each with an activity. stalled=False -> step 0
    completed + step 1 planned (IN_PROGRESS); stalled=True -> all completed, none
    planned (STALLED) — so different cycles carry different states."""
    global _seq
    _seq += 1
    acc = CompanyAccount(company_name=f"Acc{_seq}", has_buying_decision=True, account_owner=user)
    acc.save(user=user, client_id=ca.id)
    cycle = DecisionCycle(account=acc, owner=user, name=f"dc{_seq}")
    cycle.save(user=user, client_id=ca.id)
    steps = []
    for order, stage in enumerate(STAGES):
        st = DecisionStep(cycle=cycle, stage=stage, order=order, name=str(stage))
        st.save(user=user, client_id=ca.id)
        steps.append(st)

    def _act(step, status, scheduled):
        a = Activity(title="a", activity_type=ActivityType.CALL, status=status,
                     account=acc, owner=user, decision_cycle=cycle,
                     decision_step=step, scheduled_date=scheduled)
        a.save(user=user, client_id=ca.id)

    if stalled:
        for st in steps:
            _act(st, ActivityStatus.COMPLETED, TODAY)
    else:
        _act(steps[0], ActivityStatus.COMPLETED, TODAY)
        _act(steps[1], ActivityStatus.PLANNED, FUTURE)
    return cycle


def _single(authed_api_a, cycle_id):
    resp = authed_api_a.get(f"/bi/kpi/dc_cycle_state/?scope=mine&cycle_id={cycle_id}")
    assert resp.status_code == 200, resp.content
    return resp.data["data"]


def _batch(authed_api_a, specs):
    resp = authed_api_a.post("/bi/kpi/batch/", {"requests": specs}, format="json")
    assert resp.status_code == 200, resp.content
    return resp.data["data"]["results"]


@pytest.mark.django_db
class TestGroupedBatchEquivalence:

    def test_grouped_equals_per_spec_for_every_cycle(self, authed_api_a, user_a, client_account_a):
        # 11 cycles (the PO's case) with MIXED states so equivalence is meaningful.
        cycles = [_mk_cycle(user_a, client_account_a, stalled=(i % 3 == 0)) for i in range(11)]

        specs = [{"key": "dc_cycle_state", "scope": "mine",
                  "params": {"cycle_id": str(c.id)}} for c in cycles]
        grouped = _batch(authed_api_a, specs)

        assert len(grouped) == 11
        for c, item in zip(cycles, grouped):
            single = _single(authed_api_a, c.id)
            # The grouped-batch item must equal the per-spec single-endpoint dict
            # (same value, same meta — byte-identical business result).
            assert item == single, f"cycle {c.id}: grouped {item} != per-spec {single}"
            assert item["meta"]["cycle_id"] == str(c.id)


@pytest.mark.django_db
class TestGroupedBatchOrder:

    def test_interleaved_batch_preserves_index(self, authed_api_a, user_a, client_account_a):
        a = _mk_cycle(user_a, client_account_a, stalled=False)
        b = _mk_cycle(user_a, client_account_a, stalled=True)
        c = _mk_cycle(user_a, client_account_a, stalled=False)

        # dc_cycle_state and OTHER_KEY interleaved; the grouped path must scatter
        # the cycle results back to indices 0, 2, 4 (not 0, 1, 2).
        specs = [
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(a.id)}},  # 0
            {"key": OTHER_KEY, "scope": "mine", "period": "all"},                            # 1
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(b.id)}},  # 2
            {"key": OTHER_KEY, "scope": "mine", "period": "all"},                            # 3
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(c.id)}},  # 4
        ]
        results = _batch(authed_api_a, specs)

        assert len(results) == 5
        assert results[0]["key"] == "dc_cycle_state" and results[0]["meta"]["cycle_id"] == str(a.id)
        assert results[1]["key"] == OTHER_KEY
        assert results[2]["key"] == "dc_cycle_state" and results[2]["meta"]["cycle_id"] == str(b.id)
        assert results[3]["key"] == OTHER_KEY
        assert results[4]["key"] == "dc_cycle_state" and results[4]["meta"]["cycle_id"] == str(c.id)
        # And each cycle's grouped value matches its per-spec single result.
        assert results[0] == _single(authed_api_a, a.id)
        assert results[2] == _single(authed_api_a, b.id)
        assert results[4] == _single(authed_api_a, c.id)


@pytest.mark.django_db
class TestGroupedBatchStrictParity:

    def test_missing_cycle_id_is_per_item_400(self, authed_api_a, user_a, client_account_a):
        good = _mk_cycle(user_a, client_account_a, stalled=False)

        # The single endpoint's behaviour for a missing cycle_id: a 400.
        bad_single = authed_api_a.get("/bi/kpi/dc_cycle_state/?scope=mine")
        assert bad_single.status_code == 400

        specs = [
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(good.id)}},  # 0 ok
            {"key": "dc_cycle_state", "scope": "mine", "params": {}},                          # 1 no cycle_id
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(good.id)}},  # 2 ok
        ]
        results = _batch(authed_api_a, specs)

        assert len(results) == 3
        # Neighbours OK (200 shape: a 'value', no 'status' error field).
        assert results[0]["meta"]["cycle_id"] == str(good.id)
        assert "status" not in results[0]
        assert results[2]["meta"]["cycle_id"] == str(good.id)
        assert "status" not in results[2]
        # The faulty item is a per-item 400 at ITS index — strict parity.
        assert results[1]["status"] == 400
        assert results[1]["key"] == "dc_cycle_state"
        assert "cycle_id" in results[1]["error"]


@pytest.mark.django_db
class TestGroupedBatchNonRegression:

    def test_other_kpi_value_unchanged_in_mixed_batch(self, authed_api_a, user_a, client_account_a):
        # Some cycles exist so OTHER_KEY (cycles-by-outcome) has data to count.
        cyc = _mk_cycle(user_a, client_account_a, stalled=False)

        alone = authed_api_a.get(f"/bi/kpi/{OTHER_KEY}/?scope=mine&period=all")
        assert alone.status_code == 200
        alone_data = alone.data["data"]

        results = _batch(authed_api_a, [
            {"key": "dc_cycle_state", "scope": "mine", "params": {"cycle_id": str(cyc.id)}},
            {"key": OTHER_KEY, "scope": "mine", "period": "all"},
        ])
        # The non-grouped KPI returns the exact same value/meta as run alone.
        assert results[1] == alone_data
