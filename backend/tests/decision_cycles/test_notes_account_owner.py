# backend/tests/decision_cycles/test_notes_account_owner.py
"""
Account-owner read access to DecisionCycle manager notes (C6 — root fix of
the Sprint-0 403).

The ManagerNote list/retrieve gate was manager/admin OR cycle-owner only.
An account owner (AE) whose account's cycle was created by someone else
(owner=SDR) was therefore denied (403) reading the coaching notes on their
own account's cycle. We add an additive `_is_account_owner` condition; the
manager/admin gate and the cycle-owner path are untouched, and create /
destroy stay manager/admin / author-only.

Positive:  AE (account owner, not manager, not cycle owner) lists AND
           retrieves the notes -> 200.
Negative1: an unrelated individual (not manager/owner/account-owner) -> 403.
Negative2: a user from another tenant -> 404.
Regression: the cycle owner (the SDR) still reads the notes -> 200.
"""

import pytest
from rest_framework import status

from app_modules.decision_cycles.models import DecisionCycle, ManagerNote
from app_modules.accounts.models import CompanyAccount


def _notes_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/notes/'


def _note_detail_url(cycle_id, note_id):
    return f'/decision_cycles/{cycle_id}/notes/{note_id}/'


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def role_manager_a(db, client_account_a):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account_a,
        name='Manager',
        is_admin=False,
        is_manager=True,
        is_individual=False,
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )


@pytest.fixture
def manager_user_a(db, client_account_a, role_manager_a):
    from end_users.models import User
    return User.objects.create(
        email='mgr-notes@tenant-a.test',
        client_account=client_account_a,
        role=role_manager_a,
        is_active=True,
    )


@pytest.fixture
def ae_user(db, client_account_a, role_individual_a):
    """Account Executive — individual, owns the account; NOT the cycle owner."""
    from end_users.models import User
    return User.objects.create(
        email='ae-notes@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def sdr_user(db, client_account_a, role_individual_a):
    """SDR — individual, creates and owns the cycle; not the account owner."""
    from end_users.models import User
    return User.objects.create(
        email='sdr-notes@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def user_c(db, client_account_a, role_individual_a):
    """Unrelated individual on tenant A — no manager flag, no ownership tie."""
    from end_users.models import User
    return User.objects.create(
        email='rep-c-notes@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def account_ae(db, client_account_a, ae_user):
    acc = CompanyAccount(
        company_name='AE Owned Corp (notes)',
        has_buying_decision=True,
        account_owner=ae_user,
    )
    acc.save(user=ae_user, client_id=client_account_a.id)
    return acc


@pytest.fixture
def sdr_cycle(db, account_ae, sdr_user):
    """Cycle on the AE-owned account, created and owned by the SDR."""
    c = DecisionCycle(
        account=account_ae,
        owner=sdr_user,
        name='SDR-created cycle (notes)',
        is_active=True,
    )
    c.save(user=sdr_user, client_id=account_ae.client_id)
    return c


@pytest.fixture
def note_on_sdr_cycle(db, sdr_cycle, manager_user_a):
    """A coaching note authored by the manager on the SDR-created cycle."""
    note = ManagerNote(
        decision_cycle=sdr_cycle,
        content='Coach: qualify the economic buyer.',
    )
    note.save(user=manager_user_a, client_id=sdr_cycle.client_id)
    return note


# =============================================================================
# POSITIVE — account owner reads notes on their account's cycle
# =============================================================================

@pytest.mark.django_db
class TestAccountOwnerReadsNotes:

    def test_account_owner_can_list_notes(
        self, api, authenticate, ae_user, client_account_a, sdr_cycle, note_on_sdr_cycle
    ):
        authenticate(api, ae_user, client_account_a.id)
        resp = api.get(_notes_url(sdr_cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert len(data) == 1
        assert data[0]['id'] == str(note_on_sdr_cycle.id)

    def test_account_owner_can_retrieve_note(
        self, api, authenticate, ae_user, client_account_a, sdr_cycle, note_on_sdr_cycle
    ):
        authenticate(api, ae_user, client_account_a.id)
        resp = api.get(_note_detail_url(sdr_cycle.id, note_on_sdr_cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['id'] == str(note_on_sdr_cycle.id)


# =============================================================================
# NEGATIVE — boundaries unchanged
# =============================================================================

@pytest.mark.django_db
class TestNotesReadBoundaries:

    def test_unrelated_individual_is_denied(
        self, api, authenticate, user_c, client_account_a, sdr_cycle, note_on_sdr_cycle
    ):
        """Not manager/admin, not cycle owner, not account owner -> 403."""
        authenticate(api, user_c, client_account_a.id)
        resp = api.get(_notes_url(sdr_cycle.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_other_tenant_user_gets_404(
        self, api, authenticate, user_b, client_account_b, sdr_cycle, note_on_sdr_cycle
    ):
        """Cross-tenant: the cycle is not resolvable in tenant B -> 404."""
        authenticate(api, user_b, client_account_b.id)
        resp = api.get(_notes_url(sdr_cycle.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# REGRESSION — the cycle owner path is preserved
# =============================================================================

@pytest.mark.django_db
class TestCycleOwnerStillReads:

    def test_cycle_owner_can_still_list_notes(
        self, api, authenticate, sdr_user, client_account_a, sdr_cycle, note_on_sdr_cycle
    ):
        """The SDR owns the cycle (owner=creator) and must keep read access."""
        authenticate(api, sdr_user, client_account_a.id)
        resp = api.get(_notes_url(sdr_cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()['data']) == 1
