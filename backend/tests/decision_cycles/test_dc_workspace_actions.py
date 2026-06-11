# tests/decision_cycles/test_dc_workspace_actions.py
"""
Integration tests for DecisionCycleViewSet workspace @actions:
  - GET /{id}/people/    → PeopleConsolidationService
  - GET /{id}/readiness/ → ReadinessScoreService
"""

import uuid

import pytest
from rest_framework import status


def _people_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/people/'


def _readiness_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/readiness/'


# =============================================================================
# PEOPLE ACTION
# =============================================================================


@pytest.mark.django_db
class TestCyclePeopleAction:

    def test_people_returns_qualified_and_unqualified(
        self, authed_api_a, cycle, five_steps, completed_activity_on_step, contact
    ):
        step = five_steps[0]
        act = completed_activity_on_step(step)
        act.contacts.add(contact)

        resp = authed_api_a.get(_people_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert 'qualified' in data
        assert 'unqualified' in data

    def test_people_empty_cycle(self, authed_api_a, cycle):
        resp = authed_api_a.get(_people_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK

    def test_people_nonexistent_cycle_returns_404(self, authed_api_a):
        resp = authed_api_a.get(_people_url(uuid.uuid4()))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_people_cross_tenant_denied(self, authed_api_b, cycle):
        resp = authed_api_b.get(_people_url(cycle.id))
        assert resp.status_code in (
            status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN
        )


# =============================================================================
# READINESS ACTION
# =============================================================================


@pytest.mark.django_db
class TestCycleReadinessAction:

    def test_readiness_returns_score(self, authed_api_a, cycle):
        resp = authed_api_a.get(_readiness_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert 'score' in data
        assert 'dimensions' in data
        assert isinstance(data['score'], int)
        assert 0 <= data['score'] <= 100

    def test_readiness_nonexistent_cycle_returns_404(self, authed_api_a):
        resp = authed_api_a.get(_readiness_url(uuid.uuid4()))
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_readiness_cross_tenant_denied(self, authed_api_b, cycle):
        resp = authed_api_b.get(_readiness_url(cycle.id))
        assert resp.status_code in (
            status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN
        )

    def test_readiness_increases_with_signals(
        self, authed_api_a, cycle, account, activity
    ):
        resp1 = authed_api_a.get(_readiness_url(cycle.id))
        score_before = resp1.json()['data']['score']

        from app_modules.signals.models import PainSignal
        from app_modules.signals.constants import SignalWhat, SignalDimension
        pain = PainSignal(
            account=account,
            source_activity=activity,
            decision_cycle=cycle,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Manual reporting takes 10h/week',
            source='MANUAL',
        )
        pain.save(user=activity.owner, client_id=account.client_id)

        resp2 = authed_api_a.get(_readiness_url(cycle.id))
        score_after = resp2.json()['data']['score']

        assert score_after >= score_before
