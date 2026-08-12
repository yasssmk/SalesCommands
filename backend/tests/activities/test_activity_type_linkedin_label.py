# backend/tests/activities/test_activity_type_linkedin_label.py
"""
Display label of the LINKEDIN activity type.

The label is defined once on the ActivityType enum (activities/constants.py) and
surfaces everywhere the type is shown via get_activity_type_display() —
including the playlist card's `activity_type_display`
(ActivityListSerializer.get_activity_type_display). This pins the shortened
label "LinkedIn" on the real display path. The stored VALUE stays 'LINKEDIN'.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.activities.models import Activity
from app_modules.activities.serializers import ActivityListSerializer


@pytest.mark.django_db
def test_linkedin_activity_type_display_is_linkedin(account, user_a):
    activity = Activity(
        title='Connect on LinkedIn',
        activity_type=ActivityType.LINKEDIN,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        scheduled_date=timezone.now().date() + timedelta(days=1),
    )
    activity.save(user=user_a, client_id=account.client_id)

    # Stored value is unchanged — only the display label is shortened.
    assert activity.activity_type == 'LINKEDIN'

    # Real display path used by the model and the serializer.
    assert activity.get_activity_type_display() == 'LinkedIn'
    assert ActivityListSerializer(activity).data['activity_type_display'] == 'LinkedIn'
