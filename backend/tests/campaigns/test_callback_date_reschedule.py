# backend/tests/campaigns/test_callback_date_reschedule.py
"""
Editable callback date + chain reschedule (D7).

A campaign chain's dates are otherwise fixed, but the CALLBACK step's
scheduled_date is editable. Moving it recales the remaining regular steps behind
the new date via the existing cascade — nothing else changes:

    - only a callback move triggers the cascade (guard is_callback_followup);
    - an ordinary step edit cascades nothing;
    - an edit that does not change the date cascades nothing;
    - positions and the contact's CALLBACK_PENDING status are untouched;
    - the recale happens on the PATCH write path, never a GET (Q6-safe).

Tests cover the service method directly and the PATCH endpoint end to end
(including that ActivitySerializer now exposes is_callback_followup, without
which the front-end freezes the field).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityStatus
from app_modules.campaigns.constants import CampaignContactStatus
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)


def _svc(user_a, account):
    return CampaignExecutionService(user=user_a, client_id=account.client_id)


def _detail_url(activity):
    return f'/module-activities/{activity.id}/'


def _chain(make_campaign_activity, cc, today):
    """A callback at position 2 followed by two real-delay regular steps."""
    callback = make_campaign_activity(
        cc, scheduled_date=today + timedelta(days=3), sequence_position=2,
        is_callback_followup=True,
    )
    step3 = make_campaign_activity(
        cc, scheduled_date=today + timedelta(days=10), sequence_position=3,
        min_delay_days=7,
    )
    step4 = make_campaign_activity(
        cc, scheduled_date=today + timedelta(days=17), sequence_position=4,
        min_delay_days=7,
    )
    return callback, step3, step4


# =============================================================================
# SERVICE — reschedule_after_callback_date_change
# =============================================================================

@pytest.mark.django_db
class TestRescheduleService:

    def test_cascades_following_steps_from_new_date(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.CALLBACK_PENDING,
                                   callback_date=today + timedelta(days=3))
        callback, step3, step4 = _chain(make_campaign_activity, cc, today)

        svc = _svc(user_a, account)
        new_date = today + timedelta(days=30)
        callback.scheduled_date = new_date
        callback.save(user=user_a)

        svc.reschedule_after_callback_date_change(callback)

        step3.refresh_from_db()
        step4.refresh_from_db()
        # step3 anchored at new_date + its own delay; step4 follows step3.
        assert step3.scheduled_date == svc._next_business_day(new_date + timedelta(days=7))
        assert step4.scheduled_date == svc._next_business_day(
            step3.scheduled_date + timedelta(days=7)
        )

    def test_noop_for_ordinary_step(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        ordinary = make_campaign_activity(cc, scheduled_date=today, sequence_position=2)
        step3 = make_campaign_activity(cc, scheduled_date=today + timedelta(days=10),
                                       sequence_position=3, min_delay_days=7)

        # Not a callback -> the guard makes this a no-op.
        _svc(user_a, account).reschedule_after_callback_date_change(ordinary)

        step3.refresh_from_db()
        assert step3.scheduled_date == today + timedelta(days=10)

    def test_preserves_contact_status(
        self, campaign, make_campaign_contact, make_campaign_activity, user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.CALLBACK_PENDING,
                                   callback_date=today + timedelta(days=3))
        callback, _step3, _step4 = _chain(make_campaign_activity, cc, today)

        callback.scheduled_date = today + timedelta(days=20)
        callback.save(user=user_a)
        _svc(user_a, account).reschedule_after_callback_date_change(callback)

        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.CALLBACK_PENDING


# =============================================================================
# PATCH endpoint — the wiring (viewset guard + serializer field)
# =============================================================================

@pytest.mark.django_db
class TestCallbackDatePatch:

    def test_patch_callback_date_triggers_cascade(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity,
        user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.CALLBACK_PENDING,
                                   callback_date=today + timedelta(days=3))
        callback, step3, step4 = _chain(make_campaign_activity, cc, today)

        new_date = today + timedelta(days=30)
        resp = authed_api_a.patch(
            _detail_url(callback),
            {'scheduled_date': new_date.isoformat(),
             'scheduled_time': None, 'due_date': None},
            format='json',
        )
        assert resp.status_code == 200, resp.data
        # Serializer now exposes the callback marker (without it the UI freezes).
        assert resp.data['data']['is_callback_followup'] is True

        svc = _svc(user_a, account)
        step3.refresh_from_db()
        step4.refresh_from_db()
        assert step3.scheduled_date == svc._next_business_day(new_date + timedelta(days=7))
        assert step4.scheduled_date == svc._next_business_day(
            step3.scheduled_date + timedelta(days=7)
        )
        # The move does not resume the contact.
        cc.refresh_from_db()
        assert cc.status == CampaignContactStatus.CALLBACK_PENDING

    def test_patch_ordinary_step_date_does_not_cascade(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity,
        user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
        step2 = make_campaign_activity(cc, scheduled_date=today, sequence_position=2)
        step3 = make_campaign_activity(cc, scheduled_date=today + timedelta(days=10),
                                       sequence_position=3, min_delay_days=7)

        resp = authed_api_a.patch(
            _detail_url(step2),
            {'scheduled_date': (today + timedelta(days=25)).isoformat(),
             'scheduled_time': None, 'due_date': None},
            format='json',
        )
        assert resp.status_code == 200, resp.data
        # Ordinary step edited: its own date moves, but nothing cascades.
        step3.refresh_from_db()
        assert step3.scheduled_date == today + timedelta(days=10)

    def test_patch_callback_same_date_no_cascade(
        self, authed_api_a, campaign, make_campaign_contact, make_campaign_activity,
        user_a, account
    ):
        today = timezone.now().date()
        cc = make_campaign_contact(status=CampaignContactStatus.CALLBACK_PENDING,
                                   callback_date=today + timedelta(days=3))
        callback, step3, _step4 = _chain(make_campaign_activity, cc, today)
        original_step3 = step3.scheduled_date

        # PATCH the same date (e.g. only notes-like fields would change) — no move.
        resp = authed_api_a.patch(
            _detail_url(callback),
            {'scheduled_date': callback.scheduled_date.isoformat(),
             'scheduled_time': None, 'due_date': None},
            format='json',
        )
        assert resp.status_code == 200, resp.data
        step3.refresh_from_db()
        assert step3.scheduled_date == original_step3
