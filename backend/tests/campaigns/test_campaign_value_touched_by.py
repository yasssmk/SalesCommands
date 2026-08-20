# backend/tests/campaigns/test_campaign_value_touched_by.py
"""
Campaign MONEY objectives count a deal the campaign WORKED, not only one it created.

PO rule, per KPI type:

  DECISION_CYCLES  -> ORIGIN ONLY. A cycle counts for the campaign that created
                      it (``DecisionCycle.source_campaign``). Unchanged.
  PIPELINE_VALUE   -> UNION: born-from OR touched-by.
  REVENUE_WON         A cycle's value counts for a campaign when the cycle is
                      EITHER born from it, OR carries a SUCCESSFUL activity of
                      it. One cycle may count for several campaigns; campaign
                      values are therefore NOT additive across campaigns, by
                      design.

"Successful" is not redefined here: it is
``campaign_execution_service.SUCCESSFUL_OUTCOMES`` — {SUCCESSFUL,
MEETING_SCHEDULED} — paired with ``status=COMPLETED`` (``outcome`` is only
meaningful once completed, activities/models.py).

Touched-by is reached through the SAME three edges the MEETINGS objective already
unions (campaign_analytics_service._count_meetings):
  1. ``Activity.campaign``                 — a campaign activity on the cycle;
  2. ``DecisionCycle.source_campaign``     — the born-from branch;
  3. ``Activity.source_activity.campaign`` — an activity born from a campaign
     activity, on a cycle that never got source_campaign.

THE CORRECTNESS RISK this module exists to pin: the money must count each cycle
ONCE PER CAMPAIGN. Reaching cycles through their activities is a to-many
traversal, and DEAL_VALUE_SUM is itself a join over deal_products
(deal_value_sql.py) — a join-based union would multiply by activities AND by
product lines, silently. ``test_a_cycle_with_three_successful_activities_counts_once``
is the anti-inflation guard: 60k, never 180k.

Personal objectives/quotas are OUT OF SCOPE and must not move: the union lives in
the campaign layer, ABOVE the canonical bi/metrics functions that quotas share.

Harness mirrors tests/campaigns/test_campaign_list_objective_progress.py (same
factories, same parity guard style).
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityOutcome, ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType, ObjectiveType
from app_modules.campaigns.models import Campaign, CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from tests.deal_value_helpers import give_deal_value


TODAY = timezone.now().date()


# ---------------------------------------------------------------------------
# Factories (mirror test_campaign_list_objective_progress.py)
# ---------------------------------------------------------------------------

def _mk_campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_objective(campaign, owner, ca, objective_type, target=100000):
    o = CampaignObjective(campaign=campaign, name=str(objective_type),
                          objective_type=objective_type, target_value=target,
                          is_primary=True)
    o.save(user=owner, client_id=ca.id)
    return o


def _mk_cycle(owner, account, ca, *, source_campaign=None, amount=None,
              outcome=None, outcome_date=None, name='dc'):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign, outcome=outcome,
                       outcome_date=outcome_date)
    dc.save(user=owner, client_id=ca.id)
    give_deal_value(dc, amount, user=owner)
    return dc


def _mk_activity(owner, account, ca, *, campaign=None, cycle=None,
                 source_activity=None, outcome=ActivityOutcome.SUCCESSFUL,
                 status=ActivityStatus.COMPLETED, title='act'):
    a = Activity(title=title, activity_type=ActivityType.CALL, status=status,
                 outcome=outcome, account=account, owner=owner,
                 campaign=campaign, decision_cycle=cycle,
                 source_activity=source_activity, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _detail_value(ca, campaign, objective):
    """The per-campaign calculation the DETAIL serializer uses."""
    svc = CampaignAnalyticsService(client_id=ca.id)
    return float(svc._calculate_objective_value(campaign, objective) or 0)


def _list_value(ca, campaign):
    """The batch calculation the LIST card uses."""
    batch = compute_primary_objective_progress_batch([campaign], ca.id)
    return batch[campaign.id]['current_value']


def _both(ca, campaign, objective):
    """Detail and list must agree — asserted on every case, not once."""
    detail = _detail_value(ca, campaign, objective)
    assert _list_value(ca, campaign) == detail, 'list/detail drift'
    return detail


# ===========================================================================
# TOUCHED-BY — the three edges
# ===========================================================================

@pytest.mark.django_db
class TestTouchedByAttribution:

    def test_a_successful_campaign_activity_pulls_the_deal_in(
        self, user_a, client_account_a, account,
    ):
        """Edge 1 — Activity.campaign. The cycle was born from campaign A; a
        successful activity of campaign B makes its value count for B TOO."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _both(client_account_a, camp_b, obj_b) == 60000.0

    def test_the_origin_counts_once_it_has_worked_the_deal(
        self, user_a, client_account_a, account,
    ):
        """The origin campaign claims the money through the same door as anyone
        else: a completed successful activity.

        This test used to assert that being the origin was enough on its own.
        The PO reversed that — creation is rewarded by DECISION_CYCLES, value by
        work — so the unworked case is now pinned in
        TestMoneyRequiresASuccessfulActivity."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_a, cycle=cycle)

        assert _both(client_account_a, camp_a, obj_a) == 60000.0

    def test_an_activity_born_from_a_campaign_activity_pulls_the_deal_in(
        self, user_a, client_account_a, account,
    ):
        """Edge 3 — source_activity.campaign. The cycle has NO source_campaign
        and the follow-up carries no campaign of its own; only the activity it
        was born from does. This is the pre-existing-deal case."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        seed = _mk_activity(user_a, account, client_account_a,
                            campaign=camp_b, title='seed')
        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a, campaign=None,
                     cycle=cycle, source_activity=seed, title='followup')

        assert _both(client_account_a, camp_b, obj_b) == 60000.0


