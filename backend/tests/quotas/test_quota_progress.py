# backend/tests/quotas/test_quota_progress.py
"""
Quota progress — current value and attainment ratio, computed by consuming the
canonical bi/metrics formulas.

Perimeter is derived from the OWNER's tier: individual -> own data, manager ->
DIRECT team members (no descent), admin -> whole tenant. The ratio is
value/target and is never clamped (over-achievement stays visible). Batch
computation groups quotas so the metric runs once per group (no N+1).

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityOutcome, ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi.metrics import MetricKey
from app_modules.campaigns.models.campaign import Campaign
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P


TODAY = date.today()


# ---------------------------------------------------------------------------
# factories
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


def _team(ca, name, manager):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _account(owner, ca, name='Acc'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type='OUTBOUND', owner=owner, executor=owner,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _cycle(owner, account, ca, *, name='dc', source_campaign=None, created_on=None):
    dc = DecisionCycle(account=account, owner=owner, name=name, source_campaign=source_campaign)
    dc.save(user=owner, client_id=ca.id)
    if created_on is not None:
        DecisionCycle.objects.filter(pk=dc.pk).update(
            created_at=timezone.make_aware(
                timezone.datetime(created_on.year, created_on.month, created_on.day, 12, 0))
        )
    return dc


def _meeting(owner, account, cycle, ca):
    """A meeting HELD by ``owner``. ``completed_at`` is what MEETINGS is windowed
    on (bi/metrics/sales_metrics.meetings) — without it the row is outside every
    period, which is the documented meaning of a meeting never completed."""
    step = DecisionStep(cycle=cycle, name='s', stage=PipelineStep.QUALIFICATION, order=1,
                        expected_end=None)
    step.save(user=owner, client_id=ca.id)
    a = Activity(title='m', activity_type=ActivityType.CALL, status=ActivityStatus.COMPLETED,
                 outcome=ActivityOutcome.MEETING_SCHEDULED, account=account, owner=owner,
                 decision_cycle=cycle, decision_step=step, scheduled_date=TODAY,
                 completed_at=timezone.now())
    a.save(user=owner, client_id=ca.id)
    return a


def _quota(owner, ca, *, metric=MetricKey.DECISION_CYCLES, target=Decimal('10'),
           start=None, end=None, source_campaign=None):
    q = Quota(owner=owner, metric=metric, target_value=target,
              period_start=start or TODAY - timedelta(days=15),
              period_end=end or TODAY + timedelta(days=15),
              source_campaign=source_campaign)
    q.save(user=owner, client_id=ca.id)
    return q


# ---------------------------------------------------------------------------
# Individual perimeter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIndividualPerimeter:

    def test_counts_only_own_data(self, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        me = _user('me@a.test', client_account_a, role)
        other = _user('other@a.test', client_account_a, role)
        acc = _account(me, client_account_a)
        _cycle(me, acc, client_account_a, name='mine')       # positive
        _cycle(other, acc, client_account_a, name='others')  # negative
        q = _quota(me, client_account_a, target=Decimal('5'))
        prog = P.compute_progress(q)
        assert prog.current_value == 1        # only my cycle
        assert prog.ratio == 0.2


# ---------------------------------------------------------------------------
# Manager perimeter — DIRECT team members (no descent)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestManagerPerimeter:

    def test_counts_team_aggregate_including_self_excluding_outsider(self, client_account_a):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_mgr = _role(client_account_a, 'Mgr', manager=True)
        manager = _user('mgr@a.test', client_account_a, role_mgr)
        team = _team(client_account_a, 'T', manager)
        # The manager is attached to their own team via the User.team FK.
        manager.team = team
        manager.save()
        member = _user('member@a.test', client_account_a, role_ind, team=team)
        outsider = _user('out@a.test', client_account_a, role_ind)  # no team

        acc = _account(manager, client_account_a)
        _cycle(member, acc, client_account_a, name='member')      # in team (positive)
        _cycle(manager, acc, client_account_a, name='manager')    # self (positive)
        _cycle(outsider, acc, client_account_a, name='outsider')  # out of team (negative)

        q = _quota(manager, client_account_a, target=Decimal('10'))
        prog = P.compute_progress(q)
        assert prog.current_value == 2        # member + manager, NOT outsider
        assert prog.ratio == 0.2

    def test_manager_with_no_team_measures_empty(self, client_account_a):
        role_mgr = _role(client_account_a, 'Mgr', manager=True)
        manager = _user('mgr2@a.test', client_account_a, role_mgr)  # team=None
        acc = _account(manager, client_account_a)
        _cycle(manager, acc, client_account_a)
        q = _quota(manager, client_account_a, target=Decimal('10'))
        assert P.compute_progress(q).current_value == 0


# ---------------------------------------------------------------------------
# Admin perimeter — whole tenant, never cross-tenant
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminPerimeter:

    def test_counts_whole_tenant_not_other_tenant(
            self, client_account_a, client_account_b, role_individual_b, user_b):
        role_ind = _role(client_account_a, 'Ind', individual=True)
        role_admin = _role(client_account_a, 'Adm', admin=True)
        admin = _user('adm@a.test', client_account_a, role_admin)
        u1 = _user('u1@a.test', client_account_a, role_ind)

        acc_a = _account(admin, client_account_a)
        _cycle(admin, acc_a, client_account_a, name='a1')
        _cycle(u1, acc_a, client_account_a, name='a2')
        # another tenant's cycle must never enter
        acc_b = _account(user_b, client_account_b)
        _cycle(user_b, acc_b, client_account_b, name='b1')

        q = _quota(admin, client_account_a, target=Decimal('10'))
        assert P.compute_progress(q).current_value == 2   # both tenant-A, not B


# ---------------------------------------------------------------------------
# source_campaign / window / over-achievement
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCampaignWindowOverachievement:

    def test_source_campaign_declines_scope(self, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        me = _user('me3@a.test', client_account_a, role)
        acc = _account(me, client_account_a)
        camp = _campaign(me, client_account_a)
        _cycle(me, acc, client_account_a, name='in', source_campaign=camp)
        _cycle(me, acc, client_account_a, name='out', source_campaign=None)

        q_camp = _quota(me, client_account_a, target=Decimal('10'), source_campaign=camp)
        q_glob = _quota(me, client_account_a, target=Decimal('10'), source_campaign=None)
        assert P.compute_progress(q_camp).current_value == 1   # only the campaign one
        assert P.compute_progress(q_glob).current_value == 2   # everything

    def test_window_on_created_at_anchor(self, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        me = _user('me4@a.test', client_account_a, role)
        acc = _account(me, client_account_a)
        _cycle(me, acc, client_account_a, name='in', created_on=TODAY - timedelta(days=5))
        _cycle(me, acc, client_account_a, name='out', created_on=TODAY - timedelta(days=40))
        q = _quota(me, client_account_a, target=Decimal('10'),
                   start=TODAY - timedelta(days=10), end=TODAY)
        assert P.compute_progress(q).current_value == 1   # the out-of-window one excluded

    def test_overachievement_ratio_not_clamped(self, client_account_a):
        role = _role(client_account_a, 'Ind', individual=True)
        me = _user('me5@a.test', client_account_a, role)
        acc = _account(me, client_account_a)
        for i in range(13):
            _cycle(me, acc, client_account_a, name=f'c{i}')
        q = _quota(me, client_account_a, target=Decimal('10'))   # target 10, value 13
        prog = P.compute_progress(q)
        assert prog.current_value == 13
        assert prog.ratio == 1.3          # NOT clamped to 1.0
        assert prog.is_over_achieved is True

    def test_meetings_metric_individual(self, client_account_a):
        # exercises the Activity-based metric path (owner = whoever LOGGED the
        # meeting — bi/metrics/attribution_scope.activity_scope_q).
        role = _role(client_account_a, 'Ind', individual=True)
        me = _user('me6@a.test', client_account_a, role)
        acc = _account(me, client_account_a)
        cyc = _cycle(me, acc, client_account_a)
        _meeting(me, acc, cyc, client_account_a)
        q = _quota(me, client_account_a, metric=MetricKey.MEETINGS, target=Decimal('4'))
        prog = P.compute_progress(q)
        assert prog.current_value == 1
        assert prog.ratio == 0.25


# ---------------------------------------------------------------------------
# Anti-N+1 — a list of quotas sharing a group is ONE metric call
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAntiNPlusOne:

    def test_batch_query_count_constant(self, django_assert_num_queries, client_account_a):
        role_mgr = _role(client_account_a, 'Mgr', manager=True)
        manager = _user('mgrb@a.test', client_account_a, role_mgr)
        team = _team(client_account_a, 'TB', manager)
        manager.team = team
        manager.save()
        member = _user('memb@a.test', client_account_a,
                       _role(client_account_a, 'Ind', individual=True), team=team)
        acc = _account(manager, client_account_a)
        for i in range(4):
            _cycle(member, acc, client_account_a, name=f'c{i}')

        # 8 quotas of the SAME (metric, perimeter, window, campaign): one group.
        quotas = [
            _quota(manager, client_account_a, target=Decimal(str(t)))
            for t in range(1, 9)
        ]
        quota_list = list(
            Quota.objects.filter(id__in=[q.id for q in quotas]).select_related('source_campaign')
        )

        # Owners (1) + the manager subtree's team ids (1) + one metric query for
        # the single group (1) = 3, independent of the 8 quotas. (Sub-step 4bis:
        # the manager perimeter now descends the team subtree, adding the one
        # constant team-adjacency query — was 2 before the recursive fix.)
        with django_assert_num_queries(3):
            results = P.compute_progress_batch(quota_list)

        assert len(results) == 8
        for q in quotas:
            r = results[q.id]
            assert r.current_value == 4
            assert r.ratio == 4.0 / float(q.target_value)
