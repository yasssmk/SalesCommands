# backend/tests/campaigns/test_activity_title.py
"""
Campaign activity titles — structured, groupable, no mutable data.

Format: "<PREFIX> · <campaign> · <account> › <contact> — <step_name>"
The head "<PREFIX> · <campaign>" is common to every activity of the same
campaign (visual grouping); only step_name varies within a chain, and a callback
reads "… — Callback". Neither the scheduled date nor a step number appears — both
are mutable and must never be frozen into the name.

The prefix is a property of the sequence (OUT for Outbound, TGT for Targeted);
a campaign with no sequence falls back to the generic "CMP".
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityOutcome, ActivityStatus
from app_modules.campaigns.constants import CampaignContactStatus, CampaignType
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


# =============================================================================
# HELPER — pure format, no DB
# =============================================================================

class TestBuildActivityTitleFormat:
    """_build_activity_title composes the validated format for every case."""

    def _svc(self):
        # No __init__ DB work — the helper is pure string composition.
        return CampaignExecutionService(user=None, client_id="c1")

    def _stub(self, sequence_type, name="Q3 Outbound"):
        campaign = SimpleNamespace(name=name, sequence_type=sequence_type)
        account = SimpleNamespace(company_name="CAPSULE CORP")
        contact = SimpleNamespace(first_name="Bulma", last_name="Brief")
        return campaign, account, contact

    def test_outbound_prefix(self):
        c, a, ct = self._stub("OUTBOUND")
        title = self._svc()._build_activity_title(c, a, ct, "Follow-up Email")
        assert title == "OUT · Q3 Outbound · CAPSULE CORP › Bulma Brief — Follow-up Email"

    def test_targeted_prefix_omits_campaign_name(self):
        # An account is in a single Targeted campaign, so the name is redundant
        # and dropped: head is "TGT · <account>", not "TGT · <campaign> · …".
        c, a, ct = self._stub("TARGETED", name="Warm Q3")
        title = self._svc()._build_activity_title(c, a, ct, "Gentle Follow-up Email")
        assert title == "TGT · CAPSULE CORP › Bulma Brief — Gentle Follow-up Email"
        assert "Warm Q3" not in title

    def test_callback_shares_head(self):
        c, a, ct = self._stub("OUTBOUND")
        step = self._svc()._build_activity_title(c, a, ct, "Follow-up Email")
        callback = self._svc()._build_activity_title(c, a, ct, "Callback")
        # Same head, only the step name differs -> a united chain.
        head = "OUT · Q3 Outbound · CAPSULE CORP › Bulma Brief — "
        assert step.startswith(head) and callback == head + "Callback"

    def test_no_sequence_falls_back_to_cmp(self):
        c, a, ct = self._stub("", name="Ad-hoc Push")
        title = self._svc()._build_activity_title(c, a, ct, "Follow-up")
        assert title == "CMP · Ad-hoc Push · CAPSULE CORP › Bulma Brief — Follow-up"

    def test_no_date_no_step_number(self):
        c, a, ct = self._stub("OUTBOUND")
        title = self._svc()._build_activity_title(c, a, ct, "Second Call Attempt")
        assert "Step" not in title
        assert "2026" not in title and "-" not in title.split("—")[0]


# =============================================================================
# GENERATION — real sequence engine, DB
# =============================================================================

@pytest.mark.django_db
class TestGeneratedTitles:
    """Driving the real generator yields the structured title with no mutable bits."""

    def _campaign_with_sequence(self, account, user_a, sequence_type):
        from app_modules.campaigns.models import Campaign, CampaignAccount

        today = timezone.now().date()
        c = Campaign(
            name='Q3 Outbound',
            campaign_type=CampaignType.OUTBOUND,
            sequence_type=sequence_type,
            owner=user_a,
            planned_start_date=today,
            planned_end_date=today + timedelta(days=30),
            actual_start_date=today,
        )
        c.save(user=user_a, client_id=account.client_id)
        ca = CampaignAccount(campaign=c, account=account)
        ca.save(user=user_a, client_id=account.client_id)
        return c, ca

    def _contact_with_channels(self, account, user_a):
        from app_modules.contacts.models import Contact

        c = Contact(
            account=account,
            first_name='Bulma',
            last_name='Brief',
            email='bulma@capsule.corp',
            phone_number='+33123456789',
        )
        c.save(user=user_a, client_id=account.client_id)
        return c

    def _first_step_title(self, campaign_contact):
        return (
            Activity.objects.filter(
                campaign_contact=campaign_contact,
                is_callback_followup=False,
            )
            .order_by('sequence_position')
            .first()
            .title
        )

    def test_outbound_generated_title(self, account, user_a):
        campaign, ca = self._campaign_with_sequence(account, user_a, 'OUTBOUND')
        contact = self._contact_with_channels(account, user_a)

        _svc(user_a, account).generate_activities_for_contact(campaign, ca, contact)

        from app_modules.campaigns.models import CampaignContact
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)

        title = self._first_step_title(cc)
        # Standard Outbound step 1 = "Initial Outreach Call".
        assert title == (
            "OUT · Q3 Outbound · " + account.company_name
            + " › Bulma Brief — Initial Outreach Call"
        )
        # The two mutable elements are gone.
        assert "Step" not in title
        assert str(timezone.now().year) not in title

    def test_targeted_generated_title(self, account, user_a):
        campaign, ca = self._campaign_with_sequence(account, user_a, 'TARGETED')
        contact = self._contact_with_channels(account, user_a)

        _svc(user_a, account).generate_activities_for_contact(campaign, ca, contact)

        from app_modules.campaigns.models import CampaignContact
        cc = CampaignContact.objects.get(campaign_account=ca, contact=contact)

        title = self._first_step_title(cc)
        # Targeted omits the campaign name: head is "TGT · <account>".
        assert title.startswith("TGT · " + account.company_name + " › Bulma Brief — ")
        assert campaign.name not in title
        assert "Step" not in title
        assert str(timezone.now().year) not in title


# =============================================================================
# CALLBACK — wiring through process_result
# =============================================================================

@pytest.mark.django_db
class TestCallbackTitle:
    """A logged callback creates an activity whose title shares the chain head."""

    def test_callback_activity_title(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        # Real generated activities carry the contact; the fixture does not, so
        # attach it to mirror production before logging the callback.
        step1.contacts.add(cc.contact)
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=2, min_delay_days=7)

        _svc(user_a, account).process_result(
            step1,
            {'outcome': ActivityOutcome.CALLBACK_REQUESTED,
             'callback_date': today + timedelta(days=3)},
        )

        callback = Activity.objects.get(campaign_contact=cc, is_callback_followup=True)
        # The fixture campaign has no sequence_type -> CMP fallback; step = Callback.
        contact = cc.contact
        contact_name = f"{contact.first_name} {contact.last_name}".strip()
        assert callback.title == (
            f"CMP · {campaign.name} · {account.company_name} › {contact_name} — Callback"
        )
        assert "Step" not in callback.title
        assert str(today.year) not in callback.title