# ===========================================================================
# THE ANTI-INFLATION GUARD — once per campaign
# ===========================================================================

@pytest.mark.django_db
class TestCountedOncePerCampaign:

    def test_a_cycle_with_three_successful_activities_counts_once(
        self, user_a, client_account_a, account,
    ):
        """THE dedup proof. A to-many join would return the cycle three times and
        report 180000. The value must be 60000."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        for i in range(3):
            _mk_activity(user_a, account, client_account_a,
                         campaign=camp_b, cycle=cycle, title=f'act{i}')

        assert _both(client_account_a, camp_b, obj_b) == 60000.0

    def test_a_cycle_both_born_from_and_touched_by_counts_once(
        self, user_a, client_account_a, account,
    ):
        """The two branches of the union overlap on the SAME campaign — an OR,
        not a sum."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_a, cycle=cycle)

        assert _both(client_account_a, camp_a, obj_a) == 60000.0

    def test_a_multi_line_deal_is_not_multiplied_by_its_lines(
        self, user_a, client_account_a, account,
    ):
        """The second multiplier: DEAL_VALUE_SUM joins deal_products. Two lines
        AND two activities must still give the deal's own total, once."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('40000'))
        give_deal_value(cycle, Decimal('20000'), user=user_a)   # a second line
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle, title='a1')
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle, title='a2')

        assert _both(client_account_a, camp_b, obj_b) == 60000.0

    def test_one_deal_counts_for_BOTH_campaigns(
        self, user_a, client_account_a, account,
    ):
        """Non-additive across campaigns — intended. A shared deal is 60k in each,
        not 30k each."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        # Each campaign claims through its OWN successful activity — A's origin
        # is not a claim on the money by itself.
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_a, cycle=cycle, title='by-a')
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle, title='by-b')

        assert _both(client_account_a, camp_a, obj_a) == 60000.0
        assert _both(client_account_a, camp_b, obj_b) == 60000.0


# ===========================================================================
# WHAT DOES *NOT* ATTRIBUTE
# ===========================================================================

