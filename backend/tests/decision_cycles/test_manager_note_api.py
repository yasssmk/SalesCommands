# tests/decision_cycles/test_manager_note_api.py
"""
Integration tests for ManagerNote API endpoints nested under a DecisionCycle.

Covers CRUD, permission checks (manager/admin vs individual, author-only delete),
and cross-tenant isolation.
"""

import uuid

import pytest
from rest_framework import status

from app_modules.decision_cycles.models import ManagerNote


def _notes_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/notes/'


def _note_detail_url(cycle_id, note_id):
    return f'/decision_cycles/{cycle_id}/notes/{note_id}/'


# =============================================================================
# FIXTURES — manager user on tenant A
# =============================================================================

@pytest.fixture
def manager_user_a(db, client_account_a):
    """A manager-tier user on tenant A."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = User.objects.create_user(
        email='manager@tenanta.com',
        password='testpass123',
        is_manager=True,
        is_admin=False,
        is_individual=False,
    )
    user.client_id = client_account_a.id
    user.save()
    return user


@pytest.fixture
def authed_api_manager(api, authenticate, manager_user_a, client_account_a):
    """Authenticated API client for the manager user on tenant A."""
    authenticate(api, manager_user_a, client_account_a)
    return api


@pytest.fixture
def manager_note(db, cycle, manager_user_a):
    """A ManagerNote authored by the manager on the test cycle."""
    note = ManagerNote(
        decision_cycle=cycle,
        content='Review pipeline velocity.',
    )
    note.save(user=manager_user_a, client_id=cycle.client_id)
    return note


# =============================================================================
# CREATE
# =============================================================================

@pytest.mark.django_db
class TestManagerNoteCreate:

    def test_manager_can_create_note(self, authed_api_manager, cycle):
        resp = authed_api_manager.post(
            _notes_url(cycle.id),
            {'content': 'Push on technical validation.'},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['content'] == 'Push on technical validation.'
        assert data['author_name'] is not None

    def test_individual_cannot_create_note(self, authed_api_a, cycle):
        resp = authed_api_a.post(
            _notes_url(cycle.id),
            {'content': 'Should fail.'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_with_empty_content_fails(self, authed_api_manager, cycle):
        resp = authed_api_manager.post(
            _notes_url(cycle.id),
            {'content': ''},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_on_nonexistent_cycle_returns_404(self, authed_api_manager):
        resp = authed_api_manager.post(
            _notes_url(uuid.uuid4()),
            {'content': 'Orphan note.'},
            format='json',
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# LIST / RETRIEVE
# =============================================================================

@pytest.mark.django_db
class TestManagerNoteRead:

    def test_manager_can_list_notes(self, authed_api_manager, cycle, manager_note):
        resp = authed_api_manager.get(_notes_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert len(data) == 1
        assert data[0]['id'] == str(manager_note.id)

    def test_cycle_owner_can_list_notes(self, authed_api_a, cycle, manager_note):
        resp = authed_api_a.get(_notes_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()['data']) == 1

    def test_list_empty_cycle(self, authed_api_manager, cycle):
        resp = authed_api_manager.get(_notes_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] == []

    def test_retrieve_note(self, authed_api_manager, cycle, manager_note):
        resp = authed_api_manager.get(_note_detail_url(cycle.id, manager_note.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['id'] == str(manager_note.id)


# =============================================================================
# DELETE
# =============================================================================

@pytest.mark.django_db
class TestManagerNoteDelete:

    def test_author_can_delete_own_note(self, authed_api_manager, cycle, manager_note):
        resp = authed_api_manager.delete(_note_detail_url(cycle.id, manager_note.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not ManagerNote.objects.filter(id=manager_note.id).exists()

    def test_non_author_manager_cannot_delete(self, cycle, manager_note, db, api, authenticate, client_account_a):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        other_manager = User.objects.create_user(
            email='other_manager@tenanta.com',
            password='testpass123',
            is_manager=True,
            is_admin=False,
            is_individual=False,
        )
        other_manager.client_id = client_account_a.id
        other_manager.save()
        authenticate(api, other_manager, client_account_a)

        resp = api.delete(_note_detail_url(cycle.id, manager_note.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_individual_cannot_delete(self, authed_api_a, cycle, manager_note):
        resp = authed_api_a.delete(_note_detail_url(cycle.id, manager_note.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# ISOLATION — cross-tenant
# =============================================================================

@pytest.mark.django_db
class TestManagerNoteIsolation:

    def test_tenant_b_cannot_access_tenant_a_notes(
        self, authed_api_b, cycle, manager_note
    ):
        resp = authed_api_b.get(_notes_url(cycle.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
