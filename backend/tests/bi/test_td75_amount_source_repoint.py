# backend/tests/bi/test_td75_amount_source_repoint.py
"""
TD-75 — every DC amount aggregation reads the DERIVED roll-up, not estimated_value.

Before this repoint, PIPELINE_VALUE / REVENUE_WON (campaign objectives, personal
objectives, personal quotas) summed ``DecisionCycle.estimated_value``, which no
runtime path has ever populated — so they were all structurally stuck at 0.
They now sum ``total_deal_value``, the product roll-up.

CROSS-COVERAGE (TD-125): the amount is aggregated at FIVE independent sites, in
four modules. One test per site, all on the SAME data, because repointing four
of five is exactly the failure this class of bug is made of:

  1. bi/metrics/sales_metrics.pipeline_value / revenue_won   (canonical)
  2. campaigns/.../campaign_analytics_service (per-objective + grouped batch)
  3. campaigns/.../campaign_objective_progress (campaign LIST page)
  4. quotas/services/progress                 (personal objectives, modern)
  5. bi/quota.compute_quota_current_value     (personal quotas, legacy)

Every cycle here also carries a DECOY ``estimated_value`` (999_999). If any path
still read the old field the number would be unmistakable — the decoy is the
proof, not a comment.

Shared scenario: OPEN cycle worth 60_000, WON cycle worth 40_000, LOST cycle
worth 77_000 (must count nowhere). Pipeline is EXCLUSIVE — won and lost have
left it.

Harness mirrors tests/bi/test_metrics_canonical.py (same factories, same
AuthContext helper) and tests/bi/test_kpi_quota.py for the legacy SalesQuota.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.bi import metrics
from app_modules.bi.metrics import MetricKey
from app_modules.bi.quota import compute_quota_current_value
from app_modules.campaigns.constants import ObjectiveType
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_objective import CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as quota_progress
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


TODAY = date.today()
PERIOD_START = TODAY - timedelta(days=30)
PERIOD_END = TODAY + timedelta(days=30)

OPEN_VALUE = Decimal('60000')
WON_VALUE = Decimal('40000')
LOST_VALUE = Decimal('77000')

# If any aggregation still summed estimated_value, totals would land here.
DECOY = Decimal('999999')


# ---------------------------------------------------------------------------
# factories (mirror tests/bi/test_metrics_canonical.py)
# ---------------------------------------------------------------------------

def _account(owner, ca, name='Acc'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type='OUTBOUND', owner=owner, executor=owner,
                 planned_start_date=PERIOD_START, planned_end_date=PERIOD_END)
    c.save(user=owner, client_id=ca.id)
    return c


def _cycle(owner, account, ca, *, name, amount, outcome=None, outcome_date=None,
           source_campaign=None, dated_step=True):
    """A cycle worth ``amount`` through a real product line, carrying a DECOY
    estimated_value. ``dated_step`` gives it the expected close date
    pipeline_value windows on, so it survives a period filter.

    The parameter keeps its name so every call site below reads unchanged, but
    the date now lives on the cycle's own ``expected_close_date`` — level 1 of
    the effective close date (decision_cycles/services/close_date_sql.py) that
    replaced the old Max(steps.expected_end) anchor."""
    dc = DecisionCycle(
        account=account, owner=owner, name=name, source_campaign=source_campaign,
        outcome=outcome, outcome_date=outcome_date, estimated_value=DECOY,
        expected_close_date=TODAY if dated_step else None,
    )
    dc.save(user=owner, client_id=ca.id)
    give_deal_value(dc, amount, user=owner)
    return dc


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True)


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    """Local owner fixture — tests/bi/conftest.py re-exports the tenant/role
    fixtures only; users are built per test (see test_metrics_canonical.py)."""
    return _mk_user('td75_owner@a.test', client_account_a, role_individual_a)


@pytest.fixture
def scenario(db, client_account_a, user_a):
    """OPEN 60k + WON 40k + LOST 77k, all on one campaign, one owner."""
    account = _account(user_a, client_account_a)
    campaign = _campaign(user_a, client_account_a)

    opened = _cycle(user_a, account, client_account_a, name='open',
                    amount=OPEN_VALUE, source_campaign=campaign)
    won = _cycle(user_a, account, client_account_a, name='won', amount=WON_VALUE,
                 outcome=CycleOutcome.WON, outcome_date=TODAY,
                 source_campaign=campaign)
    lost = _cycle(user_a, account, client_account_a, name='lost', amount=LOST_VALUE,
                  outcome=CycleOutcome.LOST, outcome_date=TODAY,
                  source_campaign=campaign)

    return {
        'account': account, 'campaign': campaign,
        'open': opened, 'won': won, 'lost': lost,
        'ca': client_account_a, 'user': user_a,
    }


def _dc_base(client_account):
    return DecisionCycle.objects.filter(client_id=client_account.id)


# ===========================================================================
# SITE 1 — the canonical metric formulas
# ===========================================================================

class TestCanonicalMetrics:

    def test_pipeline_value_sums_open_cycles_only(self, scenario):
        value = metrics.pipeline_value(_dc_base(scenario['ca']), period=None)
        assert Decimal(str(value)) == OPEN_VALUE

    def test_revenue_won_sums_won_cycles_only(self, scenario):
        value = metrics.revenue_won(_dc_base(scenario['ca']), period=None)
        assert Decimal(str(value)) == WON_VALUE

    def test_won_and_lost_have_left_the_pipeline(self, scenario):
        """Pipeline is EXCLUSIVE — the 40k won and the 77k lost are not in it."""
        value = Decimal(str(metrics.pipeline_value(_dc_base(scenario['ca']), period=None)))
        assert value == OPEN_VALUE
        assert value != OPEN_VALUE + WON_VALUE
        assert value != OPEN_VALUE + WON_VALUE + LOST_VALUE

    def test_lost_counts_nowhere(self, scenario):
        pipeline = Decimal(str(metrics.pipeline_value(_dc_base(scenario['ca']), period=None)))
        won = Decimal(str(metrics.revenue_won(_dc_base(scenario['ca']), period=None)))
        assert LOST_VALUE not in (pipeline, won)
        assert pipeline + won == OPEN_VALUE + WON_VALUE

    def test_a_cycle_without_lines_contributes_zero(self, scenario):
        _cycle(scenario['user'], scenario['account'], scenario['ca'],
               name='empty', amount=None)

        value = metrics.pipeline_value(_dc_base(scenario['ca']), period=None)
        assert Decimal(str(value)) == OPEN_VALUE       # unchanged, no crash

    def test_discount_is_included(self, scenario):
        """The roll-up the metric sums is the discounted one."""
        extra = _cycle(scenario['user'], scenario['account'], scenario['ca'],
                       name='discounted', amount=None)
        line = give_deal_value(extra, Decimal('10000'), user=scenario['user'])
        line.discount_percent = Decimal('50')
        line.save(user=scenario['user'])

        value = metrics.pipeline_value(_dc_base(scenario['ca']), period=None)
        assert Decimal(str(value)) == OPEN_VALUE + Decimal('5000')


# ===========================================================================
# SITE 2 — campaign objectives (per-objective AND grouped batch)
# ===========================================================================

def _objective(campaign, ca, user, objective_type, target=Decimal('100000')):
    obj = CampaignObjective(campaign=campaign, name=str(objective_type),
                            objective_type=objective_type, target_value=target,
                            is_primary=(objective_type == ObjectiveType.PIPELINE_VALUE))
    obj.save(user=user, client_id=ca.id)
    return obj


class TestCampaignObjectives:

    def test_per_objective_values(self, scenario):
        campaign, ca, user = scenario['campaign'], scenario['ca'], scenario['user']
        pipe = _objective(campaign, ca, user, ObjectiveType.PIPELINE_VALUE)
        won = _objective(campaign, ca, user, ObjectiveType.REVENUE_WON)

        rows = CampaignAnalyticsService(ca.id).get_objectives_progress(campaign)
        by_id = {row['id']: row['current_value'] for row in rows}

        assert Decimal(str(by_id[str(pipe.id)])) == OPEN_VALUE
        assert Decimal(str(by_id[str(won.id)])) == WON_VALUE

    def test_grouped_batch_matches_per_objective(self, scenario):
        """The batch aggregate (Count + two filtered Sums in ONE query) must
        return the same amounts AND keep its cycle count exact — the roll-up is
        summed off the per-cycle annotation precisely so the join cannot
        multiply dc_count."""
        campaign, ca, user = scenario['campaign'], scenario['ca'], scenario['user']
        pipe = _objective(campaign, ca, user, ObjectiveType.PIPELINE_VALUE)
        won = _objective(campaign, ca, user, ObjectiveType.REVENUE_WON)
        cycles = _objective(campaign, ca, user, ObjectiveType.DECISION_CYCLES)

        service = CampaignAnalyticsService(ca.id)
        values = service.calculate_objective_values(campaign, [pipe, won, cycles])

        assert Decimal(str(values[pipe.id])) == OPEN_VALUE
        assert Decimal(str(values[won.id])) == WON_VALUE
        assert values[cycles.id] == 3          # open + won + lost, NOT x lines

    def test_campaign_list_grouped_progress(self, scenario):
        """SITE 3 — the campaign LIST page's own grouped query."""
        campaign, ca, user = scenario['campaign'], scenario['ca'], scenario['user']
        _objective(campaign, ca, user, ObjectiveType.PIPELINE_VALUE)

        batch = compute_primary_objective_progress_batch([campaign], ca.id)
        row = batch[campaign.id]

        assert Decimal(str(row['current_value'])) == OPEN_VALUE


