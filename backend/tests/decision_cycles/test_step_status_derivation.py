# backend/tests/decision_cycles/test_step_status_derivation.py
"""
Tests for StepStatusDerivationService._compute_status derivation logic.

Covers the 7 P0 scenarios from the test plan:
  1. No activities         → NOT_STARTED
  2. PLANNED activity      → IN_PROGRESS
  3. All COMPLETED + PLANNED elsewhere in cycle → VALIDATED (branch 2a)
  4. Last completed step, no PLANNED in cycle   → STALLED  (branch 2b)
  5. step.expected_end in the past              → OVERDUE  (branch 1)
  6. PLANNED activity with past scheduled_date  → OVERDUE  (branch 1 variant)
  7. derive_bulk() matches derive() on identical data (single/bulk coherence)

All tests call the PUBLIC service methods (derive / derive_bulk) and
assert the returned status string — the service never writes to the DB.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.decision_cycles.constants import DecisionStepStatus
from app_modules.decision_cycles.services.step_status_derivation_service import (
    StepStatusDerivationService,
)


@pytest.fixture
def svc():
    return StepStatusDerivationService()


# =========================================================================
# 1 — No activities → NOT_STARTED
# =========================================================================

class TestNotStarted:

    @pytest.mark.django_db
    def test_step_without_activities(self, svc, five_steps):
        """A step with zero activities derives to NOT_STARTED."""
        result = svc.derive(five_steps[0])
        assert result['status'] == DecisionStepStatus.NOT_STARTED


# =========================================================================
# 2 — PLANNED activity → IN_PROGRESS
# =========================================================================

class TestInProgress:

    @pytest.mark.django_db
    def test_step_with_planned_activity(self, svc, five_steps, planned_activity_on_step):
        """A step with a future PLANNED activity derives to IN_PROGRESS."""
        planned_activity_on_step(five_steps[0])
        result = svc.derive(five_steps[0])
        assert result['status'] == DecisionStepStatus.IN_PROGRESS


# =========================================================================
# 3 — All COMPLETED + PLANNED elsewhere → VALIDATED (branch 2a)
# =========================================================================

class TestValidatedWithPlannedElsewhere:

    @pytest.mark.django_db
    def test_completed_step_with_planned_on_other_step(
        self, svc, five_steps,
        completed_activity_on_step, planned_activity_on_step,
    ):
        """
        Step whose activities are all COMPLETED, while another step in the
        same cycle has a PLANNED activity, derives to VALIDATED.
        """
        completed_activity_on_step(five_steps[0])
        planned_activity_on_step(five_steps[1])

        result = svc.derive(five_steps[0])
        assert result['status'] == DecisionStepStatus.VALIDATED


# =========================================================================
# 4 — Last completed step, no PLANNED anywhere → STALLED (branch 2b)
# =========================================================================

class TestStalled:

    @pytest.mark.django_db
    def test_last_completed_step_no_planned_in_cycle(
        self, svc, five_steps, completed_activity_on_step,
    ):
        """
        The step with the highest order among those that have COMPLETED
        activities, when no PLANNED activity exists in the entire cycle,
        derives to STALLED.
        """
        completed_activity_on_step(five_steps[0])
        completed_activity_on_step(five_steps[1])

        result = svc.derive(five_steps[1])
        assert result['status'] == DecisionStepStatus.STALLED

    @pytest.mark.django_db
    def test_non_last_completed_step_no_planned_is_validated(
        self, svc, five_steps, completed_activity_on_step,
    ):
        """
        Branch 2c: a completed step that is NOT the last completed one
        (lower order) still derives to VALIDATED even without PLANNED
        activities in the cycle.
        """
        completed_activity_on_step(five_steps[0])
        completed_activity_on_step(five_steps[1])

        result = svc.derive(five_steps[0])
        assert result['status'] == DecisionStepStatus.VALIDATED


# =========================================================================
# 5 — step.expected_end in the past → OVERDUE (branch 1)
# =========================================================================

class TestOverdueStepDeadline:

    @pytest.mark.django_db
    def test_step_expected_end_in_past(
        self, svc, five_steps, planned_activity_on_step, user_a,
    ):
        """
        A step whose expected_end is before today derives to OVERDUE,
        regardless of activity dates.
        """
        step = five_steps[0]
        step.expected_end = timezone.now().date() - timedelta(days=1)
        step.save(user=user_a, update_fields=['expected_end'])

        planned_activity_on_step(step)

        result = svc.derive(step)
        assert result['status'] == DecisionStepStatus.OVERDUE


# =========================================================================
# 6 — PLANNED activity with past scheduled_date → OVERDUE (variant)
# =========================================================================

class TestOverdueActivityDate:

    @pytest.mark.django_db
    def test_planned_activity_with_past_scheduled_date(
        self, svc, five_steps, planned_activity_on_step,
    ):
        """
        A PLANNED activity whose scheduled_date is before today makes the
        step OVERDUE even when step.expected_end is not set.
        """
        planned_activity_on_step(
            five_steps[0],
            scheduled_date=timezone.now().date() - timedelta(days=2),
        )

        result = svc.derive(five_steps[0])
        assert result['status'] == DecisionStepStatus.OVERDUE


# =========================================================================
# 7 — derive_bulk() matches derive() (single/bulk coherence)
# =========================================================================

class TestBulkCoherence:

    @pytest.mark.django_db
    def test_derive_bulk_matches_derive(
        self, svc, five_steps, user_a,
        completed_activity_on_step, planned_activity_on_step,
    ):
        """
        derive_bulk() must return the same status as derive() for every
        step when given identical underlying data.

        Setup: step[0] COMPLETED-only (STALLED or VALIDATED depending on
        cycle context), step[1] has a PLANNED (IN_PROGRESS), steps[2-4]
        empty (NOT_STARTED).
        """
        completed_activity_on_step(five_steps[0])
        planned_activity_on_step(five_steps[1])

        single_results = {}
        for step in five_steps:
            single_results[step.id] = svc.derive(step)['status']

        from django.db.models import Prefetch
        from app_modules.activities.models import Activity
        from app_modules.decision_cycles.models import DecisionStep

        prefetched_steps = list(
            DecisionStep.objects.filter(
                cycle=five_steps[0].cycle,
            ).prefetch_related(
                Prefetch('activities', queryset=Activity.objects.all()),
            ).order_by('order')
        )

        bulk_results = svc.derive_bulk(prefetched_steps)

        for step in prefetched_steps:
            assert bulk_results[step.id]['status'] == single_results[step.id], (
                f"Mismatch on step order={step.order}: "
                f"bulk={bulk_results[step.id]['status']} vs single={single_results[step.id]}"
            )
