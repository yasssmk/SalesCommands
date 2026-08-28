# tests/signals/test_constraint_signal_api.py
"""
Integration tests for ConstraintSignal API endpoints.

Covers CRUD + validate/reject/reopen lifecycle + model_map routing +
canonical_key clustering + cross-tenant isolation.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import (
    ConstraintNature,
    SignalSource,
    SignalStatus,
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
            'nature': ConstraintNature.FINANCIAL,
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
            'nature': ConstraintNature.OPERATIONAL,
            'summary': 'Deployment before Q3 close',
            'rigidity': Rigidity.FLEXIBLE,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()['data']['status'] == SignalStatus.PENDING

    def test_create_requires_nature(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': 'Missing nature',
            'rigidity': Rigidity.FIRM,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_succeeds_without_what_dimension(self, authed_api_a, account, activity):
        # Constraint is detached from what × dimension: a constraint creates
        # with nature only (no what/dimension), stays domain-valid, no canonical_key.
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'nature': ConstraintNature.CONTRACTUAL,
            'summary': 'GDPR compliance required',
            'rigidity': Rigidity.FIRM,
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['nature'] == ConstraintNature.CONTRACTUAL

        from app_modules.signals.models import ConstraintSignal
        obj = ConstraintSignal.objects.get(id=data['id'])
        assert obj.is_domain_valid is True
        assert obj.canonical_key is None
        assert obj.what is None
        assert obj.dimension is None

    def test_create_rejects_invalid_nature(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'nature': 'NOT_A_REAL_NATURE',
            'summary': 'Bad nature value',
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
            'nature': ConstraintNature.FINANCIAL,
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
            'nature': ConstraintNature.TECHNICAL,
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
            'nature': ConstraintNature.OPERATIONAL,
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
            'nature': ConstraintNature.FUNCTIONAL,
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
            'nature': ConstraintNature.FINANCIAL,
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
            nature=ConstraintNature.FINANCIAL,
            summary='Tenant A only',
            rigidity=Rigidity.FIRM,
            source=SignalSource.MANUAL,
        )
        signal.save(user=user_a, client_id=account.client_id)

        resp = authed_api_b.get(_detail_url(signal.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
