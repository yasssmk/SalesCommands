# backend/tests/quotas/test_personal_scope_union.py
"""
WHOSE number is it — the personal/manager attribution rule, end to end.

THE RULE UNDER TEST (PO truth table, final), declared in
bi/metrics/attribution_scope.py:

  PIPELINE_VALUE / REVENUE_WON / NEW_LOGOS
      a deal is yours if  owner = you  OR  created_by = you
                          OR  account.account_owner = you
      counted ONCE per deal however many of the three hold,
      and the SAME deal may be counted for TWO different people.

  MEETINGS
      created_by = you, ONLY — plus status=COMPLETED and an outcome in
      SUCCESSFUL_OUTCOMES, windowed on completed_at.

  MANAGER
      the same predicate widened to the team subtree.

WHY IT NEEDED CHANGING — before this, each metric scoped on ONE field:
PIPELINE/WON on ``owner``, NEW_LOGOS on ``account_owner``, MEETINGS on
``decision_step -> cycle -> owner``. ``created_by`` was read by NO metric at
all, so an SDR who opened deals and handed them to an AE had an attainment of
zero on every one of them. The tests below are written from that failure: each
one is a rep who did real work and could not see it.

The windows, the discount roll-up and the exclusivity rules are NOT restated
here — they are pinned in tests/quotas/test_quota_attainment_amounts.py. What
is pinned here is attribution only, plus the query bound that keeps the union
from turning into an N+1 or a fan-out.

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import (
    ActivityOutcome, ActivityStatus, ActivityType,
)
from app_modules.activities.models import Activity
from app_modules.bi import metrics
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


TODAY = date.today()
WINDOW_START = TODAY - timedelta(days=15)
WINDOW_END = TODAY + timedelta(days=15)
AFTER_WINDOW = WINDOW_END + timedelta(days=1)


# ---------------------------------------------------------------------------
# factories (mirror tests/quotas/test_quota_attainment_amounts.py)
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


def _account(ca, *, account_owner, created_by=None, name='Acc'):
    """An account whose OWNER and CREATOR can differ — the two account-side
    links of the union."""
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=account_owner)
    acc.save(user=created_by or account_owner, client_id=ca.id)
    return acc


def _cycle(ca, *, owner, created_by=None, account=None, amount=None, name='dc',
           outcome=None, outcome_date=None, expected_close=TODAY):
    """A cycle whose three attribution links are set INDEPENDENTLY.

    ``created_by`` is the audit field ModuleBaseModel stamps from ``save(user=)``
    (moduleBaseModels.py:39-46, :92-96) — the SDR link. The default keeps it
    equal to the owner, the historical shape where all three coincide.
    """
    account = account or _account(ca, account_owner=owner, name=f'Acc-{owner.email}')
    cycle = DecisionCycle(account=account, owner=owner, name=f'{name}-{owner.email}',
                          outcome=outcome, outcome_date=outcome_date,
                          expected_close_date=expected_close)
    cycle.save(user=created_by or owner, client_id=ca.id)
    give_deal_value(cycle, amount, user=owner)
    return cycle


def _meeting(ca, *, created_by, account, status=ActivityStatus.COMPLETED,
             outcome=ActivityOutcome.MEETING_SCHEDULED, completed_at=None,
             scheduled_date=None, decision_cycle=None, decision_step=None):
    act = Activity(title='m', activity_type=ActivityType.MEETING, status=status,
                   outcome=outcome, account=account, owner=created_by,
                   decision_cycle=decision_cycle, decision_step=decision_step,
                   scheduled_date=scheduled_date or TODAY,
                   completed_at=completed_at)
    act.save(user=created_by, client_id=ca.id)
    return act


def _quota(owner, ca, metric, *, target=Decimal('100000'),
           start=WINDOW_START, end=WINDOW_END):
    quota = Quota(owner=owner, metric=metric, target_value=target,
                  period_start=start, period_end=end)
    quota.save(user=owner, client_id=ca.id)
    return quota


def _attainment(quota):
    return Decimal(str(P.compute_progress(quota).current_value))


def _dc_base(ca):
    return DecisionCycle.objects.filter(client_id=ca.id)


def _act_base(ca):
    return Activity.objects.filter(client_id=ca.id)


def _acc_base(ca):
    return CompanyAccount.objects.filter(client_id=ca.id)


@pytest.fixture
def ind_role(db, client_account_a):
    return _role(client_account_a, 'Ind', individual=True)


@pytest.fixture
def sdr(db, client_account_a, ind_role):
    return _user('sdr@a.test', client_account_a, ind_role)


@pytest.fixture
def ae(db, client_account_a, ind_role):
    return _user('ae@a.test', client_account_a, ind_role)


@pytest.fixture
def am(db, client_account_a, ind_role):
    """Account manager — owns the ACCOUNT, neither owns nor created the deal."""
    return _user('am@a.test', client_account_a, ind_role)


# ===========================================================================
# G1 — the three branches of the union, one at a time
# ===========================================================================

class TestTheThreeBranches:
    """Each branch alone must be enough. Before the union only the first was."""

    def test_owner_alone_counts(self, ae, sdr, client_account_a):
        # owner=ae, created_by=sdr, account owned by sdr -> only the OWNER link
        # attaches this deal to the AE.
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(ae, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_created_by_alone_counts(self, sdr, ae, client_account_a):
        """THE regression this rule exists for: the SDR opened the deal, the AE
        owns it and owns the account. Under the owner-only rule the SDR's
        pipeline read 0 — their entire contribution was invisible."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(sdr, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_account_owner_alone_counts(self, am, ae, sdr, client_account_a):
        # The account manager neither owns nor created the deal; they own the
        # ACCOUNT it sits on.
        acc = _account(client_account_a, account_owner=am, name='AmAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(am, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_a_stranger_still_counts_nothing(self, ae, sdr, am, client_account_a):
        """The union widens attribution; it does not abolish it."""
        stranger = _user('nobody@a.test', client_account_a,
                         _role(client_account_a, 'Ind9', individual=True))
        acc = _account(client_account_a, account_owner=am, name='AmAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(stranger, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('0')

    def test_the_same_union_applies_to_won(self, sdr, ae, client_account_a):
        """A deal must not change hands when it is won — same union, both sides."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(sdr, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')
        assert _attainment(_quota(ae, client_account_a, MetricKey.REVENUE_WON)) \
            == Decimal('40000')


# ===========================================================================
# G2 — counted ONCE, however many branches match
# ===========================================================================

class TestCountedOncePerDeal:

    def test_all_three_links_on_one_user_is_still_one_deal(self, ae, client_account_a):
        """owner AND created_by AND account_owner all = the same rep. Three
        matching branches of an OR on to-ONE joins is still ONE row: 60 000, not
        180 000. A join-shaped union would have inflated it."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        _cycle(client_account_a, owner=ae, created_by=ae, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(ae, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')

    def test_two_deals_on_the_same_account_are_two(self, ae, client_account_a):
        """Anti-over-correction: dedup is per DEAL, not per account."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        _cycle(client_account_a, owner=ae, account=acc, amount=Decimal('60000'),
               name='one')
        _cycle(client_account_a, owner=ae, account=acc, amount=Decimal('25000'),
               name='two')

        assert _attainment(_quota(ae, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('85000')


# ===========================================================================
# G3 — one deal, two people, full value each (PO-accepted)
# ===========================================================================

class TestOneDealTwoPeople:

    def test_the_sdr_and_the_ae_each_carry_the_whole_deal(
        self, sdr, ae, client_account_a,
    ):
        """PO-locked and deliberately NOT a partition: individual attainments do
        not sum to the company pipeline. 60 000 is on the table once; two people
        delivered it, and each is measured on what they delivered."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(sdr, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')
        assert _attainment(_quota(ae, client_account_a, MetricKey.PIPELINE_VALUE)) \
            == Decimal('60000')
        # ... while the tenant-wide read still sees ONE deal.
        assert Decimal(str(metrics.pipeline_value(_dc_base(client_account_a)))) \
            == Decimal('60000')


# ===========================================================================
# G4/G5/G6 — MEETINGS: created_by only, completed+successful, completed_at
# ===========================================================================

class TestMeetingsAttribution:

    def test_credited_to_who_logged_it_not_to_the_cycle_owner(
        self, sdr, ae, client_account_a,
    ):
        """The SDR holds the meeting on the AE's deal. It is the SDR's meeting.

        Under the previous rule it was counted through
        ``decision_step -> cycle -> owner`` — the AE's — and only when the
        activity carried a decision step at all."""
        acc = _account(client_account_a, account_owner=ae, name='AeAcc')
        cyc = _cycle(client_account_a, owner=ae, account=acc, amount=Decimal('10'))
        _meeting(client_account_a, created_by=sdr, account=acc, decision_cycle=cyc,
                 completed_at=timezone.now())

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 1
        assert metrics.meetings(_act_base(client_account_a), user=ae) == 0

    def test_a_meeting_with_no_decision_step_is_no_longer_lost(
        self, sdr, client_account_a,
    ):
        """The old owner filter traversed a NULLABLE FK in positive form, so a
        meeting logged straight on an account — the common case — was dropped by
        the join and belonged to nobody."""
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _meeting(client_account_a, created_by=sdr, account=acc,
                 completed_at=timezone.now())

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 1

    def test_planned_and_cancelled_do_not_count(self, sdr, client_account_a):
        """A meeting counts once it has been HELD. A booking is not a meeting,
        and CANCELLED needs no special case — it is not COMPLETED."""
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _meeting(client_account_a, created_by=sdr, account=acc,
                 status=ActivityStatus.PLANNED, completed_at=timezone.now())
        _meeting(client_account_a, created_by=sdr, account=acc,
                 status=ActivityStatus.CANCELLED, completed_at=timezone.now())

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 0

    def test_an_unsuccessful_outcome_does_not_count(self, sdr, client_account_a):
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _meeting(client_account_a, created_by=sdr, account=acc,
                 outcome=ActivityOutcome.NO_ANSWER, completed_at=timezone.now())

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 0

    def test_both_successful_outcomes_count(self, sdr, client_account_a):
        """SUCCESSFUL_OUTCOMES is the campaign progression's own set, reused —
        {SUCCESSFUL, MEETING_SCHEDULED}, not a second opinion here."""
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _meeting(client_account_a, created_by=sdr, account=acc,
                 outcome=ActivityOutcome.SUCCESSFUL, completed_at=timezone.now())
        _meeting(client_account_a, created_by=sdr, account=acc,
                 outcome=ActivityOutcome.MEETING_SCHEDULED,
                 completed_at=timezone.now())

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 2

    def test_the_window_is_the_completion_not_the_booking(
        self, sdr, client_account_a,
    ):
        """A meeting BOOKED outside the window and HELD inside it counts; the
        reverse does not. The old anchor was ``scheduled_date`` — the date it was
        booked for — so a meeting moved into the next quarter was still counted
        in the one it was first planned in."""
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        # booked long before the window, held inside it -> counts
        _meeting(client_account_a, created_by=sdr, account=acc,
                 scheduled_date=WINDOW_START - timedelta(days=90),
                 completed_at=timezone.now())
        # booked inside the window, held after it -> does not
        _meeting(client_account_a, created_by=sdr, account=acc,
                 scheduled_date=TODAY,
                 completed_at=timezone.make_aware(
                     timezone.datetime(AFTER_WINDOW.year, AFTER_WINDOW.month,
                                       AFTER_WINDOW.day, 10, 0)))

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 2
        quota = _quota(sdr, client_account_a, MetricKey.MEETINGS,
                       target=Decimal('10'))
        assert _attainment(quota) == Decimal('1')

    def test_a_meeting_never_completed_is_outside_every_window(
        self, sdr, client_account_a,
    ):
        """DOCUMENTED consequence of anchoring on ``completed_at``: it is NULL
        until the meeting is marked done, so a windowed read cannot see it —
        which is the point, an unheld meeting is not an attainment."""
        acc = _account(client_account_a, account_owner=sdr, name='SdrAcc')
        _meeting(client_account_a, created_by=sdr, account=acc, completed_at=None)

        assert metrics.meetings(_act_base(client_account_a), user=sdr) == 1
        assert _attainment(_quota(sdr, client_account_a, MetricKey.MEETINGS,
                                  target=Decimal('10'))) == Decimal('0')


# ===========================================================================
# G7 — NEW_LOGOS follows the deal that produced it
# ===========================================================================

class TestNewLogosAttribution:

    def _converted(self, ca, *, account_owner, created_by=None, name='Acc'):
        acc = _account(ca, account_owner=account_owner, created_by=created_by,
                       name=name)
        acc.became_client_at = timezone.now()
        acc.save(user=created_by or account_owner)
        return acc

    def test_the_account_owner_still_counts(self, am, client_account_a):
        self._converted(client_account_a, account_owner=am)

        assert _attainment(_quota(am, client_account_a, MetricKey.NEW_LOGOS,
                                  target=Decimal('5'))) == Decimal('1')

    def test_the_rep_who_won_the_deal_counts_too(self, sdr, ae, am,
                                                 client_account_a):
        """The logo follows the deal that produced it: the SDR who opened the
        winning cycle gets the logo even though the account is owned by the AM
        and was created by someone else. Under the account-only rule they had
        nothing."""
        acc = self._converted(client_account_a, account_owner=am, name='AmAcc')
        _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
               amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        for who in (am, ae, sdr):
            assert _attainment(_quota(who, client_account_a, MetricKey.NEW_LOGOS,
                                      target=Decimal('5'))) == Decimal('1'), who.email

    def test_an_open_cycle_grants_no_logo(self, sdr, am, client_account_a):
        """Only a WON cycle carries the logo — an open deal on a converted
        account is not a conversion by that rep."""
        acc = self._converted(client_account_a, account_owner=am, name='AmAcc')
        _cycle(client_account_a, owner=sdr, created_by=sdr, account=acc,
               amount=Decimal('40000'), name='open')

        assert _attainment(_quota(sdr, client_account_a, MetricKey.NEW_LOGOS,
                                  target=Decimal('5'))) == Decimal('0')

    def test_two_won_cycles_are_still_one_logo(self, sdr, am, client_account_a):
        """The cycle branch is an isolated ``pk__in`` sub-query, not a join, so
        an account won twice is counted ONCE."""
        acc = self._converted(client_account_a, account_owner=am, name='AmAcc')
        for index in range(2):
            _cycle(client_account_a, owner=sdr, created_by=sdr, account=acc,
                   amount=Decimal('40000'), name=f'won{index}',
                   outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(sdr, client_account_a, MetricKey.NEW_LOGOS,
                                  target=Decimal('5'))) == Decimal('1')

    def test_an_imported_client_is_still_not_a_logo(self, sdr, am,
                                                    client_account_a):
        """The population rule is untouched by the widened attribution: a NULL
        ``became_client_at`` is never a new logo, whoever won on it."""
        acc = _account(client_account_a, account_owner=am, name='Imported')
        _cycle(client_account_a, owner=sdr, created_by=sdr, account=acc,
               amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(sdr, client_account_a, MetricKey.NEW_LOGOS,
                                  target=Decimal('5'))) == Decimal('0')


# ===========================================================================
# G8 — MANAGER = the same union over the subtree
# ===========================================================================

class TestManagerIsTheSameUnion:

    def _hierarchy(self, ca):
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

    def test_the_manager_total_is_the_sum_of_its_members(self, client_account_a):
        """Disjoint deals: manager == Σ members, the PO's headline invariant."""
        manager, direct, deep, _out = self._hierarchy(client_account_a)
        _cycle(client_account_a, owner=direct, amount=Decimal('60000'))
        _cycle(client_account_a, owner=deep, amount=Decimal('25000'))

        m_quota = _quota(manager, client_account_a, MetricKey.PIPELINE_VALUE)
        total = sum(
            _attainment(_quota(who, client_account_a, MetricKey.PIPELINE_VALUE))
            for who in (direct, deep)
        )

        assert _attainment(m_quota) == total == Decimal('85000')

    def test_a_deal_reaching_the_subtree_only_by_created_by_counts(
        self, client_account_a,
    ):
        """The manager predicate is the SAME union: a deal owned OUTSIDE the
        subtree but created by a member is the team's. Under the owner-only team
        filter the manager could not see their own SDR's work."""
        manager, direct, _deep, outsider = self._hierarchy(client_account_a)
        acc = _account(client_account_a, account_owner=outsider, name='OutAcc')
        _cycle(client_account_a, owner=outsider, created_by=direct, account=acc,
               amount=Decimal('60000'))

        assert _attainment(_quota(manager, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('60000')

    def test_a_deal_with_no_link_into_the_subtree_never_counts(
        self, client_account_a,
    ):
        manager, _direct, _deep, outsider = self._hierarchy(client_account_a)
        _cycle(client_account_a, owner=outsider, amount=Decimal('99000'))

        assert _attainment(_quota(manager, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('0')

    def test_a_deal_shared_by_two_members_counts_once_for_the_manager(
        self, client_account_a,
    ):
        """The arithmetic consequence of the union, pinned so it is a decision
        and not a surprise: when ONE deal links to TWO members of the same
        subtree, each member carries it in full (60 000 each) while the manager
        carries it ONCE (60 000, not 120 000). Manager == Σ members holds only
        while no deal is shared — the team has one deal on the table, and both
        reps delivered it."""
        manager, direct, deep, _out = self._hierarchy(client_account_a)
        acc = _account(client_account_a, account_owner=deep, name='DeepAcc')
        _cycle(client_account_a, owner=deep, created_by=direct, account=acc,
               amount=Decimal('60000'))

        per_member = [
            _attainment(_quota(who, client_account_a, MetricKey.PIPELINE_VALUE))
            for who in (direct, deep)
        ]
        assert per_member == [Decimal('60000'), Decimal('60000')]
        assert _attainment(_quota(manager, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('60000')

    def test_meetings_manager_scope_follows_created_by(self, client_account_a):
        manager, direct, _deep, outsider = self._hierarchy(client_account_a)
        acc = _account(client_account_a, account_owner=outsider, name='OutAcc')
        _meeting(client_account_a, created_by=direct, account=acc,
                 completed_at=timezone.now())
        _meeting(client_account_a, created_by=outsider, account=acc,
                 completed_at=timezone.now())

        assert _attainment(_quota(manager, client_account_a, MetricKey.MEETINGS,
                                  target=Decimal('10'))) == Decimal('1')

    def test_new_logos_manager_scope_follows_the_won_cycle(self, client_account_a):
        manager, direct, _deep, outsider = self._hierarchy(client_account_a)
        acc = _account(client_account_a, account_owner=outsider, name='OutAcc')
        acc.became_client_at = timezone.now()
        acc.save(user=outsider)
        _cycle(client_account_a, owner=outsider, created_by=direct, account=acc,
               amount=Decimal('40000'), name='won',
               outcome=CycleOutcome.WON, outcome_date=TODAY)

        assert _attainment(_quota(manager, client_account_a, MetricKey.NEW_LOGOS,
                                  target=Decimal('5'))) == Decimal('1')

    def test_admin_still_measures_the_whole_tenant(self, client_account_a):
        admin = _user('admin@a.test', client_account_a,
                      _role(client_account_a, 'Adm', admin=True))
        someone = _user('anyone@a.test', client_account_a,
                        _role(client_account_a, 'Ind3', individual=True))
        _cycle(client_account_a, owner=someone, amount=Decimal('12000'))

        assert _attainment(_quota(admin, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('12000')


# ===========================================================================
# Isolation + query bound — the union must not leak or multiply queries
# ===========================================================================

class TestIsolationAndQueryBound:

    def test_the_union_does_not_cross_tenants(self, client_account_a,
                                              client_account_b):
        """The union widens WITHIN the caller's tenant only: the base queryset is
        client-bounded before any of it applies."""
        role_a = _role(client_account_a, 'IndA', individual=True)
        role_b = _role(client_account_b, 'IndB', individual=True)
        rep_a = _user('rep@a.test', client_account_a, role_a)
        rep_b = _user('rep@b.test', client_account_b, role_b)
        _cycle(client_account_b, owner=rep_b, amount=Decimal('99000'))

        assert _attainment(_quota(rep_a, client_account_a,
                                  MetricKey.PIPELINE_VALUE)) == Decimal('0')

    def test_the_union_is_still_one_query_per_metric(
        self, ae, sdr, am, client_account_a, django_assert_num_queries,
    ):
        """Three ORed branches are three JOIN conditions in ONE statement, not
        three queries — and not a per-row lookup."""
        acc = _account(client_account_a, account_owner=am, name='AmAcc')
        for index in range(5):
            _cycle(client_account_a, owner=ae, created_by=sdr, account=acc,
                   amount=Decimal('1000'), name=f'dc{index}')

        with django_assert_num_queries(1):
            metrics.pipeline_value(_dc_base(client_account_a), user=sdr)
        with django_assert_num_queries(1):
            metrics.revenue_won(_dc_base(client_account_a), user=sdr)
        with django_assert_num_queries(1):
            metrics.meetings(_act_base(client_account_a), user=sdr)
        with django_assert_num_queries(1):
            metrics.new_logos(_acc_base(client_account_a), user=sdr)

    def test_a_manager_attainment_does_not_scale_with_the_team(
        self, client_account_a, django_assert_num_queries,
    ):
        mgr_role = _role(client_account_a, 'Mgr2', manager=True)
        ind_role = _role(client_account_a, 'Ind2', individual=True)
        manager = _user('mgr2@a.test', client_account_a, mgr_role)
        region = _team(client_account_a, 'Region2', manager=manager)
        manager.team = region
        manager.save()
        for index in range(4):
            member = _user(f'm{index}@a.test', client_account_a, ind_role,
                           team=region)
            _cycle(client_account_a, owner=member, amount=Decimal('1000'),
                   name=f'dc{index}')

        quota = _quota(manager, client_account_a, MetricKey.PIPELINE_VALUE)

        # owner fetch + team adjacency descent + the metric aggregate.
        with django_assert_num_queries(3):
            P.compute_progress(quota)
