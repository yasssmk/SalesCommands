# backend/tests/bi/test_amount_unblock_e2e.py
"""
END-TO-END proof of the Sprint C amount unblock, one scenario, four paths.

Sub-step 4 repointed every DC amount aggregation from the dead
``estimated_value`` to the derived ``total_deal_value``. This module proves the
unblock is real THROUGH each consumer's own entry point — in particular the
PERSONAL paths, which had no test touching an amount at all (their existing
tests cover progress mechanics and perimeters, never the money).

ONE fixture, reused by every path:

    DC_open   60_000  outcome NULL   -> two lines: 40_000 + (40_000 - 50%)
    DC_won    40_000  outcome WON
    DC_lost   30_000  outcome LOST

The open cycle's 60_000 is DISCOUNTED money: without the 50% on its second line
it would be 80_000, asserted as a control, so the discount is proven to flow all
the way into every KPI rather than assumed.

Paths and entry points:
  1. Campaign PIPELINE_VALUE   -> CampaignAnalyticsService.get_objectives_progress
  2. Campaign REVENUE_WON      -> same
  3. Personal quota / objective-> quotas.services.progress.compute_progress
                                  (modern Quota) and bi.quota
                                  .compute_quota_current_value (legacy SalesQuota)
  4. Personal objective / sales plan -> SalesPlanningService (see the GAP class
     at the bottom: this path does NOT read decision cycles at all)

Status is the only criterion: ``outcome IS NULL`` = open, ``outcome=WON`` = won.
``is_active`` plays no part — asserted explicitly.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.bi.metrics import MetricKey
from app_modules.bi.quota import compute_quota_current_value
from app_modules.campaigns.constants import ObjectiveType
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_objective import CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DealProduct, DecisionCycle
from app_modules.product_catalog.models import ProductCatalog
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as quota_progress


pytestmark = pytest.mark.django_db


TODAY = date.today()
PERIOD_START = TODAY - timedelta(days=30)
PERIOD_END = TODAY + timedelta(days=30)

FULL_LINE = Decimal('40000')            # open cycle, line 1 — no discount
DISCOUNTED_LINE_LIST = Decimal('40000')  # open cycle, line 2 — list price
DISCOUNT = Decimal('50')                 # ... at 50% off -> 20_000

OPEN_VALUE = Decimal('60000')            # 40_000 + 20_000
OPEN_VALUE_IF_DISCOUNT_IGNORED = Decimal('80000')
WON_VALUE = Decimal('40000')
LOST_VALUE = Decimal('30000')


# ---------------------------------------------------------------------------
# factories — real create path only (mirrors tests/bi/test_metrics_canonical.py)
# ---------------------------------------------------------------------------

def _user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True)


def _account(owner, ca, name='Acc'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _campaign(owner, ca, name='Camp'):
    campaign = Campaign(name=name, campaign_type='OUTBOUND', owner=owner,
                        executor=owner, planned_start_date=PERIOD_START,
                        planned_end_date=PERIOD_END)
    campaign.save(user=owner, client_id=ca.id)
    return campaign


def _cycle(owner, account, ca, *, name, campaign, outcome=None, is_active=False):
    # expected_close_date puts the cycle inside the period a quota windows on.
    # It is level 1 of the effective close date
    # (decision_cycles/services/close_date_sql.py), which replaced the old
    # Max(steps.expected_end) anchor this factory used to seed with a dated step.
    cycle = DecisionCycle(account=account, owner=owner, name=name,
                          source_campaign=campaign, outcome=outcome,
                          outcome_date=TODAY if outcome else None,
                          expected_close_date=TODAY,
                          is_active=is_active)
    cycle.save(user=owner, client_id=ca.id)
    return cycle


def _line(cycle, owner, *, price, discount=Decimal('0'), label='p'):
    product = ProductCatalog(name=f'{label}-{cycle.name}-{price}-{discount}')
    product.save(user=owner, client_id=cycle.client_id)
    line = DealProduct(decision_cycle=cycle, product_catalog_entry=product,
                       quantity=1, unit_price=price, discount_percent=discount)
    line.save(user=owner, client_id=cycle.client_id)
    return line


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def owner(db, client_account_a, role_individual_a):
    return _user('e2e_owner@a.test', client_account_a, role_individual_a)


@pytest.fixture
def world(db, client_account_a, owner):
    """open 60k (discounted) + won 40k + lost 30k, one owner, one campaign."""
    ca = client_account_a
    account = _account(owner, ca)
    campaign = _campaign(owner, ca)

    opened = _cycle(owner, account, ca, name='open', campaign=campaign,
                    is_active=True)
    _line(opened, owner, price=FULL_LINE, label='full')
    _line(opened, owner, price=DISCOUNTED_LINE_LIST, discount=DISCOUNT,
          label='disc')

    won = _cycle(owner, account, ca, name='won', campaign=campaign,
                 outcome=CycleOutcome.WON)
    _line(won, owner, price=WON_VALUE, label='won')

    lost = _cycle(owner, account, ca, name='lost', campaign=campaign,
                  outcome=CycleOutcome.LOST)
    _line(lost, owner, price=LOST_VALUE, label='lost')

    return {'ca': ca, 'owner': owner, 'account': account, 'campaign': campaign,
            'open': opened, 'won': won, 'lost': lost}


def _objective(world, objective_type, target=Decimal('200000')):
    obj = CampaignObjective(
        campaign=world['campaign'], name=str(objective_type),
        objective_type=objective_type, target_value=target,
        is_primary=(objective_type == ObjectiveType.PIPELINE_VALUE),
    )
    obj.save(user=world['owner'], client_id=world['ca'].id)
    return obj


def _modern_quota(world, metric, target=Decimal('200000')):
    quota = Quota(owner=world['owner'], metric=metric, target_value=target,
                  period_start=PERIOD_START, period_end=PERIOD_END)
    quota.save(user=world['owner'], client_id=world['ca'].id)
    return quota


def _legacy_quota(world, target_type):
    from end_users.models import SalesQuota

    quota = SalesQuota(
        user=world['owner'], name=f'Q-{target_type}', target_type=target_type,
        target_value=Decimal('200000'), recurrence_type='annual',
        fiscal_year=TODAY.year, period_number=1,
        period_start=PERIOD_START, period_end=PERIOD_END,
    )
    quota.save()
    return quota


# ===========================================================================
# The fixture itself — the amounts the four paths are measured against
# ===========================================================================

class TestScenarioAmounts:

    def test_derived_totals_are_what_we_think(self, world):
        assert world['open'].total_deal_value == OPEN_VALUE
        assert world['won'].total_deal_value == WON_VALUE
        assert world['lost'].total_deal_value == LOST_VALUE

    def test_the_open_total_is_discounted_money(self, world):
        """Control: ignoring the 50% line would give 80_000, not 60_000. Every
        KPI assertion below therefore proves the discount travelled with it."""
        assert OPEN_VALUE != OPEN_VALUE_IF_DISCOUNT_IGNORED
        undiscounted = sum(
            line.quantity * line.unit_price
            for line in world['open'].deal_products.all()
        )
        assert undiscounted == OPEN_VALUE_IF_DISCOUNT_IGNORED
        assert world['open'].total_deal_value == OPEN_VALUE


# ===========================================================================
# PATH 1 + 2 — campaign objectives
# ===========================================================================

class TestCampaignObjectives:

    def _values(self, world):
        rows = CampaignAnalyticsService(world['ca'].id).get_objectives_progress(
            world['campaign']
        )
        return {row['objective_type']: Decimal(str(row['current_value']))
                for row in rows}

    def test_pipeline_value_is_the_open_cycle_only(self, world):
        _objective(world, ObjectiveType.PIPELINE_VALUE)
        _objective(world, ObjectiveType.REVENUE_WON)

        values = self._values(world)

        assert values[ObjectiveType.PIPELINE_VALUE] == OPEN_VALUE
        assert values[ObjectiveType.PIPELINE_VALUE] != OPEN_VALUE_IF_DISCOUNT_IGNORED

    def test_revenue_won_is_the_won_cycle_only(self, world):
        _objective(world, ObjectiveType.REVENUE_WON)

        assert self._values(world)[ObjectiveType.REVENUE_WON] == WON_VALUE

    def test_won_and_lost_are_out_of_the_pipeline_figure(self, world):
        _objective(world, ObjectiveType.PIPELINE_VALUE)

        pipeline = self._values(world)[ObjectiveType.PIPELINE_VALUE]

        assert pipeline == OPEN_VALUE
        assert pipeline != OPEN_VALUE + WON_VALUE
        assert pipeline != OPEN_VALUE + WON_VALUE + LOST_VALUE

    def test_lost_is_in_neither_figure(self, world):
        _objective(world, ObjectiveType.PIPELINE_VALUE)
        _objective(world, ObjectiveType.REVENUE_WON)

        values = self._values(world)

        assert values[ObjectiveType.PIPELINE_VALUE] + \
            values[ObjectiveType.REVENUE_WON] == OPEN_VALUE + WON_VALUE

    def test_progress_percentage_follows_the_real_amount(self, world):
        """The unblock is visible where the user reads it: 60k / 200k = 30%."""
        _objective(world, ObjectiveType.PIPELINE_VALUE, target=Decimal('200000'))

        rows = CampaignAnalyticsService(world['ca'].id).get_objectives_progress(
            world['campaign']
        )
        row = next(r for r in rows
                   if r['objective_type'] == ObjectiveType.PIPELINE_VALUE)

        assert row['progress_percentage'] == 30.0


# ===========================================================================
# PATH 3 — personal quota / personal objective (THE PATH WITH NO AMOUNT TEST)
# ===========================================================================

class TestPersonalQuotaAndObjective:

    def test_modern_quota_pipeline_reads_the_derived_amount(self, world):
        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE)

        result = quota_progress.compute_progress(quota)

        assert Decimal(str(result.current_value)) == OPEN_VALUE
        assert Decimal(str(result.current_value)) != OPEN_VALUE_IF_DISCOUNT_IGNORED

    def test_modern_quota_won_reads_the_derived_amount(self, world):
        quota = _modern_quota(world, MetricKey.REVENUE_WON)

        result = quota_progress.compute_progress(quota)

        assert Decimal(str(result.current_value)) == WON_VALUE

    def test_modern_quota_attainment_ratio_is_real(self, world):
        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE,
                              target=Decimal('200000'))

        result = quota_progress.compute_progress(quota)

        assert result.ratio == pytest.approx(0.30)

    def test_won_and_lost_are_out_of_the_personal_pipeline(self, world):
        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE)

        value = Decimal(str(quota_progress.compute_progress(quota).current_value))

        assert value == OPEN_VALUE
        assert value != OPEN_VALUE + WON_VALUE + LOST_VALUE

    def test_legacy_sales_quota_pipeline_reads_the_derived_amount(self, world):
        quota = _legacy_quota(world, 'pipeline')

        assert Decimal(str(compute_quota_current_value(quota))) == OPEN_VALUE

    def test_legacy_sales_quota_closed_won_reads_the_derived_amount(self, world):
        quota = _legacy_quota(world, 'closed_won')

        assert Decimal(str(compute_quota_current_value(quota))) == WON_VALUE

    def test_a_cycle_without_lines_contributes_zero(self, world):
        _cycle(world['owner'], world['account'], world['ca'], name='empty',
               campaign=world['campaign'])
        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE)

        value = Decimal(str(quota_progress.compute_progress(quota).current_value))

        assert value == OPEN_VALUE          # unchanged, and no crash


# ===========================================================================
# STATUS is the criterion — is_active is not
# ===========================================================================

class TestStatusIsTheOnlyCriterion:

    def test_an_inactive_open_cycle_still_counts_in_the_pipeline(self, world):
        """`is_active` marks the cycle DISPLAYED for an account; it says nothing
        about whether the deal is open. Only `outcome` does."""
        extra = _cycle(world['owner'], world['account'], world['ca'],
                       name='second-open', campaign=world['campaign'],
                       is_active=False)
        _line(extra, world['owner'], price=Decimal('5000'), label='x')
        assert extra.is_active is False

        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE)
        value = Decimal(str(quota_progress.compute_progress(quota).current_value))

        assert value == OPEN_VALUE + Decimal('5000')

    def test_closing_a_cycle_moves_its_amount_from_pipeline_to_won(self, world):
        pipe = _modern_quota(world, MetricKey.PIPELINE_VALUE)
        won = _modern_quota(world, MetricKey.REVENUE_WON)

        world['open'].outcome = CycleOutcome.WON
        world['open'].outcome_date = TODAY
        world['open'].save(user=world['owner'])
        cache.clear()

        assert Decimal(str(quota_progress.compute_progress(pipe).current_value)) \
            == Decimal('0')
        assert Decimal(str(quota_progress.compute_progress(won).current_value)) \
            == WON_VALUE + OPEN_VALUE


# ===========================================================================
# N+1 — the personal paths stay query-bounded
# ===========================================================================

class TestQueryBound:

    def test_personal_quota_value_is_query_bounded(
        self, world, django_assert_num_queries,
    ):
        quota = _modern_quota(world, MetricKey.PIPELINE_VALUE)
        for index in range(5):
            extra = _cycle(world['owner'], world['account'], world['ca'],
                           name=f'bulk-{index}', campaign=world['campaign'])
            _line(extra, world['owner'], price=Decimal('1000'), label=f'b{index}')

        # 1 owner fetch + 1 metric aggregate. Constant in the number of cycles.
        with django_assert_num_queries(2):
            value = quota_progress.compute_progress(quota).current_value

        assert Decimal(str(value)) == OPEN_VALUE + Decimal('5000')

    def test_a_batch_of_quotas_does_not_scale_per_quota(
        self, world, django_assert_num_queries,
    ):
        """Two quotas sharing (metric, perimeter, window) share ONE metric call."""
        quotas = [
            _modern_quota(world, MetricKey.PIPELINE_VALUE, target=Decimal('100000')),
            _modern_quota(world, MetricKey.PIPELINE_VALUE, target=Decimal('300000')),
        ]

        with django_assert_num_queries(2):
            results = quota_progress.compute_progress_batch(quotas)

        assert {Decimal(str(r.current_value)) for r in results.values()} == {OPEN_VALUE}


# ===========================================================================
# PATH 4 — sales plan / personal objective: NOT WIRED TO DECISION CYCLES (GAP)
# ===========================================================================

class TestSalesPlanPathIsNotWiredToDecisionCycles:
    """GAP — reported, deliberately NOT fixed here (PO decides the scope).

    The sales-plan / personal-milestone path never consumed bi/metrics, so TD-75
    could not unblock it. It reads
    ``performance_data['opportunities']['pipeline_value' | 'won_value']``
    (end_users/services/sales_planning_service.py:79-81,
    end_users/models/sales_milestone.py:276-282), produced by
    ``UserPerformanceService.get_user_complete_performance_optimized``
    (sales_planning_service.py:112-117). That method is RAW SQL over the LEGACY
    tables — ``opportunities_opportunity`` joined to
    ``opportunity_financial_summaries``, summing ``ofs.total_amount`` by the
    legacy ``opp.status`` (end_users/services/user_performance_service.py:83-86).
    Decision cycles and deal products are not in the query at all.

    On top of that the method cannot currently run: its user check does
    ``User.objects.get(id=..., client_id=...)``
    (user_performance_service.py:469-471) while ``User`` carries
    ``client_account`` — every call raises FieldError, which
    ``generate_complete_analysis`` swallows into a fallback payload
    (sales_planning_service.py:148-150).

    Net effect for the PO: a rep with 60_000 of real open pipeline sees no
    amount on a sales-plan milestone — not a stale one, none at all. Two
    separate decisions are needed: repoint this path to bi/metrics (or retire
    the sales-plan milestones), and fix or delete the broken user check.

    These tests pin that reality. When either is fixed they FAIL and must be
    flipped — that is their purpose.
    """

    def test_the_sales_plan_feed_cannot_be_computed_at_all(self, world):
        from core.exceptions import StandardizedValidationError
        from end_users.services import UserPerformanceService

        assert world['open'].total_deal_value == OPEN_VALUE      # not vacuous

        with pytest.raises(StandardizedValidationError) as excinfo:
            UserPerformanceService.get_user_complete_performance_optimized(
                user_id=world['owner'].id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                client_id=str(world['ca'].id),
            )

        # The user check filters a field User does not have.
        assert "Cannot resolve keyword 'client_id'" in str(excinfo.value)

    def test_the_sales_plan_analysis_never_surfaces_the_real_pipeline(self, world):
        """The public entry point does not crash — it silently falls back, and
        the rep's 60_000 appears nowhere in the payload."""
        from end_users.models import SalesPlan, SalesQuota
        from end_users.services.sales_planning_service import SalesPlanningService

        quota = SalesQuota(
            user=world['owner'], name='Q-plan', target_type='pipeline',
            target_value=Decimal('200000'), recurrence_type='annual',
            fiscal_year=TODAY.year, period_number=1,
            period_start=PERIOD_START, period_end=PERIOD_END,
        )
        quota.save()

        plan = SalesPlan(user=world['owner'], quota=quota, name='Plan',
                         period_start=PERIOD_START, period_end=PERIOD_END)
        plan.save(client_id=world['ca'].id)

        analysis = SalesPlanningService.generate_complete_analysis(plan)

        assert '60000' not in str(analysis)
        assert str(OPEN_VALUE) not in str(analysis)

    def test_the_amounts_it_would_read_come_from_the_legacy_tables(self):
        """The source of the gap, as an assertion rather than a comment."""
        import inspect

        from end_users.services import user_performance_service as live

        source = inspect.getsource(live.UserPerformanceService
                                   .get_user_complete_performance_optimized)

        assert 'opportunities_opportunity' in source
        assert 'opportunities_opportunityfinancialsummary' in source
        assert 'ofs.total_amount' in source
        # ... and nothing from the modern product roll-up.
        assert 'decision_cycles' not in source
        assert 'deal_products' not in source
        assert 'total_deal_value' not in source
