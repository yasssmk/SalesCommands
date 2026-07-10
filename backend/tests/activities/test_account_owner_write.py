# backend/tests/activities/test_account_owner_write.py
"""
Account-owner inheritance for activity WRITE access (C6).

An account owner (AE) must be able to edit activities on their account even
when the activity was created/owned by someone else (e.g. an SDR from a
campaign). This is enforced additively through the OWNERSHIP_MAP
`account_owner_user` key (account__account_owner_id) applied in the
`mine`-scope builder.

Read stays `client` and delete stays `none` for individuals — this pack
only exercises the update/partial_update widening and its boundaries.

Positive:  AE edits an SDR-created activity on their account -> 200.
Negative1: another individual (owns a different account) -> 403.
Negative2: a user from another tenant -> 404.
Negative3: the widening does NOT leak into my-activities (owner-only).
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount


def _detail_url(activity_id):
    return f'/module-activities/{activity_id}/'


_MY_ACTIVITIES_URL = '/module-activities/my-activities/'


# =============================================================================
# FIXTURES — AE (account owner), SDR (creator), and an unrelated individual C
# =============================================================================

@pytest.fixture
def ae_user(db, client_account_a, role_individual_a):
    """Account Executive — individual tier, owns the account under test."""
    from end_users.models import User
    return User.objects.create(
        email='ae@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def sdr_user(db, client_account_a, role_individual_a):
    """SDR — individual tier, creates the activity but does not own the account."""
    from end_users.models import User
    return User.objects.create(
        email='sdr@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def user_c(db, client_account_a, role_individual_a):
    """Another individual on tenant A who owns a DIFFERENT account (out of scope)."""
    from end_users.models import User
    return User.objects.create(
        email='rep-c@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def account_ae(db, client_account_a, ae_user):
    """CompanyAccount whose account_owner is the AE."""
    acc = CompanyAccount(
        company_name='AE Owned Corp',
        has_buying_decision=True,
        account_owner=ae_user,
    )
    acc.save(user=ae_user, client_id=client_account_a.id)
    return acc


@pytest.fixture
def account_c(db, client_account_a, user_c):
    """A separate CompanyAccount owned by individual C — establishes C as a
    legitimate rep on the tenant who simply owns a different account."""
    acc = CompanyAccount(
        company_name='C Owned Corp',
        has_buying_decision=True,
        account_owner=user_c,
    )
    acc.save(user=user_c, client_id=client_account_a.id)
    return acc


@pytest.fixture
def sdr_activity(db, account_ae, sdr_user):
    """Activity on the AE-owned account, created and owned by the SDR."""
    a = Activity(
        title='SDR prospecting call',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.PLANNED,
        account=account_ae,
        owner=sdr_user,
        scheduled_date=timezone.now().date() + timedelta(days=5),
    )
    a.save(user=sdr_user, client_id=account_ae.client_id)
    return a


# =============================================================================
# POSITIVE — the account owner can edit an activity created by someone else
# =============================================================================

@pytest.mark.django_db
class TestAccountOwnerCanWrite:

    def test_account_owner_can_patch_sdr_created_activity(
        self, api, authenticate, ae_user, client_account_a, account_ae, sdr_activity
    ):
        authenticate(api, ae_user, client_account_a.id)

        resp = api.patch(
            _detail_url(sdr_activity.id),
            {'title': 'Edited by account owner'},
            format='json',
        )

        assert resp.status_code == status.HTTP_200_OK
        sdr_activity.refresh_from_db()
        assert sdr_activity.title == 'Edited by account owner'


# =============================================================================
# NEGATIVE — boundaries must not move (isolation preserved)
# =============================================================================

@pytest.mark.django_db
class TestWriteBoundaries:

    def test_unrelated_individual_cannot_patch(
        self, api, authenticate, user_c, client_account_a, account_c, sdr_activity
    ):
        """Individual C owns a different account -> not owner, not creator -> 403."""
        authenticate(api, user_c, client_account_a.id)

        resp = api.patch(
            _detail_url(sdr_activity.id),
            {'title': 'Should not be allowed'},
            format='json',
        )

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        sdr_activity.refresh_from_db()
        assert sdr_activity.title == 'SDR prospecting call'

    def test_other_tenant_user_gets_404(
        self, api, authenticate, user_b, client_account_b, sdr_activity
    ):
        """A user from tenant B must not even see the tenant-A activity -> 404."""
        authenticate(api, user_b, client_account_b.id)

        resp = api.patch(
            _detail_url(sdr_activity.id),
            {'title': 'Cross-tenant edit'},
            format='json',
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        sdr_activity.refresh_from_db()
        assert sdr_activity.title == 'SDR prospecting call'

    def test_my_activities_does_not_include_account_owned_activity(
        self, api, authenticate, ae_user, client_account_a, account_ae, sdr_activity
    ):
        """The account-owner widening must NOT leak into my-activities, which
        is strictly owner==request.user."""
        authenticate(api, ae_user, client_account_a.id)

        resp = api.get(_MY_ACTIVITIES_URL)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()['data']['results']
        returned_ids = {row['id'] for row in results}
        assert str(sdr_activity.id) not in returned_ids
