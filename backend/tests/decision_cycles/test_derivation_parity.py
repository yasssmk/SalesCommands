"""
Parity between the SQL step-status annotation and the Python oracle.

annotate_step_derived_status (services/derivation_sql.py) translates
StepStatusDerivationService._compute_status into ORM annotations. This suite is
the guardrail that forbids the two from diverging: for a dataset covering EACH
named branch of _compute_status, the annotation and the Python service must
return the SAME status.

Branches covered (named, not sampled):
  1. no activity                                   → NOT_STARTED
  2. planned only                                  → IN_PROGRESS
  3. completed + planned (same step)               → IN_PROGRESS
  4. completed, no planned, planned elsewhere      → VALIDATED   (branch 1a)
  5. completed, no planned, last completed step    → STALLED     (branch 1b)
  6. completed, no planned, NOT last completed     → VALIDATED   (branch 1c)
  7. step.expected_end in the past                 → OVERDUE     (branch 2)
  8. planned activity past scheduled_date          → OVERDUE     (branch 2)
  9. planned activity past due_date                → OVERDUE     (branch 2)

Plus an anti-fan-out test: N cycles x M steps x P activities resolved in a
SINGLE list query, every status correct together and one row per step (mirror
of tests/campaigns/test_campaign_targets_progress.py).

The Python oracle is derive_bulk() — the exact path (step.activities, grouped
by cycle) the annotation is built to replace.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.decision_cycles.constants import (
    DecisionStepStatus,
    PIPELINE_STEPS_CONFIG,
)
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.decision_cycles.services import annotate_step_derived_status
from app_modules.decision_cycles.services.step_status_derivation_service import (
    StepStatusDerivationService,
)


TODAY = timezone.now().date()


# =============================================================================
# HELPERS
# =============================================================================

def _sql_statuses(cycle):
    """SQL-annotated status per step id, from a single annotated queryset."""
    qs = annotate_step_derived_status(DecisionStep.objects.filter(cycle=cycle))
    return {s.id: s._derived_status for s in qs}


def _py_statuses(cycle):
    """Python-derived status per step id, via the bulk oracle."""
    steps = list(
        DecisionStep.objects.filter(cycle=cycle).prefetch_related('activities')
    )
    derived = StepStatusDerivationService().derive_bulk(steps)
    return {sid: r['status'] for sid, r in derived.items()}


def _assert_parity(cycle):
    """The annotation and the Python oracle must agree on every step."""
    sql = _sql_statuses(cycle)
    py = _py_statuses(cycle)
    assert sql == py, f"SQL {sql} != Python {py}"
    return sql


def _make_cycle_with_steps(account, user_a, name):
    """Create a DecisionCycle + its 5 pipeline steps (mirror _create_pipeline_steps)."""
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
# 1 — no activity → NOT_STARTED
# =============================================================================

@pytest.mark.django_db
def test_branch_no_activity_not_started(cycle, five_steps):
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.NOT_STARTED


# =============================================================================
# 2 — planned only → IN_PROGRESS
# =============================================================================

@pytest.mark.django_db
def test_branch_planned_only_in_progress(cycle, five_steps, planned_activity_on_step):
    planned_activity_on_step(five_steps[0])
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.IN_PROGRESS


# =============================================================================
# 3 — completed + planned on the SAME step → IN_PROGRESS (not DONE)
# =============================================================================

@pytest.mark.django_db
def test_branch_completed_and_planned_in_progress(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    completed_activity_on_step(five_steps[0])
    planned_activity_on_step(five_steps[0])  # future planned → not overdue
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.IN_PROGRESS


# =============================================================================
# 4 — completed, no planned here, PLANNED elsewhere in cycle → VALIDATED (1a)
# =============================================================================

@pytest.mark.django_db
def test_branch_done_planned_elsewhere_validated(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    completed_activity_on_step(five_steps[0])
    planned_activity_on_step(five_steps[1])  # keeps the cycle moving
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.VALIDATED


# =============================================================================
# 5 — completed, no planned in cycle, LAST completed step → STALLED (1b)
# =============================================================================

@pytest.mark.django_db
def test_branch_done_last_completed_stalled(
    cycle, five_steps, completed_activity_on_step
):
    # Only the highest-order step has a completed activity, nothing planned.
    completed_activity_on_step(five_steps[4])
    sql = _assert_parity(cycle)
    assert sql[five_steps[4].id] == DecisionStepStatus.STALLED


# =============================================================================
# 6 — completed, no planned in cycle, NOT last completed → VALIDATED (1c)
# =============================================================================

@pytest.mark.django_db
def test_branch_done_not_last_completed_validated(
    cycle, five_steps, completed_activity_on_step
):
    # step[0] and step[2] both completed, no planned anywhere.
    # step[2] is the last completed (STALLED); step[0] is not last → VALIDATED.
    completed_activity_on_step(five_steps[0])
    completed_activity_on_step(five_steps[2])
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.VALIDATED
    assert sql[five_steps[2].id] == DecisionStepStatus.STALLED


# =============================================================================
# 7 — step.expected_end in the past → OVERDUE (branch 2, step deadline)
# =============================================================================

@pytest.mark.django_db
def test_branch_step_deadline_passed_overdue(
    cycle, five_steps, planned_activity_on_step
):
    step = five_steps[0]
    planned_activity_on_step(step)  # future planned → not overdue by itself
    step.expected_end = TODAY - timedelta(days=1)
    step.save(update_fields=['expected_end'])
    sql = _assert_parity(cycle)
    assert sql[step.id] == DecisionStepStatus.OVERDUE


# =============================================================================
# 8 — planned activity past scheduled_date → OVERDUE (branch 2, activity)
# =============================================================================

@pytest.mark.django_db
def test_branch_activity_past_scheduled_overdue(
    cycle, five_steps, planned_activity_on_step
):
    planned_activity_on_step(five_steps[0], scheduled_date=TODAY - timedelta(days=2))
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.OVERDUE


# =============================================================================
# 9 — planned activity past due_date → OVERDUE (branch 2, activity)
# =============================================================================

@pytest.mark.django_db
def test_branch_activity_past_due_overdue(
    cycle, five_steps, planned_activity_on_step
):
    # scheduled in the future so ONLY due_date makes it overdue.
    planned_activity_on_step(
        five_steps[0],
        scheduled_date=TODAY + timedelta(days=5),
        due_date=TODAY - timedelta(days=1),
    )
    sql = _assert_parity(cycle)
    assert sql[five_steps[0].id] == DecisionStepStatus.OVERDUE


# =============================================================================
# ANTI-FAN-OUT — N cycles x M steps x P activities in ONE list query.
# =============================================================================

@pytest.mark.django_db
def test_anti_fanout_single_query_all_statuses_together(
    account, user_a, planned_activity_on_step, completed_activity_on_step
):
    """
    THE anti-fan-out test: 2 cycles x 5 steps = 10 steps. One step carries 5
    activities (fan-out bait). A single annotated list query must (a) return
    exactly 10 rows — never 10 x P — and (b) give every step the same status as
    the Python oracle, all at once.

    Exists() and a scalar Subquery cannot multiply rows: a deep Count over
    steps x activities would. This asserts the difference.
    """
    cycle_a, steps_a = _make_cycle_with_steps(account, user_a, 'Fanout A')
    cycle_b, steps_b = _make_cycle_with_steps(account, user_a, 'Fanout B')

    # Cycle A — a moving cycle (planned work exists), one step overloaded.
    completed_activity_on_step(steps_a[0])          # 1 completed on the bait step
    for _ in range(3):                              # 3 more completed on the SAME step
        completed_activity_on_step(steps_a[0])
    planned_activity_on_step(steps_a[0])            # + planned here → not done → IN_PROGRESS
    planned_activity_on_step(steps_a[1])            # planned → IN_PROGRESS
    planned_activity_on_step(                       # planned past scheduled → OVERDUE
        steps_a[2], scheduled_date=TODAY - timedelta(days=3)
    )
    completed_activity_on_step(steps_a[3])          # done, planned exists in cycle → VALIDATED
    # steps_a[4] → NOT_STARTED

    # Cycle B — NO planned activity anywhere → its last completed step STALLS.
    completed_activity_on_step(steps_b[4])          # last completed, no planned → STALLED
    # steps_b[0..3] → NOT_STARTED

    ids = [s.id for s in steps_a + steps_b]

    # ONE query over BOTH cycles' steps.
    annotated = list(
        annotate_step_derived_status(DecisionStep.objects.filter(id__in=ids))
    )
    assert len(annotated) == 10, "fan-out: expected exactly one row per step"

    sql = {s.id: s._derived_status for s in annotated}
    py = {}
    py.update(_py_statuses(cycle_a))
    py.update(_py_statuses(cycle_b))
    assert sql == py, f"SQL {sql} != Python {py}"

    # Concrete expectations, so the parity assert is not vacuous — five distinct
    # statuses resolved in the single query above.
    assert sql[steps_a[0].id] == DecisionStepStatus.IN_PROGRESS  # overloaded bait step
    assert sql[steps_a[2].id] == DecisionStepStatus.OVERDUE
    assert sql[steps_a[3].id] == DecisionStepStatus.VALIDATED
    assert sql[steps_a[4].id] == DecisionStepStatus.NOT_STARTED
    assert sql[steps_b[4].id] == DecisionStepStatus.STALLED
