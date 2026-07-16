# backend/tests/bi/test_kpi_campaign.py
"""
KPI 2 — Campaign progress + objectives (custom compute_fn, param campaign_id).

Proves:
- value = campaign completion rate (CampaignAccount COMPLETED / total),
- meta.objectives = current/target/progress_pct per objective_type (module
  objectives, current via get_current_value),
- scope positive AND negative: owner AND executor see the campaign; a third
  user does not (apply_role_scope on Campaign, owner + assigned_to_user=executor),
- query-bounded (assertNumQueries): 3 + #objectives, no per-account N+1.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignAccountStatus, ObjectiveType
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_account import CampaignAccount
from app_modules.campaigns.models.campaign_objective import CampaignObjective
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.campaigns import campaign_progress
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext


TODAY = timezone.now().date()


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_campaign(owner, ca, executor=None):
    c = Campaign(name='Camp', campaign_type='OUTBOUND', owner=owner, executor=executor,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_campaign_account(campaign, account, ca, status=CampaignAccountStatus.PENDING):
    x = CampaignAccount(campaign=campaign, account=account, status=status)
    x.save(user=campaign.owner, client_id=ca.id)
    return x


def _mk_objective(campaign, ca, objective_type, target, is_primary=False):
    o = CampaignObjective(campaign=campaign, name=str(objective_type),
                          objective_type=objective_type, target_value=target,
                          is_primary=is_primary)
    o.save(user=campaign.owner, client_id=ca.id)
    return o


def _mk_meeting(campaign, account, owner, ca):
    a = Activity(title='m', activity_type=ActivityType.MEETING,
                 status=ActivityStatus.COMPLETED, outcome='SUCCESSFUL',
                 account=account, owner=owner, campaign=campaign, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _mk_dc_activity(campaign, account, owner, ca):
    dc = DecisionCycle(account=account, owner=owner, name='dc')
    dc.save(user=owner, client_id=ca.id)
    a = Activity(title='c', activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
                 account=account, owner=owner, campaign=campaign, decision_cycle=dc,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield campaign_progress
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def owner(db, client_account_a, role_individual_a):
    return _mk_user('owner@a.test', client_account_a, role_individual_a)


@pytest.fixture
def executor(db, client_account_a, role_individual_a):
    return _mk_user('exec@a.test', client_account_a, role_individual_a)


@pytest.fixture
def outsider(db, client_account_a, role_individual_a):
    return _mk_user('outsider@a.test', client_account_a, role_individual_a)


@pytest.fixture
def campaign(db, client_account_a, owner, executor):
    c = _mk_campaign(owner, client_account_a, executor=executor)
    accts = [_mk_account(f'A{i}', owner, client_account_a) for i in range(4)]
    _mk_campaign_account(c, accts[0], client_account_a, CampaignAccountStatus.COMPLETED)
    _mk_campaign_account(c, accts[1], client_account_a, CampaignAccountStatus.COMPLETED)
    _mk_campaign_account(c, accts[2], client_account_a, CampaignAccountStatus.PENDING)
    _mk_campaign_account(c, accts[3], client_account_a, CampaignAccountStatus.PENDING)
    # objectives
    _mk_objective(c, client_account_a, ObjectiveType.MEETINGS, 10, is_primary=True)
    _mk_objective(c, client_account_a, ObjectiveType.DECISION_CYCLES, 4)
    # current values: 3 completed meetings, 2 distinct decision cycles
    for _ in range(3):
        _mk_meeting(c, accts[0], owner, client_account_a)
    _mk_dc_activity(c, accts[1], owner, client_account_a)
    _mk_dc_activity(c, accts[2], owner, client_account_a)
    return c


@pytest.mark.django_db
def test_registered_custom_compute(kpi):
    assert registry.get('campaign_progress') is kpi
    assert kpi.compute_fn is not None


@pytest.mark.django_db
class TestValue:

    def test_progress_and_objectives(self, kpi, owner, client_account_a, campaign):
        res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                         params={'campaign_id': str(campaign.id)})
        assert res.value == 50.0  # 2 COMPLETED / 4 accounts
        assert res.meta['accounts_total'] == 4
        assert res.meta['accounts_completed'] == 2

        by_type = {o['objective_type']: o for o in res.meta['objectives']}
        assert by_type[ObjectiveType.MEETINGS]['target'] == 10.0
        assert by_type[ObjectiveType.MEETINGS]['current'] == 3.0
        assert by_type[ObjectiveType.MEETINGS]['progress_pct'] == 30.0
        assert by_type[ObjectiveType.MEETINGS]['is_primary'] is True
        assert by_type[ObjectiveType.DECISION_CYCLES]['current'] == 2.0
        assert by_type[ObjectiveType.DECISION_CYCLES]['progress_pct'] == 50.0


@pytest.mark.django_db
class TestStoppedCountsAsDone:
    """A STOPPED account was WORKED (contacted -> no-response / opt-out): a
    terminal OUTCOME, not a cancellation. It counts as DONE (numerator), and the
    denominator stays the raw total. "Remaining" = total - done = the non-final
    accounts (PENDING + IN_PROGRESS) — never a stopped one."""

    def _campaign_with_stopped(self, owner, ca):
        # 5 accounts: 2 COMPLETED, 1 IN_PROGRESS, 1 PENDING, 1 STOPPED.
        c = _mk_campaign(owner, ca)
        accts = [_mk_account(f'S{i}', owner, ca) for i in range(5)]
        _mk_campaign_account(c, accts[0], ca, CampaignAccountStatus.COMPLETED)
        _mk_campaign_account(c, accts[1], ca, CampaignAccountStatus.COMPLETED)
        _mk_campaign_account(c, accts[2], ca, CampaignAccountStatus.IN_PROGRESS)
        _mk_campaign_account(c, accts[3], ca, CampaignAccountStatus.PENDING)
        _mk_campaign_account(c, accts[4], ca, CampaignAccountStatus.STOPPED)
        return c

    def test_stopped_counts_as_done_denominator_is_raw_total(
        self, kpi, owner, client_account_a
    ):
        c = self._campaign_with_stopped(owner, client_account_a)
        res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                         params={'campaign_id': str(c.id)})

        # done = 2 COMPLETED + 1 STOPPED = 3 ; total = 5 (raw)
        assert res.meta['accounts_total'] == 5              # raw total, stopped NOT dropped
        assert res.meta['accounts_completed'] == 3          # DONE = completed + stopped
        assert res.meta['accounts_completed_only'] == 2     # strictly COMPLETED
        assert res.meta['accounts_stopped'] == 1
        assert res.value == 60.0                            # 3 / 5, not 2/5 (=40) nor 2/4 (=50)

        # The queue "remaining" the Home computes: total - done = the non-final
        # accounts (IN_PROGRESS + PENDING), never the stopped one.
        remaining = res.meta['accounts_total'] - res.meta['accounts_completed']
        assert remaining == 2

    def test_all_stopped_is_fully_done(self, kpi, owner, client_account_a):
        c = _mk_campaign(owner, client_account_a)
        acc = _mk_account('AllStop', owner, client_account_a)
        _mk_campaign_account(c, acc, client_account_a, CampaignAccountStatus.STOPPED)
        res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                         params={'campaign_id': str(c.id)})
        # a worked-then-stopped account is done -> 1/1 = 100%, nothing remaining
        assert res.meta['accounts_total'] == 1
        assert res.meta['accounts_completed'] == 1
        assert res.meta['accounts_stopped'] == 1
        assert res.value == 100.0
        assert res.meta['accounts_total'] - res.meta['accounts_completed'] == 0


@pytest.mark.django_db
class TestScope:

    def test_owner_and_executor_see_it_outsider_does_not(
        self, kpi, owner, executor, outsider, client_account_a, campaign
    ):
        params = {'campaign_id': str(campaign.id)}
        # owner
        assert cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                          params=params).value == 50.0
        # executor (via assigned_to_user='executor')
        assert cached_run(kpi, _ctx(executor, client_account_a), scope='mine',
                          params=params).value == 50.0
        # outsider -> not in scope -> None
        res_out = cached_run(kpi, _ctx(outsider, client_account_a), scope='mine',
                             params=params)
        assert res_out.value is None
        assert res_out.meta['reason'] == 'out_of_scope_or_missing'

    def test_client_scope_sees_it(self, kpi, outsider, client_account_a, campaign):
        # even a non-owner sees it under client scope (whole tenant)
        assert cached_run(kpi, _ctx(outsider, client_account_a), scope='client',
                          params={'campaign_id': str(campaign.id)}).value == 50.0


@pytest.mark.django_db
class TestQueryBound:

    def test_bounded_queries(self, kpi, owner, client_account_a, campaign,
                             django_assert_num_queries):
        # 2 objectives -> campaign(1) + accounts agg(1) + objectives load(1) + 2 = 5
        with django_assert_num_queries(5):
            res = cached_run(kpi, _ctx(owner, client_account_a), scope='mine',
                             params={'campaign_id': str(campaign.id)})
            _ = res.value