# ===========================================================================
# SITE 4 — personal objectives / quotas (modern Quota -> quotas.services.progress)
# ===========================================================================

class TestPersonalObjectives:

    def _quota(self, owner, ca, metric):
        quota = Quota(owner=owner, metric=metric, target_value=Decimal('100000'),
                      period_start=PERIOD_START, period_end=PERIOD_END)
        quota.save(user=owner, client_id=ca.id)
        return quota

    def test_personal_pipeline_objective_reads_the_rollup(self, scenario):
        quota = self._quota(scenario['user'], scenario['ca'], MetricKey.PIPELINE_VALUE)

        result = quota_progress.compute_progress(quota)

        assert Decimal(str(result.current_value)) == OPEN_VALUE
        assert result.current_value != float(DECOY)

    def test_personal_won_objective_reads_the_rollup(self, scenario):
        quota = self._quota(scenario['user'], scenario['ca'], MetricKey.REVENUE_WON)

        result = quota_progress.compute_progress(quota)

        assert Decimal(str(result.current_value)) == WON_VALUE

    def test_ratio_is_computed_from_the_rollup(self, scenario):
        quota = self._quota(scenario['user'], scenario['ca'], MetricKey.REVENUE_WON)

        result = quota_progress.compute_progress(quota)

        assert result.ratio == pytest.approx(float(WON_VALUE) / 100000.0)


