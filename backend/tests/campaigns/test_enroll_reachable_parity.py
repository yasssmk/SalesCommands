# backend/tests/campaigns/test_enroll_reachable_parity.py
"""
Characterization / parity tests for the reachable-channel filter at the four
campaign_account_views.py enrollment sites (#1-#4), exercised through the REAL
endpoints:

    - enroll-target  type=CONTACT     (#2)
    - enroll-target  type=DEPARTMENT  (#3)
    - enroll-target  type=ACCOUNT     (#4)
    - bulk-add       (ACTIVE campaign pre-creates CampaignContacts)   (#1)

Each test seeds the SAME channel matrix in the account and asserts the EXACT
set of contacts that ends up enrolled. This pins the current behaviour before
the inline predicates are swapped onto Contact.filter_reachable, so the swap is
proven iso-behaviour (and any drift turns red).

Reachable (enrolled) = email-only, phone-only, both. Excluded = no channel,
opted-out (even with a channel), and the former debt case email='' + phone=NULL
(no real channel — excluded since the E2 exclude fix). Real endpoints,
Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign, CampaignContact
from app_modules.contacts.models import Contact

ENROLL_URL = "/campaigns/accounts/enroll-target/"
BULK_ADD_URL = "/campaigns/accounts/bulk-add/"


def _active_targeted_campaign(account, user_a):
    """TARGETED ACTIVE campaign with no pre-created CampaignAccount."""
    today = timezone.now().date()
    c = Campaign(
        name="Parity",
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


def _mk(account, user_a, *, email, phone, opted_out=False, dept=None):
    """
    Contact in `account` whose email/phone_number columns hold EXACTLY the given
    values (None -> SQL NULL, '' -> empty string, str -> literal), set via raw
    SQL so the NULL/'' distinction is deterministic.
    """
    c = Contact(
        account=account, first_name="C", last_name="X",
        opted_out=opted_out, standard_department=dept,
    )
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s WHERE id=%s",
            [email, phone, str(c.id)],
        )
    return c


def _seed_matrix(account, user_a, dept=None):
    """
    Seed the channel matrix. Returns (reachable_ids, all_ids).
    reachable = email-only, phone-only, both.
    excluded  = no-channel, opted-out(with channel), and the former debt case
                email='' + phone=NULL (no real channel — excluded since E2).
    """
    c_email = _mk(account, user_a, email="e1@x.io", phone=None, dept=dept)
    c_phone = _mk(account, user_a, email=None, phone="+14155550001", dept=dept)
    c_both = _mk(account, user_a, email="e2@x.io", phone="+14155550002", dept=dept)
    c_none = _mk(account, user_a, email=None, phone=None, dept=dept)
    c_opted = _mk(account, user_a, email="e3@x.io", phone="+14155550003",
                  opted_out=True, dept=dept)
    c_debt = _mk(account, user_a, email="", phone=None, dept=dept)

    reachable = {c_email.id, c_phone.id, c_both.id}
    all_ids = reachable | {c_none.id, c_opted.id, c_debt.id}
    return reachable, all_ids


def _enrolled_contact_ids(campaign):
    return set(
        CampaignContact.objects.filter(
            campaign_account__campaign=campaign
        ).values_list("contact_id", flat=True)
    )


@pytest.mark.django_db
class TestEnrollReachableParity:

    def test_enroll_target_contact_mode(self, authed_api_a, account, user_a):
        """#2 — enroll-target type=CONTACT enrolls exactly the reachable contacts."""
        campaign = _active_targeted_campaign(account, user_a)
        reachable, all_ids = _seed_matrix(account, user_a)

        resp = authed_api_a.post(ENROLL_URL, data={
            "campaign_id": str(campaign.id),
            "account_id": str(account.id),
            "type": "CONTACT",
            "contact_ids": [str(i) for i in all_ids],
        }, format="json")
        assert resp.status_code in (200, 201), resp.data

        assert _enrolled_contact_ids(campaign) == reachable

    # enroll-target DEPARTMENT and ACCOUNT modes were removed (S13 sub-step 4):
    # enrollment is contact-by-contact only. The reachable-channel predicate is
    # still exercised for CONTACT mode (test_enroll_target_contact_mode above) and
    # for territory pre-creation (test_bulk_add_active_precreates_reachable below).

    def test_bulk_add_active_precreates_reachable(self, authed_api_a, account, user_a):
        """#1 — bulk-add on an ACTIVE campaign pre-creates CampaignContacts for reachable contacts only."""
        campaign = _active_targeted_campaign(account, user_a)
        reachable, _all_ids = _seed_matrix(account, user_a)

        resp = authed_api_a.post(BULK_ADD_URL, data={
            "campaign_id": str(campaign.id),
            "account_ids": [str(account.id)],
        }, format="json")
        assert resp.status_code in (200, 201), resp.data

        assert _enrolled_contact_ids(campaign) == reachable
