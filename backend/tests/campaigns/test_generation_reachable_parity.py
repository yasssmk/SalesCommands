# backend/tests/campaigns/test_generation_reachable_parity.py
"""
Characterization / parity tests for the reachable-channel filter at site #6,
CampaignExecutionService._extract_contacts, exercised through the REAL activity
generation path (_generate_for_account -> _extract_contacts -> per-contact
activity generation). This is the playlist-facing path.

_extract_contacts has BOTH branches:

    - default (channel_override != EMAIL_ONLY): email OR phone
    - EMAIL_ONLY (channel_override == EMAIL_ONLY): email present only

The tests use a CampaignAccount with NO target_contacts and NO
target_departments, so _extract_contacts takes the account-wide path that runs
the channel predicate (site #6) — NOT the target_contacts early-return at the
top of the method (which has no channel filter and is out of scope here).

The campaign has no sequence_type, so generation creates exactly one CALL
activity per extracted contact; the set of contacts that receive an activity is
therefore the set _extract_contacts returned. Each test asserts that exact set,
pinning the current behaviour before the inline predicates are swapped onto
Contact.filter_reachable.

Channel matrix (same for both branches):
    email-only, phone-only, both, no-channel, opted-out(+channel),
    and the former debt case email='' + phone=NULL (no real channel).

Expected set with an activity:
    - default    : {email-only, phone-only, both}   (debt excluded since E2)
    - EMAIL_ONLY : {email-only, both}

Real generation path, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignType, CampaignStatus, CampaignAccountStatus,
)
from app_modules.campaigns.models import Campaign, CampaignAccount
from app_modules.campaigns.services.campaign_execution_service import CampaignExecutionService
from app_modules.contacts.models import Contact

EMAIL_ONLY = 'EMAIL_ONLY'


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
    return {
        'email': _mk(account, user_a, email="e1@x.io", phone=None),
        'phone': _mk(account, user_a, email=None, phone="+14155550001"),
        'both': _mk(account, user_a, email="e2@x.io", phone="+14155550002"),
        'none': _mk(account, user_a, email=None, phone=None),
        'opted': _mk(account, user_a, email="e3@x.io", phone="+14155550003", opted_out=True),
        'debt': _mk(account, user_a, email="", phone=None),
    }


def _campaign(user_a, client_id, *, channel_override='AUTO'):
    """ACTIVE TARGETED campaign, no sequence_type (1 CALL activity per contact)."""
    today = timezone.now().date()
    c = Campaign(
        name='Gen',
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
        channel_override=channel_override,
    )
    c.save(user=user_a, client_id=client_id)
    return c


def _campaign_account(campaign, account, user_a):
    ca = CampaignAccount(
        campaign=campaign, account=account,
        status=CampaignAccountStatus.IN_PROGRESS,
    )
    ca.save(user=user_a, client_id=account.client_id)
    return ca


def _contacts_with_activities(campaign):
    return set(
        Activity.objects.filter(campaign=campaign)
        .exclude(campaign_contact__contact=None)
        .values_list('campaign_contact__contact_id', flat=True)
    )


@pytest.mark.django_db
class TestGenerationReachableParity:

    def test_default_branch_generates_for_email_or_phone(self, account, user_a, client_account_a):
        """Default: activities generated for reachable = email OR phone (debt excluded)."""
        m = _seed_matrix(account, user_a)
        campaign = _campaign(user_a, client_account_a.id, channel_override='AUTO')
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        # m['debt'] (email='' + phone=NULL) has no real channel -> excluded (E2 fix).
        assert _contacts_with_activities(campaign) == {
            m['email'].id, m['phone'].id, m['both'].id,
        }

    def test_email_only_branch_generates_for_email_present_only(self, account, user_a, client_account_a):
        """EMAIL_ONLY: activities generated only for contacts with a non-empty email."""
        m = _seed_matrix(account, user_a)
        campaign = _campaign(user_a, client_account_a.id, channel_override=EMAIL_ONLY)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        assert _contacts_with_activities(campaign) == {m['email'].id, m['both'].id}
