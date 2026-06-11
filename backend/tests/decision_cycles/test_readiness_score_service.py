# tests/decision_cycles/test_readiness_score_service.py
"""
Tests for ReadinessScoreService.

Signals are created directly via ORM (PeopleSignal / ConstraintSignal
are not yet in SignalManager.model_map). decision_cycle and status are
set explicitly on each signal instance.
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


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS — direct ORM signal creation (bypass SignalManager)
# =============================================================================

def _create_pain(account, activity, cycle, user):
    from app_modules.signals.models import PainSignal
    sig = PainSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Manual reporting takes 10h/week',
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
        summary='Reduce prep time',
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
        summary='Delayed visibility',
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
        summary='Budget owner not identified',
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
        summary='ROI > 20%',
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


# =============================================================================
# TESTS
# =============================================================================

class TestReadinessScoreEmpty:
    """Score should be 0 when cycle has no signals, products, or activities."""

    def test_empty_cycle_score_is_zero(self, cycle):
        service = ReadinessScoreService()
        result = service.calculate(cycle)
        assert result['score'] == 0
        assert all(not d['filled'] for d in result['dimensions'])

    def test_dimensions_count(self, cycle):
        service = ReadinessScoreService()
        result = service.calculate(cycle)
        assert len(result['dimensions']) == 8


class TestReadinessScoreSingleDimension:
    """Each dimension should contribute its weight independently."""

    def test_pain_only(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_pain(account, activity, cycle, user_a)

        result = ReadinessScoreService().calculate(cycle)
        pain_dim = next(d for d in result['dimensions'] if d['name'] == 'pain')
        assert pain_dim['filled'] is True
        # pain(20) + momentum(5) because activity is linked
        assert result['score'] == 25

    def test_decision_maker_via_economic_buyer(self, cycle, account, activity, user_a, contact):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.ECONOMIC_BUYER, contact=contact)

        result = ReadinessScoreService().calculate(cycle)
        dm_dim = next(d for d in result['dimensions'] if d['name'] == 'decision_maker')
        assert dm_dim['filled'] is True

    def test_champion(self, cycle, account, activity, user_a, contact):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_people(account, activity, cycle, user_a,
                       role=PeopleRole.CHAMPION, contact=contact)

        result = ReadinessScoreService().calculate(cycle)
        champ_dim = next(d for d in result['dimensions'] if d['name'] == 'champion')
        assert champ_dim['filled'] is True

    def test_risk_via_blocker(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_blocker(account, activity, cycle, user_a)

        result = ReadinessScoreService().calculate(cycle)
        risk_dim = next(d for d in result['dimensions'] if d['name'] == 'risk')
        assert risk_dim['filled'] is True

    def test_risk_via_constraint(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_constraint(account, activity, cycle, user_a)

        result = ReadinessScoreService().calculate(cycle)
        risk_dim = next(d for d in result['dimensions'] if d['name'] == 'risk')
        assert risk_dim['filled'] is True

    def test_solution(self, cycle, user_a):
        _create_deal_product(cycle, user_a)

        result = ReadinessScoreService().calculate(cycle)
        sol_dim = next(d for d in result['dimensions'] if d['name'] == 'solution')
        assert sol_dim['filled'] is True

    def test_momentum(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)

        result = ReadinessScoreService().calculate(cycle)
        mom_dim = next(d for d in result['dimensions'] if d['name'] == 'momentum')
        assert mom_dim['filled'] is True


class TestReadinessScoreFullCoverage:
    """Score should be 100 when all dimensions are filled."""

    def test_all_dimensions_filled(self, cycle, account, activity, user_a, contact):
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

        result = ReadinessScoreService().calculate(cycle)
        assert result['score'] == 100
        assert all(d['filled'] for d in result['dimensions'])


class TestReadinessScorePendingExcluded:
    """PENDING signals should not count toward readiness."""

    def test_pending_pain_not_counted(self, cycle, account, activity, user_a):
        from app_modules.signals.models import PainSignal
        activity.decision_cycle = cycle
        activity.save(user=user_a)

        sig = PainSignal(
            account=account,
            source_activity=activity,
            decision_cycle=cycle,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Pending pain',
            source='LLM_EXTRACTED',
            status=SignalStatus.PENDING,
        )
        sig.save(user=user_a, client_id=account.client_id)

        result = ReadinessScoreService().calculate(cycle)
        pain_dim = next(d for d in result['dimensions'] if d['name'] == 'pain')
        assert pain_dim['filled'] is False


class TestReadinessScoreCustomWeights:
    """Custom weights should override defaults."""

    def test_custom_weights(self, cycle, account, activity, user_a):
        activity.decision_cycle = cycle
        activity.save(user=user_a)
        _create_pain(account, activity, cycle, user_a)

        custom = {'pain': 100, 'objective': 0, 'impact': 0,
                  'decision_maker': 0, 'champion': 0, 'risk': 0,
                  'solution': 0, 'momentum': 0}
        result = ReadinessScoreService(weights=custom).calculate(cycle)
        assert result['score'] == 100
