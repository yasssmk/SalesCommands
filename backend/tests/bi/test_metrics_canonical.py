# backend/tests/bi/test_metrics_canonical.py
"""
Canonical Sales metric formulas — parity guard + filter proofs + anti-fan-out.

The parity guard is the heart of this sub-step: for every metric that ALREADY
has a live calculation on the campaign objectives (the production reference),
the canonical function called with ``source_campaign=<campaign>`` and
``period=None`` must return the SAME number as that campaign calculation. Where
the frozen canonical definition DIVERGES from the campaign one by design
(MEETINGS predicate, NEW_LOGOS field), that is asserted explicitly instead of
faked into a false equality.

DB: Postgres (subqueries + aggregates are exercised for real).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import (
    ActivityOutcome, ActivityStatus, ActivityType,
)
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignAccountStatus, ObjectiveType
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.decision_cycles.constants import CycleOutcome, PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.bi import metrics
from tests.deal_value_helpers import give_deal_value


TODAY = timezone.now().date()


# ---------------------------------------------------------------------------
# Factories (control created_at / expected_end / outcome_date / owner / campaign)
# ---------------------------------------------------------------------------

def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type='OUTBOUND', owner=owner, executor=owner,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_cycle(owner, account, ca, *, name='dc', source_campaign=None,
              estimated_value=None, outcome=None, outcome_date=None, created_on=None,
              expected_close_date=None):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign,
                       outcome=outcome, outcome_date=outcome_date,
                       expected_close_date=expected_close_date)
    dc.save(user=owner, client_id=ca.id)
    # TD-75: the money metrics sum the DERIVED product roll-up, so the amount is
    # seeded as a real product line. The parameter keeps its name so every call
    # site below reads unchanged; `estimated_value` itself is never set.
    give_deal_value(dc, estimated_value, user=owner)
    if created_on is not None:
        # created_at is auto_now_add; force it via .update() (bypasses auto).
        DecisionCycle.objects.filter(pk=dc.pk).update(
            created_at=timezone.make_aware(
                timezone.datetime(created_on.year, created_on.month, created_on.day, 12, 0)
            )
        )
        dc.refresh_from_db()
    return dc


def _mk_step(cycle, ca, order, expected_end, owner):
    s = DecisionStep(cycle=cycle, name=f'step{order}', stage=PipelineStep.QUALIFICATION,
                     order=order, expected_end=expected_end)
    s.save(user=owner, client_id=ca.id)
    return s


def _mk_activity(owner, account, ca, *, outcome=None, status=ActivityStatus.PLANNED,
                 activity_type=ActivityType.MEETING, scheduled_date=None,
                 decision_cycle=None, decision_step=None, campaign=None):
    a = Activity(title='a', activity_type=activity_type, status=status, outcome=outcome,
                 account=account, owner=owner, campaign=campaign,
                 decision_cycle=decision_cycle, decision_step=decision_step,
                 scheduled_date=scheduled_date or TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


@pytest.fixture
def owner_a(db, client_account_a, role_individual_a):
    return _mk_user('owner_a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def owner_a2(db, client_account_a, role_individual_a):
    return _mk_user('owner_a2@a.test', client_account_a, role_individual_a)


def _dc_base(ca):
    return DecisionCycle.objects.filter(client_id=ca.id)


def _act_base(ca):
    return Activity.objects.filter(client_id=ca.id)


def _acc_base(ca):
    return CompanyAccount.objects.filter(client_id=ca.id)


# ===========================================================================
# PARITY — canonical(source_campaign=camp, period=None) == campaign service
# ===========================================================================

class TestParityWithCampaignObjectives:
    """Each metric with a living campaign calculation is named explicitly."""

    def _consistent_campaign_data(self, owner, ca):
        """A campaign where every attributed DC carries BOTH the DC.source_campaign
        link (canonical attribution) AND a campaign activity pointing at it
        (campaign-service attribution), so the two attribution paths select the
        same cycles and parity is meaningful."""
        camp = _mk_campaign(owner, ca)
        acc = _mk_account('Acc', owner, ca)

        # open cycle attributed to the campaign, estimated_value 1000
        open_dc = _mk_cycle(owner, acc, ca, name='open', source_campaign=camp,
                            estimated_value=1000)
        _mk_activity(owner, acc, ca, campaign=camp, decision_cycle=open_dc,
                     activity_type=ActivityType.CALL)

        # won cycle attributed to the campaign, estimated_value 500
        won_dc = _mk_cycle(owner, acc, ca, name='won', source_campaign=camp,
                           estimated_value=500, outcome=CycleOutcome.WON,
                           outcome_date=TODAY)
        _mk_activity(owner, acc, ca, campaign=camp, decision_cycle=won_dc,
                     activity_type=ActivityType.CALL)

        # a DC of ANOTHER campaign — must not leak into the campaign totals
        other_camp = _mk_campaign(owner, ca, name='Other')
        other_dc = _mk_cycle(owner, acc, ca, name='other', source_campaign=other_camp,
                             estimated_value=9999)
        _mk_activity(owner, acc, ca, campaign=other_camp, decision_cycle=other_dc,
                     activity_type=ActivityType.CALL)

        return camp

    def test_pipeline_value_parity(self, owner_a, client_account_a):
        camp = self._consistent_campaign_data(owner_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.pipeline_value(
            _dc_base(client_account_a), source_campaign=camp, period=None)
        assert canonical == svc._sum_pipeline_value(camp) == 1000.0

    def test_revenue_won_parity(self, owner_a, client_account_a):
        camp = self._consistent_campaign_data(owner_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.revenue_won(
            _dc_base(client_account_a), source_campaign=camp, period=None)
        assert canonical == svc._sum_revenue_won(camp) == 500.0

    def test_decision_cycles_parity(self, owner_a, client_account_a):
        # NB divergence documented: campaign attributes via Activity.campaign,
        # canonical via DecisionCycle.source_campaign. With consistent data
        # (every campaign DC has a campaign activity) the two agree.
        camp = self._consistent_campaign_data(owner_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.decision_cycles(
            _dc_base(client_account_a), source_campaign=camp, period=None)
        assert canonical == svc._count_decision_cycles(camp) == 2

    def test_meetings_diverges_from_campaign_by_definition(self, owner_a, client_account_a):
        # Campaign MEETINGS = Activity type=MEETING + status=COMPLETED.
        # Canonical MEETINGS = outcome=MEETING_SCHEDULED. Different predicate.
        camp = _mk_campaign(owner_a, client_account_a)
        acc = _mk_account('Acc', owner_a, client_account_a)
        cyc = _mk_cycle(owner_a, acc, client_account_a, source_campaign=camp)
        step = _mk_step(cyc, client_account_a, 1, TODAY, owner_a)

        # counted by CAMPAIGN only (completed meeting, but not MEETING_SCHEDULED)
        _mk_activity(owner_a, acc, client_account_a, campaign=camp,
                     decision_cycle=cyc, decision_step=step,
                     activity_type=ActivityType.MEETING,
                     status=ActivityStatus.COMPLETED, outcome=ActivityOutcome.SUCCESSFUL)
        # counted by CANONICAL only (MEETING_SCHEDULED outcome, but a CALL)
        _mk_activity(owner_a, acc, client_account_a, campaign=camp,
                     decision_cycle=cyc, decision_step=step,
                     activity_type=ActivityType.CALL,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)

        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.meetings(
            _act_base(client_account_a), source_campaign=camp, period=None)
        assert svc._count_meetings(camp) == 1     # the MEETING+COMPLETED one
        assert canonical == 1                      # the MEETING_SCHEDULED one
        # Same campaign, same fixtures, DIFFERENT sets — divergence is real.


# ===========================================================================
# NEW_LOGOS — became_client_at field exists (sub-step 3); skip removed.
# ===========================================================================

class TestNewLogosFilters:
    """NEW_LOGOS counts accounts converted (became_client_at set) in the window,
    filterable by owner and source_campaign. An account imported as CLIENT
    (became_client_at NULL) is NOT a new logo."""

    def _acc(self, owner, ca, *, became_client_at=None, name='Acc'):
        acc = CompanyAccount(company_name=name, has_buying_decision=True,
                             account_owner=owner)
        acc.save(user=owner, client_id=ca.id)
        if became_client_at is not None:
            # became_client_at is editable=False (system-set); assign in code.
            acc.became_client_at = became_client_at
            acc.save(user=owner)
        return acc

    def _acc_base(self, ca):
        return CompanyAccount.objects.filter(client_id=ca.id)

    def test_imported_client_not_counted(self, owner_a, client_account_a):
        # a converted account (in period) IS counted...
        self._acc(owner_a, client_account_a,
                  became_client_at=timezone.now(), name='converted')
        # ...an imported CLIENT with NULL became_client_at is NOT.
        self._acc(owner_a, client_account_a, became_client_at=None, name='imported')
        assert metrics.new_logos(self._acc_base(client_account_a)) == 1

    def test_period_on_became_client_at(self, owner_a, client_account_a):
        now = timezone.now()
        self._acc(owner_a, client_account_a,
                  became_client_at=now - timedelta(days=3), name='in')
        self._acc(owner_a, client_account_a,
                  became_client_at=now - timedelta(days=40), name='out')
        window = (TODAY - timedelta(days=10), TODAY)
        assert metrics.new_logos(self._acc_base(client_account_a), period=window) == 1
        assert metrics.new_logos(self._acc_base(client_account_a)) == 2

    def test_user_filters_by_account_owner(self, owner_a, owner_a2, client_account_a):
        self._acc(owner_a, client_account_a,
                  became_client_at=timezone.now(), name='mine')
        self._acc(owner_a2, client_account_a,
                  became_client_at=timezone.now(), name='other')
        assert metrics.new_logos(self._acc_base(client_account_a), user=owner_a) == 1
        assert metrics.new_logos(self._acc_base(client_account_a)) == 2

    def test_source_campaign_filters_via_pivot(self, owner_a, client_account_a):
        from app_modules.campaigns.models.campaign_account import CampaignAccount
        camp = _mk_campaign(owner_a, client_account_a)
        in_camp = self._acc(owner_a, client_account_a,
                            became_client_at=timezone.now(), name='in_camp')
        CampaignAccount(campaign=camp, account=in_camp,
                        status=CampaignAccountStatus.COMPLETED).save(
                            user=owner_a, client_id=client_account_a.id)
        # a converted account NOT worked in the campaign
        self._acc(owner_a, client_account_a,
                  became_client_at=timezone.now(), name='no_camp')
        assert metrics.new_logos(self._acc_base(client_account_a),
                                 source_campaign=camp) == 1
        assert metrics.new_logos(self._acc_base(client_account_a)) == 2


# ===========================================================================
# FILTERS — user / period-on-the-right-anchor / source_campaign (pos + neg)
# ===========================================================================

class TestDecisionCyclesFilters:
    def test_user_filters(self, owner_a, owner_a2, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='mine')
        _mk_cycle(owner_a2, acc, client_account_a, name='other')
        assert metrics.decision_cycles(_dc_base(client_account_a), user=owner_a) == 1
        assert metrics.decision_cycles(_dc_base(client_account_a)) == 2  # no filter

    def test_period_on_created_at(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='in', created_on=TODAY - timedelta(days=5))
        _mk_cycle(owner_a, acc, client_account_a, name='out', created_on=TODAY - timedelta(days=40))
        window = (TODAY - timedelta(days=10), TODAY)
        assert metrics.decision_cycles(_dc_base(client_account_a), period=window) == 1
        assert metrics.decision_cycles(_dc_base(client_account_a)) == 2

    def test_source_campaign_filters(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='c', source_campaign=camp)
        _mk_cycle(owner_a, acc, client_account_a, name='nc')
        assert metrics.decision_cycles(_dc_base(client_account_a), source_campaign=camp) == 1
        assert metrics.decision_cycles(_dc_base(client_account_a)) == 2


class TestLeadsFilters:
    def _dc_with_meeting(self, owner, ca, acc, **kw):
        dc = _mk_cycle(owner, acc, ca, **kw)
        _mk_activity(owner, acc, ca, decision_cycle=dc,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     status=ActivityStatus.COMPLETED)
        return dc

    def test_requires_meeting_scheduled_activity(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        self._dc_with_meeting(owner_a, client_account_a, acc, name='lead')
        # a DC with an activity that is NOT meeting_scheduled -> not a lead
        plain = _mk_cycle(owner_a, acc, client_account_a, name='plain')
        _mk_activity(owner_a, acc, client_account_a, decision_cycle=plain,
                     outcome=ActivityOutcome.NO_ANSWER)
        assert metrics.leads(_dc_base(client_account_a)) == 1

    def test_cancelled_meeting_excluded(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        dc = _mk_cycle(owner_a, acc, client_account_a, name='c')
        _mk_activity(owner_a, acc, client_account_a, decision_cycle=dc,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     status=ActivityStatus.CANCELLED)
        assert metrics.leads(_dc_base(client_account_a)) == 0

    def test_counted_once_when_two_meetings(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        dc = _mk_cycle(owner_a, acc, client_account_a, name='c')
        for _ in range(2):
            _mk_activity(owner_a, acc, client_account_a, decision_cycle=dc,
                         outcome=ActivityOutcome.MEETING_SCHEDULED,
                         status=ActivityStatus.COMPLETED)
        assert metrics.leads(_dc_base(client_account_a)) == 1  # no fan-out

    def test_user_and_campaign_and_period(self, owner_a, owner_a2, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        self._dc_with_meeting(owner_a, client_account_a, acc, name='mine',
                              source_campaign=camp, created_on=TODAY - timedelta(days=2))
        self._dc_with_meeting(owner_a2, client_account_a, acc, name='other',
                              source_campaign=camp, created_on=TODAY - timedelta(days=2))
        assert metrics.leads(_dc_base(client_account_a), user=owner_a) == 1
        assert metrics.leads(_dc_base(client_account_a), source_campaign=camp) == 2
        assert metrics.leads(_dc_base(client_account_a),
                             period=(TODAY - timedelta(days=1), TODAY)) == 0


class TestMeetingsFilters:
    def test_outcome_and_cancelled(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.NO_ANSWER)          # wrong outcome
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     status=ActivityStatus.CANCELLED)            # cancelled
        assert metrics.meetings(_act_base(client_account_a)) == 1

    def test_period_on_scheduled_date(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     scheduled_date=TODAY - timedelta(days=3))
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     scheduled_date=TODAY - timedelta(days=30))
        window = (TODAY - timedelta(days=10), TODAY)
        assert metrics.meetings(_act_base(client_account_a), period=window) == 1
        assert metrics.meetings(_act_base(client_account_a)) == 2

    def test_user_and_campaign_via_cycle(self, owner_a, owner_a2, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        # cycle owned by owner_a, attributed to camp
        cyc = _mk_cycle(owner_a, acc, client_account_a, source_campaign=camp)
        step = _mk_step(cyc, client_account_a, 1, TODAY, owner_a)
        _mk_activity(owner_a, acc, client_account_a, decision_step=step,
                     decision_cycle=cyc, outcome=ActivityOutcome.MEETING_SCHEDULED)
        # cycle owned by owner_a2, no campaign
        cyc2 = _mk_cycle(owner_a2, acc, client_account_a, name='c2')
        step2 = _mk_step(cyc2, client_account_a, 1, TODAY, owner_a2)
        _mk_activity(owner_a2, acc, client_account_a, decision_step=step2,
                     decision_cycle=cyc2, outcome=ActivityOutcome.MEETING_SCHEDULED)
        # a MEETING_SCHEDULED activity with NO step -> excluded by owner/campaign filters
        _mk_activity(owner_a, acc, client_account_a,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)

        assert metrics.meetings(_act_base(client_account_a)) == 3      # no filter
        assert metrics.meetings(_act_base(client_account_a), user=owner_a) == 1
        assert metrics.meetings(_act_base(client_account_a), source_campaign=camp) == 1


class TestPipelineValueFilters:
    def test_open_only_and_amount(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='open', estimated_value=300)
        _mk_cycle(owner_a, acc, client_account_a, name='won', estimated_value=999,
                  outcome=CycleOutcome.WON, outcome_date=TODAY)
        assert metrics.pipeline_value(_dc_base(client_account_a)) == 300.0

    def test_anchor_is_the_effective_close_date_not_created_at(
        self, owner_a, client_account_a,
    ):
        """The window is evaluated on the cycle's EFFECTIVE CLOSE DATE
        (decision_cycles/services/close_date_sql.py), not on when it was created.

        This test previously pinned the old anchor, ``Max(steps.expected_end)``.
        That anchor was NULL on every freshly created cycle (step auto-creation
        leaves expected_end unset), so a normally used deal fell out of every
        windowed read. Same shape of proof, new rule.
        """
        acc = _mk_account('Acc', owner_a, client_account_a)
        # created LONG ago, expected to close recently.
        _mk_cycle(owner_a, acc, client_account_a, name='dc', estimated_value=400,
                  created_on=TODAY - timedelta(days=120),
                  expected_close_date=TODAY - timedelta(days=2))
        # window catches the close date (day -2), NOT created_at (day -120)
        win_in = (TODAY - timedelta(days=5), TODAY)
        assert metrics.pipeline_value(_dc_base(client_account_a), period=win_in) == 400.0
        # a window elsewhere -> the close date is outside -> excluded
        win_out = (TODAY - timedelta(days=95), TODAY - timedelta(days=85))
        assert metrics.pipeline_value(_dc_base(client_account_a), period=win_out) == 0.0
        # a window around created_at must NOT include it (proves not created_at anchored)
        win_created = (TODAY - timedelta(days=125), TODAY - timedelta(days=115))
        assert metrics.pipeline_value(_dc_base(client_account_a), period=win_created) == 0.0

    def test_a_dated_step_alone_no_longer_anchors_the_window(
        self, owner_a, client_account_a,
    ):
        """Anti-regression on the anchor SWAP: a step's expected_end is no longer
        the pipeline anchor. Only the manual close date or the CLOSING step's
        activities put a deal in a window."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        dc = _mk_cycle(owner_a, acc, client_account_a, name='stepdated',
                       estimated_value=400)
        _mk_step(dc, client_account_a, 1, TODAY, owner_a)

        assert metrics.pipeline_value(
            _dc_base(client_account_a), period=(TODAY - timedelta(days=5), TODAY)
        ) == 0.0
        # ...but an unwindowed read (the campaign convention) still counts it.
        assert metrics.pipeline_value(_dc_base(client_account_a), period=None) == 400.0

    def test_user_and_campaign(self, owner_a, owner_a2, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='mine', estimated_value=100,
                  source_campaign=camp)
        _mk_cycle(owner_a2, acc, client_account_a, name='other', estimated_value=100)
        assert metrics.pipeline_value(_dc_base(client_account_a), user=owner_a) == 100.0
        assert metrics.pipeline_value(_dc_base(client_account_a), source_campaign=camp) == 100.0
        assert metrics.pipeline_value(_dc_base(client_account_a)) == 200.0


