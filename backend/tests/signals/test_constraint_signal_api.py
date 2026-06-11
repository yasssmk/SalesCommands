# tests/signals/test_constraint_signal_api.py
"""
Integration tests for ConstraintSignal API endpoints.

Covers CRUD + validate/reject/reopen lifecycle + model_map routing +
canonical_key clustering + cross-tenant isolation.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import (
    SignalSource,
    SignalStatus,
    SignalWhat,
    SignalDimension,
    Rigidity,
)
from app_modules.signals.models import ConstraintSignal

CONSTRAINT_URL = '/module-signals/constraints/'


def _detail_url(pk):
    return f'{CONSTRAINT_URL}{pk}/'


def _action_url(pk, action):
    return f'{CONSTRAINT_URL}{pk}/{action}/'


# =============================================================================
# CREATE — via API (model_map routing)
# =============================================================================


@pytest.mark.django_db
class TestConstraintSignalCreate:

    def test_create_manual_constraint(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.OPS,
            'dimension': SignalDimension.COST,
            'summary': 'ROI > 20% within 18 months',
            'rigidity': Rigidity.FIRM,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['status'] == SignalStatus.VALIDATED
        assert data['rigidity'] == Rigidity.FIRM

    def test_create_llm_extracted_starts_pending(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.DATA,
            'dimension': SignalDimension.TIME,
            'summary': 'Deployment before Q3 close',
            'rigidity': Rigidity.FLEXIBLE,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()['data']['status'] == SignalStatus.PENDING

    def test_create_requires_what_and_dimension(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': 'Missing what/dimension',
            'rigidity': Rigidity.FIRM,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_requires_rigidity(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.OPS,
            'dimension': SignalDimension.COST,
            'summary': 'Missing rigidity',
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# LIST / RETRIEVE
# =============================================================================


@pytest.mark.django_db
class TestConstraintSignalRead:

    def test_list_returns_constraints(self, authed_api_a, account, activity):
        authed_api_a.post(CONSTRAINT_URL, {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.TECH,
            'dimension': SignalDimension.QUALITY,
            'summary': 'Must integrate with SAP',
            'rigidity': Rigidity.FIRM,
        }, format='json')

        resp = authed_api_a.get(CONSTRAINT_URL)
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get('results') or body.get('data', {}).get('results') or body
        if isinstance(results, dict):
            results = results.get('results', results)
        assert len(results) >= 1

    def test_retrieve_detail(self, authed_api_a, account, activity):
        create_resp = authed_api_a.post(CONSTRAINT_URL, {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.OPS,
            'dimension': SignalDimension.TIME,
            'summary': 'Budget cycle ends in June',
            'rigidity': Rigidity.FIRM,
        }, format='json')
        pk = create_resp.json()['data']['id']

        resp = authed_api_a.get(_detail_url(pk))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['summary'] == 'Budget cycle ends in June'


# =============================================================================
# VALIDATE / REJECT / REOPEN
# =============================================================================


@pytest.mark.django_db
class TestConstraintSignalLifecycle:

    def _create_pending(self, authed_api, account, activity):
        resp = authed_api.post(CONSTRAINT_URL, {
            'signal_type': 'constraint',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.GROWTH,
            'dimension': SignalDimension.SCALE,
            'summary': 'Must support 500+ users',
            'rigidity': Rigidity.FIRM,
        }, format='json')
        return resp.json()['data']['id']

    def test_validate(self, authed_api_a, account, activity):
        pk = self._create_pending(authed_api_a, account, activity)
        resp = authed_api_a.post(_action_url(pk, 'validate'))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.VALIDATED

    def test_reject(self, authed_api_a, account, activity):
        pk = self._create_pending(authed_api_a, account, activity)
        resp = authed_api_a.post(
            _action_url(pk, 'reject'),
            {'reason': 'Not a real constraint'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.REJECTED

    def test_reopen_rejected(self, authed_api_a, account, activity):
        pk = self._create_pending(authed_api_a, account, activity)
        authed_api_a.post(_action_url(pk, 'reject'))

        resp = authed_api_a.post(_action_url(pk, 'reopen'))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.PENDING


# =============================================================================
# CACHE INVALIDATION — cluster tag must be busted
# =============================================================================


@pytest.mark.django_db(transaction=True)
class TestConstraintCacheInvalidation:

    def test_create_invalidates_cluster_tag(
        self, authed_api_a, account, activity, cache_invalidation_calls
    ):
        authed_api_a.post(CONSTRAINT_URL, {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'what': SignalWhat.OPS,
            'dimension': SignalDimension.COST,
            'summary': 'Cache test',
            'rigidity': Rigidity.FLEXIBLE,
        }, format='json')

        tags_busted = [tag for (_, tag) in cache_invalidation_calls]
        assert 'signals' in tags_busted
        assert 'signal_clusters' in tags_busted


# =============================================================================
# CROSS-TENANT ISOLATION
# =============================================================================


@pytest.mark.django_db
class TestConstraintSignalIsolation:

    def test_retrieve_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a
    ):
        signal = ConstraintSignal(
            account=account,
            source_activity=activity,
            what=SignalWhat.OPS,
            dimension=SignalDimension.COST,
            summary='Tenant A only',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        signal.save(user=user_a, client_id=account.client_id)

        resp = authed_api_b.get(_detail_url(signal.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
