# backend/tests/campaigns/test_enroll_unreachable_count.py
"""
enroll-target must report a reliable unreachable_count for EVERY mode — including
ACCOUNT mode (contact_ids empty), where it used to be hard-coded to 0. This lets the
frontend tell "0 reachable" (unreachable>0, enrolled=0 → warning) apart from
"already active" (unreachable=0, enrolled=0 → warning) and real success (enrolled>0).
Real endpoint. Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.activities.constants import ActivityStatus

ENROLL_URL = "/campaigns/accounts/enroll-target/"


def _campaign_only(account, user_a):
    """TARGETED ACTIVE campaign with NO pre-created CampaignAccount."""
    from app_modules.campaigns.models import Campaign
    today = timezone.now().date()
    c = Campaign(name="Acc", campaign_type=CampaignType.TARGETED, status=CampaignStatus.ACTIVE,
                 owner=user_a, planned_start_date=today, planned_end_date=today + timedelta(days=30),
                 actual_start_date=today)
    c.save(user=user_a, client_id=account.client_id)
    return c


def _contact(account, user_a, n, reachable=True):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=f"C{n}", last_name="X",
                email=(f"c{n}@x.io" if reachable else None))
    c.save(user=user_a, client_id=account.client_id)
    return c


def _enroll_account(api, campaign, account):
    return api.post(ENROLL_URL, data={
        "campaign_id": str(campaign.id), "account_id": str(account.id),
        "type": "ACCOUNT", "contact_ids": [],
    }, format="json")


def _body(resp):
    return resp.data.get("data", resp.data)


@pytest.mark.django_db
class TestUnreachableCount:

    def test_account_mode_zero_reachable(self, authed_api_a, account, user_a):
        """RED before fix: ACCOUNT with only unreachable contacts → unreachable_count>0."""
        c = _campaign_only(account, user_a)
        _contact(account, user_a, 1, reachable=False)
        _contact(account, user_a, 2, reachable=False)

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 0
        assert b["unreachable_count"] == 2  # was 0 before the fix

    def test_account_mode_already_active(self, authed_api_a, account, user_a):
        """ACCOUNT re-enroll of an already-active contact → unreachable=0, enrolled=0."""
        from app_modules.campaigns.models import CampaignContact
        from app_modules.activities.models import Activity
        c = _campaign_only(account, user_a)
        ct = _contact(account, user_a, 1, reachable=True)

        # First enroll generates a PLANNED activity (contact becomes active).
        first = _enroll_account(authed_api_a, c, account)
        assert _body(first)["contacts_enrolled"] == 1
        assert Activity.objects.filter(campaign=c, status=ActivityStatus.PLANNED).exists()

        # Re-enroll ACCOUNT: contact is skipped (already has open activities).
        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 0
        assert b["unreachable_count"] == 0  # reachable, just already active

    def test_account_mode_enrolled(self, authed_api_a, account, user_a):
        """ACCOUNT with a reachable, fresh contact → enrolled>0, unreachable=0."""
        c = _campaign_only(account, user_a)
        _contact(account, user_a, 1, reachable=True)

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 1
        assert b["unreachable_count"] == 0
