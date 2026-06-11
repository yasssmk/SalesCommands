# tests/signals/test_people_signal_api.py
"""
Integration tests for PeopleSignal API endpoints.

Covers CRUD + validate/reject/reopen lifecycle + model_map routing +
cross-tenant isolation.
"""

import uuid

import pytest
from rest_framework import status

from app_modules.signals.constants import SignalStatus, PeopleRole, InfluenceLevel

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

    def test_create_llm_extracted_starts_pending(self, authed_api_a, account, activity):
        payload = {
            'signal_type': 'people',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.ECONOMIC_BUYER,
            'notes': 'Mentioned budget authority',
        }
        resp = authed_api_a.post(PEOPLE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()['data']['status'] == SignalStatus.PENDING

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

    def test_list_returns_people_signals(self, authed_api_a, account, activity):
        authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.END_USER,
        }, format='json')

        resp = authed_api_a.get(PEOPLE_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()['data']['results']
        assert len(results) >= 1

    def test_retrieve_detail(self, authed_api_a, account, activity):
        create_resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.DECISION_MAKER,
        }, format='json')
        pk = create_resp.json()['data']['id']

        resp = authed_api_a.get(_detail_url(pk))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['role'] == PeopleRole.DECISION_MAKER


# =============================================================================
# UPDATE
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalUpdate:

    def test_patch_notes(self, authed_api_a, account, activity):
        create_resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.CHAMPION,
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

    def _create_pending(self, authed_api, account, activity):
        resp = authed_api.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'LLM_EXTRACTED',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.PROCUREMENT,
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
            {'reason': 'Incorrect attribution'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.REJECTED

    def test_reopen_validated(self, authed_api_a, account, activity):
        pk = self._create_pending(authed_api_a, account, activity)
        authed_api_a.post(_action_url(pk, 'validate'))

        resp = authed_api_a.post(_action_url(pk, 'reopen'))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['status'] == SignalStatus.PENDING

    def test_validate_non_pending_fails(self, authed_api_a, account, activity):
        pk = self._create_pending(authed_api_a, account, activity)
        authed_api_a.post(_action_url(pk, 'validate'))

        resp = authed_api_a.post(_action_url(pk, 'validate'))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# CROSS-TENANT ISOLATION
# =============================================================================


@pytest.mark.django_db
class TestPeopleSignalIsolation:

    def test_tenant_b_cannot_see_tenant_a_signal(
        self, authed_api_a, authed_api_b, account, activity
    ):
        create_resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': PeopleRole.CHAMPION,
        }, format='json')
        pk = create_resp.json()['data']['id']

        resp = authed_api_b.get(_detail_url(pk))
        assert resp.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)
