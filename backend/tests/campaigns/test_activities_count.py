# backend/tests/campaigns/test_activities_count.py
"""
BUG B — CampaignContact.activities_count must report the TOTAL number of activities
(all statuses, all runs), not the ON_HOLD count. The contacts-list view prefetches
`activities` filtered to ON_HOLD (for has_on_hold); get_activities_count used to fall
back to obj.activities.count(), reading that filtered prefetch and reporting 0.

Real endpoint checked. Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignStatus, CampaignType, CampaignAccountStatus, CampaignContactStatus,
)
from app_modules.activities.constants import ActivityStatus, ActivityType

LIST_URL = "/campaigns/contacts/"


def _setup(account, user_a, name="C"):
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
    from app_modules.contacts.models import Contact
    today = timezone.now().date()
    c = Campaign(name=name, campaign_type=CampaignType.TARGETED, status=CampaignStatus.ACTIVE,
                 owner=user_a, planned_start_date=today, planned_end_date=today + timedelta(days=30),
                 actual_start_date=today)
    c.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=c, account=account, status=CampaignAccountStatus.IN_PROGRESS)
    ca.save(user=user_a, client_id=account.client_id)
    contact = Contact(account=account, first_name="Count", last_name="Me", email="c@x.io")
    contact.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=contact, status=CampaignContactStatus.IN_PROGRESS)
    cc.save(user=user_a, client_id=account.client_id)
    return c, ca, cc


def _activity(account, user_a, c, ca, cc, status, run=1):
    from app_modules.activities.models import Activity
    a = Activity(title=f"a-{status}-{run}", activity_type=ActivityType.CALL, status=status,
                 account=account, owner=user_a, campaign=c, campaign_account=ca,
                 campaign_contact=cc, sequence_position=1, sequence_run=run)
    a.save(user=user_a, client_id=account.client_id)
    return a


def _list_row(api, campaign_id, cc_id):
    resp = api.get(f"{LIST_URL}?campaign={campaign_id}")
    data = resp.data.get("data", resp.data)
    rows = data.get("results", data) if isinstance(data, dict) else data
    return next(r for r in rows if str(r["id"]) == str(cc_id))


@pytest.mark.django_db
class TestActivitiesCount:

    def test_list_counts_all_activities(self, authed_api_a, account, user_a):
        """RED before fix: 1 COMPLETED + 1 PLANNED (0 ON_HOLD) → count must be 2, not 0."""
        c, ca, cc = _setup(account, user_a, name="count-all")
        _activity(account, user_a, c, ca, cc, ActivityStatus.COMPLETED)
        _activity(account, user_a, c, ca, cc, ActivityStatus.PLANNED)

        row = _list_row(authed_api_a, c.id, cc.id)
        assert row["activities_count"] == 2
        assert row["has_on_hold"] is False

    def test_has_on_hold_still_true(self, authed_api_a, account, user_a):
        """The ON_HOLD prefetch is untouched: has_on_hold stays correct."""
        c, ca, cc = _setup(account, user_a, name="onhold")
        _activity(account, user_a, c, ca, cc, ActivityStatus.ON_HOLD)
        _activity(account, user_a, c, ca, cc, ActivityStatus.PLANNED)

        row = _list_row(authed_api_a, c.id, cc.id)
        assert row["has_on_hold"] is True
        assert row["activities_count"] == 2  # both counted

    def test_counts_all_runs(self, authed_api_a, account, user_a):
        """Total spans every run (definition = all activities, not just current run)."""
        c, ca, cc = _setup(account, user_a, name="runs")
        _activity(account, user_a, c, ca, cc, ActivityStatus.COMPLETED, run=1)
        _activity(account, user_a, c, ca, cc, ActivityStatus.COMPLETED, run=2)
        _activity(account, user_a, c, ca, cc, ActivityStatus.PLANNED, run=2)

        row = _list_row(authed_api_a, c.id, cc.id)
        assert row["activities_count"] == 3
