# backend/tests/campaigns/test_meetings_campaign_attribution.py
"""
MEETINGS campaign objective — attribution by the UNION of the two origins.

The MEETINGS objective counts completed MEETING activities of a campaign. A
meeting can reach a campaign two ways, and neither field alone captures both:

- (A) the meeting is logged inside a decision cycle of the campaign — the modal
  sets ``decision_cycle`` (+ step) but NEVER ``Activity.campaign`` (it stays
  None), and the cycle carries ``source_campaign`` (backfill). The old
  ``Activity.campaign`` filter MISSED these — the reported bug.
- (B) the meeting is a campaign meeting with no cycle — ``Activity.campaign`` is
  set, ``decision_cycle`` is None. A cycle-only filter would MISS these.

Because ``Activity.decision_cycle`` is nullable (a meeting need not have a
cycle), the fix counts a meeting for the campaign when EITHER its cycle's
``source_campaign`` is the campaign OR ``Activity.campaign`` is the campaign.
The cycle side is an isolated correlated EXISTS (no fan-out).

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.decision_cycles.models import DecisionCycle

TODAY = timezone.now().date()
CWE_URL = '/module-activities/create-with-entities/'


def _campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _cycle(owner, account, ca, *, source_campaign, name='dc'):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign)
    dc.save(user=owner, client_id=ca.id)
    return dc


def _meeting(owner, account, ca, *, campaign=None, decision_cycle=None,
             activity_type=ActivityType.MEETING, status_=ActivityStatus.COMPLETED,
             name='m'):
    a = Activity(title=name, activity_type=activity_type, status=status_,
                 outcome='SUCCESSFUL', account=account, owner=owner,
                 campaign=campaign, decision_cycle=decision_cycle,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _svc(ca):
    return CampaignAnalyticsService(client_id=ca.id)


# ---------------------------------------------------------------------------
# REPRO — cohort (A): meeting in a campaign DC, Activity.campaign is None.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSymptomRepro:

    def test_meeting_in_campaign_cycle_is_counted(self, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        dc = _cycle(user_a, account, client_account_a, source_campaign=camp)
        # The exact modal state: campaign=None, decision_cycle set (source_campaign=camp).
        _meeting(user_a, account, client_account_a, campaign=None, decision_cycle=dc)

        # OLD Activity.campaign filter returned 0 (campaign is None) — the bug.
        assert _svc(client_account_a)._count_meetings(camp) == 1


# ---------------------------------------------------------------------------
# UNION SCOPE — both origins counted, once each; other campaigns excluded.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnionScope:

    def test_counts_both_origins_without_double_counting(
            self, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        other = _campaign(user_a, client_account_a, name='Other')
        dc = _cycle(user_a, account, client_account_a, source_campaign=camp)
        dc_other = _cycle(user_a, account, client_account_a,
                          source_campaign=other, name='dcO')

        # (A) cycle-only origin: campaign None, cycle in camp.
        _meeting(user_a, account, client_account_a, campaign=None, decision_cycle=dc, name='A')
        # (B) campaign-only origin: campaign set, no cycle.
        _meeting(user_a, account, client_account_a, campaign=camp, decision_cycle=None, name='B')
        # (both) campaign set AND cycle in camp -> counted ONCE.
        _meeting(user_a, account, client_account_a, campaign=camp, decision_cycle=dc, name='both')
        # decoys: another campaign via cycle, and via Activity.campaign.
        _meeting(user_a, account, client_account_a, campaign=None, decision_cycle=dc_other, name='dO')
        _meeting(user_a, account, client_account_a, campaign=other, decision_cycle=None, name='cO')
        # not a meeting / not completed -> excluded.
        _meeting(user_a, account, client_account_a, campaign=camp,
                 activity_type=ActivityType.CALL, name='call')
        _meeting(user_a, account, client_account_a, campaign=camp,
                 status_=ActivityStatus.PLANNED, name='planned')

        assert _svc(client_account_a)._count_meetings(camp) == 3   # A + B + both (once)

    def test_scope_differs_from_old_activity_campaign_filter(
            self, user_a, client_account_a, account):
        """Documents the perimeter shift: the cohort (A) that the old
        Activity.campaign filter counted as 0 now counts. The old-filter value is
        recomputed inline for the comparison."""
        camp = _campaign(user_a, client_account_a)
        dc = _cycle(user_a, account, client_account_a, source_campaign=camp)
        _meeting(user_a, account, client_account_a, campaign=None, decision_cycle=dc)

        old_filter = Activity.objects.filter(
            campaign=camp, activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
        ).count()
        new_value = _svc(client_account_a)._count_meetings(camp)

        assert old_filter == 0        # what production saw
        assert new_value == 1         # the fix

    def test_list_batch_meetings_matches_detail_union(
            self, user_a, client_account_a, account):
        """The list card's batch MEETINGS tally uses the SAME union as the
        detail calc, so list and detail never disagree for a cohort-(A) meeting
        (cycle-only, Activity.campaign None)."""
        from app_modules.campaigns.services.campaign_objective_progress import (
            _meetings_by_campaign,
        )
        camp = _campaign(user_a, client_account_a)
        dc = _cycle(user_a, account, client_account_a, source_campaign=camp)
        _meeting(user_a, account, client_account_a, campaign=None, decision_cycle=dc)  # (A)
        _meeting(user_a, account, client_account_a, campaign=camp, decision_cycle=None)  # (B)

        detail = _svc(client_account_a)._count_meetings(camp)
        batch = _meetings_by_campaign([camp.id]).get(camp.id, 0)
        assert detail == 2
        assert batch == detail


# ---------------------------------------------------------------------------
# CONTRACT — real modal path (Activity.campaign not set) is counted.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestContractRealModalPath:

    def test_meeting_created_via_modal_counts(self, authed_api_a, user_a, client_account_a, account):
        camp = _campaign(user_a, client_account_a)
        # A campaign activity to source the DC's source_campaign backfill.
        src = Activity(title='src', activity_type=ActivityType.CALL,
                       status=ActivityStatus.COMPLETED, account=account, owner=user_a,
                       campaign=camp, scheduled_date=TODAY)
        src.save(user=user_a, client_id=client_account_a.id)

        payload = {
            'activity': {
                'title': 'Meeting', 'activity_type': ActivityType.MEETING,
                'status': ActivityStatus.COMPLETED, 'account_id': str(account.id),
                'contact_ids': [], 'decision_step_id': None, 'outcome': 'SUCCESSFUL',
                'source_activity_id': str(src.id),
            },
            'inline_cycle': {'name': 'MtgCycle', 'description': None},
            'inline_step_stage': 'QUALIFICATION',
        }
        resp = authed_api_a.post(CWE_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        act = Activity.objects.get(id=resp.json()['data']['activity']['id'])
        # The modal did NOT set Activity.campaign, but linked the cycle (which
        # carries source_campaign) — the exact bug state.
        assert act.campaign_id is None
        assert act.decision_cycle_id is not None

        assert _svc(client_account_a)._count_meetings(camp) == 1
