# backend/tests/campaigns/test_objective_source_campaign_tracking.py
"""
Campaign-objective tracking attributes DCs via ``DecisionCycle.source_campaign``.

Root cause of "the campaign objective never moves": the DC-based objective
branches (DECISION_CYCLES / PIPELINE_VALUE / REVENUE_WON) used to attribute a
cycle to a campaign through ``Activity.campaign`` — i.e. a cycle only counted if
some activity tagged with that campaign happened to point at it. But a DC created
from the activity-creation modal in a campaign context gets its OWN
``source_campaign`` set (backfill), while the created activity carries
``campaign=None``. So no ``Activity(campaign=camp, decision_cycle=DC)`` row
exists, and the old query counted nothing.

The fix rebinds those three branches to the canonical ``bi/metrics`` formulas,
attributing by ``DecisionCycle.source_campaign`` — the same definition as the
personal objectives, filtered to the campaign of origin.

SCOPE CHANGE asserted below:
- GAINED: a DC whose ``source_campaign`` is the campaign but which has NO
  campaign activity pointing at it is now counted (the symptom cohort).
- DROPPED: a DC merely linked by a campaign activity but whose own
  ``source_campaign`` is NULL is no longer counted.

DB: Postgres (aggregates/subqueries exercised for real).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType, ObjectiveType
from app_modules.campaigns.models import Campaign, CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle

TODAY = timezone.now().date()


# ---------------------------------------------------------------------------
# Factories (mirror tests/bi/test_metrics_canonical.py control over the fields)
# ---------------------------------------------------------------------------

def _mk_campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_cycle(owner, account, ca, *, name='dc', source_campaign=None,
              estimated_value=None, outcome=None, outcome_date=None):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign,
                       estimated_value=estimated_value, outcome=outcome,
                       outcome_date=outcome_date)
    dc.save(user=owner, client_id=ca.id)
    return dc


def _mk_activity(owner, account, ca, *, campaign=None, decision_cycle=None,
                 activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED):
    a = Activity(title='a', activity_type=activity_type, status=status,
                 account=account, owner=owner, campaign=campaign,
                 decision_cycle=decision_cycle, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _svc(ca):
    return CampaignAnalyticsService(client_id=ca.id)


# ---------------------------------------------------------------------------
# The realistic mixed dataset used by the repro / scope tests.
# ---------------------------------------------------------------------------

def _build_mixed(owner, ca):
    """One campaign with:
    - open_dc  : source_campaign=camp, open, value 1000, activity has campaign=None
                 (the exact modal cohort — attributed by source_campaign only).
    - won_dc   : source_campaign=camp, WON, value 500, no activity at all.
    - decoy_dc : source_campaign=None, open, value 777, BUT a campaign activity
                 points at it (only the OLD Activity.campaign attribution saw it).
    - other_dc : source_campaign=other_camp, open, value 9999 (must never leak).
    """
    camp = _mk_campaign(owner, ca)
    other_camp = _mk_campaign(owner, ca, name='Other')
    acc = owner_account = _account_for(owner, ca)

    open_dc = _mk_cycle(owner, acc, ca, name='open', source_campaign=camp,
                        estimated_value=1000)
    # modal cohort: activity linked to the DC but NOT tagged with the campaign
    _mk_activity(owner, acc, ca, campaign=None, decision_cycle=open_dc)

    won_dc = _mk_cycle(owner, acc, ca, name='won', source_campaign=camp,
                       estimated_value=500, outcome=CycleOutcome.WON,
                       outcome_date=TODAY)

    decoy_dc = _mk_cycle(owner, acc, ca, name='decoy', source_campaign=None,
                         estimated_value=777)
    _mk_activity(owner, acc, ca, campaign=camp, decision_cycle=decoy_dc)

    other_dc = _mk_cycle(owner, acc, ca, name='other', source_campaign=other_camp,
                         estimated_value=9999)
    _mk_activity(owner, acc, ca, campaign=other_camp, decision_cycle=other_dc)

    return camp


def _account_for(owner, ca):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name='Acc', has_buying_decision=True,
                       account_owner=owner)
    a.save(user=owner, client_id=ca.id)
    return a


# ---------------------------------------------------------------------------
# REPRO + SCOPE — the DC-based branches attribute by source_campaign.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSourceCampaignAttribution:

    def test_decision_cycles_counts_by_source_campaign(self, user_a, client_account_a):
        camp = _build_mixed(user_a, client_account_a)
        # open_dc + won_dc are source_campaign=camp; decoy (no source_campaign)
        # and other (other campaign) excluded. OLD calc returned 1 (decoy only).
        assert _svc(client_account_a)._count_decision_cycles(camp) == 2

    def test_pipeline_value_sums_source_campaign_open_cycles(self, user_a, client_account_a):
        camp = _build_mixed(user_a, client_account_a)
        # open_dc (1000) only. OLD calc returned 777 (decoy via its campaign activity).
        assert _svc(client_account_a)._sum_pipeline_value(camp) == 1000.0

    def test_revenue_won_sums_source_campaign_won_cycles(self, user_a, client_account_a):
        camp = _build_mixed(user_a, client_account_a)
        # won_dc (500). OLD calc returned 0 (won_dc has no campaign activity).
        assert _svc(client_account_a)._sum_revenue_won(camp) == 500.0

    def test_dc_linked_by_campaign_activity_but_no_source_campaign_dropped(
            self, user_a, client_account_a):
        """Scope shrink: a cycle with a campaign activity but source_campaign=NULL
        is NOT attributed anymore (decoy_dc, value 777, is absent from every total)."""
        camp = _build_mixed(user_a, client_account_a)
        svc = _svc(client_account_a)
        assert svc._sum_pipeline_value(camp) == 1000.0     # 777 not included
        assert svc._count_decision_cycles(camp) == 2        # decoy not counted


# ---------------------------------------------------------------------------
# CONTRACT — the symptom regression guard.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestContractSourceCampaignAloneCounts:
    """A DC attributed to a campaign SOLELY via source_campaign — with ZERO
    campaign activities pointing at it (the exact state the activity modal
    produces) — must be counted by all three DC-based objective branches. This
    locks the fix: the campaign-objective tracking can never silently regress to
    requiring an Activity.campaign link."""

    def test_source_campaign_alone_is_sufficient(self, user_a, client_account_a):
        acc = _account_for(user_a, client_account_a)
        camp = _mk_campaign(user_a, client_account_a)

        open_dc = _mk_cycle(user_a, acc, client_account_a, name='o',
                            source_campaign=camp, estimated_value=300)
        _mk_cycle(user_a, acc, client_account_a, name='w', source_campaign=camp,
                  estimated_value=200, outcome=CycleOutcome.WON, outcome_date=TODAY)
        # NO Activity rows at all → old Activity.campaign attribution would see 0.

        svc = _svc(client_account_a)
        assert svc._count_decision_cycles(camp) == 2
        assert svc._sum_pipeline_value(camp) == 300.0
        assert svc._sum_revenue_won(camp) == 200.0

    def test_objectives_progress_reflects_source_campaign_dc(self, user_a, client_account_a):
        """End-to-end through the public serializer path: get_objectives_progress
        must surface the source_campaign-attributed DC in current_value."""
        acc = _account_for(user_a, client_account_a)
        camp = _mk_campaign(user_a, client_account_a)
        _mk_cycle(user_a, acc, client_account_a, name='o', source_campaign=camp,
                  estimated_value=1500)

        obj = CampaignObjective(campaign=camp, name='Pipe',
                                objective_type=ObjectiveType.PIPELINE_VALUE,
                                target_value=3000, is_primary=True)
        obj.save(user=user_a, client_id=client_account_a.id)

        progress = _svc(client_account_a).get_objectives_progress(camp)
        row = next(r for r in progress if r['objective_type'] == ObjectiveType.PIPELINE_VALUE)
        assert row['current_value'] == 1500.0
        assert row['progress_percentage'] == 50.0