# ===========================================================================
# SITE 5 — personal quotas (legacy SalesQuota -> bi.quota)
# ===========================================================================

class TestLegacySalesQuota:

    def _sales_quota(self, user, target_type):
        from end_users.models import SalesQuota

        quota = SalesQuota(
            user=user, name=f'Q-{target_type}', target_type=target_type,
            target_value=Decimal('100000'), recurrence_type='annual',
            fiscal_year=TODAY.year, period_number=1,
            period_start=PERIOD_START, period_end=PERIOD_END,
        )
        quota.save()
        return quota

    def test_pipeline_target_type_reads_the_rollup(self, scenario):
        quota = self._sales_quota(scenario['user'], 'pipeline')

        assert Decimal(str(compute_quota_current_value(quota))) == OPEN_VALUE

    def test_closed_won_target_type_reads_the_rollup(self, scenario):
        quota = self._sales_quota(scenario['user'], 'closed_won')

        assert Decimal(str(compute_quota_current_value(quota))) == WON_VALUE


# ===========================================================================
# The decoy, stated once more as its own assertion
# ===========================================================================

class TestEstimatedValueIsNoLongerRead:

    def test_every_amount_path_ignores_estimated_value(self, scenario):
        """Every cycle carries estimated_value=999_999. Nothing returns it."""
        ca, campaign, user = scenario['ca'], scenario['campaign'], scenario['user']

        values = [
            Decimal(str(metrics.pipeline_value(_dc_base(ca), period=None))),
            Decimal(str(metrics.revenue_won(_dc_base(ca), period=None))),
            Decimal(str(CampaignAnalyticsService(ca.id)._sum_pipeline_value(campaign))),
            Decimal(str(CampaignAnalyticsService(ca.id)._sum_revenue_won(campaign))),
        ]

        assert all(v not in (DECOY, DECOY * 3) for v in values)
        assert values == [OPEN_VALUE, WON_VALUE, OPEN_VALUE, WON_VALUE]

    def test_the_decoy_is_really_on_the_rows(self, scenario):
        """Guards the guard: if the fixture stopped setting estimated_value the
        tests above would pass vacuously."""
        assert scenario['open'].estimated_value == DECOY
        assert scenario['won'].estimated_value == DECOY


# ===========================================================================
# N+1 — the repointed aggregations stay query-bounded
# ===========================================================================

class TestQueryBound:

    def test_pipeline_value_is_one_query_over_many_cycles(
        self, scenario, django_assert_num_queries,
    ):
        for index in range(5):
            _cycle(scenario['user'], scenario['account'], scenario['ca'],
                   name=f'bulk-{index}', amount=Decimal('1000'))

        with django_assert_num_queries(1):
            value = metrics.pipeline_value(_dc_base(scenario['ca']), period=None)

        assert Decimal(str(value)) == OPEN_VALUE + Decimal('5000')

    def test_revenue_won_is_one_query(self, scenario, django_assert_num_queries):
        with django_assert_num_queries(1):
            metrics.revenue_won(_dc_base(scenario['ca']), period=None)

    def test_campaign_batch_stays_one_query_for_the_dc_family(
        self, scenario, django_assert_num_queries,
    ):
        campaign, ca, user = scenario['campaign'], scenario['ca'], scenario['user']
        objectives = [
            _objective(campaign, ca, user, ObjectiveType.PIPELINE_VALUE),
            _objective(campaign, ca, user, ObjectiveType.REVENUE_WON),
            _objective(campaign, ca, user, ObjectiveType.DECISION_CYCLES),
        ]
        service = CampaignAnalyticsService(ca.id)

        with django_assert_num_queries(1):
            service.calculate_objective_values(campaign, objectives)
