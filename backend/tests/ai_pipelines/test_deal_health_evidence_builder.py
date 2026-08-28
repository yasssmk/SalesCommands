# tests/ai_pipelines/test_deal_health_evidence_builder.py
"""
Tests for DealHealthEvidenceBuilder.

Validates that the evidence pack shape matches the contract consumed
by the deal-health prompt layers. Exercises each signal type, cycle
context, readiness, people consolidation, and previous snapshot.
"""

import pytest

from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
    DealHealthEvidenceBuilder,
)
from app_modules.signals.constants import (
    ConstraintNature,
    PeopleRole,
    Rigidity,
    SignalSource,
    SignalStatus,
    SignalWhat,
    SignalDimension,
    ScopeLevel,
)


# =========================================================================
# FIXTURES — reuse cycle + five_steps from decision_cycles conftest
# =========================================================================

# Re-export all shared fixtures so pytest discovers them.
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    cache_invalidation_calls,
    cycle,
    five_steps,
    product_catalog_entry,
    deal_product,
    deal_health_snapshot,
)


@pytest.fixture
def builder():
    return DealHealthEvidenceBuilder()


# =========================================================================
# SIGNAL FACTORY HELPERS
# =========================================================================

def _create_pain(dc, user, client_id):
    from app_modules.signals.models import PainSignal

    sig = PainSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.DEPARTMENT,
        summary='Manual reporting takes 10h/week',
        source_quote='We spend 10 hours every week on manual reports',
    )
    sig.save(user=user, client_id=client_id)
    return sig


def _create_objective(dc, user, client_id):
    from app_modules.signals.models import ObjectiveSignal

    sig = ObjectiveSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.BUSINESS,
        summary='Reduce reporting time by 50%',
        source_quote='We want to cut reporting time in half',
    )
    sig.save(user=user, client_id=client_id)
    return sig


def _create_blocker(dc, user, client_id, contact=None):
    from app_modules.signals.models import BlockerSignal

    sig = BlockerSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        summary='No budget allocated',
        source_quote='We have no budget for this',
        contact=contact,
    )
    sig.save(user=user, client_id=client_id)
    return sig


def _create_constraint(dc, user, client_id):
    from app_modules.signals.models import ConstraintSignal

    sig = ConstraintSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        nature=ConstraintNature.FINANCIAL,
        summary='ROI must exceed 20% within 18 months',
        source_quote='We need at least 20% ROI in 18 months',
        rigidity=Rigidity.FIRM,
    )
    sig.save(user=user, client_id=client_id)
    return sig


def _create_people_signal(dc, user, client_id, contact=None):
    from app_modules.signals.models import PeopleSignal

    sig = PeopleSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        role=PeopleRole.CHAMPION,
        target_contact=contact,
    )
    sig.save(user=user, client_id=client_id)
    return sig


# =========================================================================
# TESTS
# =========================================================================

@pytest.mark.django_db
class TestEvidenceBuilderPackShape:
    """Verify the top-level pack structure."""

    def test_empty_cycle_returns_valid_shape(self, builder, cycle):
        pack = builder.build(cycle)

        assert 'cycle' in pack
        assert 'readiness' in pack
        assert 'people' in pack
        assert 'signals' in pack
        assert 'previous_snapshot' in pack

        assert pack['cycle']['name'] == 'Test Cycle'
        assert pack['previous_snapshot'] is None

    def test_signals_keys_present(self, builder, cycle):
        pack = builder.build(cycle)
        expected_types = {
            'pain', 'objective', 'impact', 'techstack',
            'blocker', 'constraint', 'people',
        }
        assert set(pack['signals'].keys()) == expected_types

    def test_empty_cycle_all_signals_empty(self, builder, cycle):
        pack = builder.build(cycle)
        for sig_type, sig_list in pack['signals'].items():
            assert sig_list == [], f'{sig_type} should be empty'


