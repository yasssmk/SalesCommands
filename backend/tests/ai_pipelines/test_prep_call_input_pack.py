# tests/ai_pipelines/test_prep_call_input_pack.py
"""
Tests for PrepInputPackAssembler.build().

Covers robustness scenarios: full data, no decision cycle, no
DealHealthSnapshot, no target contact.
"""

import pytest

from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
    five_steps,
)

from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
    PrepInputPackAssembler,
)


@pytest.fixture
def activity_with_cycle(db, account, cycle, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title='Demo call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        decision_cycle=cycle,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def activity_no_cycle(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title='Standalone call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        decision_cycle=None,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def deal_health_snapshot(db, cycle, user_a):
    from app_modules.decision_cycles.models import DealHealthSnapshot

    snap = DealHealthSnapshot(
        decision_cycle=cycle,
        diagnostic={
            'global_reading': 'Problem recognized but urgency unproven.',
            'dimensions': [
                {'key': 'problem_recognized', 'status': 'confirmed'},
                {'key': 'felt_pain', 'status': 'missing_evidence'},
                {'key': 'impact_understood', 'status': 'unclear'},
                {'key': 'desired_gain', 'status': 'suggested'},
                {'key': 'urgency', 'status': 'missing_evidence'},
                {'key': 'willingness_to_act', 'status': 'unclear'},
                {'key': 'solution_trust', 'status': 'suggested'},
            ],
        },
    )
    snap.save(user=user_a, client_id=cycle.client_id)
    return snap


EXPECTED_TOP_KEYS = {
    'prep_context',
    'maturity_snapshot',
    'levers',
    'stakeholder_focus',
    'discovery_gaps',
    'competitive_context',
    'evidence_scope',
    'brief_mode',
}


@pytest.mark.django_db
class TestFullData:

    def test_build_returns_complete_pack(
        self, activity_with_cycle, contact, deal_health_snapshot,
    ):
        pack = PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=contact,
            brief_mode='CONVICTION',
        )

        assert set(pack.keys()) == EXPECTED_TOP_KEYS
        assert pack['brief_mode'] == 'CONVICTION'
        assert pack['prep_context']['decision_cycle_id'] is not None
        assert pack['maturity_snapshot'] is not None
        assert pack['maturity_snapshot']['global_reading'] != ''
        assert len(pack['maturity_snapshot']['dimensions']) == 7
        assert pack['stakeholder_focus'] is not None
        assert pack['stakeholder_focus']['contact_id'] == str(contact.id)


@pytest.mark.django_db
class TestWithoutDecisionCycle:

    def test_build_skips_step_expectations(self, activity_no_cycle):
        pack = PrepInputPackAssembler().build(
            activity=activity_no_cycle,
            target_contact=None,
            brief_mode='DISCOVERY',
        )

        assert set(pack.keys()) == EXPECTED_TOP_KEYS
        ctx = pack['prep_context']
        assert ctx['decision_cycle_id'] is None
        assert ctx['current_step'] is None
        assert ctx['step_expectations'] == {'goal': '', 'criterias': []}
        assert pack['maturity_snapshot'] is None
        assert pack['discovery_gaps'] == []


@pytest.mark.django_db
class TestWithoutDealHealthSnapshot:

    def test_build_returns_none_maturity(self, activity_with_cycle):
        pack = PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=None,
            brief_mode='DISCOVERY',
        )

        assert pack['maturity_snapshot'] is None
        assert pack['discovery_gaps'] == []


@pytest.mark.django_db
class TestWithoutTargetContact:

    def test_build_returns_none_stakeholder_focus(
        self, activity_with_cycle, deal_health_snapshot,
    ):
        pack = PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=None,
            brief_mode='CONVICTION',
        )

        assert pack['stakeholder_focus'] is None