@pytest.mark.django_db
class TestUnsuccessfulActivitiesDoNotAttribute:

    @pytest.mark.parametrize('outcome', [
        ActivityOutcome.NO_ANSWER,
        ActivityOutcome.NOT_INTERESTED,
        ActivityOutcome.CALLBACK_REQUESTED,
        ActivityOutcome.FOLLOW_UP_NEEDED,
    ])
    def test_a_non_successful_outcome_does_not_pull_the_deal_in(
        self, user_a, client_account_a, account, outcome,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a, campaign=camp_b,
                     cycle=cycle, outcome=outcome)

        assert _both(client_account_a, camp_b, obj_b) == 0.0

    def test_a_planned_activity_does_not_pull_the_deal_in(
        self, user_a, client_account_a, account,
    ):
        """outcome is only meaningful once COMPLETED; a PLANNED row must not
        attribute even if an outcome was somehow set."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a, campaign=camp_b,
                     cycle=cycle, status=ActivityStatus.PLANNED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        assert _both(client_account_a, camp_b, obj_b) == 0.0

    def test_a_successful_activity_of_ANOTHER_campaign_does_not_attribute(
        self, user_a, client_account_a, account,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        camp_c = _mk_campaign(user_a, client_account_a, name='C')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_c, cycle=cycle)

        assert _both(client_account_a, camp_b, obj_b) == 0.0


# ===========================================================================
# REVENUE_WON mirrors PIPELINE_VALUE; DECISION_CYCLES does NOT
# ===========================================================================

@pytest.mark.django_db
class TestWonMirrorsPipeline:

    def test_a_won_deal_touched_by_the_campaign_counts_in_its_won(
        self, user_a, client_account_a, account,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.REVENUE_WON)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('40000'),
                          outcome=CycleOutcome.WON, outcome_date=TODAY)
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _both(client_account_a, camp_b, obj_b) == 40000.0

    def test_an_open_deal_is_not_in_won(self, user_a, client_account_a, account):
        """WON stays selective: an open deal the campaign worked is in its
        pipeline but not in its won value.

        The converse is NOT true and is asserted in
        TestWonStaysInCampaignPipeline: a WON deal REMAINS in the campaign
        pipeline. This test previously asserted that exclusivity in both
        directions; the PO reversed the pipeline side (a campaign reports a
        result, not a state), so only the won side remains selective."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_won = _mk_objective(camp_b, user_a, client_account_a,
                                ObjectiveType.REVENUE_WON)

        open_dc = _mk_cycle(user_a, account, client_account_a, name='open',
                            source_campaign=None, amount=Decimal('40000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=open_dc, title='on-open')

        assert _both(client_account_a, camp_b, obj_won) == 0.0


@pytest.mark.django_db
class TestDecisionCyclesStaysOriginOnly:

    def test_a_touched_by_cycle_is_not_in_the_created_count(
        self, user_a, client_account_a, account,
    ):
        """PO rule: DECISION_CYCLES counts what the campaign CREATED. A deal it
        merely worked must not inflate that count — the deliberate asymmetry with
        the money KPIs."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _both(client_account_a, camp_a, obj_a) == 1.0
        assert _both(client_account_a, camp_b, obj_b) == 0.0


# ===========================================================================
# PERSONAL OBJECTIVES ARE OUT OF SCOPE
# ===========================================================================

@pytest.mark.django_db
class TestPersonalMetricsUnchanged:

    def test_the_canonical_metric_still_attributes_by_origin_only(
        self, user_a, client_account_a, account,
    ):
        """bi/metrics is shared with personal quotas and team perimeters. The
        campaign union lives ABOVE it, so a touched-by deal must NOT appear when
        the canonical function is called with source_campaign."""
        from app_modules.bi import metrics

        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        base = DecisionCycle.objects.filter(client_id=client_account_a.id)

        assert metrics.pipeline_value(base, source_campaign=camp_b, period=None) == 0.0
        # ...while the user's own pipeline is untouched by any campaign notion.
        assert metrics.pipeline_value(base, user=user_a, period=None) == 60000.0


# ===========================================================================
# QUERY COST — pinned, because the union changed it
# ===========================================================================

@pytest.mark.django_db
class TestQueryCost:

    def test_the_money_batch_costs_one_query_per_campaign(
        self, user_a, client_account_a, account, django_assert_num_queries,
    ):
        """Stated plainly rather than hidden: under the union a cycle has no
        single ``source_campaign`` to GROUP BY, so the page resolves attribution
        per campaign — one aggregate each, plus the one query that loads the
        page's primary objectives.

        The other objective types keep their single grouped query; only the two
        money types pay this. Pinned so any future optimisation (a pair-listing
        tally like _meetings_by_campaign) has a baseline to beat, and so the cost
        cannot grow again unnoticed.
        """
        campaigns = []
        for i in range(3):
            camp = _mk_campaign(user_a, client_account_a, name=f'C{i}')
            _mk_objective(camp, user_a, client_account_a,
                          ObjectiveType.PIPELINE_VALUE)
            cycle = _mk_cycle(user_a, account, client_account_a, name=f'dc{i}',
                              source_campaign=None, amount=Decimal('1000'))
            _mk_activity(user_a, account, client_account_a,
                         campaign=camp, cycle=cycle, title=f'a{i}')
            campaigns.append(camp)

        # 1 objectives query + 1 aggregate per campaign.
        with django_assert_num_queries(1 + len(campaigns)):
            batch = compute_primary_objective_progress_batch(
                campaigns, client_account_a.id,
            )

        assert all(batch[c.id]['current_value'] == 1000.0 for c in campaigns)

    def test_adding_activities_to_a_cycle_does_not_add_queries(
        self, user_a, client_account_a, account, django_assert_num_queries,
    ):
        """The Exists is one correlated subquery whatever the activity count."""
        camp = _mk_campaign(user_a, client_account_a, name='C')
        _mk_objective(camp, user_a, client_account_a, ObjectiveType.PIPELINE_VALUE)
        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('1000'))
        for i in range(6):
            _mk_activity(user_a, account, client_account_a,
                         campaign=camp, cycle=cycle, title=f'a{i}')

        with django_assert_num_queries(2):
            batch = compute_primary_objective_progress_batch(
                [camp], client_account_a.id,
            )

        assert batch[camp.id]['current_value'] == 1000.0


# ===========================================================================
# ALL THREE SURFACES — list card, detail serializer, DASHBOARD
# ===========================================================================
#
# Campaign money was computed in THREE places. The parity guard in
# test_campaign_list_objective_progress.py compares the LIST batch against
# ``_calculate_objective_value`` (the DETAIL path) — it never touched
# ``calculate_objective_values``, the batch behind ``get_objectives_progress``,
# which is what the campaign DASHBOARD renders. That third site stayed
# origin-only, so the drift was invisible to every existing test and visible to
# the PO.

def _dashboard_value(ca, campaign, objective_type):
    """The value the campaign WORKSPACE DASHBOARD renders."""
    svc = CampaignAnalyticsService(client_id=ca.id)
    rows = svc.get_objectives_progress(campaign)
    row = next(r for r in rows if r['objective_type'] == objective_type)
    return float(row['current_value'])


def _all_three(ca, campaign, objective):
    """list == detail == dashboard, or fail naming which drifted."""
    detail = _detail_value(ca, campaign, objective)
    listed = _list_value(ca, campaign)
    dashboard = _dashboard_value(ca, campaign, objective.objective_type)
    assert listed == detail, f'list {listed} != detail {detail}'
    assert dashboard == detail, f'dashboard {dashboard} != detail {detail}'
    return detail


@pytest.mark.django_db
class TestAllSurfacesAgree:

    def test_the_dashboard_counts_a_touched_by_deal(
        self, user_a, client_account_a, account,
    ):
        """THE bug the PO sees: card and detail moved, the dashboard stayed at 0."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _all_three(client_account_a, camp_b, obj_b) == 60000.0

    def test_the_dashboard_counts_a_touched_by_deal_in_won(
        self, user_a, client_account_a, account,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.REVENUE_WON)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('40000'),
                          outcome=CycleOutcome.WON, outcome_date=TODAY)
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _all_three(client_account_a, camp_b, obj_b) == 40000.0

    def test_the_dashboard_does_not_inflate_on_several_activities(
        self, user_a, client_account_a, account,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        for i in range(3):
            _mk_activity(user_a, account, client_account_a,
                         campaign=camp_b, cycle=cycle, title=f'a{i}')

        assert _all_three(client_account_a, camp_b, obj_b) == 60000.0

    def test_the_dashboard_keeps_DECISION_CYCLES_origin_only(
        self, user_a, client_account_a, account,
    ):
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _all_three(client_account_a, camp_a, obj_a) == 1.0
        assert _all_three(client_account_a, camp_b, obj_b) == 0.0


# ===========================================================================
# D3 — a campaign reports a RESULT, not a state: a won deal STAYS in pipeline
# ===========================================================================

@pytest.mark.django_db
class TestWonStaysInCampaignPipeline:

    def test_winning_a_deal_does_not_empty_the_campaign_pipeline(
        self, user_a, client_account_a, account,
    ):
        """PO-confirmed: campaign pipeline is what the campaign PRODUCED, so a
        deal it produced does not vanish the moment it is won. The overlap with
        WON is intended — the same deal counts in both."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_pipeline = _mk_objective(camp_b, user_a, client_account_a,
                                     ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_b, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        assert _all_three(client_account_a, camp_b, obj_pipeline) == 60000.0

        cycle.outcome = CycleOutcome.WON
        cycle.outcome_date = TODAY
        cycle.save(user=user_a, client_id=client_account_a.id)

        # STILL in pipeline — it did not drop to 0.
        assert _all_three(client_account_a, camp_b, obj_pipeline) == 60000.0

    def test_the_won_deal_is_in_pipeline_AND_in_won(
        self, user_a, client_account_a, account,
    ):
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_b, amount=Decimal('60000'),
                          outcome=CycleOutcome.WON, outcome_date=TODAY)
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle)

        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        obj_pipeline = _mk_objective(camp_b, user_a, client_account_a,
                                     ObjectiveType.PIPELINE_VALUE)
        assert float(svc._calculate_objective_value(camp_b, obj_pipeline)) == 60000.0

        obj_won = CampaignObjective(campaign=camp_b, name='won',
                                    objective_type=ObjectiveType.REVENUE_WON,
                                    target_value=100000, is_primary=False)
        obj_won.save(user=user_a, client_id=client_account_a.id)
        assert float(svc._calculate_objective_value(camp_b, obj_won)) == 60000.0

    def test_a_LOST_deal_leaves_the_campaign_pipeline(
        self, user_a, client_account_a, account,
    ):
        """Open OR won — a LOST deal is neither, so it drops. The campaign
        produced nothing there."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        _mk_cycle(user_a, account, client_account_a,
                  source_campaign=camp_b, amount=Decimal('60000'),
                  outcome=CycleOutcome.LOST, outcome_date=TODAY)

        assert _all_three(client_account_a, camp_b, obj_b) == 0.0


# ===========================================================================
# MONEY REQUIRES WORK DONE — the origin is not a free pass
# ===========================================================================
#
# PO rule, final: a campaign claims a deal's VALUE only once it has at least one
# COMPLETED + SUCCESSFUL activity on that deal. This applies to the ORIGIN
# campaign too — being born from a campaign no longer contributes money on its
# own. DECISION_CYCLES is unaffected: it counts what the campaign CREATED,
# whether or not anyone has worked it since.
#
# This also closes two symptoms the PO reported, without touching the write
# path: a deal could enter a campaign's pipeline as soon as an activity was
# CREATED (before completion), and stayed there when that activity was
# cancelled. Both came in through the born-from branch; requiring a completed
# successful activity removes the leak.

@pytest.mark.django_db
class TestMoneyRequiresASuccessfulActivity:

    def test_the_origin_alone_no_longer_counts_money(
        self, user_a, client_account_a, account,
    ):
        """A deal born from campaign A, with products, and NOTHING done on it
        yet: A's pipeline is 0. Before this rule it was the full 60k."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        _mk_cycle(user_a, account, client_account_a,
                  source_campaign=camp_a, amount=Decimal('60000'))

        assert _all_three(client_account_a, camp_a, obj_a) == 0.0

    def test_a_successful_activity_of_the_origin_unlocks_the_money(
        self, user_a, client_account_a, account,
    ):
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))

        assert _all_three(client_account_a, camp_a, obj_a) == 0.0

        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_a, cycle=cycle)

        assert _all_three(client_account_a, camp_a, obj_a) == 60000.0

    def test_an_uncompleted_activity_of_the_origin_does_not_unlock_it(
        self, user_a, client_account_a, account,
    ):
        """The symptom: the money moved as soon as the activity was CREATED."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a, campaign=camp_a,
                     cycle=cycle, status=ActivityStatus.PLANNED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        assert _all_three(client_account_a, camp_a, obj_a) == 0.0

    def test_a_cancelled_activity_of_the_origin_does_not_unlock_it(
        self, user_a, client_account_a, account,
    ):
        """The other symptom: cancelling the activity left the deal counted."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        _mk_activity(user_a, account, client_account_a, campaign=camp_a,
                     cycle=cycle, status=ActivityStatus.CANCELLED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        assert _all_three(client_account_a, camp_a, obj_a) == 0.0

    def test_the_rule_applies_to_won_value_too(
        self, user_a, client_account_a, account,
    ):
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.REVENUE_WON)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('40000'),
                          outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _all_three(client_account_a, camp_a, obj_a) == 0.0

        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_a, cycle=cycle)

        assert _all_three(client_account_a, camp_a, obj_a) == 40000.0

    def test_DECISION_CYCLES_still_counts_an_unworked_deal(
        self, user_a, client_account_a, account,
    ):
        """The count is about CREATION, not work: a deal the campaign created
        counts even with no activity at all. This is the asymmetry with money."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        _mk_cycle(user_a, account, client_account_a,
                  source_campaign=camp_a, amount=Decimal('60000'))

        assert _all_three(client_account_a, camp_a, obj_a) == 1.0


