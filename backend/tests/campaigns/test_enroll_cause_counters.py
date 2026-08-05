# backend/tests/campaigns/test_enroll_cause_counters.py
"""
enroll-target must report four SEPARATE non-enrollment cause counters, splitting
the previously fused unreachable_count:

    no_channel_count      -- not opted-out but no channel (email/phone/linkedin)
    opted_out_count       -- opted-out (takes precedence over every other cause)
    already_active_count  -- eligible but skipped (open PLANNED activities here)
    account_empty         -- the account/department has no contact at all (bool)

Priority (locked): account_empty > opted_out > no_channel; already_active is the
eligible-but-skipped remainder. Buckets are disjoint and sum exactly:

    considered_total = opted_out + no_channel + already_active + contacts_enrolled

E4 enriches the response contract only — the set of enrolled contacts does NOT
change. Real endpoint, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.contacts.models import Contact

ENROLL_URL = "/campaigns/accounts/enroll-target/"


def _campaign(account, user_a):
    """ACTIVE TARGETED campaign (no sequence_type -> 1 CALL activity per enrolled contact)."""
    today = timezone.now().date()
    c = Campaign(
        name="E4",
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


def _mk(account, user_a, *, email=None, phone=None, linkedin=None, opted_out=False):
    """Contact with EXACT channel columns (raw SQL) and opted_out flag."""
    c = Contact(account=account, first_name="C", last_name="X", opted_out=opted_out)
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s, linkedin=%s WHERE id=%s",
            [email, phone, linkedin, str(c.id)],
        )
    return c


def _enroll_account(api, campaign, account):
    return api.post(ENROLL_URL, data={
        "campaign_id": str(campaign.id), "account_id": str(account.id),
        "type": "ACCOUNT", "contact_ids": [],
    }, format="json")


def _enroll_contact(api, campaign, account, contact):
    return api.post(ENROLL_URL, data={
        "campaign_id": str(campaign.id), "account_id": str(account.id),
        "type": "CONTACT", "contact_ids": [str(contact.id)],
    }, format="json")


def _body(resp):
    return resp.data.get("data", resp.data)


@pytest.mark.django_db
class TestEnrollCauseCounters:

    def test_no_channel_only(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        _mk(account, user_a, email=None, phone=None, linkedin=None)  # no channel

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 0
        assert b["no_channel_count"] == 1
        assert b["opted_out_count"] == 0
        assert b["already_active_count"] == 0
        assert b["account_empty"] is False

    def test_opted_out_only(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        _mk(account, user_a, email="a@x.io", opted_out=True)  # reachable but opted out

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 0
        assert b["opted_out_count"] == 1
        assert b["no_channel_count"] == 0
        assert b["already_active_count"] == 0
        assert b["account_empty"] is False

    def test_already_active_only(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        ct = _mk(account, user_a, email="a@x.io")

        first = _body(_enroll_account(authed_api_a, c, account))
        assert first["contacts_enrolled"] == 1

        b = _body(_enroll_account(authed_api_a, c, account))  # re-enroll
        assert b["contacts_enrolled"] == 0
        assert b["already_active_count"] == 1
        assert b["no_channel_count"] == 0
        assert b["opted_out_count"] == 0
        assert b["account_empty"] is False

    def test_account_empty(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)  # account has NO contacts

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 0
        assert b["account_empty"] is True
        assert b["no_channel_count"] == 0
        assert b["opted_out_count"] == 0
        assert b["already_active_count"] == 0

    def test_overlap_opted_out_and_no_channel_counts_as_opted_out(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        _mk(account, user_a, email=None, phone=None, linkedin=None, opted_out=True)  # both

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["opted_out_count"] == 1
        assert b["no_channel_count"] == 0  # opted_out takes precedence

    def test_overlap_opted_out_and_already_active_counts_as_opted_out(self, authed_api_a, account, user_a):
        c = _campaign(account, user_a)
        ct = _mk(account, user_a, email="a@x.io")

        assert _body(_enroll_account(authed_api_a, c, account))["contacts_enrolled"] == 1

        # The contact opts out AFTER becoming active.
        ct.opted_out = True
        ct.save(user=user_a)

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["opted_out_count"] == 1
        assert b["already_active_count"] == 0  # opted_out takes precedence

    def test_mixed_dataset_invariant(self, authed_api_a, account, user_a):
        """opted_out + no_channel + already_active + enrolled == considered_total (4)."""
        c = _campaign(account, user_a)
        fresh = _mk(account, user_a, email="fresh@x.io")
        active = _mk(account, user_a, email="active@x.io")
        _mk(account, user_a, email=None, phone=None)                 # no channel
        _mk(account, user_a, email="opted@x.io", opted_out=True)     # opted out

        # Make `active` already-active via a single-contact enroll first.
        assert _body(_enroll_contact(authed_api_a, c, account, active))["contacts_enrolled"] == 1

        b = _body(_enroll_account(authed_api_a, c, account))
        assert b["contacts_enrolled"] == 1          # only `fresh`
        assert b["already_active_count"] == 1        # `active`
        assert b["no_channel_count"] == 1
        assert b["opted_out_count"] == 1
        assert b["account_empty"] is False

        considered_total = 4
        assert (
            b["opted_out_count"]
            + b["no_channel_count"]
            + b["already_active_count"]
            + b["contacts_enrolled"]
            == considered_total
        )
