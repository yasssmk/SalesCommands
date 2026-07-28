# backend/tests/campaigns/test_meetings_source_activity_attribution.py
"""
MEETINGS objective — third attribution branch: Activity.source_activity.campaign.

A completed MEETING created on a PRE-EXISTING decision cycle, from a campaign
context, was counted by neither existing branch: the preexisting cycle has
``source_campaign=None`` (the backfill does not run on that path) and the modal
never sets ``Activity.campaign``. But the activity was born from a campaign
sequence, so its ``source_activity`` (the sequence activity) carries the
campaign. This locks the union to THREE branches:

    decision_cycle.source_campaign == camp
    OR Activity.campaign == camp
    OR Activity.source_activity.campaign == camp   (new)

Each branch is an isolated correlated EXISTS (no fan-out); a meeting attributable
by several branches is one Activity row, counted once. ``source_activity`` is
nullable — an activity without one must not error.

Product rule: this widens ACTIVITY attribution only. DECISION_CYCLES stays
attributed by the cycle's OWN source_campaign — a preexisting cycle never starts
counting there. A guard test locks that.

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    _meetings_by_campaign,
)
from app_modules.decision_cycles.models import DecisionCycle

TODAY = timezone.now().date()


def _campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _cycle(owner, account, ca, *, source_campaign=None, name='dc'):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign)
    dc.save(user=owner, client_id=ca.id)
    return dc


def _activity(owner, account, ca, *, campaign=None, decision_cycle=None,
              source_activity=None, activity_type=ActivityType.MEETING,
              status_=ActivityStatus.COMPLETED, name='m'):
    a = Activity(title=name, activity_type=activity_type, status=status_,
                 outcome='SUCCESSFUL', account=account, owner=owner,
                 campaign=campaign, decision_cycle=decision_cycle,
                 source_activity=source_activity, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _svc(ca):
    return CampaignAnalyticsService(client_id=ca.id)


# ---------------------------------------------------------------------------
# REPRO — meeting on a PREEXISTING cycle, attributed only via source_activity.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSourceActivityBranch:

    def test_meeting_on_existing_cycle_counted_via_source_activity(
            self, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        # Preexisting DC, created OUTSIDE the campaign -> source_campaign None.
        existing_dc = _cycle(user_a, account, client_account_a, source_campaign=None)
        # The campaign sequence activity that triggered the meeting (carries camp).
        seq = _activity(user_a, account, client_account_a, campaign=camp,
                        activity_type=ActivityType.CALL, name='seq')
        # The meeting: campaign None, cycle preexisting (no source_campaign), but
        # source_activity is the campaign sequence activity.
        _activity(user_a, account, client_account_a, campaign=None,
                  decision_cycle=existing_dc, source_activity=seq, name='mtg')

        # Both old branches fail; the new source_activity branch attributes it.
        assert _svc(client_account_a)._count_meetings(camp) == 1

    def test_activity_without_source_activity_does_not_error(
            self, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        # meeting attributed only via Activity.campaign, source_activity None.
        _activity(user_a, account, client_account_a, campaign=camp,
                  decision_cycle=None, source_activity=None)
        assert _svc(client_account_a)._count_meetings(camp) == 1


# ---------------------------------------------------------------------------
# Existing branches still count; no double counting across branches.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnionThreeBranches:

    def test_all_three_origins_and_no_double_count(self, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        other = _campaign(user_a, client_account_a, name='Other')
        dc_camp = _cycle(user_a, account, client_account_a, source_campaign=camp)
        dc_none = _cycle(user_a, account, client_account_a, source_campaign=None, name='dcN')
        seq = _activity(user_a, account, client_account_a, campaign=camp,
                        activity_type=ActivityType.CALL, name='seq')

        # (1) cycle branch only
        _activity(user_a, account, client_account_a, campaign=None,
                  decision_cycle=dc_camp, source_activity=None, name='cyc')
        # (2) Activity.campaign branch only
        _activity(user_a, account, client_account_a, campaign=camp,
                  decision_cycle=None, source_activity=None, name='camp')
        # (3) source_activity branch only (preexisting cycle, no campaign)
        _activity(user_a, account, client_account_a, campaign=None,
                  decision_cycle=dc_none, source_activity=seq, name='src')
        # (all three at once) -> must count ONCE
        _activity(user_a, account, client_account_a, campaign=camp,
                  decision_cycle=dc_camp, source_activity=seq, name='all')
        # decoys: other campaign via each vector
        seq_other = _activity(user_a, account, client_account_a, campaign=other,
                              activity_type=ActivityType.CALL, name='seqO')
        _activity(user_a, account, client_account_a, campaign=other, name='cO')
        _activity(user_a, account, client_account_a, campaign=None,
                  source_activity=seq_other, name='sO')
        # non-meeting / non-completed excluded
        _activity(user_a, account, client_account_a, campaign=camp,
                  activity_type=ActivityType.CALL, name='call')
        _activity(user_a, account, client_account_a, campaign=camp,
                  status_=ActivityStatus.PLANNED, name='planned')

        assert _svc(client_account_a)._count_meetings(camp) == 4   # 1+2+3+all(once)


# ---------------------------------------------------------------------------
# list <-> detail parity: the batch applies the SAME three-branch union.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_batch_matches_detail_for_source_activity_cohort(user_a, client_account_a, account):
    camp = _campaign(user_a, client_account_a)
    existing_dc = _cycle(user_a, account, client_account_a, source_campaign=None)
    seq = _activity(user_a, account, client_account_a, campaign=camp,
                    activity_type=ActivityType.CALL, name='seq')
    _activity(user_a, account, client_account_a, campaign=None,
              decision_cycle=existing_dc, source_activity=seq, name='mtg')

    detail = _svc(client_account_a)._count_meetings(camp)
    batch = _meetings_by_campaign([camp.id]).get(camp.id, 0)
    assert detail == 1
    assert batch == detail


# ---------------------------------------------------------------------------
# GUARD: DECISION_CYCLES is NOT widened — a preexisting cycle with a campaign
# activity on it does NOT start counting toward DECISION_CYCLES.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_decision_cycles_not_affected_by_source_activity(user_a, client_account_a, account):
    camp = _campaign(user_a, client_account_a)
    existing_dc = _cycle(user_a, account, client_account_a, source_campaign=None)
    seq = _activity(user_a, account, client_account_a, campaign=camp,
                    activity_type=ActivityType.CALL, name='seq')
    # a campaign meeting on the preexisting cycle (would count for MEETINGS)
    _activity(user_a, account, client_account_a, campaign=None,
              decision_cycle=existing_dc, source_activity=seq, name='mtg')
    # and a cycle correctly attributed by its own source_campaign
    _cycle(user_a, account, client_account_a, source_campaign=camp, name='owned')

    svc = _svc(client_account_a)
    # MEETINGS counts the meeting on the preexisting cycle...
    assert svc._count_meetings(camp) == 1
    # ...but DECISION_CYCLES counts ONLY the cycle whose OWN source_campaign is
    # the campaign — the preexisting cycle stays out.
    assert svc._count_decision_cycles(camp) == 1
