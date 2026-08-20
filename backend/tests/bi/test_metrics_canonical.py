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
                 decision_cycle=None, decision_step=None, campaign=None,
                 completed_at=None, created_by=None):
    """``created_by`` is who MEETINGS is attributed to (attribution_scope);
    ``completed_at`` is the date it is windowed on. Both default to the shape
    the older tests here assume — logged by the owner, undated."""
    a = Activity(title='a', activity_type=activity_type, status=status, outcome=outcome,
                 account=account, owner=owner, campaign=campaign,
                 decision_cycle=decision_cycle, decision_step=decision_step,
                 scheduled_date=scheduled_date or TODAY,
                 completed_at=completed_at)
    a.save(user=created_by or owner, client_id=ca.id)
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
        link (canonical attribution) AND a COMPLETED + SUCCESSFUL campaign
        activity pointing at it (campaign-service attribution), so the two
        attribution paths select the same cycles and parity is meaningful.

        The activities used to be left PLANNED, which stopped being enough: a
        campaign now claims a cycle's value only once it has WORKED it
        (campaign_dc_attribution.py), so every campaign figure read 0 and the
        parity assertions below were comparing against nothing."""
        camp = _mk_campaign(owner, ca)
        acc = _mk_account('Acc', owner, ca)

        # open cycle attributed to the campaign, estimated_value 1000
        open_dc = _mk_cycle(owner, acc, ca, name='open', source_campaign=camp,
                            estimated_value=1000)
        _mk_activity(owner, acc, ca, campaign=camp, decision_cycle=open_dc,
                     activity_type=ActivityType.CALL,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        # won cycle attributed to the campaign, estimated_value 500
        won_dc = _mk_cycle(owner, acc, ca, name='won', source_campaign=camp,
                           estimated_value=500, outcome=CycleOutcome.WON,
                           outcome_date=TODAY)
        _mk_activity(owner, acc, ca, campaign=camp, decision_cycle=won_dc,
                     activity_type=ActivityType.CALL,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        # a DC of ANOTHER campaign — must not leak into the campaign totals
        other_camp = _mk_campaign(owner, ca, name='Other')
        other_dc = _mk_cycle(owner, acc, ca, name='other', source_campaign=other_camp,
                             estimated_value=9999)
        _mk_activity(owner, acc, ca, campaign=other_camp, decision_cycle=other_dc,
                     activity_type=ActivityType.CALL,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.SUCCESSFUL)

        return camp

    def test_pipeline_diverges_from_campaign_by_definition(self, owner_a,
                                                           client_account_a):
        """NOT parity, and it must not be faked into one: the personal pipeline
        is EXCLUSIVE (a won deal has left it) while a campaign's covers OPEN or
        WON — it reports what the campaign put on the table. Same fixture, same
        campaign: 1000 personal, 1500 campaign, and the difference is exactly the
        won deal."""
        camp = self._consistent_campaign_data(owner_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)

        canonical = metrics.pipeline_value(
            _dc_base(client_account_a), source_campaign=camp, period=None)

        assert canonical == 1000.0
        assert svc._sum_pipeline_value(camp) == 1500.0
        assert svc._sum_pipeline_value(camp) - canonical == 500.0   # the won deal

    def test_revenue_won_parity(self, owner_a, client_account_a):
        camp = self._consistent_campaign_data(owner_a, client_account_a)
        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.revenue_won(
            _dc_base(client_account_a), source_campaign=camp, period=None)
        assert canonical == svc._sum_revenue_won(camp) == 500.0

    def test_a_campaign_claims_nothing_it_has_not_worked(self, owner_a,
                                                         client_account_a):
        """Guards the fixture above: without the COMPLETED + SUCCESSFUL activity
        the campaign figures are 0 whatever ``source_campaign`` says, so the
        parity assertions would be comparing two zeroes."""
        camp = _mk_campaign(owner_a, client_account_a)
        acc = _mk_account('Acc', owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='untouched',
                  source_campaign=camp, estimated_value=1000)

        svc = CampaignAnalyticsService(client_id=client_account_a.id)

        assert svc._sum_pipeline_value(camp) == 0.0
        assert svc._sum_revenue_won(camp) == 0.0
        # ... while the ORIGIN-based canonical read still sees it.
        assert metrics.pipeline_value(
            _dc_base(client_account_a), source_campaign=camp, period=None) == 1000.0

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
        # Campaign MEETINGS = Activity TYPE=MEETING + status=COMPLETED, whatever
        # the outcome. Canonical MEETINGS = COMPLETED + a SUCCESSFUL outcome,
        # whatever the type. Still different predicates — the canonical one moved
        # (it was outcome=MEETING_SCHEDULED alone, which counted a booking), and
        # the two now overlap without coinciding.
        camp = _mk_campaign(owner_a, client_account_a)
        acc = _mk_account('Acc', owner_a, client_account_a)
        cyc = _mk_cycle(owner_a, acc, client_account_a, source_campaign=camp)
        step = _mk_step(cyc, client_account_a, 1, TODAY, owner_a)

        # counted by CAMPAIGN only: a completed MEETING whose outcome is not a
        # success — the campaign counts the meeting, the canonical metric does not.
        _mk_activity(owner_a, acc, client_account_a, campaign=camp,
                     decision_cycle=cyc, decision_step=step,
                     activity_type=ActivityType.MEETING,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.NO_ANSWER)
        # counted by CANONICAL only: a successful CALL — not a MEETING type.
        _mk_activity(owner_a, acc, client_account_a, campaign=camp,
                     decision_cycle=cyc, decision_step=step,
                     activity_type=ActivityType.CALL,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)

        svc = CampaignAnalyticsService(client_id=client_account_a.id)
        canonical = metrics.meetings(
            _act_base(client_account_a), source_campaign=camp, period=None)
        assert svc._count_meetings(camp) == 1     # the MEETING+COMPLETED one
        assert canonical == 1                      # the successful one
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

    def test_user_filters_by_the_attribution_union(self, owner_a, owner_a2,
                                                   client_account_a):
        """A logo is attributed like the deal that produced it
        (attribution_scope.account_scope_q): the account's owner or creator, OR
        anyone attached to the WON cycle that converted it. Here each account is
        owned AND created by one rep, so the narrow reading and the union agree
        — the cycle branch is proved in
        tests/quotas/test_personal_scope_union.py."""
        self._acc(owner_a, client_account_a,
                  became_client_at=timezone.now(), name='mine')
        self._acc(owner_a2, client_account_a,
                  became_client_at=timezone.now(), name='other')
        assert metrics.new_logos(self._acc_base(client_account_a), user=owner_a) == 1
        assert metrics.new_logos(self._acc_base(client_account_a), user=owner_a2) == 1
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


class TestMeetingsFilters:
    """MEETINGS counts meetings HELD and gone well — COMPLETED with an outcome in
    SUCCESSFUL_OUTCOMES — credited to whoever LOGGED it and windowed on
    ``completed_at``.

    All three of those replaced weaker rules. The population was
    ``outcome=MEETING_SCHEDULED`` minus CANCELLED, which counted an intention;
    the owner was the cycle owner reached through a nullable decision_step; the
    anchor was ``scheduled_date``, the date the meeting was booked FOR. The
    attribution and the anchor are proved in
    tests/quotas/test_personal_scope_union.py; what is proved here is the
    population and the campaign filter."""

    def test_population_is_completed_plus_a_successful_outcome(
        self, owner_a, client_account_a,
    ):
        acc = _mk_account('Acc', owner_a, client_account_a)
        # counts: completed + successful
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        # does not: completed but the outcome is not a success
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.NO_ANSWER)
        # does not: a successful outcome on a row that was never completed —
        # outcome is only meaningful once completed, so a stray one cannot count
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.PLANNED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        # does not: CANCELLED needs no special case, it is not COMPLETED
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.CANCELLED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        assert metrics.meetings(_act_base(client_account_a)) == 1

    def test_both_successful_outcomes_count(self, owner_a, client_account_a):
        """SUCCESSFUL_OUTCOMES is the campaign progression's own set, reused
        here — {SUCCESSFUL, MEETING_SCHEDULED}, not a second opinion."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        for outcome in (ActivityOutcome.SUCCESSFUL,
                        ActivityOutcome.MEETING_SCHEDULED):
            _mk_activity(owner_a, acc, client_account_a,
                         status=ActivityStatus.COMPLETED, outcome=outcome)
        assert metrics.meetings(_act_base(client_account_a)) == 2

    def test_period_on_completed_at_not_scheduled_date(self, owner_a,
                                                       client_account_a):
        """Anchor SWAP: the window is when the meeting was HELD, not when it was
        booked for. Both rows below are booked on the same day and completed 27
        days apart; only the recent completion is in the window."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        booked_on = TODAY - timedelta(days=3)
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     scheduled_date=booked_on,
                     completed_at=timezone.now() - timedelta(days=3))
        _mk_activity(owner_a, acc, client_account_a,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED,
                     scheduled_date=booked_on,
                     completed_at=timezone.now() - timedelta(days=30))
        window = (TODAY - timedelta(days=10), TODAY)
        assert metrics.meetings(_act_base(client_account_a), period=window) == 1
        assert metrics.meetings(_act_base(client_account_a)) == 2
        # ... and the booking date, identical on both, decides nothing.
        assert metrics.meetings(
            _act_base(client_account_a),
            period=(booked_on, booked_on),
        ) == 1

    def test_user_is_the_logger_and_campaign_is_still_via_the_cycle(
        self, owner_a, owner_a2, client_account_a,
    ):
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        # a meeting on a campaign cycle, LOGGED BY owner_a2 though owner_a owns
        # the cycle: it is owner_a2's meeting and the campaign's.
        cyc = _mk_cycle(owner_a, acc, client_account_a, source_campaign=camp)
        step = _mk_step(cyc, client_account_a, 1, TODAY, owner_a)
        _mk_activity(owner_a, acc, client_account_a, decision_step=step,
                     decision_cycle=cyc, created_by=owner_a2,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        # a meeting on a non-campaign cycle, logged by owner_a2
        cyc2 = _mk_cycle(owner_a2, acc, client_account_a, name='c2')
        step2 = _mk_step(cyc2, client_account_a, 1, TODAY, owner_a2)
        _mk_activity(owner_a2, acc, client_account_a, decision_step=step2,
                     decision_cycle=cyc2, created_by=owner_a2,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)
        # a meeting with NO decision step at all, logged by owner_a. It used to
        # be dropped by the positive traversal of the nullable step FK; it now
        # belongs to the person who logged it, as it should.
        _mk_activity(owner_a, acc, client_account_a, created_by=owner_a,
                     status=ActivityStatus.COMPLETED,
                     outcome=ActivityOutcome.MEETING_SCHEDULED)

        assert metrics.meetings(_act_base(client_account_a)) == 3      # no filter
        assert metrics.meetings(_act_base(client_account_a), user=owner_a2) == 2
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
        """``user=`` is the attribution UNION, not ``owner`` alone
        (attribution_scope): both cycles below sit on an account owned by
        owner_a, so both are owner_a's — the second one through the account even
        though owner_a2 owns and created it. Only owner_a2's own link is narrow.

        This test used to assert 100.0 for owner_a, which pinned the owner-only
        rule the union replaces; the fixture is unchanged, the expectation is
        re-derived under the new rule."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='mine', estimated_value=100,
                  source_campaign=camp)
        _mk_cycle(owner_a2, acc, client_account_a, name='other', estimated_value=100)
        # owner_a reaches both: one as owner, one as the ACCOUNT's owner.
        assert metrics.pipeline_value(_dc_base(client_account_a), user=owner_a) == 200.0
        # owner_a2 reaches only the cycle they own/created.
        assert metrics.pipeline_value(_dc_base(client_account_a), user=owner_a2) == 100.0
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
        """Same union as PIPELINE_VALUE — a deal does not change hands when it is
        won. Both cycles sit on owner_a's account, so both are owner_a's."""
        acc = _mk_account('Acc', owner_a, client_account_a)
        camp = _mk_campaign(owner_a, client_account_a)
        _mk_cycle(owner_a, acc, client_account_a, name='mine', estimated_value=100,
                  outcome=CycleOutcome.WON, outcome_date=TODAY, source_campaign=camp)
        _mk_cycle(owner_a2, acc, client_account_a, name='other', estimated_value=100,
                  outcome=CycleOutcome.WON, outcome_date=TODAY)
        assert metrics.revenue_won(_dc_base(client_account_a), user=owner_a) == 200.0
        assert metrics.revenue_won(_dc_base(client_account_a), user=owner_a2) == 100.0
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
        return dict(open_sum=open_sum, won_sum=won_sum, dc_count=dc_count,
                    meeting_count=meeting_count)

    def test_all_metrics_correct_and_query_bounded(
            self, django_assert_num_queries, owner_a, owner_a2, client_account_a):
        exp = self._build([owner_a, owner_a2], client_account_a,
                          cycles_per_owner=3, acts_per_cycle=2, steps_per_cycle=3)

        # Correctness together (open cycles have 3 steps each -> pipeline must NOT
        # be multiplied by 3; wons counted once despite many activities).
        assert metrics.decision_cycles(_dc_base(client_account_a)) == exp['dc_count']
        assert metrics.meetings(_act_base(client_account_a)) == exp['meeting_count']
        assert metrics.pipeline_value(_dc_base(client_account_a)) == exp['open_sum']
        assert metrics.revenue_won(_dc_base(client_account_a)) == exp['won_sum']

        # Each pure metric is ONE query, regardless of the data volume above.
        with django_assert_num_queries(1):
            metrics.decision_cycles(_dc_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.meetings(_act_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.pipeline_value(_dc_base(client_account_a))
        with django_assert_num_queries(1):
            metrics.revenue_won(_dc_base(client_account_a))
