# backend/tests/campaigns/test_enroll_from_territories_reachable_parity.py
"""
Characterization / parity tests for the reachable-channel filter at site #5,
CampaignCreationService._enroll_from_territories (territory-based OUTBOUND
enrollment), which has BOTH branches:

    - default (channel_override != NO_CALLS): email OR phone
    - NO_CALLS (channel_override == NO_CALLS): email present only

They exercise the REAL method (no simulation) on a campaign whose territories
resolve the seeded account, and assert the EXACT set of contacts pre-created as
CampaignContacts. This pins the current behaviour before the two inline
predicates are swapped onto Contact.filter_reachable, proving the swap is
iso-behaviour per branch.

Channel matrix (same for both branches):
    email-only, phone-only, both, no-channel, opted-out(+channel),
    and the former debt case email='' + phone=NULL (no real channel).

Expected retained set:
    - default    : {email-only, phone-only, both}   (debt excluded since E2)
    - NO_CALLS : {email-only, both}   (phone-only w/o email is the core exclusion)

Real method, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.campaigns.constants import CampaignType
from app_modules.campaigns.models import Campaign, CampaignContact
from app_modules.campaigns.services.campaign_creation_service import CampaignCreationService
from app_modules.contacts.models import Contact
from app_modules.territories.models import Territory

NO_CALLS = 'NO_CALLS'


def _mk(account, user_a, *, email, phone, opted_out=False):
    """
    Contact in `account` whose email/phone_number columns hold EXACTLY the given
    values (None -> SQL NULL, '' -> empty string, str -> literal), set via raw
    SQL so the NULL/'' distinction is deterministic.
    """
    c = Contact(account=account, first_name="C", last_name="X", opted_out=opted_out)
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts SET email=%s, phone_number=%s WHERE id=%s",
            [email, phone, str(c.id)],
        )
    return c


def _seed_matrix(account, user_a):
    """Seed the channel matrix; return the individual contacts by role."""
    return {
        'email': _mk(account, user_a, email="e1@x.io", phone=None),
        'phone': _mk(account, user_a, email=None, phone="+14155550001"),
        'both': _mk(account, user_a, email="e2@x.io", phone="+14155550002"),
        'none': _mk(account, user_a, email=None, phone=None),
        'opted': _mk(account, user_a, email="e3@x.io", phone="+14155550003", opted_out=True),
        'debt': _mk(account, user_a, email="", phone=None),
    }


def _empty_territory(user_a, client_id):
    """Territory with an empty filter_definition -> resolves ALL tenant accounts."""
    t = Territory(name='All Tenant', owner=user_a, filter_definition={})
    t.save(user=user_a, client_id=client_id)
    return t


def _outbound_campaign(user_a, client_id, *, channel_override='AUTO'):
    today = timezone.now().date()
    c = Campaign(
        name='Territory Outbound',
        campaign_type=CampaignType.OUTBOUND,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        channel_override=channel_override,
    )
    c.save(user=user_a, client_id=client_id)
    return c


def _enrolled_contact_ids(campaign):
    return set(
        CampaignContact.objects.filter(
            campaign_account__campaign=campaign
        ).values_list("contact_id", flat=True)
    )


@pytest.mark.django_db
class TestEnrollFromTerritoriesReachableParity:

    def test_default_branch_enrolls_email_or_phone(self, account, user_a, client_account_a):
        """Default channel_override: pre-create reachable = email OR phone (debt excluded)."""
        m = _seed_matrix(account, user_a)
        territory = _empty_territory(user_a, client_account_a.id)
        campaign = _outbound_campaign(user_a, client_account_a.id, channel_override='AUTO')
        campaign.territories.add(territory)

        CampaignCreationService(user=user_a, client_id=client_account_a.id)\
            ._enroll_from_territories(campaign)

        # m['debt'] (email='' + phone=NULL) has no real channel -> excluded (E2 fix).
        assert _enrolled_contact_ids(campaign) == {
            m['email'].id, m['phone'].id, m['both'].id,
        }

    def test_email_only_branch_enrolls_email_present_only(self, account, user_a, client_account_a):
        """NO_CALLS: pre-create only contacts with a non-empty email; phone-only excluded."""
        m = _seed_matrix(account, user_a)
        territory = _empty_territory(user_a, client_account_a.id)
        campaign = _outbound_campaign(user_a, client_account_a.id, channel_override=NO_CALLS)
        campaign.territories.add(territory)

        CampaignCreationService(user=user_a, client_id=client_account_a.id)\
            ._enroll_from_territories(campaign)

        assert _enrolled_contact_ids(campaign) == {m['email'].id, m['both'].id}
