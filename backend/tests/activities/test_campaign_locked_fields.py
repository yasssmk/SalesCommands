# backend/tests/activities/test_campaign_locked_fields.py
"""
COND-1 — a CAMPAIGN activity (campaign_id set) locks the fields the campaign
owns: scheduled_date / scheduled_time / due_date / contact_ids / owner_id /
invited_user_ids. A user PATCH touching any of them is refused with a clean 400.
Title / activity_type / description / call_to_action stay editable. Non-campaign
activities are unaffected.

Fixtures are created inline (the activities suite re-exports account / user_a /
api / authenticate but no `activity`/`contact`), mirroring
tests/activities/test_people_dedup_update.py and
tests/activities/test_list_serializer_contact_coordinates.py:29-48.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status


def _url(activity_id):
    return f'/module-activities/{activity_id}/'


def _future_date():
    return (timezone.now().date() + timedelta(days=3)).isoformat()


@pytest.fixture
def campaign_a(db, account, user_a, client_account_a):
    from app_modules.campaigns.models import Campaign
    from app_modules.campaigns.constants import CampaignType, CampaignStatus
    today = timezone.now().date()
    c = Campaign(
        name='Q2 Outbound',
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.DRAFT,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user_a, client_id=client_account_a.id)
    return c


@pytest.fixture
def contact_a(db, account, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='Jane', last_name='Doe', job_title='VP')
    c.save(user=user_a, client_id=account.client_id)
    return c


@pytest.fixture
def campaign_activity(db, account, user_a, campaign_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Sequence step 1',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        campaign=campaign_a,
        sequence_position=1,
        scheduled_date=timezone.now().date() + timedelta(days=1),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def standalone_activity(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Standalone call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        scheduled_date=timezone.now().date() + timedelta(days=1),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.mark.django_db
class TestCampaignLockedFields:

    def test_patch_scheduled_date_on_campaign_activity_is_refused(
        self, api, authenticate, user_a, client_account_a, campaign_activity
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(_url(campaign_activity.id), {'scheduled_date': _future_date()}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_patch_contact_ids_on_campaign_activity_is_refused(
        self, api, authenticate, user_a, client_account_a, campaign_activity, contact_a
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(_url(campaign_activity.id), {'contact_ids': [str(contact_a.id)]}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_patch_owner_id_on_campaign_activity_is_refused(
        self, api, authenticate, user_a, client_account_a, campaign_activity
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(_url(campaign_activity.id), {'owner_id': str(user_a.id)}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_patch_invited_user_ids_on_campaign_activity_is_refused(
        self, api, authenticate, user_a, client_account_a, campaign_activity
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(_url(campaign_activity.id), {'invited_user_ids': [str(user_a.id)]}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content

    def test_patch_title_and_type_on_campaign_activity_is_allowed(
        self, api, authenticate, user_a, client_account_a, campaign_activity
    ):
        from app_modules.activities.constants import ActivityType
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(campaign_activity.id),
            {'title': 'Edited title', 'activity_type': ActivityType.EMAIL},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        campaign_activity.refresh_from_db()
        assert campaign_activity.title == 'Edited title'
        assert campaign_activity.activity_type == ActivityType.EMAIL

    def test_patch_locked_fields_on_standalone_activity_is_allowed(
        self, api, authenticate, user_a, client_account_a, standalone_activity, contact_a
    ):
        authenticate(api, user_a, client_account_a.id)
        resp = api.patch(
            _url(standalone_activity.id),
            {'scheduled_date': _future_date(), 'contact_ids': [str(contact_a.id)]},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
