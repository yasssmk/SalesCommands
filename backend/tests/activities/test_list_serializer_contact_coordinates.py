# backend/tests/activities/test_list_serializer_contact_coordinates.py
"""
Contract test for ActivityListSerializer.get_contacts — the serializer that
shapes the per-contact payload of the campaign playlist card
(CampaignViewSet.playlist -> ActivityListSerializer).

The playlist card needs the contact's reachable coordinates so the front can
render them as clickable links (tel: / mailto: / LinkedIn). The card already
consumes `email`; this test pins that `phone_number` and `linkedin` are exposed
alongside it, read straight from the Contact model fields.

Real read-serialization path (ActivityListSerializer(...).data), Postgres.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.activities.models import Activity
from app_modules.activities.serializers import ActivityListSerializer
from app_modules.contacts.models import Contact


@pytest.mark.django_db
def test_get_contacts_exposes_phone_number_and_linkedin(account, user_a):
    """A serialized playlist contact carries phone_number and linkedin,
    next to the email that was already present."""
    contact = Contact(
        account=account,
        first_name='Jane',
        last_name='Doe',
        email='jane@example.com',
        phone_number='+14155550123',
        linkedin='https://linkedin.com/in/jane-doe',
    )
    contact.save(user=user_a, client_id=account.client_id)

    activity = Activity(
        title='Intro call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        scheduled_date=timezone.now().date() + timedelta(days=1),
    )
    activity.save(user=user_a, client_id=account.client_id)
    activity.contacts.add(contact)

    data = ActivityListSerializer(activity).data
    serialized_contact = data['contacts'][0]

    # Email is the pre-existing coordinate — guards against a regression.
    assert serialized_contact['email'] == 'jane@example.com'
    # The two coordinates this step adds.
    assert serialized_contact['phone_number'] == '+14155550123'
    assert serialized_contact['linkedin'] == 'https://linkedin.com/in/jane-doe'