@pytest.mark.django_db
class TestEvidenceBuilderWithSignals:
    """Verify signals are included when VALIDATED."""

    def test_pain_signal_included(self, builder, cycle, user_a):
        _create_pain(cycle, user_a, cycle.client_id)
        pack = builder.build(cycle)

        assert len(pack['signals']['pain']) == 1
        pain = pack['signals']['pain'][0]
        assert pain['summary'] == 'Manual reporting takes 10h/week'
        assert pain['source_quote'] == 'We spend 10 hours every week on manual reports'
        assert pain['canonical_key'] == 'pain:OPS:TIME'
        assert pain['scope_level'] == ScopeLevel.DEPARTMENT
        assert pain['what'] == SignalWhat.OPS
        assert pain['dimension'] == SignalDimension.TIME

    def test_objective_signal_included(self, builder, cycle, user_a):
        _create_objective(cycle, user_a, cycle.client_id)
        pack = builder.build(cycle)

        assert len(pack['signals']['objective']) == 1
        assert pack['signals']['objective'][0]['summary'] == 'Reduce reporting time by 50%'

    def test_blocker_signal_included(self, builder, cycle, user_a, contact):
        _create_blocker(cycle, user_a, cycle.client_id, contact=contact)
        pack = builder.build(cycle)

        assert len(pack['signals']['blocker']) == 1
        blocker = pack['signals']['blocker'][0]
        assert blocker['summary'] == 'No budget allocated'
        assert blocker['contact_name'] is not None

    def test_constraint_signal_included(self, builder, cycle, user_a):
        _create_constraint(cycle, user_a, cycle.client_id)
        pack = builder.build(cycle)

        assert len(pack['signals']['constraint']) == 1
        constraint = pack['signals']['constraint'][0]
        assert constraint['rigidity'] == Rigidity.FIRM
        assert constraint['nature'] == ConstraintNature.FINANCIAL
        # Detached: canonical_key / what / dimension are no longer in the payload.
        assert 'canonical_key' not in constraint
        assert 'what' not in constraint
        assert 'dimension' not in constraint

    def test_people_signal_included(self, builder, cycle, user_a, contact):
        _create_people_signal(cycle, user_a, cycle.client_id, contact=contact)
        pack = builder.build(cycle)

        assert len(pack['signals']['people']) == 1
        people = pack['signals']['people'][0]
        assert people['role'] == PeopleRole.CHAMPION

    def test_pending_signals_excluded(self, builder, cycle, user_a):
        """Signals not yet VALIDATED must not appear."""
        from app_modules.signals.models import PainSignal

        sig = PainSignal(
            account=cycle.account,
            decision_cycle=cycle,
            source=SignalSource.LLM_EXTRACTED,
            status=SignalStatus.PENDING,
            what=SignalWhat.OPS,
            dimension=SignalDimension.TIME,
            summary='Pending pain',
        )
        sig.save(user=user_a, client_id=cycle.client_id)

        pack = builder.build(cycle)
        assert len(pack['signals']['pain']) == 0


@pytest.mark.django_db
class TestEvidenceBuilderCycleContext:
    """Verify cycle context serialization."""

    def test_current_step_included(self, builder, cycle, five_steps):
        pack = builder.build(cycle)

        step = pack['cycle']['current_step']
        assert step is not None
        assert 'name' in step
        assert 'goal' in step
        assert 'criterias' in step
        assert 'metrics' in step

    def test_products_included(self, builder, cycle, deal_product):
        pack = builder.build(cycle)

        products = pack['cycle']['products']
        assert len(products) == 1
        assert products[0]['name'] == 'Enterprise License'
        assert products[0]['quantity'] == 2


@pytest.mark.django_db
class TestEvidenceBuilderReadiness:
    """Verify readiness score is included."""

    def test_readiness_shape(self, builder, cycle):
        pack = builder.build(cycle)

        readiness = pack['readiness']
        assert 'score' in readiness
        assert 'dimensions' in readiness
        assert isinstance(readiness['score'], int)
        assert isinstance(readiness['dimensions'], list)


@pytest.mark.django_db
class TestEvidenceBuilderPeople:
    """Verify people consolidation shape."""

    def test_people_shape(self, builder, cycle):
        pack = builder.build(cycle)

        people = pack['people']
        assert 'qualified' in people
        assert 'unqualified_count' in people
        assert isinstance(people['qualified'], list)
        assert isinstance(people['unqualified_count'], int)


@pytest.mark.django_db
class TestEvidenceBuilderPreviousSnapshot:
    """Verify previous snapshot inclusion."""

    def test_with_existing_snapshot(self, builder, cycle, deal_health_snapshot):
        pack = builder.build(cycle)

        prev = pack['previous_snapshot']
        assert prev is not None
        assert 'global_reading' in prev
        assert 'snapshot_date' in prev

    def test_without_snapshot(self, builder, cycle):
        pack = builder.build(cycle)
        assert pack['previous_snapshot'] is None
