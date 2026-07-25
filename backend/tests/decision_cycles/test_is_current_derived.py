"""
DecisionStep.is_current must track the DERIVED current step.

The current step is the first step (by order) whose DERIVED status is not
VALIDATED — the single definition shared by annotate_cycle_state
(services/derivation_sql.py) and CycleAggregationService._compute_progress.

The old is_current read the stored `DecisionStep.status` column, which is never
updated (always NOT_STARTED), so it flagged only the first step as current
regardless of real progress — misleading the two AI pipelines that call
step.is_current (deal_health_evidence_builder, prep_call/input_pack_assembler).

These tests pin the correct, derived behaviour across several configurations.
"""

import pytest

from app_modules.decision_cycles.constants import DecisionStepStatus
from app_modules.decision_cycles.services import annotate_cycle_state
from app_modules.decision_cycles.models import DecisionCycle


def _current_step_order_from_annotation(cycle):
    """The 1b source of truth for the cycle's current step order."""
    c = annotate_cycle_state(DecisionCycle.objects.filter(id=cycle.id)).get()
    return c._current_step_order


# =========================================================================
# THE REPRO — current step is NOT the first step
# =========================================================================

@pytest.mark.django_db
def test_current_step_is_not_the_first_step(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    """
    step0 completed + a planned activity later in the cycle → step0 is derived
    VALIDATED and step1 is IN_PROGRESS, so the CURRENT step is step1, not step0.

    Old is_current (stored status) wrongly flags step0 (the first step) and
    misses step1. This is the defect.
    """
    completed_activity_on_step(five_steps[0])   # step0 done
    planned_activity_on_step(five_steps[1])      # planned elsewhere → step0 VALIDATED

    # Sanity: the 1b annotation agrees the current step is step1 (order 2).
    assert _current_step_order_from_annotation(cycle) == five_steps[1].order

    assert five_steps[0].is_current is False   # validated → not current
    assert five_steps[1].is_current is True    # first non-validated → current
    assert five_steps[2].is_current is False


# =========================================================================
# Fresh cycle — current step is the first step
# =========================================================================

@pytest.mark.django_db
def test_fresh_cycle_first_step_is_current(cycle, five_steps):
    """No activities → every step NOT_STARTED → the first step is current."""
    assert _current_step_order_from_annotation(cycle) == five_steps[0].order
    assert five_steps[0].is_current is True
    assert all(not s.is_current for s in five_steps[1:])


# =========================================================================
# Early steps validated — current step is the first non-terminal one
# =========================================================================

@pytest.mark.django_db
def test_early_steps_validated_current_is_first_non_validated(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    """step0 and step1 completed, a planned activity keeps the cycle moving →
    step0, step1 VALIDATED, step2 is the current step."""
    completed_activity_on_step(five_steps[0])
    completed_activity_on_step(five_steps[1])
    planned_activity_on_step(five_steps[2])   # step2 IN_PROGRESS

    assert _current_step_order_from_annotation(cycle) == five_steps[2].order
    assert five_steps[0].is_current is False
    assert five_steps[1].is_current is False
    assert five_steps[2].is_current is True
    assert five_steps[3].is_current is False


# =========================================================================
# Every step done — current is the STALLED tail (first non-VALIDATED)
# =========================================================================

@pytest.mark.django_db
def test_all_done_current_is_the_stalled_tail(
    cycle, five_steps, completed_activity_on_step
):
    """
    Every step completed, no planned anywhere → steps 0-3 VALIDATED and the last
    step STALLED. "All VALIDATED" is unreachable through derivation (a moving
    cycle needs a planned, non-validated step), so the current step is the
    STALLED tail — the first non-VALIDATED step by order.
    """
    for s in five_steps:
        completed_activity_on_step(s)

    assert _current_step_order_from_annotation(cycle) == five_steps[4].order
    assert all(not s.is_current for s in five_steps[:4])
    assert five_steps[4].is_current is True


# =========================================================================
# A validated step is never current (the terminal-status guard, derived)
# =========================================================================

@pytest.mark.django_db
def test_validated_step_is_not_current(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step
):
    completed_activity_on_step(five_steps[0])
    planned_activity_on_step(five_steps[1])   # step0 → VALIDATED

    # cross-check the derived status really is VALIDATED
    from app_modules.decision_cycles.services import StepStatusDerivationService
    steps = list(cycle.steps.prefetch_related('activities'))
    derived = StepStatusDerivationService().derive_bulk(steps)
    by_order = {s.order: derived[s.id]['status'] for s in steps}
    assert by_order[five_steps[0].order] == DecisionStepStatus.VALIDATED

    assert five_steps[0].is_current is False
