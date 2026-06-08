# backend/tests/signals/test_reopen_action.py
"""
API-level coverage for the reopen action across signal types.

Endpoints under test:
  POST /module-signals/blockers/{id}/reopen/
  POST /module-signals/pain/{id}/reopen/
  (other types inherit from the same base — blocker + pain cover the surface)

Cases:
  A. VALIDATED → reopen → PENDING, validated_at/by nullified
  B. REJECTED  → reopen → PENDING, validated_at/by nullified
  C. PENDING   → reopen → 400
  D. Cross-tenant isolation → 404
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import BlockerSignal, PainSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# URL HELPERS
# =============================================================================

def _url_blocker_reopen(pk):
    return reverse('module_signals:blocker-reopen', kwargs={'pk': pk})


def _url_pain_reopen(pk):
    return reverse('module_signals:pain-reopen', kwargs={'pk': pk})


# =============================================================================
# BLOCKER REOPEN
# =============================================================================

class TestReopenBlockerSignal:

    def test_reopen_validated_blocker_sets_pending(
        self, authed_api_a, account, activity, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='validated blocker', source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)
        assert b.status == SignalStatus.VALIDATED

        response = authed_api_a.post(_url_blocker_reopen(b.id), {}, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING
        assert data['validated_by'] is None
        assert data['validated_at'] is None

    def test_reopen_rejected_blocker_sets_pending(
        self, authed_api_a, account, activity, user_a,
    ):
        from app_modules.signals.services.signal_manager import SignalManager

        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='rejected blocker', source=SignalSource.LLM_EXTRACTED,
        )
        b.save(user=user_a, client_id=account.client_id)
        SignalManager.reject(b, user_a, reason='test reject')
        assert b.status == SignalStatus.REJECTED

        response = authed_api_a.post(_url_blocker_reopen(b.id), {}, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING
        assert data['validated_by'] is None
        assert data['validated_at'] is None

    def test_reopen_pending_blocker_returns_400(
        self, authed_api_a, account, activity, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='pending blocker', source=SignalSource.LLM_EXTRACTED,
        )
        b.save(user=user_a, client_id=account.client_id)
        assert b.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_blocker_reopen(b.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'pending' in response.content.decode().lower()

    def test_reopen_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='tenant-A blocker', source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        response = authed_api_b.post(_url_blocker_reopen(b.id), {}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# PAIN REOPEN (verifies inheritance works for qualification signals)
# =============================================================================

class TestReopenPainSignal:

    def test_reopen_validated_pain_sets_pending(
        self, authed_api_a, account, activity, user_a,
    ):
        from app_modules.signals.services.signal_manager import SignalManager

        p = PainSignal(
            account=account, source_activity=activity,
            summary='validated pain', source=SignalSource.LLM_EXTRACTED,
            what='OPS', dimension='TIME',
        )
        p.save(user=user_a, client_id=account.client_id)
        SignalManager.validate(p, user_a)
        assert p.status == SignalStatus.VALIDATED

        response = authed_api_a.post(_url_pain_reopen(p.id), {}, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING
        assert data['validated_by'] is None
        assert data['validated_at'] is None

    def test_reopen_pending_pain_returns_400(
        self, authed_api_a, account, activity, user_a,
    ):
        p = PainSignal(
            account=account, source_activity=activity,
            summary='pending pain', source=SignalSource.LLM_EXTRACTED,
            what='OPS', dimension='TIME',
        )
        p.save(user=user_a, client_id=account.client_id)
        assert p.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_pain_reopen(p.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
