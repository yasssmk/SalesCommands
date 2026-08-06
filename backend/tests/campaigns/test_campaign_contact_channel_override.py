# backend/tests/campaigns/test_campaign_contact_channel_override.py
"""
E9b.1 — the per-contact CampaignContact.channel_override field.

Only the field itself is under test here: a CampaignContact created without an
override defaults to NULL (None) = "follow the campaign", and an explicit
NO_CALLS value persists. Enrollment wiring, generation reading, the API and the
modal come in later E9b sub-steps.

Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignType, CampaignStatus, CampaignAccountStatus, CampaignContactStatus,
    ChannelOverride,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.contacts.models import Contact


def _campaign_account(user_a, account):
    today = timezone.now().date()
    campaign = Campaign(
        name='CC-override',
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    campaign.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(
        campaign=campaign, account=account,
        status=CampaignAccountStatus.IN_PROGRESS,
    )
    ca.save(user=user_a, client_id=account.client_id)
    return ca


def _contact(account, user_a):
    c = Contact(account=account, first_name="C", last_name="X", email="c@x.io")
    c.save(user=user_a, client_id=account.client_id)
    return c


@pytest.mark.django_db
class TestCampaignContactChannelOverride:

    def test_defaults_to_none(self, account, user_a):
        """A CampaignContact created without an override follows the campaign (NULL)."""
        ca = _campaign_account(user_a, account)
        cc = CampaignContact(
            campaign_account=ca, contact=_contact(account, user_a),
            status=CampaignContactStatus.IN_PROGRESS,
        )
        cc.save(user=user_a, client_id=account.client_id)
        cc.refresh_from_db()
        assert cc.channel_override is None

    def test_no_calls_persists(self, account, user_a):
        """An explicit NO_CALLS override is stored and reloaded."""
        ca = _campaign_account(user_a, account)
        cc = CampaignContact(
            campaign_account=ca, contact=_contact(account, user_a),
            status=CampaignContactStatus.IN_PROGRESS,
            channel_override=ChannelOverride.NO_CALLS,
        )
        cc.save(user=user_a, client_id=account.client_id)
        cc.refresh_from_db()
        assert cc.channel_override == ChannelOverride.NO_CALLS
