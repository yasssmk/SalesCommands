# tests/signals/test_people_signal_api.py
"""
Integration tests for PeopleSignal API endpoints.

Covers CRUD + validate/reject/reopen lifecycle + model_map routing +
cross-tenant isolation.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import (
    SignalSource,
    SignalStatus,
    PeopleRole,
    InfluenceLevel,
)
from app_modules.signals.models import PeopleSignal

PEOPLE_URL = '/module-signals/people/'


def _detail_url(pk):
    return f'{PEOPLE_URL}{pk}/'


def _action_url(pk, action):
    return f'{PEOPLE_URL}{pk}/{action}/'


# =============================================================================
# CREATE — via API (model_map routing)
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalCreate:

    def test_create_manual_people_signal(self, authed_api_a, account, activity, contact):
        payload = {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.CHAMPION,
            'influence': InfluenceLevel.HIGH,
            'target_contact': str(contact.id),
            'notes': 'Key champion identified during discovery',
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['role'] == PeopleRole.CHAMPION
        assert data['status'] == SignalStatus.VALIDATED

    def test_create_llm_extracted_starts_pending(self, authed_api_a, account, activity, contact):
        payload = {
            'signal_type': 'people',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.ECONOMIC_BUYER,
            'target_contact': str(contact.id),
            'notes': 'Mentioned budget authority',
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()['data']['status'] == SignalStatus.PENDING

    def test_create_manual_dc_level_without_source_activity(
        self, authed_api_a, account, decision_cycle, contact,
    ):
        """MANUAL + decision_cycle (no source_activity) → 201 + VALIDATED."""
        payload = {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'decision_cycle': str(decision_cycle.id),
            'role': PeopleRole.CHAMPION,
            'influence': InfluenceLevel.HIGH,
            'target_contact': str(contact.id),
            'notes': 'Qualified from DC workspace',
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['role'] == PeopleRole.CHAMPION
        assert data['status'] == SignalStatus.VALIDATED

    def test_create_llm_without_source_activity_fails(
        self, authed_api_a, account, decision_cycle, contact,
    ):
        """LLM source without source_activity → 400 even with decision_cycle."""
        payload = {
            'signal_type': 'people',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'decision_cycle': str(decision_cycle.id),
            'role': PeopleRole.INFLUENCER,
            'target_contact': str(contact.id),
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_requires_account(self, authed_api_a, activity):
        payload = {
            'signal_type': 'people',
            'source': 'MANUAL',
            'source_activity': str(activity.id),
            'role': PeopleRole.INFLUENCER,
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# LIST / RETRIEVE
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalRead:

    def test_list_returns_people_signals(self, authed_api_a, account, activity, contact):
        authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.END_USER,
            'target_contact': str(contact.id),
        }, format='json')

        resp = authed_api_a.get(PEOPLE_URL)
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        results = body.get('results') or body.get('data', {}).get('results') or body
        if isinstance(results, dict):
            results = results.get('results', results)
        assert len(results) >= 1

    def test_retrieve_detail(self, authed_api_a, account, activity, contact):
        create_resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.DECISION_MAKER,
            'target_contact': str(contact.id),
        }, format='json')
        pk = create_resp.json()['data']['id']

        resp = authed_api_a.get(_detail_url(pk))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['role'] == PeopleRole.DECISION_MAKER


# =============================================================================
# UPDATE
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalUpdate:

    def test_patch_notes(self, authed_api_a, account, activity, contact):
        create_resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.CHAMPION,
            'target_contact': str(contact.id),
        }, format='json')
        pk = create_resp.json()['data']['id']

        resp = authed_api_a.patch(
            _detail_url(pk),
            {'notes': 'Updated notes'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['notes'] == 'Updated notes'


# =============================================================================
# VALIDATE / REJECT / REOPEN
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalLifecycle:

    def _create_pending(self, authed_api, account, activity, contact):
        resp = authed_api.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.PROCUREMENT,
            'target_contact': str(contact.id),
        }, format='json')
        return resp.json()['data']['id']

    def test_validate(self, authed_api_a, account, activity, contact):
        pk = self._create_pending(authed_api_a, account, activity, contact)
        resp = authed_api_a.post(_action_url(pk, 'validate'))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.VALIDATED

    def test_reject(self, authed_api_a, account, activity, contact):
        pk = self._create_pending(authed_api_a, account, activity, contact)
        resp = authed_api_a.post(
            _action_url(pk, 'reject'),
            {'reason': 'Incorrect attribution'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.REJECTED

    def test_reopen_validated(self, authed_api_a, account, activity, contact):
        pk = self._create_pending(authed_api_a, account, activity, contact)
        authed_api_a.post(_action_url(pk, 'validate'))

        resp = authed_api_a.post(_action_url(pk, 'reopen'))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.PENDING

    def test_validate_non_pending_fails(self, authed_api_a, account, activity, contact):
        pk = self._create_pending(authed_api_a, account, activity, contact)
        authed_api_a.post(_action_url(pk, 'validate'))

        resp = authed_api_a.post(_action_url(pk, 'validate'))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# CROSS-TENANT ISOLATION
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalIsolation:

    def test_retrieve_cross_tenant_returns_404(
        self, authed_api_b, account, activity, contact, user_a
    ):
        signal = PeopleSignal(
            account=account,
            source_activity=activity,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            source=SignalSource.MANUAL,
        )
        signal.save(user=user_a, client_id=account.client_id)

        resp = authed_api_b.get(_detail_url(signal.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
