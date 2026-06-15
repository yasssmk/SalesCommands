# tests/decision_cycles/test_readiness_recompute.py
"""
Tests for readiness_score auto-recompute via Django signals.

Verifies that creating/deleting signals, products, and activities
automatically updates DecisionCycle.readiness_score.

All signal-triggered test classes use ``transaction=True`` so that
``transaction.on_commit`` callbacks execute during the test (same
pattern as tests/signals/test_blocker_model.py).
"""

import pytest

from app_modules.decision_cycles.services.readiness_score_service import (
    ReadinessScoreService,
)
from app_modules.signals.constants import (
    PeopleRole,
    SignalStatus,
    SignalWhat,
    SignalDimension,
    Rigidity,
)


# =============================================================================
# HELPERS
# =============================================================================

def _refresh(cycle):
    cycle.refresh_from_db()
    return cycle.readiness_score


def _create_pain(account, activity, cycle, user):
    from app_modules.signals.models import PainSignal
    sig = PainSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Test pain',
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_objective(account, activity, cycle, user):
    from app_modules.signals.models import ObjectiveSignal
    sig = ObjectiveSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Test objective',
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_impact(account, activity, cycle, user):
    from app_modules.signals.models import ImpactSignal
    sig = ImpactSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Test impact',
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_blocker(account, activity, cycle, user):
    from app_modules.signals.models import BlockerSignal
    sig = BlockerSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        summary='Test blocker',
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_constraint(account, activity, cycle, user):
    from app_modules.signals.models import ConstraintSignal
    sig = ConstraintSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        what=SignalWhat.OPS,
        dimension=SignalDimension.COST,
        summary='Test constraint',
        rigidity=Rigidity.FIRM,
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_people(account, activity, cycle, user, role, contact=None):
    from app_modules.signals.models import PeopleSignal
    sig = PeopleSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        role=role,
        target_contact=contact,
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _create_deal_product(cycle, user):
    from app_modules.product_catalog.models import ProductCatalog
    from app_modules.decision_cycles.models import DealProduct
    catalog = ProductCatalog(name='Test Product', default_unit_price=1000)
    catalog.save(user=user, client_id=cycle.client_id)
    dp = DealProduct(
        decision_cycle=cycle,
        product_catalog_entry=catalog,
        quantity=1,
    )
    dp.save(user=user, client_id=cycle.client_id)
    return dp


def _create_second_cycle(account, user):
    from app_modules.decision_cycles.models import DecisionCycle
    c = DecisionCycle(
        account=account,
        owner=user,
        name='Second Cycle',
        is_active=True,
    )
    c.save(user=user, client_id=account.client_id)
    return c


# =============================================================================
# RECOMPUTE_AND_STORE METHOD
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestRecomputeAndStore:
    """ReadinessScoreService.recompute_and_store persists the score."""

    def test_stores_zero_on_empty_cycle(self, cycle):
        ReadinessScoreService.recompute_and_store(cycle)
        cycle.refresh_from_db()
        assert cycle.readiness_score == 0

    def test_stores_calculated_score(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_pain(account, activity, cycle, user_a)

        ReadinessScoreService.recompute_and_store(cycle)
        cycle.refresh_from_db()
        # pain(20) + momentum(5) = 25
        assert cycle.readiness_score == 25


# =============================================================================
# SIGNAL-TRIGGERED RECOMPUTE
# =============================================================================

@pytest.mark.django_db(transaction=True)
class TestSignalTriggeredRecompute:
    """Django signals auto-recompute readiness_score on model changes."""

    def test_pain_save_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_pain(account, activity, cycle, user_a)
        # pain(20) + momentum(5)
        assert _refresh(cycle) == 25

    def test_pain_delete_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        sig = _create_pain(account, activity, cycle, user_a)
        assert _refresh(cycle) == 25

        sig.delete()
        # momentum(5) only
        assert _refresh(cycle) == 5

    def test_objective_save_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_objective(account, activity, cycle, user_a)
        # objective(15) + momentum(5)
        assert _refresh(cycle) == 20

    def test_impact_save_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_impact(account, activity, cycle, user_a)
        # impact(15) + momentum(5)
        assert _refresh(cycle) == 20

    def test_blocker_save_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_blocker(account, activity, cycle, user_a)
        # risk(10) + momentum(5)
        assert _refresh(cycle) == 15

    def test_constraint_save_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_constraint(account, activity, cycle, user_a)
        # risk(10) + momentum(5)
        assert _refresh(cycle) == 15

    def test_people_decision_maker_triggers_recompute(self, cycle, account, activity, user_a, contact):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.DECISION_MAKER, contact=contact)
        # decision_maker(15) + momentum(5)
        assert _refresh(cycle) == 20

    def test_people_champion_triggers_recompute(self, cycle, account, activity, user_a, contact):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.CHAMPION, contact=contact)
        # champion(10) + momentum(5)
        assert _refresh(cycle) == 15

    def test_deal_product_save_triggers_recompute(self, cycle, user_a):
        _create_deal_product(cycle, user_a)
        # solution(10)
        assert _refresh(cycle) == 10

    def test_deal_product_delete_triggers_recompute(self, cycle, user_a):
        dp = _create_deal_product(cycle, user_a)
        assert _refresh(cycle) == 10

        dp.delete()
        assert _refresh(cycle) == 0

    def test_activity_link_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        # momentum(5)
        assert _refresh(cycle) == 5

    def test_activity_unlink_triggers_recompute(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        assert _refresh(cycle) == 5

        activity.decision_cycle = None
        activity.save(user=user_a)
        assert _refresh(cycle) == 0

    def test_activity_reassignment_recomputes_both_cycles(
        self, cycle, account, activity, user_a,
    ):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        assert _refresh(cycle) == 5

        cycle_b = _create_second_cycle(account, user_a)
        activity.decision_cycle = cycle_b
        activity.save(user=user_a)

        assert _refresh(cycle) == 0
        assert _refresh(cycle_b) == 5


@pytest.mark.django_db(transaction=True)
class TestSignalTriggeredFullCoverage:
    """Score reaches 100 when all dimensions are filled via signal triggers."""

    def test_incremental_to_100(self, cycle, account, activity, user_a, contact):
        activity.decision_cycle = cycle
        activity.save(user=user_a)

        _create_pain(account, activity, cycle, user_a)
        _create_objective(account, activity, cycle, user_a)
        _create_impact(account, activity, cycle, user_a)
        _create_blocker(account, activity, cycle, user_a)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.DECISION_MAKER, contact=contact)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.CHAMPION, contact=contact)
        _create_deal_product(cycle, user_a)

        assert _refresh(cycle) == 100


@pytest.mark.django_db(transaction=True)
class TestNoRecomputeWithoutCycle:
    """Signals on models not linked to a cycle should not error."""

    def test_activity_without_cycle_no_error(self, account, activity, user_a):
        activity.decision_cycle = None
        activity.save(user=user_a)
