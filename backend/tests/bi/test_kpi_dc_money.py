# backend/tests/bi/test_kpi_dc_money.py
"""
KPI 7 — DC monetary: $ pipeline (open, STOCK) and $ result (WON, FLUX by period).

value = product roll-up over deal_products:
  Σ quantity × Coalesce(unit_price, catalog.default_unit_price, 0) × (1 − discount%/100)

Proves:
- correct Σ with a unit_price override AND with the catalog default price,
- discount applied,
- multi-line DC -> Σ of its lines, NOT a multiple (anti double-count on the
  to-many join),
- pipe (STOCK, period=None) vs result (FLUX, WON in period by outcome_date),
- scope negative + C6,
- assertNumQueries(1).
"""

from datetime import date

import pytest
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle, DealProduct
from app_modules.product_catalog.models import ProductCatalog
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.decision_cycles import dc_pipeline_value, dc_won_value
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.bi.types import Period
from permissions.compat import AuthContext


PERIOD = Period(start=date(2026, 1, 1), end=date(2026, 12, 31))
IN_PERIOD = date(2026, 6, 1)
OUT_PERIOD = date(2025, 6, 1)

_acc_seq = 0


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(owner, ca):
    global _acc_seq
    _acc_seq += 1
    acc = CompanyAccount(company_name=f'Acc{_acc_seq}', has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_cycle(owner, ca, account=None, outcome=None, outcome_date=None):
    acc = account or _mk_account(owner, ca)
    c = DecisionCycle(account=acc, owner=owner, name='dc',
                      outcome=outcome, outcome_date=outcome_date)
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_product(owner, ca, default_price=None):
    global _acc_seq
    _acc_seq += 1
    p = ProductCatalog(name=f'P{_acc_seq}', default_unit_price=default_price)
    p.save(user=owner, client_id=ca.id)
    return p


def _mk_line(cycle, product, owner, ca, quantity, unit_price=None, discount=0):
    dp = DealProduct(decision_cycle=cycle, product_catalog_entry=product,
                     quantity=quantity, unit_price=unit_price, discount_percent=discount)
    dp.save(user=owner, client_id=ca.id)
    return dp


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpis(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield (dc_pipeline_value, dc_won_value)
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    return _mk_user('b@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_registered(kpis):
    assert registry.get('dc_pipeline_value') is kpis[0]
    assert registry.get('dc_won_value') is kpis[1]


@pytest.mark.django_db
class TestPipelineValue:

    def test_pipeline_override_catalog_and_discount(self, kpis, user_a, client_account_a):
        pipe, _ = kpis
        # DC1 (open) — two lines: override price + catalog default price
        dc1 = _mk_cycle(user_a, client_account_a)
        p_cat = _mk_product(user_a, client_account_a, default_price=50)
        p_any = _mk_product(user_a, client_account_a, default_price=None)
        _mk_line(dc1, p_any, user_a, client_account_a, quantity=2, unit_price=100)  # 200
        _mk_line(dc1, p_cat, user_a, client_account_a, quantity=1)                  # 50 (catalog)
        # DC2 (open) — with discount
        dc2 = _mk_cycle(user_a, client_account_a)
        _mk_line(dc2, p_any, user_a, client_account_a, quantity=1, unit_price=100, discount=10)  # 90
        # a WON cycle must NOT count towards pipeline
        won = _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, outcome_date=IN_PERIOD)
        _mk_line(won, p_any, user_a, client_account_a, quantity=1, unit_price=999)

        res = cached_run(pipe, _ctx(user_a, client_account_a), scope='mine', period=None)
        assert float(res.value) == 340.0  # 200 + 50 + 90

    def test_multiline_no_double_count(self, kpis, client_account_a, role_individual_a):
        """A single open DC with 3 lines -> Σ of the 3 lines, not a multiple."""
        pipe, _ = kpis
        solo = _mk_user('solo@a.test', client_account_a, role_individual_a)
        dc = _mk_cycle(solo, client_account_a)
        p = _mk_product(solo, client_account_a, default_price=None)
        _mk_line(dc, p, solo, client_account_a, quantity=1, unit_price=100)   # 100
        _mk_line(dc, _mk_product(solo, client_account_a), solo, client_account_a,
                 quantity=1, unit_price=200)                                   # 200
        _mk_line(dc, _mk_product(solo, client_account_a), solo, client_account_a,
                 quantity=1, unit_price=50)                                    # 50

        res = cached_run(pipe, _ctx(solo, client_account_a), scope='mine', period=None)
        assert float(res.value) == 350.0  # not 3× anything

    def test_empty_pipeline_is_zero(self, kpis, client_account_a, role_individual_a):
        pipe, _ = kpis
        u = _mk_user('empty@a.test', client_account_a, role_individual_a)
        res = cached_run(pipe, _ctx(u, client_account_a), scope='mine', period=None)
        assert float(res.value) == 0.0


@pytest.mark.django_db
class TestWonValue:

    def test_won_in_period_only(self, kpis, user_a, client_account_a):
        _, won_kpi = kpis
        p = _mk_product(user_a, client_account_a, default_price=None)
        # WON in period
        won_in = _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, outcome_date=IN_PERIOD)
        _mk_line(won_in, p, user_a, client_account_a, quantity=2, unit_price=100)  # 200
        # WON out of period -> excluded
        won_out = _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, outcome_date=OUT_PERIOD)
        _mk_line(won_out, p, user_a, client_account_a, quantity=1, unit_price=500)
        # OPEN cycle -> not a "result"
        opn = _mk_cycle(user_a, client_account_a)
        _mk_line(opn, p, user_a, client_account_a, quantity=1, unit_price=999)

        res = cached_run(won_kpi, _ctx(user_a, client_account_a), scope='mine', period=PERIOD)
        assert float(res.value) == 200.0


