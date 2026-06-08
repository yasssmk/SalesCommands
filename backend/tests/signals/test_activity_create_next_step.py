# backend/tests/signals/test_activity_create_next_step.py
"""
Tests for Activity creation with next_step_signal_id.

Validates that:
  1. Creating an Activity with a PENDING NextStepSignal auto-validates the signal.
  2. Creating with an already-VALIDATED signal returns 400.
  3. Creating with a cross-tenant signal returns 400.
  4. Creating without next_step_signal_id succeeds normally (retro-compat).
"""

import pytest
from datetime import date


# =============================================================================
# FIXTURES — NextStepSignal instances scoped to this test module
# =============================================================================

@pytest.fixture
def next_step_signal_pending(db, account, activity, user_a):
    """PENDING NextStepSignal on tenant A."""
    from app_modules.signals.models import NextStepSignal
    from app_modules.signals.constants import SignalSource

    signal = NextStepSignal(
        account=account,
        source_activity=activity,
        suggested_title='Follow up on pricing',
        suggested_activity_type='CALL',
        suggested_due_date=date(2026, 6, 15),
        source_quote='We should discuss pricing next week',
        source=SignalSource.LLM_EXTRACTED,
    )
    signal.save(user=user_a, client_id=account.client_id)
    return signal


@pytest.fixture
def next_step_signal_validated(db, account, activity, user_a):
    """VALIDATED NextStepSignal on tenant A."""
    from app_modules.signals.models import NextStepSignal
    from app_modules.signals.constants import SignalSource

    signal = NextStepSignal(
        account=account,
        source_activity=activity,
        suggested_title='Send proposal',
        suggested_activity_type='EMAIL',
        source=SignalSource.MANUAL,
    )
    signal.save(user=user_a, client_id=account.client_id)
    return signal


@pytest.fixture
def other_tenant_next_step(db, other_tenant_account, other_tenant_activity, user_b):
    """PENDING NextStepSignal on tenant B."""
    from app_modules.signals.models import NextStepSignal
    from app_modules.signals.constants import SignalSource

    signal = NextStepSignal(
        account=other_tenant_account,
        source_activity=other_tenant_activity,
        suggested_title='Cross-tenant signal',
        suggested_activity_type='MEETING',
        source=SignalSource.LLM_EXTRACTED,
    )
    signal.save(user=user_b, client_id=other_tenant_account.client_id)
    return signal


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db
class TestActivityCreateWithNextStepSignal:
    """POST /module-activities/ with next_step_signal_id."""

    URL = '/module-activities/'

    def _base_payload(self, account, contact):
        return {
            'title': 'Follow up call',
            'activity_type': 'CALL',
            'account_id': str(account.id),
            'contact_ids': [str(contact.id)],
            'scheduled_date': '2026-06-15',
        }

    def test_create_with_pending_signal_validates_signal(
        self, authed_api_a, account, contact, next_step_signal_pending
    ):
        """Activity created + signal auto-VALIDATED in same transaction."""
        from app_modules.signals.constants import SignalStatus

        payload = self._base_payload(account, contact)
        payload['next_step_signal_id'] = str(next_step_signal_pending.id)

        response = authed_api_a.post(self.URL, payload, format='json')

        assert response.status_code == 201, response.data
        activity_data = response.data['data']
        assert activity_data['next_step_signal'] == str(next_step_signal_pending.id)

        next_step_signal_pending.refresh_from_db()
        assert next_step_signal_pending.status == SignalStatus.VALIDATED

    def test_create_with_validated_signal_returns_400(
        self, authed_api_a, account, contact, next_step_signal_validated
    ):
        """Signal already VALIDATED → 400, no Activity created."""
        from app_modules.activities.models import Activity

        count_before = Activity.objects.filter(client_id=account.client_id).count()

        payload = self._base_payload(account, contact)
        payload['next_step_signal_id'] = str(next_step_signal_validated.id)

        response = authed_api_a.post(self.URL, payload, format='json')

        assert response.status_code == 400
        assert Activity.objects.filter(client_id=account.client_id).count() == count_before

    def test_create_with_cross_tenant_signal_returns_400(
        self, authed_api_a, account, contact, other_tenant_next_step
    ):
        """Signal from another tenant → 400."""
        payload = self._base_payload(account, contact)
        payload['next_step_signal_id'] = str(other_tenant_next_step.id)

        response = authed_api_a.post(self.URL, payload, format='json')

        assert response.status_code == 400

    def test_create_without_signal_succeeds(
        self, authed_api_a, account, contact
    ):
        """Standard creation without next_step_signal_id still works."""
        payload = self._base_payload(account, contact)

        response = authed_api_a.post(self.URL, payload, format='json')

        assert response.status_code == 201
        assert response.data['data'].get('next_step_signal') is None
