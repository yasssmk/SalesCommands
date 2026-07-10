# backend/tests/bi/test_kpi_dc_counters.py
"""
KPI 5 — DC counters: decision cycles grouped by outcome (None = open).

Proves the declared KPI (app_modules/bi/definitions/decision_cycles.py):
- produces the correct breakdown by outcome, and
- is scoped by the decision_cycles role scope — positive (a rep sees their own
  cycles) AND negative (another rep's cycles are excluded).

The foundation handles compute/cache/scope; this KPI only declares source /
aggregation / period / scope_module / cache wiring.
"""

import pytest
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.decision_cycles import dc_cycles_by_outcome
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.bi.types import OutputShape
from permissions.compat import AuthContext


# --- helpers ---------------------------------------------------------------

def _ctx(user, client_account):
    return AuthContext(user_id=str(user.id), client_id=str(client_account.id),
                       is_authenticated=True)


def _mk_user(email, client_account, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=client_account,
                               role=role, is_active=True)


def _mk_cycle(owner, client_account, outcome=None, name='Cycle'):
    """Create a cycle on its OWN account (owned by `owner`) to keep the
    one-active-cycle-per-account invariant satisfied."""
    acc = CompanyAccount(company_name=f'{name} Corp', has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    cyc = DecisionCycle(account=acc, owner=owner, name=name, outcome=outcome)
    cyc.save(user=owner, client_id=client_account.id)
    return cyc


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def kpi(db):
    """Load the declared KPIs (idempotent) and wire invalidation."""
    load_all()
    ci.connect_invalidation_receivers()
    yield dc_cycles_by_outcome
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_b(db, client_account_a, role_individual_a):
    """A different rep in the SAME tenant (out of user_a's owner scope)."""
    return _mk_user('rep-b@a.test', client_account_a, role_individual_a)


# =============================================================================
# The KPI is declared / discoverable
# =============================================================================

@pytest.mark.django_db
def test_kpi_is_registered(kpi):
    assert registry.get('dc_cycles_by_outcome') is kpi
    assert kpi.output_shape is OutputShape.BREAKDOWN
    assert kpi.dimension == 'outcome'


# =============================================================================
# Values
# =============================================================================

@pytest.mark.django_db
class TestValues:

    def test_breakdown_by_outcome(self, kpi, user_a, client_account_a):
        _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, name='W')
        _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.LOST, name='L')
        _mk_cycle(user_a, client_account_a, outcome=None, name='O1')  # open
        _mk_cycle(user_a, client_account_a, outcome=None, name='O2')  # open

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine')
        assert res.shape is OutputShape.BREAKDOWN
        assert res.value == {CycleOutcome.WON: 1, CycleOutcome.LOST: 1, None: 2}


# =============================================================================
# Scope — positive AND negative
# =============================================================================

@pytest.mark.django_db
class TestScope:

    def test_mine_excludes_other_reps_cycles(self, kpi, user_a, user_b, client_account_a):
        _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, name='A-won')
        _mk_cycle(user_a, client_account_a, outcome=None, name='A-open')
        _mk_cycle(user_b, client_account_a, outcome=None, name='B-open')  # other rep

        # positive: user_a sees only their own two
        mine_a = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine')
        assert mine_a.value == {CycleOutcome.WON: 1, None: 1}
        assert sum(mine_a.value.values()) == 2  # user_b's cycle excluded

        # negative: user_b sees only their own one
        mine_b = cached_run(kpi, _ctx(user_b, client_account_a), scope='mine')
        assert mine_b.value == {None: 1}

    def test_client_scope_sees_whole_tenant(self, kpi, user_a, user_b, client_account_a):
        _mk_cycle(user_a, client_account_a, outcome=CycleOutcome.WON, name='A-won')
        _mk_cycle(user_a, client_account_a, outcome=None, name='A-open')
        _mk_cycle(user_b, client_account_a, outcome=None, name='B-open')

        res = cached_run(kpi, _ctx(user_a, client_account_a), scope='client')
        assert res.value == {CycleOutcome.WON: 1, None: 2}  # both reps' cycles
