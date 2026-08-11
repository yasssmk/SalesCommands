# backend/tests/campaigns/test_campaign_is_inactive.py
"""
Campaign inactivity — is_inactive annotated on the queryset (single source).

is_inactive is a VISUAL SIGNAL (prompt the rep to resume or drop a sleeping
campaign), not an exact metric. It is computed set-based via
Campaign.objects.with_inactivity() so a whole list is marked in ONE query —
never a per-instance property (which would N+1 a list of campaigns).

Rule (edge cases deliberately NOT refined — PO):
    reference_date = MAX(completed_at) over the campaign's COMPLETED activities,
                     OR created_at when nothing is completed yet.
    is_inactive    = campaign OPEN (status not terminal: not COMPLETED /
                     not CANCELLED) AND reference_date older than
                     N_INACTIVE_DAYS days.

Only COMPLETED activities count — PLANNED / ON_HOLD never move the clock.
Applies to every campaign type. Postgres 5432, --reuse-db.
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
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(account, user_a, *, status, created_days_ago=None,
                   campaign_type=CampaignType.OUTBOUND, name="Inactivity probe"):
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=campaign_type,
        status=status,
        owner=user_a,
        planned_start_date=today - timedelta(days=90),
        planned_end_date=today + timedelta(days=90),
    )
    c.save(user=user_a, client_id=account.client_id)

    if created_days_ago is not None:
        old = timezone.now() - timedelta(days=created_days_ago)
        Campaign.objects.filter(pk=c.pk).update(created_at=old)
        c.refresh_from_db()
    return c


def _add_activity(account, user_a, campaign, *, status, completed_days_ago=None,
                  scheduled_days_ahead=None):
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


def _flag(campaign):
    """Read the annotated is_inactive for a single campaign (fresh query)."""
    from app_modules.campaigns.models import Campaign
    return Campaign.objects.with_inactivity().get(pk=campaign.pk).is_inactive


# ---------------------------------------------------------------------------
# OPEN campaign — last DONE activity drives the reference date
# ---------------------------------------------------------------------------

def test_open_campaign_last_done_older_than_threshold_is_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE, created_days_ago=200)
    _add_activity(account, user_a, c, status=ActivityStatus.COMPLETED,
                  completed_days_ago=N_INACTIVE_DAYS + 5)

    assert _flag(c) is True


def test_open_campaign_recent_done_is_not_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE, created_days_ago=200)
    _add_activity(account, user_a, c, status=ActivityStatus.COMPLETED, completed_days_ago=1)

    assert _flag(c) is False


# ---------------------------------------------------------------------------
# OPEN campaign — no DONE activity → fall back to created_at
# ---------------------------------------------------------------------------

def test_open_campaign_no_done_activity_old_creation_is_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5)

    assert _flag(c) is True


def test_open_campaign_no_done_activity_recent_creation_is_not_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE, created_days_ago=1)

    assert _flag(c) is False


# ---------------------------------------------------------------------------
# CRUCIAL — only DONE activities count; PLANNED never reset the clock
# ---------------------------------------------------------------------------

def test_recent_planned_activities_do_not_prevent_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5)
    _add_activity(account, user_a, c, status=ActivityStatus.PLANNED, scheduled_days_ahead=2)
    _add_activity(account, user_a, c, status=ActivityStatus.ON_HOLD, scheduled_days_ahead=1)

    assert _flag(c) is True


# ---------------------------------------------------------------------------
# Terminal campaigns are never inactive, however stale
# ---------------------------------------------------------------------------

def test_completed_campaign_is_never_inactive(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.COMPLETED, created_days_ago=500)

    assert _flag(c) is False


def test_cancelled_campaign_is_never_inactive(account, user_a):
    # Campaign has no STOPPED status — CANCELLED is the terminal "stopped" state.
    c = _make_campaign(account, user_a, status=CampaignStatus.CANCELLED, created_days_ago=500)

    assert _flag(c) is False


# ---------------------------------------------------------------------------
# Applies to Targeted campaigns too (no exclusion)
# ---------------------------------------------------------------------------

def test_targeted_campaign_is_covered(account, user_a):
    c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                       created_days_ago=N_INACTIVE_DAYS + 5,
                       campaign_type=CampaignType.TARGETED)

    assert _flag(c) is True


# ---------------------------------------------------------------------------
# ANTI-N+1 — a whole list is marked in a single query
# ---------------------------------------------------------------------------

def test_with_inactivity_is_a_single_query_for_a_list(account, user_a,
                                                       django_assert_num_queries):
    from app_modules.campaigns.models import Campaign

    pks = []
    for i in range(4):
        c = _make_campaign(account, user_a, status=CampaignStatus.ACTIVE,
                           created_days_ago=N_INACTIVE_DAYS + 5, name=f"C{i}")
        _add_activity(account, user_a, c, status=ActivityStatus.COMPLETED,
                      completed_days_ago=N_INACTIVE_DAYS + 5)
        pks.append(c.pk)

    qs = Campaign.objects.with_inactivity().filter(pk__in=pks)

    # One SELECT for the whole list; reading .is_inactive per row hits no DB.
    with django_assert_num_queries(1):
        flags = {c.pk: c.is_inactive for c in qs}

    assert all(flags.values()) is True
    assert len(flags) == 4
