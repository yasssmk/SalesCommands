# backend/tests/campaigns/test_noanswer_exhausted_completed.py
"""
Reclassify the natural end of a chasing sequence.

Product rule (BUG 2): a TARGETED contact whose sequence runs to its last step
without ever answering (final outcome NO_ANSWER, no PLANNED activity left) has
FINISHED its sequence — that is a COMPLETED contact, not a STOPPED one. STOPPED
must stay reserved for genuine stops: a franc terminal outcome (NOT_INTERESTED,
…), a manual stop, a campaign close, a bulk cancel.

The whole scenario is driven through the REAL entry point
`CampaignExecutionService.process_result` (the path the smoke test exercises),
never by setting the status by hand — hand-set fixtures have masked this exact
class of bug before.

The first test is the RED repro: before the fix, the exhausted sequence lands on
STOPPED and the COMPLETED assertion fails. The iso guards (mid-sequence NO_ANSWER
stays IN_PROGRESS; a terminal outcome still STOPS) stay green throughout, proving
the change is a targeted reclassification and not an over-correction.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignType,
    CampaignStatus,
    CampaignAccountStatus,
    CampaignContactStatus,
)
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


def _targeted_active(campaign, cc, user_a):
    """Make the chain a running TARGETED campaign with an IN_PROGRESS account, so
    the account-completion cascade is a valid transition once the contact ends."""
    campaign.campaign_type = CampaignType.TARGETED
    campaign.status = CampaignStatus.ACTIVE
    campaign.save(user=user_a)
    ca = cc.campaign_account
    ca.status = CampaignAccountStatus.IN_PROGRESS
    ca.save(user=user_a)


@pytest.mark.django_db
class TestNoAnswerExhaustedReclassified:

    def test_noanswer_to_last_step_completes_contact(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """RED before fix: NO_ANSWER through the last step (sequence exhausted)
        must finish the contact as COMPLETED, not STOPPED."""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        _targeted_active(campaign, cc, user_a)

        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        step2 = make_campaign_activity(
            cc, scheduled_date=today + timedelta(days=3), sequence_position=2
        )

        # Step 1 NO_ANSWER — a step remains, sequence continues.
        _svc(user_a, account).process_result(step1, {"outcome": "NO_ANSWER"})
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS

        # Step 2 NO_ANSWER — last step, sequence exhausted → COMPLETED.
        _svc(user_a, account).process_result(step2, {"outcome": "NO_ANSWER"})
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.COMPLETED

        # The causal reason must survive on the contact — this is a no-answer
        # completion, not a commercial success.
        assert cc.notes and "no answer" in cc.notes.lower()
        assert "exhausted" in cc.notes.lower()

    def test_noanswer_midsequence_does_not_complete(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Iso: a NO_ANSWER with a PLANNED step still remaining keeps the contact
        IN_PROGRESS — only the exhausted last step reclassifies."""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        _targeted_active(campaign, cc, user_a)

        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        make_campaign_activity(
            cc, scheduled_date=today + timedelta(days=3), sequence_position=2
        )

        _svc(user_a, account).process_result(step1, {"outcome": "NO_ANSWER"})
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS

    def test_terminal_outcome_still_stops(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Iso (no over-correction): a franc terminal outcome (NOT_INTERESTED)
        still STOPS the contact, even on the last step."""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        _targeted_active(campaign, cc, user_a)

        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)

        _svc(user_a, account).process_result(step1, {"outcome": "NOT_INTERESTED"})
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.STOPPED
