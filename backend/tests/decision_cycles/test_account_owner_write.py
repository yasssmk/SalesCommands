# backend/tests/decision_cycles/test_account_owner_write.py
"""
Account-owner inheritance for decision-cycle WRITE access (C6).

An account owner (AE) must be able to edit decision cycles on their account
even when the cycle was created/owned by someone else (e.g. an SDR from a
campaign, whose cycle defaults owner=creator). Enforced additively through
the OWNERSHIP_MAP `account_owner_user` key (account__account_owner_id)
applied in the `mine`-scope builder.

Only update/partial_update is widened; read stays `client`, delete stays
`none`, and the by_account/people/readiness actions stay `client`.

Positive:  AE edits an SDR-created cycle on their account -> 200.
Negative1: another individual (owns a different account) -> 403.
Negative2: a user from another tenant -> 404.
"""

import pytest
from rest_framework import status

from app_modules.decision_cycles.models import DecisionCycle
from app_modules.accounts.models import CompanyAccount


def _detail_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/'


# =============================================================================
# FIXTURES — AE (account owner), SDR (creator), and an unrelated individual C
# =============================================================================

@pytest.fixture
def ae_user(db, client_account_a, role_individual_a):
    """Account Executive — individual tier, owns the account under test."""
    from end_users.models import User
    return User.objects.create(
        email='ae-dc@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def sdr_user(db, client_account_a, role_individual_a):
    """SDR — individual tier, creates the cycle but does not own the account."""
    from end_users.models import User
    return User.objects.create(
        email='sdr-dc@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def user_c(db, client_account_a, role_individual_a):
    """Another individual on tenant A who owns a DIFFERENT account (out of scope)."""
    from end_users.models import User
    return User.objects.create(
        email='rep-c-dc@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def account_ae(db, client_account_a, ae_user):
    """CompanyAccount whose account_owner is the AE."""
    acc = CompanyAccount(
        company_name='AE Owned Corp (DC)',
        has_buying_decision=True,
        account_owner=ae_user,
    )
    acc.save(user=ae_user, client_id=client_account_a.id)
    return acc


@pytest.fixture
def account_c(db, client_account_a, user_c):
    """A separate CompanyAccount owned by individual C."""
    acc = CompanyAccount(
        company_name='C Owned Corp (DC)',
        has_buying_decision=True,
        account_owner=user_c,
    )
    acc.save(user=user_c, client_id=client_account_a.id)
    return acc


@pytest.fixture
def sdr_cycle(db, account_ae, sdr_user):
    """DecisionCycle on the AE-owned account, created and owned by the SDR."""
    c = DecisionCycle(
        account=account_ae,
        owner=sdr_user,
        name='SDR-created cycle',
        is_active=True,
    )
    c.save(user=sdr_user, client_id=account_ae.client_id)
    return c


# =============================================================================
# POSITIVE — the account owner can edit a cycle created by someone else
# =============================================================================

@pytest.mark.django_db
class TestAccountOwnerCanWriteCycle:

    def test_account_owner_can_patch_sdr_created_cycle(
        self, api, authenticate, ae_user, client_account_a, account_ae, sdr_cycle
    ):
        authenticate(api, ae_user, client_account_a.id)

        resp = api.patch(
            _detail_url(sdr_cycle.id),
            {'name': 'Edited by account owner'},
            format='json',
        )

        assert resp.status_code == status.HTTP_200_OK
        sdr_cycle.refresh_from_db()
        assert sdr_cycle.name == 'Edited by account owner'


# =============================================================================
# NEGATIVE — boundaries must not move (isolation preserved)
# =============================================================================

@pytest.mark.django_db
class TestCycleWriteBoundaries:

    def test_unrelated_individual_cannot_patch(
        self, api, authenticate, user_c, client_account_a, account_c, sdr_cycle
    ):
        """Individual C owns a different account -> not owner, not creator -> 403."""
        authenticate(api, user_c, client_account_a.id)

        resp = api.patch(
            _detail_url(sdr_cycle.id),
            {'name': 'Should not be allowed'},
            format='json',
        )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        sdr_cycle.refresh_from_db()
        assert sdr_cycle.name == 'SDR-created cycle'

    def test_other_tenant_user_gets_404(
        self, api, authenticate, user_b, client_account_b, sdr_cycle
    ):
        """A user from tenant B must not even see the tenant-A cycle -> 404."""
        authenticate(api, user_b, client_account_b.id)

        resp = api.patch(
            _detail_url(sdr_cycle.id),
            {'name': 'Cross-tenant edit'},
            format='json',
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        sdr_cycle.refresh_from_db()
        assert sdr_cycle.name == 'SDR-created cycle'
