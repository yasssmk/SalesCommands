# tests/decision_cycles/test_people_consolidation_service.py
"""
Tests for PeopleConsolidationService.

Signals are created directly via ORM (PeopleSignal is not yet in
SignalManager.model_map). decision_cycle and status are set
explicitly on each signal instance.
"""

import pytest

from app_modules.decision_cycles.services.people_consolidation_service import (
    PeopleConsolidationService,
)
from app_modules.signals.constants import PeopleRole, SignalStatus


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _create_people_signal(account, activity, cycle, user, role, contact=None, dept=None):
    from app_modules.signals.models import PeopleSignal
    sig = PeopleSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        role=role,
        target_contact=contact,
        target_department=dept,
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _link_activity_to_cycle(activity, cycle, user):
    """Set decision_cycle on an activity and save."""
    activity.decision_cycle = cycle
    activity.save(user=user)


def _add_contact_to_activity(activity, contact):
    """Add a contact to the activity M2M."""
    activity.contacts.add(contact)


# =============================================================================
# TESTS — EMPTY CYCLE
# =============================================================================

class TestEmptyCycle:

    def test_empty_cycle_returns_empty_lists(self, cycle):
        service = PeopleConsolidationService()
        result = service.consolidate(cycle)
        assert result == {'qualified': [], 'unqualified': []}


# =============================================================================
# TESTS — QUALIFIED
# =============================================================================

class TestQualified:

    def test_validated_people_signal_appears_in_qualified(
        self, cycle, account, activity, user_a, contact,
    ):
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)
        _create_people_signal(
            account, activity, cycle, user_a,
            role=PeopleRole.CHAMPION, contact=contact,
        )

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 1
        q = result['qualified'][0]
        assert q['role'] == PeopleRole.CHAMPION
        assert q['target_contact']['id'] == str(contact.id)

    def test_pending_signal_excluded_from_qualified(
        self, cycle, account, activity, user_a, contact,
    ):
        from app_modules.signals.models import PeopleSignal
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)
        sig = PeopleSignal(
            account=account,
            source_activity=activity,
            decision_cycle=cycle,
            role=PeopleRole.CHAMPION,
            target_contact=contact,
            source='LLM_EXTRACTED',
            status=SignalStatus.PENDING,
        )
        sig.save(user=user_a, client_id=account.client_id)

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 0

    def test_department_only_signal(
        self, cycle, account, activity, user_a,
    ):
        from app_modules.core_modules.models import StandardDepartment
        dept = StandardDepartment.objects.first()

        _link_activity_to_cycle(activity, cycle, user_a)
        _create_people_signal(
            account, activity, cycle, user_a,
            role=PeopleRole.ECONOMIC_BUYER, dept=dept,
        )

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 1
        assert result['qualified'][0]['target_contact'] is None
        assert result['qualified'][0]['target_department'] is not None


# =============================================================================
# TESTS — UNQUALIFIED
# =============================================================================

class TestUnqualified:

    def test_contact_in_activity_without_signal_is_unqualified(
        self, cycle, account, activity, user_a, contact,
    ):
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 0
        assert len(result['unqualified']) == 1
        assert result['unqualified'][0]['contact']['id'] == str(contact.id)

    def test_contact_in_step_without_signal_is_unqualified(
        self, cycle, five_steps, user_a, contact,
    ):
        from app_modules.decision_cycles.models import DecisionStepContact
        step = five_steps[0]
        DecisionStepContact.objects.create(
            step=step, contact=contact, client_id=cycle.client_id,
        )

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['unqualified']) == 1
        assert result['unqualified'][0]['contact']['id'] == str(contact.id)

    def test_qualified_contact_not_in_unqualified(
        self, cycle, account, activity, user_a, contact,
    ):
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)
        _create_people_signal(
            account, activity, cycle, user_a,
            role=PeopleRole.CHAMPION, contact=contact,
        )

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 1
        assert len(result['unqualified']) == 0


# =============================================================================
# TESTS — MIXED
# =============================================================================

class TestMixed:

    def test_two_contacts_one_qualified_one_not(
        self, cycle, account, activity, user_a, contact, contact_extra,
    ):
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)
        _add_contact_to_activity(activity, contact_extra)

        _create_people_signal(
            account, activity, cycle, user_a,
            role=PeopleRole.CHAMPION, contact=contact,
        )

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['qualified']) == 1
        assert len(result['unqualified']) == 1
        assert result['unqualified'][0]['contact']['id'] == str(contact_extra.id)

    def test_activity_count_for_unqualified(
        self, cycle, account, activity, user_a, contact,
        completed_activity_on_step, five_steps,
    ):
        _link_activity_to_cycle(activity, cycle, user_a)
        _add_contact_to_activity(activity, contact)

        act2 = completed_activity_on_step(five_steps[0])
        act2.contacts.add(contact)

        result = PeopleConsolidationService().consolidate(cycle)
        assert len(result['unqualified']) == 1
        assert result['unqualified'][0]['activity_count'] == 2
