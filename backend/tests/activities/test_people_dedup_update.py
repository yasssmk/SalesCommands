# backend/tests/activities/test_people_dedup_update.py
"""
DUP-FIX — ActivityUpdateSerializer must DEDUPLICATE contact_ids / invited_user_ids
before the existence count-check. Previously a duplicated (but valid) id made
`queryset.count() != len(ids)` fail with a misleading "not found" 400. After the
fix a duplicate is collapsed silently (M2M .set does the rest); a TRULY missing
id is still rejected.

Fixtures: the activities suite re-exports `account` / `user_a` / `api` /
`authenticate` from tests/signals/conftest but NOT an `activity` (nor `contact`)
fixture — so the Activity, its Contact and an invitee are created inline here,
mirroring tests/activities/test_list_serializer_contact_coordinates.py:29-48
(Contact + Activity build/save) and tests/activities/test_account_owner_write.py
(inline User creation + owner-authed PATCH on /module-activities/{id}/).
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status


def _url(activity_id):
    return f'/module-activities/{activity_id}/'


def _future_date():
    return (timezone.now().date() + timedelta(days=3)).isoformat()


# =============================================================================
# FIXTURES — inline, on the current tenant (account / user_a are re-exported)
# =============================================================================

@pytest.fixture
def contact_a(db, account, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account,
        first_name='Jane',
        last_name='Doe',
        job_title='VP Engineering',
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


@pytest.fixture
def edit_activity(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Discovery call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        scheduled_date=timezone.now().date() + timedelta(days=1),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def invitee(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='invitee@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


# =============================================================================
# DEDUP — a duplicated but valid id must NOT 400; it is collapsed
# =============================================================================

@pytest.mark.django_db
class TestPeopleDedupUpdate:

    def test_duplicate_contact_ids_are_deduped_not_rejected(
        self, api, authenticate, user_a, client_account_a, edit_activity, contact_a
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(edit_activity.id),
            {'scheduled_date': _future_date(), 'contact_ids': [str(contact_a.id), str(contact_a.id)]},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        edit_activity.refresh_from_db()
        assert list(edit_activity.contacts.values_list('id', flat=True)) == [contact_a.id]

    def test_duplicate_invited_user_ids_are_deduped_not_rejected(
        self, api, authenticate, user_a, client_account_a, edit_activity, contact_a, invitee
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(edit_activity.id),
            {
                'scheduled_date': _future_date(),
                'contact_ids': [str(contact_a.id)],
                'invited_user_ids': [str(invitee.id), str(invitee.id)],
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        edit_activity.refresh_from_db()
        assert list(edit_activity.invited_users.values_list('id', flat=True)) == [invitee.id]

    # =========================================================================
    # A TRULY missing id must STILL be rejected (the count-check keeps its job)
    # =========================================================================

    def test_truly_missing_contact_id_still_rejected(
        self, api, authenticate, user_a, client_account_a, edit_activity, contact_a
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(edit_activity.id),
            {'scheduled_date': _future_date(), 'contact_ids': [str(contact_a.id), str(uuid.uuid4())]},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_truly_missing_invited_id_still_rejected(
        self, api, authenticate, user_a, client_account_a, edit_activity, contact_a, invitee
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(edit_activity.id),
            {
                'scheduled_date': _future_date(),
                'contact_ids': [str(contact_a.id)],
                'invited_user_ids': [str(invitee.id), str(uuid.uuid4())],
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
