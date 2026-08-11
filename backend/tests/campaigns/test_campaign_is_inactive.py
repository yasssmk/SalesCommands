# backend/tests/campaigns/test_campaign_is_inactive.py
"""
Campaign.is_inactive — read-time inactivity flag.

Product rule (locked):
    reference_date = MAX(completed_at) of DONE (COMPLETED) activities of the
                     campaign, OR campaign.created_at when none is done yet.
    is_inactive    = campaign is OPEN (status not terminal: not COMPLETED /
                     not CANCELLED) AND (now - reference_date).days
                     > N_INACTIVE_DAYS.

Only COMPLETED activities move the reference date — PLANNED / ON_HOLD / future
activities must never count. Applies to ALL campaign types (Targeted included).

No stored field: the property aggregates at read-time. Postgres 5432, --reuse-db.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignStatus,
    CampaignType,
    N_INACTIVE_DAYS,
)
from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers — build campaigns / activities with full control over the dates
# ---------------------------------------------------------------------------

def _make_campaign(account, user_a, *, status, created_days_ago=None,
                   campaign_type=CampaignType.OUTBOUND):
    """Create a campaign in a given status, optionally backdating created_at."""
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name="Inactivity probe",
        campaign_type=campaign_type,
        status=status,
        owner=user_a,
        planned_start_date=today - timedelta(days=90),
        planned_end_date=today + timedelta(days=90),
    )
    c.save(user=user_a, client_id=account.client_id)

    if created_days_ago is not None:
        old = timezone.now() - timedelta(days=created_days_ago)
        # created_at is auto_now_add — bypass it with a raw UPDATE.
        Campaign.objects.filter(pk=c.pk).update(created_at=old)
        c.refresh_from_db()
    return c


def _add_activity(account, user_a, campaign, *, status, completed_days_ago=None,
                  scheduled_days_ahead=None):
    """Attach one activity to the campaign, controlling completed_at."""
    from app_modules.activities.models import Activity

    today = timezone.now().date()
    a = Activity(
        title="probe",
        activity_type=ActivityType.CALL,
        status=status,
        account=account,
        owner=user_a,
        campaign=campaign,
    )
    if scheduled_days_ahead is not None:
        a.scheduled_date = today + timedelta(days=scheduled_days_ahead)
    if completed_days_ago is not None:
        a.completed_at = timezone.now() - timedelta(days=completed_days_ago)
    a.save(user=user_a, client_id=account.client_id)
    return a


# ---------------------------------------------------------------------------
# OPEN campaign — last DONE activity drives the reference date
# ---------------------------------------------------------------------------

def test_open_campaign_last_done_older_than_threshold_is_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=200)
    _add_activity(account, user_a, c, status=ActivityStatus.COMPLETED,
                  completed_days_ago=N_INACTIVE_DAYS + 5)

    assert c.is_inactive is True


def test_open_campaign_recent_done_is_not_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=200)
    _add_activity(account, user_a, c, status=ActivityStatus.COMPLETED,
                  completed_days_ago=1)

    assert c.is_inactive is False


# ---------------------------------------------------------------------------
# OPEN campaign — no DONE activity → fall back to created_at
# ---------------------------------------------------------------------------

def test_open_campaign_no_done_activity_old_creation_is_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5)

    assert c.is_inactive is True


def test_open_campaign_no_done_activity_recent_creation_is_not_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=1)

    assert c.is_inactive is False


# ---------------------------------------------------------------------------
# CRUCIAL — only DONE activities count; PLANNED never reset the clock
# ---------------------------------------------------------------------------

def test_recent_planned_activities_do_not_prevent_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5)
    # Fresh work scheduled ahead, but nothing has actually been DONE.
    _add_activity(account, user_a, c, status=ActivityStatus.PLANNED,
                  scheduled_days_ahead=2)
    _add_activity(account, user_a, c, status=ActivityStatus.ON_HOLD,
                  scheduled_days_ahead=1)

    assert c.is_inactive is True


# ---------------------------------------------------------------------------
# Terminal campaigns are never inactive, however stale
# ---------------------------------------------------------------------------

def test_completed_campaign_is_never_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.COMPLETED,
                       created_days_ago=500)

    assert c.is_inactive is False


def test_cancelled_campaign_is_never_inactive(account, user_a):
    # Campaign has no STOPPED status — CANCELLED is the terminal "stopped" state.
    c = _make_campaign(account, user_a, status=CampaignStatus.CANCELLED,
                       created_days_ago=500)

    assert c.is_inactive is False


# ---------------------------------------------------------------------------
# Applies to Targeted campaigns too (no exclusion)
# ---------------------------------------------------------------------------

def test_targeted_campaign_is_covered(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5,
                       campaign_type=CampaignType.TARGETED)

    assert c.is_inactive is True
