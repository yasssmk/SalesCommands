# backend/tests/campaigns/test_campaign_contact_transitions.py
"""
CampaignContact state-machine transition tests.

Focus: terminal-state re-transitions are an idempotent no-op, while
distinct terminal-to-terminal transitions still raise. Also covers a
regular non-terminal transition to guard against over-broad short-circuit.
"""

import pytest

from app_modules.campaigns.constants import CampaignContactStatus
from core.exceptions import StandardizedValidationError


class TestTerminalSameStatusNoOp:
    """COMPLETED -> COMPLETED and STOPPED -> STOPPED are silent no-ops."""

    @pytest.mark.django_db
    def test_completed_to_completed_is_noop(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.COMPLETED)

        result = cc.mark_completed(notes='re-completed')

        assert result == {
            'previous_status': CampaignContactStatus.COMPLETED,
            'new_status': CampaignContactStatus.COMPLETED,
        }
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.COMPLETED
        # Notes update remains allowed on the idempotent path.
        assert cc.notes == 're-completed'

    @pytest.mark.django_db
    def test_completed_to_completed_without_notes_preserves_notes(
        self, make_campaign_contact
    ):
        cc = make_campaign_contact(
            status=CampaignContactStatus.COMPLETED, notes='original'
        )

        cc.mark_completed()

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.COMPLETED
        assert cc.notes == 'original'

    @pytest.mark.django_db
    def test_stopped_to_stopped_is_noop(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.STOPPED)

        result = cc.mark_stopped(notes='re-stopped')

        assert result == {
            'previous_status': CampaignContactStatus.STOPPED,
            'new_status': CampaignContactStatus.STOPPED,
        }
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.STOPPED


class TestDistinctTerminalTransitionsStillRaise:
    """Terminal -> different terminal must still be rejected."""

    @pytest.mark.django_db
    def test_completed_to_stopped_raises(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.COMPLETED)

        with pytest.raises(StandardizedValidationError):
            cc.mark_stopped()

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.COMPLETED

    @pytest.mark.django_db
    def test_stopped_to_completed_raises(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.STOPPED)

        with pytest.raises(StandardizedValidationError):
            cc.mark_completed()

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.STOPPED


class TestRegularTransitionsUnaffected:
    """A normal, allowed transition still succeeds and persists."""

    @pytest.mark.django_db
    def test_pending_to_in_progress(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.PENDING)

        result = cc.start_progress()

        assert result['previous_status'] == CampaignContactStatus.PENDING
        assert result['new_status'] == CampaignContactStatus.IN_PROGRESS
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS

    @pytest.mark.django_db
    def test_in_progress_to_completed(self, make_campaign_contact):
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)

        cc.mark_completed(notes='won')

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.COMPLETED
        assert cc.notes == 'won'