@pytest.mark.django_db
class TestScope:

    def test_pipeline_scope_negative(self, kpis, user_a, user_b, client_account_a):
        pipe, _ = kpis
        p = _mk_product(user_a, client_account_a, default_price=None)
        # user_a's open cycle
        dc_a = _mk_cycle(user_a, client_account_a)
        _mk_line(dc_a, p, user_a, client_account_a, quantity=1, unit_price=100)
        # user_b's open cycle (own account) -> not in user_a's pipe
        dc_b = _mk_cycle(user_b, client_account_a)
        _mk_line(dc_b, p, user_b, client_account_a, quantity=1, unit_price=500)

        res = cached_run(pipe, _ctx(user_a, client_account_a), scope='mine', period=None)
        assert float(res.value) == 100.0

    def test_c6_account_owner_sees_others_cycle(self, kpis, user_a, user_b, client_account_a):
        pipe, _ = kpis
        p = _mk_product(user_a, client_account_a, default_price=None)
        # account owned by user_a; open cycle on it owned by user_b -> C6 for user_a
        acc_a = _mk_account(user_a, client_account_a)
        dc = _mk_cycle(user_b, client_account_a, account=acc_a)
        _mk_line(dc, p, user_b, client_account_a, quantity=1, unit_price=100)

        res = cached_run(pipe, _ctx(user_a, client_account_a), scope='mine', period=None)
        assert float(res.value) == 100.0


@pytest.mark.django_db
class TestQueryBound:

    def test_single_query(self, kpis, user_a, client_account_a, django_assert_num_queries):
        pipe, _ = kpis
        p = _mk_product(user_a, client_account_a, default_price=None)
        for _i in range(3):
            dc = _mk_cycle(user_a, client_account_a)
            _mk_line(dc, p, user_a, client_account_a, quantity=1, unit_price=100)
        with django_assert_num_queries(1):
            res = cached_run(pipe, _ctx(user_a, client_account_a), scope='mine', period=None)
            _ = res.value
