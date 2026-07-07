# backend/tests/campaigns/test_playlist.py
"""
Campaign playlist endpoint tests.

Covers the three guarantees of the read-only playlist refactor:
  1. GET /campaigns/<id>/playlist/ performs zero writes (no UPDATE/INSERT).
  2. Overdue-chain rescheduling now happens on the log-response POST flow.
  3. The optional `limit` param slices results after the priority sort while
     total_count stays the pre-slice total.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus
from app_modules.campaigns.constants import CampaignContactStatus


def _playlist_url(campaign):
    return f'/campaigns/{campaign.id}/playlist/'


def _log_response_url(campaign):
    return f'/campaigns/{campaign.id}/log-response/'


class TestPlaylistIsReadOnly:
    @pytest.mark.django_db
    def test_get_playlist_issues_no_writes(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        # An overdue step — under the old behaviour the GET would have
        # rescheduled (written) this row.
        make_campaign_activity(
            cc, scheduled_date=today - timedelta(days=3), sequence_position=1
        )

        with CaptureQueriesContext(connection) as ctx:
            resp = authed_api_a.get(_playlist_url(campaign))

        assert resp.status_code == 200

        writes = [
            q['sql']
            for q in ctx.captured_queries
            if q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT'))
        ]
        assert writes == [], f'playlist GET issued write queries: {writes}'


class TestRescheduleOnLogResponse:
    @pytest.mark.django_db
    def test_log_response_reschedules_overdue_chain(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()

        # Overdue chain on one contact: first step in the past, plus a later
        # step to prove the cascade runs from the anchored first step.
        cc_over = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        over_1 = make_campaign_activity(
            cc_over, scheduled_date=today - timedelta(days=3), sequence_position=1
        )
        over_2 = make_campaign_activity(
            cc_over,
            scheduled_date=today - timedelta(days=1),
            sequence_position=2,
            min_delay_days=2,
        )

        # A second contact whose activity we log a response on — this drives
        # process_result, which now triggers the campaign-scoped reschedule.
        cc_trig = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        trig = make_campaign_activity(
            cc_trig, scheduled_date=today, sequence_position=1
        )

        resp = authed_api_a.post(
            _log_response_url(campaign),
            {'activity_id': str(trig.id), 'response': 'NO_RESPONSE'},
            format='json',
        )
        assert resp.status_code == 200

        over_1.refresh_from_db()
        over_2.refresh_from_db()

        # First overdue step anchored to today; the later step cascaded forward.
        assert over_1.scheduled_date == today
        assert over_1.status == ActivityStatus.PLANNED
        assert over_2.scheduled_date >= today


class TestPlaylistLimit:
    @pytest.mark.django_db
    def test_limit_slices_results_but_total_count_is_pre_slice(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()
        # Three eligible contacts, each with one first-step activity due today.
        for _ in range(3):
            cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
            make_campaign_activity(cc, scheduled_date=today, sequence_position=1)

        resp = authed_api_a.get(_playlist_url(campaign), {'limit': 2})
        assert resp.status_code == 200
        data = resp.data['data']
        assert len(data['results']) == 2
        assert data['total_count'] == 3

    @pytest.mark.django_db
    def test_no_limit_returns_all(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()
        for _ in range(3):
            cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
            make_campaign_activity(cc, scheduled_date=today, sequence_position=1)

        resp = authed_api_a.get(_playlist_url(campaign))
        assert resp.status_code == 200
        data = resp.data['data']
        assert len(data['results']) == 3
        assert data['total_count'] == 3

    @pytest.mark.django_db
    def test_limit_is_clamped_to_at_least_one(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity
    ):
        today = timezone.now().date()
        for _ in range(3):
            cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
            make_campaign_activity(cc, scheduled_date=today, sequence_position=1)

        resp = authed_api_a.get(_playlist_url(campaign), {'limit': 0})
        assert resp.status_code == 200
        data = resp.data['data']
        assert len(data['results']) == 1
        assert data['total_count'] == 3

    @pytest.mark.django_db
    def test_invalid_limit_returns_400(self, authed_api_a, campaign):
        resp = authed_api_a.get(_playlist_url(campaign), {'limit': 'abc'})
        assert resp.status_code == 400
