# backend/tests/bi/test_kpi_cycle_state.py
"""
KPI 9 — Decision cycle STATE (not a %): current stage + derived status
(STALLED visible) + next action + secondary "X/N stages validated".

Reuses the REPAIRED derived logic. Proves:
- an in-progress cycle: derived status, current stage, X/N,
- a STALLED cycle: STALLED surfaces in the KPI + the "act" next_action
  (the motivation lever) — proof the signal reaches the KPI,
- scope negative + C6,
- assertNumQueries bounded.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.decision_cycles import dc_cycle_state
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext


TODAY = timezone.now().date()
FUTURE = TODAY + timedelta(days=30)
STAGES = [PipelineStep.QUALIFICATION, PipelineStep.TECHNICAL_FIT,
          PipelineStep.SOLUTION_VALIDATION, PipelineStep.BUSINESS_CASE,
          PipelineStep.CLOSING]

_seq = 0


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(owner, ca):
    global _seq
    _seq += 1
    acc = CompanyAccount(company_name=f'Acc{_seq}', has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_cycle(owner, ca, account=None):
    acc = account or _mk_account(owner, ca)
    c = DecisionCycle(account=acc, owner=owner, name='dc')
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_step(cycle, owner, ca, stage, order):
    s = DecisionStep(cycle=cycle, stage=stage, order=order, name=str(stage))
    s.save(user=owner, client_id=ca.id)
    return s


def _mk_act(step, cycle, owner, ca, status, scheduled=TODAY):
    a = Activity(title='a', activity_type=ActivityType.CALL, status=status,
                 account=cycle.account, owner=owner, decision_cycle=cycle,
                 decision_step=step, scheduled_date=scheduled)
    a.save(user=owner, client_id=ca.id)
    return a


def _build_five_steps(cycle, owner, ca):
    return [_mk_step(cycle, owner, ca, STAGES[i], i) for i in range(5)]


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield dc_cycle_state
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_registered(kpi):
    assert registry.get('dc_cycle_state') is kpi
    assert kpi.compute_fn is not None


@pytest.mark.django_db
class TestState:

    def test_in_progress_state(self, kpi, user_a, client_account_a):
        cyc = _mk_cycle(user_a, client_account_a)
        steps = _build_five_steps(cyc, user_a, client_account_a)
        # step0 done, step1 has a (future) planned activity -> step0 VALIDATED, step1 IN_PROGRESS
        _mk_act(steps[0], cyc, user_a, client_account_a, ActivityStatus.COMPLETED)
        _mk_act(steps[1], cyc, user_a, client_account_a, ActivityStatus.PLANNED, scheduled=FUTURE)

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'cycle_id': str(cyc.id)})
        assert res.value == 'IN_PROGRESS'
        assert res.meta['validated_steps'] == 1
        assert res.meta['total_steps'] == 5           # "1/5"
        assert res.meta['current_step_order'] == 1
        assert res.meta['current_stage'] == PipelineStep.TECHNICAL_FIT
        assert res.meta['next_action'].startswith('Advance:')
        assert 'percentage' not in res.meta           # no % exposed

    def test_stalled_state_surfaces(self, kpi, user_a, client_account_a):
        cyc = _mk_cycle(user_a, client_account_a)
        steps = _build_five_steps(cyc, user_a, client_account_a)
        # every step done, NO planned anywhere -> steps 0-3 VALIDATED, step4 STALLED
        for s in steps:
            _mk_act(s, cyc, user_a, client_account_a, ActivityStatus.COMPLETED)

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'cycle_id': str(cyc.id)})
        assert res.value == 'STALLED'                 # the signal reaches the KPI
        assert res.meta['validated_steps'] == 4
        assert res.meta['total_steps'] == 5           # "4/5"
        assert res.meta['next_action'] == 'Act: close the deal or define the next step'


@pytest.mark.django_db
class TestScope:

    def test_other_users_cycle_not_visible(self, kpi, user_a, user_b, client_account_a):
        cyc_b = _mk_cycle(user_b, client_account_a)
        _build_five_steps(cyc_b, user_b, client_account_a)
        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'cycle_id': str(cyc_b.id)})
        assert res.value is None
        assert res.meta['reason'] == 'out_of_scope_or_missing'

    def test_c6_account_owner_sees_cycle(self, kpi, user_a, user_b, client_account_a):
        acc_a = _mk_account(user_a, client_account_a)          # owned by user_a
        cyc = _mk_cycle(user_b, client_account_a, account=acc_a)  # owned by user_b, on user_a's account
        steps = _build_five_steps(cyc, user_b, client_account_a)
        _mk_act(steps[0], cyc, user_b, client_account_a, ActivityStatus.PLANNED, scheduled=FUTURE)

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                         params={'cycle_id': str(cyc.id)})
        assert res.value is not None                  # visible via C6
        assert res.meta['cycle_id'] == str(cyc.id)


@pytest.mark.django_db
class TestQueryBound:

    def test_bounded(self, kpi, user_a, client_account_a, django_assert_num_queries):
        cyc = _mk_cycle(user_a, client_account_a)
        steps = _build_five_steps(cyc, user_a, client_account_a)
        for s in steps:
            _mk_act(s, cyc, user_a, client_account_a, ActivityStatus.COMPLETED)
        # cycle fetch + steps prefetch + activities prefetch = 3 (derive uses cache)
        with django_assert_num_queries(3):
            res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                             params={'cycle_id': str(cyc.id)})
            _ = res.value
