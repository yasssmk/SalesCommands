# backend/tests/bi/test_kpi_leads.py
"""
KPI 6 — Leads = decision cycles + activities CREATED in the period.

No Lead entity; two atomic KPIs (leads_dc_created, leads_activities_created)
whose sum is "leads generated". Proves:
- period filtering on created_at (a DateTimeField) is inclusive at the end
  boundary (the _apply_period date-granularity fix),
- scope positive AND negative (a rep's created rows only; C6 for account owner),
- the two atomic KPIs sum to the total.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.leads import leads_dc_created, leads_activities_created
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.bi.types import OutputShape, Period
from permissions.compat import AuthContext


TODAY = timezone.now().date()
PERIOD = Period(start=TODAY - timedelta(days=30), end=TODAY)  # end = today (boundary)


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _set_created_at(instance, when):
    """Backdate created_at (auto_now_add is bypassed by .update())."""
    type(instance).objects.filter(pk=instance.pk).update(created_at=when)


def _mk_cycle(owner, ca, created_at=None):
    acc = _mk_account('Cyc Corp', owner, ca)
    c = DecisionCycle(account=acc, owner=owner, name='C')
    c.save(user=owner, client_id=ca.id)
    if created_at:
        _set_created_at(c, created_at)
    return c


def _mk_activity(owner, account, ca, created_at=None):
    a = Activity(title='t', activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
                 account=account, owner=owner, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    if created_at:
        _set_created_at(a, created_at)
    return a


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpis(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield (leads_dc_created, leads_activities_created)
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('rep-b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_kpis_registered(kpis):
    assert registry.get('leads_dc_created') is kpis[0]
    assert registry.get('leads_activities_created') is kpis[1]
    assert kpis[0].output_shape is OutputShape.SCALAR


@pytest.mark.django_db
class TestPeriodAndValue:

    def test_counts_created_in_period(self, kpis, user_a, client_account_a):
        dc_kpi, act_kpi = kpis
        acc = _mk_account('A Corp', user_a, client_account_a)

        # In period (created today = end boundary)
        _mk_cycle(user_a, client_account_a)
        _mk_cycle(user_a, client_account_a)
        _mk_activity(user_a, acc, client_account_a)
        _mk_activity(user_a, acc, client_account_a)
        _mk_activity(user_a, acc, client_account_a)
        # Out of period (created > 30d ago)
        old = timezone.now() - timedelta(days=400)
        _mk_cycle(user_a, client_account_a, created_at=old)
        _mk_activity(user_a, acc, client_account_a, created_at=old)

        ctx = _ctx(user_a, client_account_a)
        dc = cached_run(dc_kpi, ctx, scope='mine', period=PERIOD)
        act = cached_run(act_kpi, ctx, scope='mine', period=PERIOD)

        assert dc.value == 2       # today included (end-boundary inclusive), old excluded
        assert act.value == 3
        # "leads generated" = the sum of the two atomic KPIs
        assert dc.value + act.value == 5


@pytest.mark.django_db
class TestScope:

    def test_mine_excludes_other_rep(self, kpis, user_a, user_b, client_account_a):
        dc_kpi, act_kpi = kpis
        acc_a = _mk_account('A Corp', user_a, client_account_a)
        acc_b = _mk_account('B Corp', user_b, client_account_a)

        _mk_cycle(user_a, client_account_a)          # a's
        _mk_activity(user_a, acc_a, client_account_a)  # a's
        _mk_cycle(user_b, client_account_a)          # b's
        _mk_activity(user_b, acc_b, client_account_a)  # b's

        ctx_a = _ctx(user_a, client_account_a)
        assert cached_run(dc_kpi, ctx_a, scope='mine', period=PERIOD).value == 1
        assert cached_run(act_kpi, ctx_a, scope='mine', period=PERIOD).value == 1

        # client scope sees the whole tenant
        assert cached_run(dc_kpi, ctx_a, scope='client', period=PERIOD).value == 2
        assert cached_run(act_kpi, ctx_a, scope='client', period=PERIOD).value == 2

    def test_c6_account_owner_counts_others_activities_on_their_account(
        self, kpis, user_a, user_b, client_account_a
    ):
        _, act_kpi = kpis
        acc_a = _mk_account('A Corp', user_a, client_account_a)  # owned by user_a
        _mk_activity(user_b, acc_a, client_account_a)  # created by user_b on a's account

        # C6: user_a (account owner) counts it under mine
        assert cached_run(act_kpi, _ctx(user_a, client_account_a),
                          scope='mine', period=PERIOD).value == 1
