# backend/tests/campaigns/test_callback_sequence_position.py
"""
Callback insertion renumbering — inserting a callback must not collide with the
step it precedes.

Product defect: on a real-delay chain, requesting a callback creates the callback
activity at position P+1 while the existing next step still sits at P+1 — two
activities share a position, so the "Step N" chips are wrong and the timeline is
out of order. The fix shifts every later step of the contact up by one before
inserting the callback, keeping positions contiguous and unique.

RED before fix: test_callback_insertion_keeps_positions_contiguous asserts
unique, contiguous positions; it fails today because the callback duplicates
position P+1 (positions come out [1, 2, 2, 3]).

Iso (must stay green): a chain with no callback keeps its positions untouched
(the renumber is guarded by is_callback_followup), and the manual follow-up path
on a non-sequence campaign shifts nothing.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityOutcome
from app_modules.campaigns.constants import CampaignContactStatus
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


def _positions(cc):
    return sorted(
        Activity.objects.filter(campaign_contact=cc).values_list(
            'sequence_position', flat=True
        )
    )


@pytest.mark.django_db
class TestCallbackSequencePosition:

    def test_callback_insertion_keeps_positions_contiguous(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """RED before fix: inserting a callback on a real-delay chain must leave
        contiguous, unique positions — the callback at the slot of the step it
        precedes, later steps shifted up by one."""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)

        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        # Real delays (not 0 days), as a launched sequence would carry.
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=2, min_delay_days=7)
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=14),
                               sequence_position=3, min_delay_days=7)

        _svc(user_a, account).process_result(
            step1,
            {'outcome': ActivityOutcome.CALLBACK_REQUESTED,
             'callback_date': today + timedelta(days=3)},
        )

        # Contiguous 1,2,3,4 with no duplicate.
        positions = _positions(cc)
        assert positions == [1, 2, 3, 4], positions
        assert len(positions) == len(set(positions))  # no collision

        # The callback takes the position of the step it precedes (P+1 = 2).
        callback = Activity.objects.get(
            campaign_contact=cc, is_callback_followup=True
        )
        assert callback.sequence_position == 2

        # The former steps 2 and 3 shift up to 3 and 4.
        later = list(
            Activity.objects.filter(campaign_contact=cc, is_callback_followup=False)
            .exclude(id=step1.id)
            .order_by('sequence_position')
            .values_list('sequence_position', flat=True)
        )
        assert later == [3, 4], later

    def test_chain_without_callback_keeps_positions(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Iso: logging a non-callback outcome never shifts positions — the
        renumber is guarded by is_callback_followup."""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=2, min_delay_days=7)
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=14),
                               sequence_position=3, min_delay_days=7)

        _svc(user_a, account).process_result(
            step1, {'outcome': ActivityOutcome.NO_ANSWER, 'callback_date': None}
        )

        assert _positions(cc) == [1, 2, 3]

    def test_manual_followup_non_sequence_does_not_shift(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Iso: the manual follow-up path (non-sequence campaign,
        is_callback_followup=False) inserts a follow-up without shifting the
        contact's existing steps."""
        today = timezone.now().date()
        # The fixture campaign has no sequence_type -> manual follow-up path.
        assert not campaign.sequence_type
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        step1 = make_campaign_activity(cc, scheduled_date=today, sequence_position=1)
        step2 = make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                                       sequence_position=2, min_delay_days=7)

        _svc(user_a, account).process_result(
            step1,
            {'outcome': ActivityOutcome.OTHER, 'callback_date': None,
             'next_activity_type': 'CALL'},
        )

        # The existing step keeps its position — the shift did NOT fire.
        step2.refresh_from_db()
        assert step2.sequence_position == 2
        # And a manual follow-up was created (is_callback_followup=False).
        assert (
            Activity.objects.filter(campaign_contact=cc, is_callback_followup=False)
            .exclude(id__in=[step1.id, step2.id])
            .exists()
        )