class TestRevenueWonFilters:
    def test_won_only_and_amount(self, owner_a, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='won', estimated_value=700,
                  outcome=CycleOutcome.WON, outcome_date=TODAY - timedelta(days=1))
        _mk_cycle(owner_a, acc, client_account_a, name='open', estimated_value=999)
        assert metrics.revenue_won(_dc_base(client_account_a)) == 700.0

    def test_period_on_outcome_date(self, owner_a, client_account_a):
        """The won window anchors on the cycle's single close date; the WON
        population is selected by status first (see metrics.revenue_won)."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='in', estimated_value=700,
                  outcome=CycleOutcome.WON, outcome_date=TODAY - timedelta(days=3))
        _mk_cycle(owner_a, acc, client_account_a, name='out', estimated_value=700,
                  outcome=CycleOutcome.WON, outcome_date=TODAY - timedelta(days=40))

        window = (TODAY - timedelta(days=10), TODAY)
        assert metrics.revenue_won(_dc_base(client_account_a), period=window) == 700.0
        assert metrics.revenue_won(_dc_base(client_account_a)) == 1400.0

    def test_user_and_campaign(self, owner_a, owner_a2, client_account_a):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='mine', estimated_value=100,
                  outcome=CycleOutcome.WON, outcome_date=TODAY, source_campaign=camp)
        _mk_cycle(owner_a2, acc, client_account_a, name='other', estimated_value=100,
                  outcome=CycleOutcome.WON, outcome_date=TODAY)
        assert metrics.revenue_won(_dc_base(client_account_a), user=owner_a) == 100.0
        assert metrics.revenue_won(_dc_base(client_account_a), source_campaign=camp) == 100.0
        assert metrics.revenue_won(_dc_base(client_account_a)) == 200.0


# ===========================================================================
# ANTI-FAN-OUT — many users × cycles × activities × steps, all metrics at once,
# query count does NOT grow with volume.
# ===========================================================================

class TestAntiFanOut:
    def _build(self, owners, ca, *, cycles_per_owner, acts_per_cycle, steps_per_cycle):
        acc = _mk_account('Acc', owners[0], ca)
        open_sum = 0.0
        won_sum = 0.0
        dc_count = 0
        lead_count = 0
        meeting_count = 0
        for owner in owners:
            for i in range(cycles_per_owner):
                is_won = (i % 2 == 1)
                dc = _mk_cycle(
                    owner, acc, ca, name=f'{owner.email}-{i}',
                    estimated_value=100,
                    outcome=CycleOutcome.WON if is_won else None,
                    outcome_date=TODAY if is_won else None,
                )
                dc_count += 1
                if is_won:
                    won_sum += 100.0
                else:
                    open_sum += 100.0
                steps = [_mk_step(dc, ca, o, TODAY, owner) for o in range(1, steps_per_cycle + 1)]
                for j in range(acts_per_cycle):
                    sched = ActivityOutcome.MEETING_SCHEDULED if j == 0 else ActivityOutcome.NO_ANSWER
                    _mk_activity(owner, acc, ca, decision_cycle=dc,
                                 decision_step=steps[0], outcome=sched,
                                 status=ActivityStatus.COMPLETED)
                    if j == 0:
                        meeting_count += 1
                if acts_per_cycle >= 1:
                    lead_count += 1
        return dict(open_sum=open_sum, won_sum=won_sum, dc_count=dc_count,
                    lead_count=lead_count, meeting_count=meeting_count)

    def test_all_metrics_correct_and_query_bounded(
            self, django_assert_num_queries, owner_a, owner_a2, client_account_a):
        exp = self._build([owner_a, owner_a2], client_account_a,
                          cycles_per_owner=3, acts_per_cycle=2, steps_per_cycle=3)

        # Correctness together (open cycles have 3 steps each -> pipeline must NOT
        # be multiplied by 3; wons counted once despite many activities).
        assert metrics.decision_cycles(_dc_base(client_account_a)) == exp['dc_count']
        assert metrics.leads(_dc_base(client_account_a)) == exp['lead_count']
        assert metrics.meetings(_act_base(client_account_a)) == exp['meeting_count']
        assert metrics.pipeline_value(_dc_base(client_account_a)) == exp['open_sum']
        assert metrics.revenue_won(_dc_base(client_account_a)) == exp['won_sum']

        # Each pure metric is ONE query, regardless of the data volume above.
        with django_assert_num_queries(1):
            metrics.decision_cycles(_dc_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.leads(_dc_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.meetings(_act_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.pipeline_value(_dc_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.revenue_won(_dc_base(client_account_a))