# ===========================================================================
# CANCELLING THE WORK REMOVES THE CLAIM — no special cancel handling
# ===========================================================================

@pytest.mark.django_db
class TestCancellingTheActivityDropsTheDeal:

    def test_cancelling_the_only_successful_activity_drops_the_deal(
        self, user_a, client_account_a, account,
    ):
        """Attribution rests entirely on Exists(COMPLETED + SUCCESSFUL), so a
        cancelled activity stops matching and the deal leaves the campaign's
        money on its own. There is no cancel-handling code to get wrong."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        activity = _mk_activity(user_a, account, client_account_a,
                                campaign=camp_b, cycle=cycle)

        assert _all_three(client_account_a, camp_b, obj_b) == 60000.0

        activity.status = ActivityStatus.CANCELLED
        activity.save(user=user_a, client_id=client_account_a.id)

        assert _all_three(client_account_a, camp_b, obj_b) == 0.0

    def test_cancelling_one_of_two_leaves_the_deal_counted(
        self, user_a, client_account_a, account,
    ):
        """The claim survives while ANY successful activity remains — and the
        deal is still counted ONCE, not twice."""
        camp_b = _mk_campaign(user_a, client_account_a, name='B')
        obj_b = _mk_objective(camp_b, user_a, client_account_a,
                              ObjectiveType.PIPELINE_VALUE)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=None, amount=Decimal('60000'))
        first = _mk_activity(user_a, account, client_account_a,
                             campaign=camp_b, cycle=cycle, title='a1')
        _mk_activity(user_a, account, client_account_a,
                     campaign=camp_b, cycle=cycle, title='a2')

        first.status = ActivityStatus.CANCELLED
        first.save(user=user_a, client_id=client_account_a.id)

        assert _all_three(client_account_a, camp_b, obj_b) == 60000.0

    def test_cancelling_does_not_touch_the_created_count(
        self, user_a, client_account_a, account,
    ):
        """DECISION_CYCLES records CREATION. Cancelling the work done on a deal
        does not un-create it."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        cycle = _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp_a, amount=Decimal('60000'))
        activity = _mk_activity(user_a, account, client_account_a,
                                campaign=camp_a, cycle=cycle)

        assert _all_three(client_account_a, camp_a, obj_a) == 1.0

        activity.status = ActivityStatus.CANCELLED
        activity.save(user=user_a, client_id=client_account_a.id)

        assert _all_three(client_account_a, camp_a, obj_a) == 1.0


