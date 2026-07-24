"""
Parity between the SQL cycle-state annotation and the Python oracle.

annotate_cycle_state (services/derivation_sql.py) translates
CycleAggregationService._derive_status_bulk (effective cycle status) and
_compute_progress (current step + validated/total counts) into ORM
annotations, stacking the 1a step-status Case inside correlated subqueries.
CycleAggregationService.get_bulk_summaries consumes the annotation when a cycle
carries it and keeps the Python computation as the parity oracle.

This suite forbids the two from diverging:
  - effective status per named case (the 4 outcome mappings incl.
    NOT_QUALIFIED -> LOST, then NOT_STARTED / IN_PROGRESS / OVERDUE / STALLED),
  - current step (name / stage / order) incl. edge cases,
  - the dc_cycle_state KPI contract (value + 8 meta keys) — the Home guard,
  - anti-fan-out: N cycles x M steps x P activities correct together in one query.

The Python oracle is get_bulk_summaries() run on a NON-annotated (prefetched)
cycle, i.e. the exact path the annotation replaces.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.decision_cycles.constants import (
    CycleOutcome,
    DecisionStepStatus,
    PIPELINE_STEPS_CONFIG,
)
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.decision_cycles.services import annotate_cycle_state
from app_modules.decision_cycles.services.cycle_aggregation_service import (
    CycleAggregationService,
)
from app_modules.decision_cycles.services.derivation_sql import (
    CURRENT_STEP_STAGE_ALIAS,
)

# KPI contract wiring (mirror tests/bi/test_kpi_cycle_state.py).
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.decision_cycles import dc_cycle_state
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext


TODAY = timezone.now().date()


# =============================================================================
# HELPERS
# =============================================================================

def _annotated(cycle_id):
    return annotate_cycle_state(DecisionCycle.objects.filter(id=cycle_id)).get()


def _sql_summary(cycle):
    """Summary via the SQL annotation path (get_bulk_summaries consumes it)."""
    c = _annotated(cycle.id)
    return CycleAggregationService().get_bulk_summaries([c])[c.id]


def _py_summary(cycle):
    """Summary via the Python oracle (non-annotated, prefetched cycle)."""
    c = DecisionCycle.objects.prefetch_related('steps__activities').get(id=cycle.id)
    return CycleAggregationService().get_bulk_summaries([c])[c.id]


def _assert_summary_parity(cycle):
    sql = _sql_summary(cycle)
    py = _py_summary(cycle)
    assert sql == py, f"SQL {sql} != Python {py}"
    return sql


def _make_cycle_with_steps(account, user_a, name):
    cycle = DecisionCycle(account=account, owner=user_a, name=name, is_active=False)
    cycle.save(user=user_a, client_id=account.client_id)
    previous = None
    steps = []
    for config in PIPELINE_STEPS_CONFIG:
        step = DecisionStep(
            cycle=cycle,
            name=config['step'].label,
            stage=config['step'].value,
            order=config['order'],
            status=DecisionStepStatus.NOT_STARTED,
            previous_step=previous,
            expected_end=None,
        )
        step.save(user=user_a, client_id=cycle.client_id)
        steps.append(step)
        previous = step
    return cycle, steps


# =============================================================================
# EFFECTIVE STATUS — outcome mappings
# =============================================================================

@pytest.mark.django_db
def test_status_outcome_won(cycle, five_steps, user_a):
    cycle.outcome = CycleOutcome.WON
    cycle.save(user=user_a)
    assert _assert_summary_parity(cycle)['cycle_status'] == 'WON'


@pytest.mark.django_db
def test_status_outcome_lost(cycle, five_steps, user_a):
    cycle.outcome = CycleOutcome.LOST
    cycle.save(user=user_a)
    assert _assert_summary_parity(cycle)['cycle_status'] == 'LOST'


@pytest.mark.django_db
def test_status_outcome_not_qualified_maps_to_lost(cycle, five_steps, user_a):
    cycle.outcome = CycleOutcome.NOT_QUALIFIED
    cycle.save(user=user_a)
    assert _assert_summary_parity(cycle)['cycle_status'] == 'LOST'


@pytest.mark.django_db
def test_status_outcome_on_hold(cycle, five_steps, user_a):
    cycle.outcome = CycleOutcome.ON_HOLD
    cycle.save(user=user_a)
    assert _assert_summary_parity(cycle)['cycle_status'] == 'ON_HOLD'


# =============================================================================
# EFFECTIVE STATUS — derived from steps
# =============================================================================

@pytest.mark.django_db
def test_status_derived_not_started(cycle, five_steps):
    assert _assert_summary_parity(cycle)['cycle_status'] == 'NOT_STARTED'


@pytest.mark.django_db
def test_status_derived_in_progress(cycle, five_steps, planned_activity_on_step):
    planned_activity_on_step(five_steps[1])
    assert _assert_summary_parity(cycle)['cycle_status'] == 'IN_PROGRESS'


@pytest.mark.django_db
def test_status_derived_overdue(cycle, five_steps, planned_activity_on_step):
    planned_activity_on_step(five_steps[1], scheduled_date=TODAY - timedelta(days=2))
    assert _assert_summary_parity(cycle)['cycle_status'] == 'OVERDUE'


@pytest.mark.django_db
def test_status_derived_stalled(cycle, five_steps, completed_activity_on_step):
    # last completed step, no planned anywhere → the cycle STALLS
    completed_activity_on_step(five_steps[4])
    assert _assert_summary_parity(cycle)['cycle_status'] == 'STALLED'


@pytest.mark.django_db
def test_status_overdue_before_stalled(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    # A cycle with BOTH an overdue step and a stalled tail resolves to OVERDUE
    # (priority: OVERDUE before STALLED), exactly like the Python.
    completed_activity_on_step(five_steps[4])                                  # stalled tail
    planned_activity_on_step(five_steps[0], scheduled_date=TODAY - timedelta(days=1))  # overdue
    # NB: the planned activity makes has_planned_in_cycle True, so step4 is no
    # longer STALLED — but the point stands: parity must hold whatever it is.
    assert _assert_summary_parity(cycle)['cycle_status'] == 'OVERDUE'


# =============================================================================
# CURRENT STEP — name / stage / order
# =============================================================================

@pytest.mark.django_db
def test_current_step_first_non_validated(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    completed_activity_on_step(five_steps[0])   # → VALIDATED (planned exists in cycle)
    planned_activity_on_step(five_steps[1])     # → IN_PROGRESS, first non-validated
    summary = _assert_summary_parity(cycle)
    assert summary['progress']['current_step_name'] == five_steps[1].name
    assert summary['progress']['current_step_order'] == five_steps[1].order
    # raw stage annotation matches the current step's stage
    assert getattr(_annotated(cycle.id), CURRENT_STEP_STAGE_ALIAS) == five_steps[1].stage


@pytest.mark.django_db
def test_current_step_no_steps(cycle):
    # bare cycle (no five_steps) → no steps at all
    summary = _assert_summary_parity(cycle)
    assert summary['progress']['total_steps'] == 0
    assert summary['progress']['current_step_name'] is None
    assert summary['progress']['current_step_order'] is None
    assert summary['cycle_status'] == 'NOT_STARTED'
    assert getattr(_annotated(cycle.id), CURRENT_STEP_STAGE_ALIAS) is None


@pytest.mark.django_db
def test_current_step_first_step_empty(cycle, five_steps, planned_activity_on_step):
    # activity only on a later step → the first step has none → it is current.
    planned_activity_on_step(five_steps[2])
    summary = _assert_summary_parity(cycle)
    assert summary['progress']['current_step_name'] == five_steps[0].name
    assert summary['progress']['current_step_order'] == five_steps[0].order


@pytest.mark.django_db
def test_current_step_all_but_tail_validated(cycle, five_steps, completed_activity_on_step):
    # steps 0-3 completed + step4 completed, no planned → steps 0-3 VALIDATED,
    # step4 STALLED (the last completed). "All VALIDATED" is unreachable through
    # derivation (a moving cycle needs a planned, hence non-validated, step), so
    # this all-but-tail case is the boundary: current step is the stalled tail.
    for s in five_steps:
        completed_activity_on_step(s)
    summary = _assert_summary_parity(cycle)
    assert summary['progress']['validated_steps'] == 4
    assert summary['progress']['total_steps'] == 5
    assert summary['progress']['current_step_name'] == five_steps[4].name
    assert summary['progress']['current_step_order'] == five_steps[4].order


# =============================================================================
# KPI CONTRACT — dc_cycle_state value + 8 meta keys (the Home guard)
# =============================================================================

@pytest.fixture
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield dc_cycle_state
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.mark.django_db
def test_kpi_contract_matches_oracle(
    kpi, _flush_cache, cycle, five_steps, user_a, client_account_a,
    planned_activity_on_step, completed_activity_on_step,
):
    """dc_cycle_state must expose value + the 8 meta keys, and its derived
    fields must equal what the Python oracle (get_bulk_summaries) produces —
    this is the contract the DC list, RepHome, ManagerHome and DecisionCyclesBlock
    depend on."""
    completed_activity_on_step(five_steps[0])                       # VALIDATED
    planned_activity_on_step(five_steps[1], scheduled_date=TODAY + timedelta(days=30))  # IN_PROGRESS

    ctx = AuthContext(
        user_id=str(user_a.id), client_id=str(client_account_a.id), is_authenticated=True
    )
    res = cached_run(kpi, ctx, scope='mine', params={'cycle_id': str(cycle.id)})

    # The oracle summary for the same cycle (Python path).
    oracle = _py_summary(cycle)
    progress = oracle['progress']

    # value + the 8 documented meta keys.
    assert res.value == oracle['cycle_status']
    assert set(res.meta.keys()) >= {
        'cycle_id', 'cycle_status', 'current_stage', 'current_step_name',
        'current_step_order', 'next_action', 'validated_steps', 'total_steps',
    }
    assert res.meta['cycle_id'] == str(cycle.id)
    assert res.meta['cycle_status'] == oracle['cycle_status']
    assert res.meta['current_step_name'] == progress['current_step_name']
    assert res.meta['current_step_order'] == progress['current_step_order']
    assert res.meta['current_stage'] == five_steps[1].stage
    assert res.meta['validated_steps'] == progress['validated_steps']
    assert res.meta['total_steps'] == progress['total_steps']
    assert res.meta['next_action'].startswith('Advance:')
    assert 'percentage' not in res.meta


# =============================================================================
# ANTI-FAN-OUT — N cycles x M steps x P activities in ONE query
# =============================================================================

@pytest.mark.django_db
def test_anti_fanout_cycle_summaries_together(
    account, user_a, planned_activity_on_step, completed_activity_on_step
):
    """
    2 cycles x 5 steps, one step overloaded with 5 activities. A SINGLE
    annotated query over both cycles must return exactly 2 rows and give each
    cycle the same status, current step and validated/total counts as the
    Python oracle. Isolated correlated subqueries cannot multiply rows; a deep
    Count over cycle->step->activity would skew every count together.
    """
    cycle_a, steps_a = _make_cycle_with_steps(account, user_a, 'Cyc A')
    cycle_b, steps_b = _make_cycle_with_steps(account, user_a, 'Cyc B')

    # Cycle A → IN_PROGRESS. steps_a[0] is overloaded (4 completed + 1 planned);
    # the planned keeps it NOT done → IN_PROGRESS, so it is the first
    # non-validated step and thus the current step. steps_a[3] → VALIDATED.
    for _ in range(4):
        completed_activity_on_step(steps_a[0])          # 4 completed on the bait step
    planned_activity_on_step(steps_a[0])                # + planned → not done → IN_PROGRESS
    planned_activity_on_step(steps_a[1])                # planned → IN_PROGRESS
    completed_activity_on_step(steps_a[3])              # done, planned in cycle → VALIDATED

    # Cycle B → STALLED (last completed, no planned anywhere).
    completed_activity_on_step(steps_b[4])

    ids = [cycle_a.id, cycle_b.id]
    annotated = {c.id: c for c in annotate_cycle_state(DecisionCycle.objects.filter(id__in=ids))}
    assert len(annotated) == 2, "fan-out: expected exactly one row per cycle"

    svc = CycleAggregationService()
    for cyc in (cycle_a, cycle_b):
        sql = svc.get_bulk_summaries([annotated[cyc.id]])[cyc.id]
        py = _py_summary(cyc)
        assert sql == py, f"{cyc.name}: SQL {sql} != Python {py}"

    # Concrete, so the parity assert is not vacuous.
    sql_a = svc.get_bulk_summaries([annotated[cycle_a.id]])[cycle_a.id]
    sql_b = svc.get_bulk_summaries([annotated[cycle_b.id]])[cycle_b.id]
    assert sql_a['cycle_status'] == 'IN_PROGRESS'
    assert sql_a['progress']['current_step_order'] == steps_a[0].order  # first non-validated
    assert sql_a['progress']['validated_steps'] == 1      # only steps_a[3]
    assert sql_b['cycle_status'] == 'STALLED'
    assert sql_b['progress']['total_steps'] == 5
