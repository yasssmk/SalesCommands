# backend/tests/quotas/test_quota_attainment_amounts.py
"""
Personal-quota ATTAINMENT in money — the typed, period-bounded, role-scoped rule.

The engine already exists (quotas/services/progress.py consuming
bi/metrics/sales_metrics.py); what did not exist was coverage of its MONEY
behaviour. tests/quotas/* covered perimeters and ratio mechanics over COUNTS
(MetricKey.DECISION_CYCLES) and never asserted an amount, so none of the rules
below were pinned.

The rule, as implemented and asserted here:

  TYPE      PIPELINE_VALUE -> OPEN cycles   (outcome IS NULL)
            REVENUE_WON    -> WON cycles    (outcome = WON)
            never mixed; LOST counts in neither.

  PERIOD    WON      -> bounded by ``closed_at``, the timestamp of the WON
                       transition, stamped by DecisionCycle.save() and compared
                       at date granularity (sales_metrics.revenue_won). The
                       scenarios below give the two won cycles the SAME
                       outcome_date and differ only in closed_at, so the window
                       can only be reading the new anchor.
            PIPELINE -> bounded by the cycle's EXPECTED CLOSE, which is derived
                       as ``Max(steps.expected_end)`` via a correlated Subquery
                       (sales_metrics.py:222-235). DecisionCycle stores no
                       ``expected_close_date`` column — see the module note in
                       the report; an open cycle with no dated step has a NULL
                       anchor and therefore falls outside ANY window. That
                       consequence is pinned below because it is easy to read as
                       a bug and is in fact the documented behaviour.
            Both bounds are INCLUSIVE (``__gte`` / ``__lte``, sales_metrics.py
            ``_between``) — asserted on the exact edges.

  SCOPE     individual -> the owner's own cycles.
            manager    -> the WHOLE team subtree rooted at the manager's node,
                          resolved by quotas/services/progress.team_subtree_ids
                          (progress.py:86-119) and applied by
                          compute_metric_for_team_node (progress.py:122-138).
            admin      -> the whole tenant.

  AMOUNT    total_deal_value, the derived product roll-up, discount included.

Harness mirrors tests/quotas/test_quota_progress_hierarchy.py (same team/user
factories) and uses tests/deal_value_helpers.give_deal_value for the money.

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.constants import CycleOutcome, PipelineStep
from app_modules.decision_cycles.models import DealProduct, DecisionCycle, DecisionStep
from app_modules.product_catalog.models import ProductCatalog
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P
from tests.deal_value_helpers import give_deal_value, set_closed_at


pytestmark = pytest.mark.django_db


TODAY = date.today()
WINDOW_START = TODAY - timedelta(days=15)
WINDOW_END = TODAY + timedelta(days=15)
BEFORE_WINDOW = WINDOW_START - timedelta(days=1)
AFTER_WINDOW = WINDOW_END + timedelta(days=1)


def _at(day, hour=12):
    """Midday on ``day``, aware — a closed_at value for a win on that date."""
    return timezone.make_aware(
        timezone.datetime(day.year, day.month, day.day, hour, 0)
    )


# ---------------------------------------------------------------------------
# factories (mirror tests/quotas/test_quota_progress_hierarchy.py)
# ---------------------------------------------------------------------------

def _role(ca, name, *, admin=False, manager=False, individual=False):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=ca, name=name, is_admin=admin, is_manager=manager,
        is_individual=individual, read=True, write=True, modify=True, can_delete=True,
    )


def _user(email, ca, role, team=None):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True, team=team)


def _team(ca, name, *, parent=None, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, parent_team=parent,
                               manager=manager)


def _account(owner, ca, name='Acc'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, ca, *, amount, name='dc', outcome=None, outcome_date=None,
           closed_at=None, expected_close=None, account=None):
    """A cycle worth ``amount``.

    ``expected_close`` becomes a step's ``expected_end`` — the cycle-level
    expected close the pipeline window is evaluated on. Pass None to leave the
    cycle undated (it then falls outside every window).
    """
    account = account or _account(owner, ca, name=f'Acc-{owner.email}')
    cycle = DecisionCycle(account=account, owner=owner, name=f'{name}-{owner.email}',
                          outcome=outcome, outcome_date=outcome_date)
    cycle.save(user=owner, client_id=ca.id)
    if expected_close is not None:
        step = DecisionStep(cycle=cycle, name='s', stage=PipelineStep.QUALIFICATION,
                            order=1, expected_end=expected_close)
        step.save(user=owner, client_id=ca.id)
    give_deal_value(cycle, amount, user=owner)
    if closed_at is not None:
        # save() stamped closed_at at the transition (i.e. now); rewrite it when
        # the scenario needs the win dated elsewhere.
        set_closed_at(cycle, closed_at)
    return cycle


def _discounted_cycle(owner, ca, *, list_price, discount, expected_close):
    """One line at ``list_price`` with ``discount``% off — so the attainment can
    only be right if the discount travelled with it."""
    cycle = _cycle(owner, ca, amount=None, name='disc',
                   expected_close=expected_close)
    product = ProductCatalog(name=f'disc-{owner.email}-{list_price}')
    product.save(user=owner, client_id=ca.id)
    line = DealProduct(decision_cycle=cycle, product_catalog_entry=product,
                       quantity=1, unit_price=list_price,
                       discount_percent=discount)
    line.save(user=owner, client_id=ca.id)
    return cycle


def _quota(owner, ca, metric, *, target=Decimal('100000'),
           start=WINDOW_START, end=WINDOW_END):
    quota = Quota(owner=owner, metric=metric, target_value=target,
                  period_start=start, period_end=end)
    quota.save(user=owner, client_id=ca.id)
    return quota


def _attainment(quota):
    return Decimal(str(P.compute_progress(quota).current_value))


@pytest.fixture
def rep(db, client_account_a):
    return _user('rep@a.test', client_account_a, _role(client_account_a, 'Ind',
                                                       individual=True))


# ===========================================================================
# PIPELINE quota — open cycles, windowed on the expected close
# ===========================================================================

class TestPipelineQuota:

    def test_open_cycle_expected_to_close_in_the_window_counts(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_open_cycle_expected_to_close_outside_the_window_is_excluded(
        self, rep, client_account_a,
    ):
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('25000'), name='late',
               expected_close=AFTER_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_a_won_cycle_is_not_in_a_pipeline_quota(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY, expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_a_lost_cycle_is_not_in_a_pipeline_quota(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('30000'), name='lost',
               outcome=CycleOutcome.LOST, outcome_date=TODAY, expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_an_undated_open_cycle_falls_outside_every_window(
        self, rep, client_account_a,
    ):
        """DOCUMENTED consequence of deriving the expected close from the steps:
        a cycle with no dated step has a NULL anchor, so a WINDOWED quota cannot
        see it (sales_metrics.py:216-218). Pinned so the behaviour is a decision,
        not a surprise."""
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=None)

        windowed = _quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)
        assert _attainment(windowed) == Decimal('0')

        # ... while the same cycle IS counted by an unwindowed read.
        from app_modules.bi import metrics
        assert Decimal(str(metrics.pipeline_value(
            DecisionCycle.objects.filter(client_id=client_account_a.id),
            user=rep, period=None,
        ))) == Decimal('60000')

    def test_only_the_owner_cycles_count_for_an_individual(
        self, rep, client_account_a,
    ):
        other = _user('other@a.test', client_account_a,
                      _role(client_account_a, 'Ind2', individual=True))
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        _cycle(other, client_account_a, amount=Decimal('99000'), expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_discount_flows_into_the_attainment(self, rep, client_account_a):
        _discounted_cycle(rep, client_account_a, list_price=Decimal('40000'),
                          discount=Decimal('50'), expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('20000')


# ===========================================================================
# WON quota — won cycles, windowed on outcome_date (the close date)
# ===========================================================================

class TestWonQuota:

    def test_cycle_won_inside_the_window_counts(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')

    def test_cycle_won_outside_the_window_is_excluded(self, rep, client_account_a):
        """Both cycles carry outcome_date=TODAY (inside the window); they differ
        only in closed_at. Only the WON-transition anchor can exclude the second
        one, so this test fails if the window ever reads outcome_date again."""
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('15000'), name='old-won',
               outcome=CycleOutcome.WON, outcome_date=TODAY,
               closed_at=_at(BEFORE_WINDOW))

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')

    def test_an_open_cycle_is_not_in_a_won_quota(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')

    def test_a_lost_cycle_is_not_in_a_won_quota(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(rep, client_account_a, amount=Decimal('30000'), name='lost',
               outcome=CycleOutcome.LOST, outcome_date=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')

    def test_the_won_amount_is_the_deal_roll_up_not_a_target(
        self, rep, client_account_a,
    ):
        _cycle(rep, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        quota = _quota(rep, client_account_a, MetricKey.REVENUE_WON,
                       target=Decimal('80000'))

        result = P.compute_progress(quota)

        assert Decimal(str(result.current_value)) == Decimal('40000')
        assert result.ratio == pytest.approx(0.5)


# ===========================================================================
# Period edges — inclusive on both ends
# ===========================================================================

class TestWindowEdges:

    def test_pipeline_includes_both_edges_and_excludes_the_days_outside(
        self, rep, client_account_a,
    ):
        _cycle(rep, client_account_a, amount=Decimal('1000'), name='edge-start',
               expected_close=WINDOW_START)
        _cycle(rep, client_account_a, amount=Decimal('2000'), name='edge-end',
               expected_close=WINDOW_END)
        _cycle(rep, client_account_a, amount=Decimal('4000'), name='day-before',
               expected_close=BEFORE_WINDOW)
        _cycle(rep, client_account_a, amount=Decimal('8000'), name='day-after',
               expected_close=AFTER_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('3000')          # 1000 + 2000, edges in

    def test_won_includes_both_edges_and_excludes_the_days_outside(
        self, rep, client_account_a,
    ):
        for label, when, amount in (
            ('edge-start', WINDOW_START, Decimal('1000')),
            ('edge-end', WINDOW_END, Decimal('2000')),
            ('day-before', BEFORE_WINDOW, Decimal('4000')),
            ('day-after', AFTER_WINDOW, Decimal('8000')),
        ):
            _cycle(rep, client_account_a, amount=amount, name=label,
                   outcome=CycleOutcome.WON, outcome_date=when,
                   closed_at=_at(when))

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('3000')


# ===========================================================================
# Manager scope — the whole team subtree, via the existing helper
# ===========================================================================

class TestManagerScope:

    def _hierarchy(self, ca):
        """manager on 'Region', two members below it, one outsider elsewhere."""
        mgr_role = _role(ca, 'Mgr', manager=True)
        ind_role = _role(ca, 'Ind', individual=True)

        manager = _user('mgr@a.test', ca, mgr_role)
        region = _team(ca, 'Region', manager=manager)
        country = _team(ca, 'Country', parent=region)
        manager.team = region
        manager.save()

        member_direct = _user('t1@a.test', ca, ind_role, team=region)
        member_deep = _user('t2@a.test', ca, ind_role, team=country)
        outsider = _user('out@a.test', ca, ind_role, team=_team(ca, 'Other'))

        return manager, member_direct, member_deep, outsider

    def test_pipeline_quota_sums_the_whole_subtree(self, client_account_a):
        manager, direct, deep, outsider = self._hierarchy(client_account_a)
        _cycle(direct, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        _cycle(deep, client_account_a, amount=Decimal('25000'), expected_close=TODAY)
        _cycle(outsider, client_account_a, amount=Decimal('99000'), expected_close=TODAY)

        quota = _quota(manager, client_account_a, MetricKey.PIPELINE_VALUE)

        assert _attainment(quota) == Decimal('85000')       # 60k + 25k, no outsider

    def test_won_quota_sums_the_whole_subtree(self, client_account_a):
        manager, direct, deep, outsider = self._hierarchy(client_account_a)
        _cycle(direct, client_account_a, amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(deep, client_account_a, amount=Decimal('10000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(outsider, client_account_a, amount=Decimal('99000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        quota = _quota(manager, client_account_a, MetricKey.REVENUE_WON)

        assert _attainment(quota) == Decimal('50000')

    def test_the_manager_perimeter_is_the_shared_team_helper(self, client_account_a):
        """Team membership is resolved by progress.team_subtree_ids, not by a
        second notion of 'my team' — the node plus every descendant."""
        manager, direct, deep, _outsider = self._hierarchy(client_account_a)

        subtree = P.team_subtree_ids(manager.team_id, client_account_a.id)

        assert direct.team_id in subtree
        assert deep.team_id in subtree          # descendant, not a direct member
        assert manager.team_id in subtree

    def test_a_cycle_owned_outside_the_subtree_never_counts(self, client_account_a):
        manager, direct, _deep, outsider = self._hierarchy(client_account_a)
        _cycle(outsider, client_account_a, amount=Decimal('99000'), expected_close=TODAY)

        quota = _quota(manager, client_account_a, MetricKey.PIPELINE_VALUE)

        assert _attainment(quota) == Decimal('0')

    def test_admin_measures_the_whole_tenant(self, client_account_a):
        admin = _user('admin@a.test', client_account_a,
                      _role(client_account_a, 'Adm', admin=True))
        someone = _user('anyone@a.test', client_account_a,
                        _role(client_account_a, 'Ind3', individual=True))
        _cycle(someone, client_account_a, amount=Decimal('12000'), expected_close=TODAY)

        quota = _quota(admin, client_account_a, MetricKey.PIPELINE_VALUE)

        assert _attainment(quota) == Decimal('12000')


# ===========================================================================
# Query bound
# ===========================================================================

class TestQueryBound:

    def test_manager_attainment_does_not_scale_with_the_team(
        self, client_account_a, django_assert_num_queries,
    ):
        mgr_role = _role(client_account_a, 'Mgr', manager=True)
        ind_role = _role(client_account_a, 'Ind', individual=True)
        manager = _user('mgr2@a.test', client_account_a, mgr_role)
        region = _team(client_account_a, 'Region2', manager=manager)
        manager.team = region
        manager.save()

        for index in range(4):
            member = _user(f'm{index}@a.test', client_account_a, ind_role, team=region)
            _cycle(member, client_account_a, amount=Decimal('1000'),
                   expected_close=TODAY)

        quota = _quota(manager, client_account_a, MetricKey.PIPELINE_VALUE)

        # owner fetch + team adjacency descent + the metric aggregate.
        with django_assert_num_queries(3):
            value = P.compute_progress(quota).current_value

        assert Decimal(str(value)) == Decimal('4000')

    def test_a_batch_of_quotas_shares_one_metric_call(
        self, rep, client_account_a, django_assert_num_queries,
    ):
        _cycle(rep, client_account_a, amount=Decimal('60000'), expected_close=TODAY)
        quotas = [
            _quota(rep, client_account_a, MetricKey.PIPELINE_VALUE,
                   target=Decimal('100000')),
            _quota(rep, client_account_a, MetricKey.PIPELINE_VALUE,
                   target=Decimal('300000')),
        ]

        with django_assert_num_queries(2):
            results = P.compute_progress_batch(quotas)

        assert {Decimal(str(r.current_value)) for r in results.values()} \
            == {Decimal('60000')}


# ===========================================================================
# The one divergence from the locked rule — legacy SalesQuota (REPORTED)
# ===========================================================================

class TestLegacySalesQuotaIsNotWindowedOnPipeline:
    """OPEN QUESTION for the PO — pinned, not changed.

    The locked rule says a PIPELINE quota counts open cycles whose expected
    close falls in the window. The MODERN quota path does exactly that (above).
    The LEGACY ``end_users.SalesQuota`` path does NOT: bi/quota.py:48-54 applies
    no period at all to ``pipeline``, by an explicit decision recorded in its own
    docstring ("STOCK: everything currently open for the user (no period filter
    — a deal opened 8 months ago is still in the pipe today)").

    Both readings are defensible and the two quota systems currently disagree.
    Changing it silently would overwrite a deliberate design note, so this test
    pins today's behaviour; flip it if the PO wants the legacy path windowed too.
    """

    def test_legacy_pipeline_ignores_the_quota_window(self, rep, client_account_a):
        from app_modules.bi.quota import compute_quota_current_value
        from end_users.models import SalesQuota

        # expected close well outside the quota window
        _cycle(rep, client_account_a, amount=Decimal('60000'),
               expected_close=AFTER_WINDOW + timedelta(days=200))

        legacy = SalesQuota(
            user=rep, name='Q-pipe', target_type='pipeline',
            target_value=Decimal('100000'), recurrence_type='annual',
            fiscal_year=TODAY.year, period_number=1,
            period_start=WINDOW_START, period_end=WINDOW_END,
        )
        legacy.save()

        # The legacy path counts it (no window); the modern one would not.
        assert Decimal(str(compute_quota_current_value(legacy))) == Decimal('60000')
        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('0')
