# backend/tests/campaigns/test_enroll_channel_override.py
"""
E9b.3 — enroll_target reads a per-contact channel_override, persists it on the
CampaignContact rows it creates, and applies the NO_CALLS reachable filter
(email OR LinkedIn) so a phone-only contact is excluded up front.

Real endpoint (POST /campaigns/accounts/enroll-target/). Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignType, CampaignStatus, CampaignAccountStatus, ChannelOverride,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.contacts.models import Contact

ENROLL_URL = "/campaigns/accounts/enroll-target/"


def _mk(account, user_a, *, email, phone, linkedin):
    """Contact whose email/phone_number/linkedin columns hold exactly the given
    values (None -> SQL NULL), set via raw SQL for a deterministic channel mix."""
    c = Contact(account=account, first_name="C", last_name="X")
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s, linkedin=%s WHERE id=%s",
            [email, phone, linkedin, str(c.id)],
        )
    return c


def _campaign(account, user_a, *, channel_override=ChannelOverride.AUTO):
    today = timezone.now().date()
    c = Campaign(
        name='Enroll-override',
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
        sequence_type='TARGETED',
        channel_override=channel_override,
    )
    c.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=c, account=account, status=CampaignAccountStatus.IN_PROGRESS)
    ca.save(user=user_a, client_id=account.client_id)
    return c, ca


def _enroll(api, campaign, account, contact_ids, *, channel_override=None):
    payload = {
        "campaign_id": str(campaign.id),
        "account_id": str(account.id),
        "type": "CONTACT",
        "contact_ids": [str(cid) for cid in contact_ids],
    }
    if channel_override is not None:
        payload["channel_override"] = channel_override
    return api.post(ENROLL_URL, data=payload, format="json")


def _cc(campaign, contact):
    return CampaignContact.objects.filter(
        campaign_account__campaign=campaign, contact=contact
    ).first()


@pytest.mark.django_db
class TestEnrollChannelOverride:

    def test_override_no_calls_persisted_on_created_contact(self, authed_api_a, account, user_a):
        """CORE (RED before fix): channel_override='NO_CALLS' must be stored on the
        newly enrolled CampaignContact. Before the fix the param is ignored -> None."""
        contact = _mk(account, user_a, email="x@x.io", phone="+14155550030", linkedin=None)
        campaign, ca = _campaign(account, user_a, channel_override=ChannelOverride.AUTO)

        resp = _enroll(authed_api_a, campaign, account, [contact.id],
                       channel_override=ChannelOverride.NO_CALLS)
        assert resp.status_code in (200, 201)

        cc = _cc(campaign, contact)
        assert cc is not None
        assert cc.channel_override == ChannelOverride.NO_CALLS

    def test_phone_only_excluded_when_no_calls(self, authed_api_a, account, user_a):
        """CORE (RED before fix): with NO_CALLS the reachable filter is email OR
        LinkedIn, so a phone-only contact must NOT be enrolled (no empty sequence).
        Before the fix the default filter enrolls it."""
        contact = _mk(account, user_a, email=None, phone="+14155550031", linkedin=None)
        campaign, ca = _campaign(account, user_a, channel_override=ChannelOverride.AUTO)

        resp = _enroll(authed_api_a, campaign, account, [contact.id],
                       channel_override=ChannelOverride.NO_CALLS)
        assert resp.status_code in (200, 201)

        assert _cc(campaign, contact) is None

    def test_no_param_keeps_null_and_default_filter(self, authed_api_a, account, user_a):
        """Guard — without the param, override stays NULL and a phone-only contact
        is still reachable (default email/phone/LinkedIn filter, current behavior)."""
        contact = _mk(account, user_a, email=None, phone="+14155550032", linkedin=None)
        campaign, ca = _campaign(account, user_a, channel_override=ChannelOverride.AUTO)

        resp = _enroll(authed_api_a, campaign, account, [contact.id])
        assert resp.status_code in (200, 201)

        cc = _cc(campaign, contact)
        assert cc is not None
        assert cc.channel_override is None

    def test_linkedin_only_enrolled_with_no_calls(self, authed_api_a, account, user_a):
        """Guard — a LinkedIn-only contact is reachable under NO_CALLS and gets the override."""
        contact = _mk(account, user_a, email=None, phone=None,
                      linkedin="https://www.linkedin.com/in/gero")
        campaign, ca = _campaign(account, user_a, channel_override=ChannelOverride.AUTO)

        resp = _enroll(authed_api_a, campaign, account, [contact.id],
                       channel_override=ChannelOverride.NO_CALLS)
        assert resp.status_code in (200, 201)

        cc = _cc(campaign, contact)
        assert cc is not None
        assert cc.channel_override == ChannelOverride.NO_CALLS
