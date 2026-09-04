# backend/tests/activities/test_people_dedup_update.py
"""
DUP-FIX — ActivityUpdateSerializer must DEDUPLICATE contact_ids / invited_user_ids
before the existence count-check. Previously a duplicated (but valid) id made
`queryset.count() != len(ids)` fail with a misleading "not found" 400. After the
fix a duplicate is collapsed silently (M2M .set does the rest); a TRULY missing
id is still rejected.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status


def _url(activity_id):
    return f'/module-activities/{activity_id}/'


@pytest.fixture
def invitee(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='invitee@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


def _future_date():
    return (timezone.now().date() + timedelta(days=3)).isoformat()


@pytest.mark.django_db
class TestPeopleDedupUpdate:

    def test_duplicate_contact_ids_are_deduped_not_rejected(
        self, api, authenticate, user_a, client_account_a, activity, contact
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(activity.id),
            {'scheduled_date': _future_date(), 'contact_ids': [str(contact.id), str(contact.id)]},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        activity.refresh_from_db()
        assert list(activity.contacts.values_list('id', flat=True)) == [contact.id]

    def test_duplicate_invited_user_ids_are_deduped_not_rejected(
        self, api, authenticate, user_a, client_account_a, activity, contact, invitee
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(activity.id),
            {
                'scheduled_date': _future_date(),
                'contact_ids': [str(contact.id)],
                'invited_user_ids': [str(invitee.id), str(invitee.id)],
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        activity.refresh_from_db()
        assert list(activity.invited_users.values_list('id', flat=True)) == [invitee.id]

    def test_truly_missing_contact_id_still_rejected(
        self, api, authenticate, user_a, client_account_a, activity, contact
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(activity.id),
            {'scheduled_date': _future_date(), 'contact_ids': [str(contact.id), str(uuid.uuid4())]},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_truly_missing_invited_id_still_rejected(
        self, api, authenticate, user_a, client_account_a, activity, contact, invitee
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(activity.id),
            {
                'scheduled_date': _future_date(),
                'contact_ids': [str(contact.id)],
                'invited_user_ids': [str(invitee.id), str(uuid.uuid4())],
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
