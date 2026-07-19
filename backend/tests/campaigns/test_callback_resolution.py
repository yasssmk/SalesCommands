# backend/tests/campaigns/test_callback_resolution.py
"""
Callback resolution — logging the callback lifts the CALLBACK_PENDING pause.

Product rule: the log of the CALLBACK activity (is_callback_followup=True), and
nothing else, returns the contact from CALLBACK_PENDING to IN_PROGRESS and clears
callback_date — whether logged on the callback day or ahead of it.

Iso (unchanged): a terminal callback outcome keeps its final state (SUCCESSFUL ->
COMPLETED, terminal -> STOPPED); logging an ordinary step never resumes a paused
contact; and a fresh callback requested in the same log keeps CALLBACK_PENDING
with the new date.

The first test is the RED repro (a non-terminal callback log leaves the contact
CALLBACK_PENDING today); the fix turns it green with the iso guards staying green.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignAccountStatus, CampaignContactStatus,
)
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


def _start_account(cc, user_a):
    """Put the contact's account IN_PROGRESS (as a launched campaign would), so a
    terminal outcome's account-completion cascade is a valid transition."""
    ca = cc.campaign_account
    ca.status = CampaignAccountStatus.IN_PROGRESS
    ca.save(user=user_a)


@pytest.mark.django_db
class TestCallbackResolution:

    def test_logging_callback_non_terminal_resumes_contact(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """RED before fix: logging the callback with a non-terminal outcome must
        return the contact to IN_PROGRESS and clear callback_date."""
        today = timezone.now().date()
        cc = make_campaign_contact(
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date=today + timedelta(days=5),
        )
        callback = make_campaign_activity(
            cc, scheduled_date=today, sequence_position=2, is_callback_followup=True
        )
        # A remaining regular step so NO_ANSWER continues (does not exhaust->stop).
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=3)

        _svc(user_a, account).process_result(
            callback, {'outcome': 'NO_ANSWER', 'callback_date': None}
        )

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS
        assert cc.callback_date is None

    def test_logging_callback_early_resumes_contact(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Logging the callback AHEAD of its date resumes the contact just the
        same — it is the log of the callback that lifts the status, not the date."""
        today = timezone.now().date()
        cc = make_campaign_contact(
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date=today + timedelta(days=5),
        )
        # The callback activity is scheduled in the future; the rep logs it now.
        callback = make_campaign_activity(
            cc, scheduled_date=today + timedelta(days=5), sequence_position=2,
            is_callback_followup=True,
        )
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=3)

        _svc(user_a, account).process_result(
            callback, {'outcome': 'NO_ANSWER', 'callback_date': None}
        )

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.IN_PROGRESS
        assert cc.callback_date is None

    def test_terminal_callback_keeps_final_state(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Terminal outcomes on the callback keep the final state — never
        IN_PROGRESS: SUCCESSFUL -> COMPLETED, terminal -> STOPPED."""
        today = timezone.now().date()

        cc_ok = make_campaign_contact(
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date=today + timedelta(days=5),
        )
        cb_ok = make_campaign_activity(
            cc_ok, scheduled_date=today, sequence_position=2, is_callback_followup=True
        )
        _start_account(cc_ok, user_a)
        _svc(user_a, account).process_result(
            cb_ok, {'outcome': 'SUCCESSFUL', 'callback_date': None}
        )
        cc_ok.refresh_from_db()
        assert cc_ok.status == CampaignContactStatus.COMPLETED

        cc_ko = make_campaign_contact(
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date=today + timedelta(days=5),
        )
        cb_ko = make_campaign_activity(
            cc_ko, scheduled_date=today, sequence_position=2, is_callback_followup=True
        )
        _start_account(cc_ko, user_a)
        _svc(user_a, account).process_result(
            cb_ko, {'outcome': 'NOT_INTERESTED', 'callback_date': None}
        )
        cc_ko.refresh_from_db()
        assert cc_ko.status == CampaignContactStatus.STOPPED

    def test_logging_ordinary_step_does_not_resume(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """Resolution is carried by the CALLBACK activity only: logging an
        ordinary step of a CALLBACK_PENDING contact leaves the pause in place."""
        today = timezone.now().date()
        cc = make_campaign_contact(
            status=CampaignContactStatus.CALLBACK_PENDING,
            callback_date=today + timedelta(days=5),
        )
        ordinary = make_campaign_activity(
            cc, scheduled_date=today, sequence_position=2, is_callback_followup=False
        )
        make_campaign_activity(cc, scheduled_date=today + timedelta(days=7),
                               sequence_position=3)

        _svc(user_a, account).process_result(
            ordinary, {'outcome': 'NO_ANSWER', 'callback_date': None}
        )

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.CALLBACK_PENDING

    def test_fresh_callback_requested_stays_pending(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        """A log that requests a callback (has_callback) posts CALLBACK_PENDING
        and the resume must NOT fire — the `not has_callback` guard. (The contact
        starts IN_PROGRESS: re-requesting a callback while already
        CALLBACK_PENDING hits a separate pre-existing transition limitation,
        out of scope here.)"""
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        callback = make_campaign_activity(
            cc, scheduled_date=today, sequence_position=2, is_callback_followup=True
        )
        new_date = today + timedelta(days=10)

        _svc(user_a, account).process_result(
            callback,
            {'outcome': 'NO_ANSWER', 'callback_date': new_date, 'callback_time': None},
        )

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.CALLBACK_PENDING
        assert cc.callback_date == new_date
