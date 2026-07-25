# backend/tests/decision_cycles/test_step_terminal_status.py
"""
Regression tests for DecisionStepStatus.REJECTED removal.

DecisionStepStatus.REJECTED was removed from the enum (moved to CycleOutcome).
This suite covers the surviving user-facing surfaces around step status:

  1. DecisionStep.is_current — now derived (a validated step is not current,
     the step after a validated one is current); no crash.
  2. The PATCH /decision_cycles/steps/<pk>/status/ endpoint, which only ever
     wrote the now-removed stored `status` column, no longer exists.
"""

import pytest
from django.urls import reverse, NoReverseMatch

from app_modules.decision_cycles.constants import DecisionStepStatus


# =========================================================================
# is_current property — VALIDATED step must return False, no crash
# =========================================================================

class TestIsCurrentAfterRejectRemoval:

    @pytest.mark.django_db
    def test_validated_step_is_not_current(
        self, five_steps, planned_activity_on_step, completed_activity_on_step
    ):
        """A DERIVED-validated step returns is_current=False (no crash).

        is_current now reads the DERIVED status, not the stored column, so the
        step is made validated via activities (completed here + a planned
        activity keeping the cycle moving), not by writing `status`.
        """
        completed_activity_on_step(five_steps[0])
        planned_activity_on_step(five_steps[1])   # step0 → VALIDATED

        assert five_steps[0].is_current is False

    @pytest.mark.django_db
    def test_not_started_first_step_is_current(self, five_steps):
        """Sanity: first NOT_STARTED step (no previous) is current."""
        assert five_steps[0].is_current is True

    @pytest.mark.django_db
    def test_step_after_validated_previous_is_current(
        self, five_steps, planned_activity_on_step, completed_activity_on_step
    ):
        """The step after a DERIVED-validated one is the current step."""
        completed_activity_on_step(five_steps[0])   # step0 → VALIDATED
        planned_activity_on_step(five_steps[1])      # step1 → IN_PROGRESS (current)

        assert five_steps[1].is_current is True


# =========================================================================
# update_status endpoint — removed with the stored status column
# =========================================================================

class TestUpdateStatusEndpointRemoved:

    def test_step_status_route_no_longer_exists(self):
        """The PATCH /decision_cycles/steps/<pk>/status/ endpoint is gone: it
        only ever wrote the stored `status` column, which no longer exists.
        Its named route must not resolve."""
        with pytest.raises(NoReverseMatch):
            reverse(
                'decision_cycles:step-status',
                kwargs={'pk': '00000000-0000-0000-0000-000000000000'},
            )
