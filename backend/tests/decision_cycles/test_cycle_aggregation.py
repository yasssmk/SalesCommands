# backend/tests/decision_cycles/test_cycle_aggregation.py
"""
Tests for CycleAggregationService._derive_status cycle-level derivation.

Covers:
  - Explicit outcome override: WON, LOST, NOT_QUALIFIED, ON_HOLD
  - No steps → NOT_STARTED
  - All steps NOT_STARTED → NOT_STARTED
  - A step OVERDUE → cycle OVERDUE
  - A step STALLED (no PLANNED in cycle) → cycle STALLED
  - A step IN_PROGRESS or VALIDATED → cycle IN_PROGRESS

Note on branch reachability:
  STALLED and IN_PROGRESS step statuses are mutually exclusive in the
  same cycle (IN_PROGRESS requires a PLANNED activity; STALLED requires
  zero PLANNED in the entire cycle).  A cycle with STALLED + VALIDATED
  steps IS reachable (two completed steps, no PLANNED, the higher-order
  one is STALLED, the lower-order one is VALIDATED via branch 2c of
  _compute_status).  A cycle with STALLED + IN_PROGRESS steps is NOT
  reachable — that scenario is not tested.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.services.cycle_aggregation_service import (
    CycleAggregationService,
)


@pytest.fixture
def svc():
    return CycleAggregationService()


# =========================================================================
# EXPLICIT OUTCOME OVERRIDES
# =========================================================================

class TestExplicitOutcomeOverride:

    @pytest.mark.django_db
    def test_outcome_won(self, svc, cycle, five_steps, user_a):
        """cycle.outcome = WON overrides step-derived statuses."""
        cycle.outcome = CycleOutcome.WON
        cycle.save(user=user_a, update_fields=['outcome'])

        assert svc.get_cycle_status(cycle) == 'WON'

    @pytest.mark.django_db
    def test_outcome_lost(self, svc, cycle, five_steps, user_a):
        """cycle.outcome = LOST overrides step-derived statuses."""
        cycle.outcome = CycleOutcome.LOST
        cycle.save(user=user_a, update_fields=['outcome'])

        assert svc.get_cycle_status(cycle) == 'LOST'

    @pytest.mark.django_db
    def test_outcome_not_qualified(self, svc, cycle, five_steps, user_a):
        """cycle.outcome = NOT_QUALIFIED maps to LOST."""
        cycle.outcome = CycleOutcome.NOT_QUALIFIED
        cycle.save(user=user_a, update_fields=['outcome'])

        assert svc.get_cycle_status(cycle) == 'LOST'

    @pytest.mark.django_db
    def test_outcome_on_hold(self, svc, cycle, five_steps, user_a):
        """cycle.outcome = ON_HOLD overrides step-derived statuses."""
        cycle.outcome = CycleOutcome.ON_HOLD
        cycle.save(user=user_a, update_fields=['outcome'])

        assert svc.get_cycle_status(cycle) == 'ON_HOLD'


# =========================================================================
# NO STEPS → NOT_STARTED
# =========================================================================

class TestNoSteps:

    @pytest.mark.django_db
    def test_cycle_without_steps(self, svc, cycle):
        """A cycle with zero steps derives to NOT_STARTED."""
        assert svc.get_cycle_status(cycle) == 'NOT_STARTED'


# =========================================================================
# ALL STEPS NOT_STARTED → NOT_STARTED
# =========================================================================

class TestAllNotStarted:

    @pytest.mark.django_db
    def test_all_steps_not_started(self, svc, cycle, five_steps):
        """All 5 steps with no activities → all NOT_STARTED → cycle NOT_STARTED."""
        assert svc.get_cycle_status(cycle) == 'NOT_STARTED'


# =========================================================================
# ANY STEP OVERDUE → CYCLE OVERDUE
# =========================================================================

class TestCycleOverdue:

    @pytest.mark.django_db
    def test_step_overdue_makes_cycle_overdue(
        self, svc, cycle, five_steps, planned_activity_on_step, user_a,
    ):
        """A step with expected_end in the past makes the cycle OVERDUE."""
        step = five_steps[0]
        step.expected_end = timezone.now().date() - timedelta(days=1)
        step.save(user=user_a, update_fields=['expected_end'])
        planned_activity_on_step(step)

        assert svc.get_cycle_status(cycle) == 'OVERDUE'


# =========================================================================
# STALLED STEP → CYCLE STALLED
# =========================================================================

class TestCycleStalled:

    @pytest.mark.django_db
    def test_stalled_step_makes_cycle_stalled(
        self, svc, cycle, five_steps, completed_activity_on_step,
    ):
        """
        The last completed step with no PLANNED in the cycle derives to
        STALLED (step level), which propagates to cycle STALLED.

        Setup: step[0] completed, step[1] completed (highest order with
        completed → STALLED), no PLANNED anywhere.
        """
        completed_activity_on_step(five_steps[0])
        completed_activity_on_step(five_steps[1])

        assert svc.get_cycle_status(cycle) == 'STALLED'


# =========================================================================
# IN_PROGRESS / VALIDATED STEP → CYCLE IN_PROGRESS
# =========================================================================

class TestCycleInProgress:

    @pytest.mark.django_db
    def test_planned_activity_makes_cycle_in_progress(
        self, svc, cycle, five_steps, planned_activity_on_step,
    ):
        """A step with a PLANNED activity → IN_PROGRESS → cycle IN_PROGRESS."""
        planned_activity_on_step(five_steps[0])

        assert svc.get_cycle_status(cycle) == 'IN_PROGRESS'

    @pytest.mark.django_db
    def test_validated_step_makes_cycle_in_progress(
        self, svc, cycle, five_steps,
        completed_activity_on_step, planned_activity_on_step,
    ):
        """
        A VALIDATED step (completed + PLANNED elsewhere) propagates to
        cycle IN_PROGRESS.
        """
        completed_activity_on_step(five_steps[0])
        planned_activity_on_step(five_steps[1])

        assert svc.get_cycle_status(cycle) == 'IN_PROGRESS'
