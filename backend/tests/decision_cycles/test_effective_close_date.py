# backend/tests/decision_cycles/test_effective_close_date.py
"""
The effective close date — the two-level rule, and the personal pipeline on it.

RULE (PO-locked, declared once in decision_cycles/services/close_date_sql.py):

  1. ``DecisionCycle.expected_close_date`` — the MANUAL field. Wins when set.
  2. FALLBACK — the date of the LAST activity of the cycle's CLOSING step
     (``stage='CLOSING'``), read as ``COALESCE(due_date, scheduled_date)``,
     CANCELLED excluded.
  3. Neither → None. No close date is a real answer, not a zero.

Before this sub-step the personal pipeline anchored on ``Max(steps.expected_end)``
(bi/metrics/sales_metrics.py), which is NULL on every freshly created cycle —
step auto-creation sets ``expected_end=None`` on all five steps — so a normally
used deal was invisible to a windowed pipeline read. That is the "objective shows
0" bug.

What is deliberately NOT changed, and is pinned here as a regression guard:
  * CAMPAIGN pipeline is UNWINDOWED (``period=None`` on both its paths), so no
    campaign number can move;
  * REVENUE_WON still windows on ``outcome_date``.

Harness mirrors tests/quotas/test_quota_attainment_amounts.py (same role/user
factories, same give_deal_value helper, same TODAY-relative window).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi import metrics
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.constants import CycleOutcome, PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.decision_cycles.services.close_date_sql import (
    CLOSE_DATE_ALIAS,
    annotate_effective_close_date,
)
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


TODAY = date.today()
WINDOW_START = TODAY - timedelta(days=15)
WINDOW_END = TODAY + timedelta(days=15)
IN_WINDOW = TODAY
AFTER_WINDOW = WINDOW_END + timedelta(days=365)


# ---------------------------------------------------------------------------
# factories (mirror tests/quotas/test_quota_attainment_amounts.py)
# ---------------------------------------------------------------------------

def _role(ca, name):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=ca, name=name, is_individual=True,
        read=True, write=True, modify=True, can_delete=True,
    )


def _user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role,
                               is_active=True)


def _account(owner, ca, name='Acc'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, ca, *, name='dc', amount=Decimal('60000'),
           expected_close_date=None, outcome=None, outcome_date=None,
           with_steps=True):
    """An OPEN cycle worth ``amount``, with the real 5-step pipeline attached so
    the CLOSING step exists exactly as the app creates it."""
    cycle = DecisionCycle(account=_account(owner, ca, name=f'Acc-{name}-{owner.email}'),
                          owner=owner, name=f'{name}-{owner.email}',
                          expected_close_date=expected_close_date,
                          outcome=outcome, outcome_date=outcome_date)
    cycle.save(user=owner, client_id=ca.id)

    if with_steps:
        previous = None
        for order, stage in enumerate(
            [PipelineStep.QUALIFICATION, PipelineStep.TECHNICAL_FIT,
             PipelineStep.SOLUTION_VALIDATION, PipelineStep.BUSINESS_CASE,
             PipelineStep.CLOSING], start=1,
        ):
            step = DecisionStep(cycle=cycle, name=stage.label, stage=stage.value,
                                order=order, previous_step=previous,
                                expected_end=None)   # exactly as the app creates them
            step.save(user=owner, client_id=ca.id)
            previous = step

    if amount is not None:
        give_deal_value(cycle, amount, user=owner)
    return cycle


def _step(cycle, stage):
    return cycle.steps.get(stage=stage)


def _activity(cycle, stage, owner, ca, *, scheduled_date=None, due_date=None,
              status=ActivityStatus.PLANNED, title='act'):
    activity = Activity(
        title=title, activity_type=ActivityType.CALL, status=status,
        account=cycle.account, owner=owner,
        decision_cycle=cycle, decision_step=_step(cycle, stage),
        scheduled_date=scheduled_date, due_date=due_date,
    )
    activity.save(user=owner, client_id=ca.id)
    return activity


def _quota(owner, ca, metric, *, target=Decimal('100000')):
    quota = Quota(owner=owner, metric=metric, target_value=target,
                  period_start=WINDOW_START, period_end=WINDOW_END)
    quota.save(user=owner, client_id=ca.id)
    return quota


def _attainment(quota):
    return Decimal(str(P.compute_progress(quota).current_value))


def _resolved(cycle):
    """The effective close date as the ANNOTATION computes it (the mass-read
    binding), not via the property — so the SQL itself is under test."""
    return (
        annotate_effective_close_date(DecisionCycle.objects.filter(pk=cycle.pk))
        .values_list(CLOSE_DATE_ALIAS, flat=True)
        .first()
    )


@pytest.fixture
def rep(db, client_account_a):
    return _user('rep-ecd@a.test', client_account_a, _role(client_account_a, 'Ind'))


# ===========================================================================
# THE RESOLVER — the rule itself
# ===========================================================================

class TestResolver:

    def test_the_manual_date_wins(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=IN_WINDOW)

        assert _resolved(cycle) == IN_WINDOW

    def test_the_manual_date_wins_over_a_closing_activity(self, rep, client_account_a):
        """Precedence, proved with a DIFFERENT fallback date underneath: only a
        resolver that reads the manual field first can return IN_WINDOW."""
        cycle = _cycle(rep, client_account_a, expected_close_date=IN_WINDOW)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=AFTER_WINDOW)

        assert _resolved(cycle) == IN_WINDOW

    def test_it_falls_back_to_the_closing_step_activity(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW)

        assert _resolved(cycle) == IN_WINDOW

    def test_the_fallback_takes_the_LAST_closing_activity(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW - timedelta(days=5), title='early')
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW, title='late')

        assert _resolved(cycle) == IN_WINDOW

    def test_an_activity_of_a_NON_closing_step_is_ignored(self, rep, client_account_a):
        """Specificity: the rule reads the CLOSING step, not any activity of the
        cycle. A dated qualification call must not become the close date."""
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.QUALIFICATION, rep, client_account_a,
                  scheduled_date=IN_WINDOW)

        assert _resolved(cycle) is None

    def test_due_date_is_read_when_it_is_the_populated_one(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  due_date=IN_WINDOW)

        assert _resolved(cycle) == IN_WINDOW

    def test_a_cancelled_closing_activity_does_not_count(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW, status=ActivityStatus.CANCELLED)

        assert _resolved(cycle) is None

    def test_no_manual_date_and_no_closing_activity_is_None(self, rep, client_account_a):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)

        assert _resolved(cycle) is None

    def test_the_property_agrees_with_the_annotation(self, rep, client_account_a):
        """One rule, two bindings: the single-instance accessor must never
        diverge from the mass-read SQL."""
        manual = _cycle(rep, client_account_a, name='man',
                        expected_close_date=IN_WINDOW)
        fallback = _cycle(rep, client_account_a, name='fb', expected_close_date=None)
        _activity(fallback, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW)
        undated = _cycle(rep, client_account_a, name='none', expected_close_date=None)

        for cycle in (manual, fallback, undated):
            fresh = DecisionCycle.objects.get(pk=cycle.pk)
            assert fresh.effective_close_date == _resolved(cycle)

    def test_the_property_is_free_on_an_annotated_row(
        self, rep, client_account_a, django_assert_num_queries,
    ):
        cycle = _cycle(rep, client_account_a, expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW)

        row = annotate_effective_close_date(
            DecisionCycle.objects.filter(pk=cycle.pk)
        ).first()

        with django_assert_num_queries(0):
            assert row.effective_close_date == IN_WINDOW


# ===========================================================================
# PERSONAL PIPELINE — anchored on the effective close date
# ===========================================================================

class TestPersonalPipelineAnchor:

    def test_a_manually_dated_deal_counts_in_the_window(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('60000'),
               expected_close_date=IN_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_a_deal_dated_far_out_is_excluded(self, rep, client_account_a):
        _cycle(rep, client_account_a, amount=Decimal('60000'),
               expected_close_date=AFTER_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('0')

    def test_a_deal_dated_only_by_its_closing_activity_counts(
        self, rep, client_account_a,
    ):
        cycle = _cycle(rep, client_account_a, amount=Decimal('60000'),
                       expected_close_date=None)
        _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                  scheduled_date=IN_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_a_deal_dated_only_by_a_NON_closing_activity_does_not_count(
        self, rep, client_account_a,
    ):
        cycle = _cycle(rep, client_account_a, amount=Decimal('60000'),
                       expected_close_date=None)
        _activity(cycle, PipelineStep.QUALIFICATION, rep, client_account_a,
                  scheduled_date=IN_WINDOW)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('0')

    def test_a_deal_with_no_close_date_at_all_is_excluded(self, rep, client_account_a):
        """Unchanged from before — but now it means "nobody said when this
        closes", not "the steps happen to be undated"."""
        _cycle(rep, client_account_a, amount=Decimal('60000'),
               expected_close_date=None)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('0')

    def test_a_won_deal_is_never_in_the_pipeline(self, rep, client_account_a):
        _cycle(rep, client_account_a, name='open', amount=Decimal('60000'),
               expected_close_date=IN_WINDOW)
        _cycle(rep, client_account_a, name='won', amount=Decimal('40000'),
               expected_close_date=IN_WINDOW,
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(rep, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_the_pipeline_aggregation_stays_query_bounded(
        self, rep, client_account_a, django_assert_max_num_queries,
    ):
        """Both the amount and the close date are isolated correlated
        subqueries, so N cycles cost the same as one. Guards the N+1 a Python
        resolver in a loop would introduce."""
        for i in range(4):
            cycle = _cycle(rep, client_account_a, name=f'c{i}',
                           amount=Decimal('1000'), expected_close_date=None)
            _activity(cycle, PipelineStep.CLOSING, rep, client_account_a,
                      scheduled_date=IN_WINDOW)

        base = DecisionCycle.objects.filter(client_id=client_account_a.id)
        with django_assert_max_num_queries(2):
            metrics.pipeline_value(base, user=rep,
                                   period=(WINDOW_START, WINDOW_END))


# ===========================================================================
# WHAT MUST NOT MOVE — cross-coverage guards
# ===========================================================================

class TestUntouchedConsumers:

    def test_campaign_pipeline_is_unwindowed_and_unaffected(
        self, rep, client_account_a,
    ):
        """The campaign path calls pipeline_value with period=None
        (campaign_analytics_service.py) — a cycle with NO close date at all must
        still be counted there. The anchor change cannot move a campaign
        number."""
        _cycle(rep, client_account_a, amount=Decimal('60000'),
               expected_close_date=None)

        base = DecisionCycle.objects.filter(client_id=client_account_a.id)

        assert Decimal(str(metrics.pipeline_value(base, user=rep, period=None))) \
            == Decimal('60000')

    def test_revenue_won_still_windows_on_outcome_date(self, rep, client_account_a):
        """WON keeps its own anchor: a deal won inside the window counts even
        with no expected close date, and the effective close date does not
        window it."""
        _cycle(rep, client_account_a, name='won', amount=Decimal('40000'),
               expected_close_date=None,
               outcome=CycleOutcome.WON, outcome_date=TODAY)
        _cycle(rep, client_account_a, name='wonlate', amount=Decimal('7000'),
               expected_close_date=IN_WINDOW,          # in-window EXPECTED date
               outcome=CycleOutcome.WON,
               outcome_date=WINDOW_END + timedelta(days=40))   # out-of-window ACTUAL

        assert _attainment(_quota(rep, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')
