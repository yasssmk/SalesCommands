# backend/tests/campaigns/test_generation_channel_variants.py
"""
E7 — Per-channel sequence-variant generation, exercised through the REAL
generation path (_generate_for_account -> _extract_contacts ->
generate_activities_for_contact -> SequenceDispatcher), NOT a dispatcher
simulation. This is the playlist-facing path the reps actually see.

The campaign carries a sequence_type ('OUTBOUND'), so generation runs the
per-contact channel-variant branch (campaign_execution_service.py:192-247) and
stamps each generated Activity with its ActivityType. Each test asserts the
exact set of ActivityType values produced for one contact, pinning the routing
in base_sequence.get_sequence_for_channels:

    phone + email            -> STANDARD       {CALL, EMAIL}
    phone + LinkedIn no email -> WITHOUT_EMAIL  {CALL, LINKEDIN}   <-- E7 core
    email only               -> WITHOUT_PHONE  {EMAIL}
    phone only               -> PHONE_ONLY     {CALL}

RED before the fix: has_linkedin is computed from a nonexistent attribute
(getattr(contact, 'linkedin_url', None) -> always None), so a phone + LinkedIn
contact without an email is misrouted to PHONE_ONLY and gets NO LinkedIn step.
The WITHOUT_EMAIL test fails until the typo is fixed to read the real field
`linkedin`. The three other tests are non-regression guards: green before AND
after the fix.

The linkedin column is written via raw SQL as the REAL model field `linkedin`
(core/models.py) — deliberately not the buggy 'linkedin_url' attribute.

Real generation path, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignType, CampaignStatus, CampaignAccountStatus, ChannelOverride,
)
from app_modules.campaigns.models import Campaign, CampaignAccount
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)
from app_modules.contacts.models import Contact


def _mk(account, user_a, *, email, phone, linkedin):
    """
    Contact in `account` whose email / phone_number / linkedin columns hold
    EXACTLY the given values (None -> SQL NULL, str -> literal), set via raw SQL
    so the NULL distinction is deterministic. `linkedin` is the REAL model field
    (core/models.py), NOT the 'linkedin_url' attribute the service typo reads.
    """
    c = Contact(account=account, first_name="C", last_name="X")
    c.save(user=user_a, client_id=account.client_id)
    with connection.cursor() as cur:
        cur.execute(
            "UPDATE module_contacts "
            "SET email=%s, phone_number=%s, linkedin=%s WHERE id=%s",
            [email, phone, linkedin, str(c.id)],
        )
    return c


def _campaign(user_a, client_id, *, sequence_type='OUTBOUND',
              channel_override=ChannelOverride.AUTO):
    """
    ACTIVE OUTBOUND campaign WITH a sequence_type, so generation runs the
    per-channel variant path (not the single-CALL no-sequence path).
    """
    today = timezone.now().date()
    c = Campaign(
        name='GenVariants',
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.ACTIVE,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
        sequence_type=sequence_type,
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


def _types_for_contact(campaign, contact):
    """Set of ActivityType values generated for one contact in this campaign."""
    return set(
        Activity.objects.filter(campaign=campaign, campaign_contact__contact=contact)
        .values_list('activity_type', flat=True)
    )


@pytest.mark.django_db
class TestGenerationChannelVariants:

    def test_phone_and_linkedin_without_email_generates_linkedin_steps(
        self, account, user_a, client_account_a
    ):
        """
        E7 CORE (RED before fix): phone + LinkedIn, NO email -> WITHOUT_EMAIL,
        which replaces email steps with LinkedIn steps. On the buggy code
        has_linkedin is always False, so the contact is misrouted to PHONE_ONLY
        and no LINKEDIN activity exists -> this fails RED.
        """
        contact = _mk(
            account, user_a,
            email=None, phone="+14155550001",
            linkedin="https://www.linkedin.com/in/gero",
        )
        campaign = _campaign(user_a, client_account_a.id)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        types = _types_for_contact(campaign, contact)
        assert ActivityType.LINKEDIN in types, (
            "phone + LinkedIn without email must generate LinkedIn steps "
            f"(WITHOUT_EMAIL variant); got {sorted(types)}"
        )
        assert ActivityType.EMAIL not in types, "no email channel -> no EMAIL step"
        assert ActivityType.CALL in types, "WITHOUT_EMAIL keeps the calls"

    def test_linkedin_only_generates_linkedin_only(
        self, account, user_a, client_account_a
    ):
        """
        E8 CORE (RED before the LINKEDIN_ONLY branch exists): a contact with
        ONLY LinkedIn (no phone, no email) must get a 100% LinkedIn sequence.
        Before E8 the routing has no branch for (F, F, True), so the contact
        falls through to the STANDARD fallback and receives calls + emails
        (channels it does not even have) -> this fails RED until LINKEDIN_ONLY
        is added and routed before the fallback.
        """
        contact = _mk(
            account, user_a,
            email=None, phone=None,
            linkedin="https://www.linkedin.com/in/gero",
        )
        campaign = _campaign(user_a, client_account_a.id)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        types = _types_for_contact(campaign, contact)
        assert types == {ActivityType.LINKEDIN}, (
            "LinkedIn-only contact must get a 100% LinkedIn sequence "
            f"(LINKEDIN_ONLY variant); got {sorted(types)}"
        )

    def test_phone_and_email_generates_standard_no_linkedin(
        self, account, user_a, client_account_a
    ):
        """Non-regression guard — STANDARD: calls + emails, never LinkedIn."""
        contact = _mk(
            account, user_a,
            email="both@x.io", phone="+14155550002", linkedin=None,
        )
        campaign = _campaign(user_a, client_account_a.id)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        assert _types_for_contact(campaign, contact) == {
            ActivityType.CALL, ActivityType.EMAIL,
        }

    def test_email_only_generates_without_phone(
        self, account, user_a, client_account_a
    ):
        """Non-regression guard — WITHOUT_PHONE: email only, no calls/LinkedIn."""
        contact = _mk(
            account, user_a,
            email="mail@x.io", phone=None, linkedin=None,
        )
        campaign = _campaign(user_a, client_account_a.id)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        assert _types_for_contact(campaign, contact) == {ActivityType.EMAIL}

    def test_phone_only_generates_phone_only(
        self, account, user_a, client_account_a
    ):
        """Non-regression guard — PHONE_ONLY: calls only."""
        contact = _mk(
            account, user_a,
            email=None, phone="+14155550003", linkedin=None,
        )
        campaign = _campaign(user_a, client_account_a.id)
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        assert _types_for_contact(campaign, contact) == {ActivityType.CALL}


@pytest.mark.django_db
class TestNoCallsGeneration:
    """
    E9a.2 — NO_CALLS = never call; reachable on email OR LinkedIn.

    Exercised through the real _generate_for_account path on an OUTBOUND
    campaign with channel_override=NO_CALLS. NO_CALLS forces has_phone=False,
    so routing lands on WITHOUT_PHONE (contact has an email) or LINKEDIN_ONLY
    (contact has LinkedIn but no email). A contact with neither email nor
    LinkedIn is not reachable and gets nothing.
    """

    def test_linkedin_only_contact_enrolls_as_linkedin_only(
        self, account, user_a, client_account_a
    ):
        """
        E9a.2 CORE (RED before the filter change): a LinkedIn-only contact
        (no phone, no email) in a NO_CALLS campaign must be enrolled and get a
        100% LinkedIn sequence. Under the legacy strict-email filter the contact
        is excluded (no activity at all) -> this fails RED until NO_CALLS accepts
        email OR LinkedIn.
        """
        contact = _mk(
            account, user_a,
            email=None, phone=None,
            linkedin="https://www.linkedin.com/in/gero",
        )
        campaign = _campaign(
            user_a, client_account_a.id, channel_override=ChannelOverride.NO_CALLS
        )
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        types = _types_for_contact(campaign, contact)
        assert types == {ActivityType.LINKEDIN}, (
            "LinkedIn-only contact must be enrolled in NO_CALLS and get a 100% "
            f"LinkedIn sequence (LINKEDIN_ONLY); got {sorted(types)}"
        )

    def test_email_contact_gets_without_phone_no_calls(
        self, account, user_a, client_account_a
    ):
        """Guard — a contact with an email in NO_CALLS gets WITHOUT_PHONE: emails only, never a call."""
        contact = _mk(
            account, user_a,
            email="mail@x.io", phone="+14155550009", linkedin=None,
        )
        campaign = _campaign(
            user_a, client_account_a.id, channel_override=ChannelOverride.NO_CALLS
        )
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        types = _types_for_contact(campaign, contact)
        assert types == {ActivityType.EMAIL}, (
            f"NO_CALLS with an email -> WITHOUT_PHONE (no CALL); got {sorted(types)}"
        )

    def test_phone_only_contact_not_enrolled_in_no_calls(
        self, account, user_a, client_account_a
    ):
        """Guard — a phone-only contact (no email, no LinkedIn) is unreachable in NO_CALLS: no activity."""
        contact = _mk(
            account, user_a,
            email=None, phone="+14155550010", linkedin=None,
        )
        campaign = _campaign(
            user_a, client_account_a.id, channel_override=ChannelOverride.NO_CALLS
        )
        ca = _campaign_account(campaign, account, user_a)

        CampaignExecutionService(user=user_a, client_id=client_account_a.id)\
            ._generate_for_account(campaign, ca, ActivityType.CALL)

        assert _types_for_contact(campaign, contact) == set()
