# backend/tests/decision_cycles/test_step_terminal_status.py
"""
Regression tests for DecisionStepStatus.REJECTED removal.

REJECTED was removed from the DecisionStepStatus enum (moved to
CycleOutcome) but three code sites still referenced it, causing
AttributeError at runtime.  These tests exercise the two user-facing
paths that crashed:

  1. DecisionStep.is_current property on a VALIDATED step.
  2. PATCH /decision_cycles/steps/<pk>/status/ with status=VALIDATED.

Both must succeed without exception after the fix.
"""

import pytest
from django.urls import reverse

from app_modules.decision_cycles.constants import DecisionStepStatus


# =========================================================================
# is_current property — VALIDATED step must return False, no crash
# =========================================================================

class TestIsCurrentAfterRejectRemoval:

    @pytest.mark.django_db
    def test_validated_step_is_not_current(self, five_steps, user_a):
        """A VALIDATED step must return is_current=False (no AttributeError)."""
        step = five_steps[0]
        step.status = DecisionStepStatus.VALIDATED
        step.save(user=user_a, update_fields=['status'])

        assert step.is_current is False

    @pytest.mark.django_db
    def test_not_started_first_step_is_current(self, five_steps):
        """Sanity: first NOT_STARTED step (no previous) is current."""
        assert five_steps[0].is_current is True

    @pytest.mark.django_db
    def test_step_after_validated_previous_is_current(self, five_steps, user_a):
        """Step whose previous_step is VALIDATED should be current."""
        first = five_steps[0]
        first.status = DecisionStepStatus.VALIDATED
        first.save(user=user_a, update_fields=['status'])

        assert five_steps[1].is_current is True


# =========================================================================
# update_status endpoint — PATCH to VALIDATED must not crash
# =========================================================================

class TestUpdateStatusAfterRejectRemoval:

    @pytest.mark.django_db
    def test_patch_status_validated_succeeds(self, authed_api_a, five_steps):
        """PATCH status=VALIDATED returns 200 and sets completed_at."""
        step = five_steps[0]
        url = reverse('decision_cycles:step-status', kwargs={'pk': step.id})

        response = authed_api_a.patch(url, {'status': 'VALIDATED'}, format='json')

        assert response.status_code == 200
        step.refresh_from_db()
        assert step.status == DecisionStepStatus.VALIDATED
        assert step.completed_at is not None

    @pytest.mark.django_db
    def test_revert_from_validated_clears_completed_at(
        self, authed_api_a, five_steps, user_a,
    ):
        """Reverting from VALIDATED clears completed_at (no AttributeError)."""
        step = five_steps[0]
        step.status = DecisionStepStatus.VALIDATED
        step.save(user=user_a, update_fields=['status'])

        url = reverse('decision_cycles:step-status', kwargs={'pk': step.id})
        response = authed_api_a.patch(
            url, {'status': 'IN_PROGRESS'}, format='json',
        )

        assert response.status_code == 200
        assert response.data['data']['completed_at'] is None