@pytest.mark.django_db
class TestDecisionCyclesCountsEveryCreatedDeal:

    def test_a_lost_deal_still_counts_as_created(
        self, user_a, client_account_a, account,
    ):
        """Creating it was a campaign result even if it went nowhere: the count
        is not filtered by outcome, and there is no DC-cancel concept to filter
        on either (CycleOutcome has no CANCELLED)."""
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        _mk_cycle(user_a, account, client_account_a, name='lost',
                  source_campaign=camp_a, amount=Decimal('60000'),
                  outcome=CycleOutcome.LOST, outcome_date=TODAY)

        assert _all_three(client_account_a, camp_a, obj_a) == 1.0

    def test_every_outcome_counts_as_created(
        self, user_a, client_account_a, account,
    ):
        camp_a = _mk_campaign(user_a, client_account_a, name='A')
        obj_a = _mk_objective(camp_a, user_a, client_account_a,
                              ObjectiveType.DECISION_CYCLES, target=10)

        for name, outcome in (
            ('open', None),
            ('won', CycleOutcome.WON),
            ('lost', CycleOutcome.LOST),
            ('hold', CycleOutcome.ON_HOLD),
            ('nq', CycleOutcome.NOT_QUALIFIED),
        ):
            _mk_cycle(user_a, account, client_account_a, name=name,
                      source_campaign=camp_a, amount=Decimal('1000'),
                      outcome=outcome,
                      outcome_date=TODAY if outcome else None)

        assert _all_three(client_account_a, camp_a, obj_a) == 5.0
