# backend/tests/ai_pipelines/test_people_context.py
"""
People stage (UX Activity — People S1): context layer + single-department
resolver.

  * build_context_layer(activity, 'people') is accepted and carries the
    People taxonomy: the 7 PeopleRole codes, the SIGNAL InfluenceLevel codes
    (never the contacts.InfluenceLevel faux-ami: GATEKEEPER / UNKNOWN), and the
    StandardDepartment vocabulary.
  * The "already identified in this deal" block lists the non-REJECTED
    PeopleSignals of the activity's decision cycle (participant reference when
    the person is a participant); empty without a decision cycle.
  * The other stages' context is untouched by People data.
  * resolve_person_department: exact / unambiguous-word match, General
    Management KEPT, ambiguous word -> None.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    build_context_layer,
)
from app_modules.signals.constants import (
    InfluenceLevel,
    PeopleRole,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import PeopleSignal

from tests.signals.conftest import decision_cycle  # noqa: F401


pytestmark = pytest.mark.django_db

_IDENTIFIED_HEADER = 'PEOPLE ALREADY IDENTIFIED IN THIS DEAL'

_OTHER_STAGES = (
    'pain_impact', 'pain', 'objective', 'impact', 'techstack', 'blocker',
    'constraint', 'competitor',
)


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _attach_cycle(activity, cycle):
    from app_modules.activities.models import Activity
    Activity.objects.filter(id=activity.id).update(decision_cycle=cycle)
    activity.refresh_from_db()
    return activity


def _mk_people(activity, user, *, role, status=SignalStatus.PENDING,
               full_name='', contact=None, department=None, cycle=None):
    signal = PeopleSignal(
        account=activity.account,
        source_activity=activity,
        decision_cycle=cycle,
        role=role,
        full_name=full_name,
        target_contact=contact,
        target_department=department,
        # LLM-sourced signals must be created PENDING (BaseSignal.save guard);
        # other statuses are seeded as MANUAL rows.
        source=(SignalSource.LLM_EXTRACTED if status == SignalStatus.PENDING
                else SignalSource.MANUAL),
        status=status,
    )
    signal.save(user=user, client_id=activity.client_id)
    return signal


# =============================================================================
# STAGE ACCEPTED + TAXONOMY
# =============================================================================

class TestPeopleTaxonomy:

    def test_people_stage_is_accepted(self, activity):
        context = build_context_layer(activity, 'people')
        assert 'SESSION CONTEXT' in context

    def test_all_people_roles_listed(self, activity):
        context = build_context_layer(activity, 'people')
        for code in PeopleRole.values:
            assert f'"{code}"' in context

    def test_signal_influence_levels_listed_not_contact_faux_ami(self, activity):
        context = build_context_layer(activity, 'people')
        for code in InfluenceLevel.values:
            assert f'"{code}"' in context
        # contacts.InfluenceLevel values that are NOT signal influence levels.
        assert 'GATEKEEPER' not in context
        assert 'UNKNOWN' not in context

    def test_department_vocabulary_listed_general_management_included(self, activity):
        context = build_context_layer(activity, 'people')
        assert '"Finance"' in context
        assert '"General Management"' in context

    def test_influence_and_department_may_be_null(self, activity):
        context = build_context_layer(activity, 'people')
        assert 'MAY be null' in context


# =============================================================================
# ALREADY IDENTIFIED IN THIS DEAL
# =============================================================================

class TestIdentifiedPeopleBlock:

    def test_no_decision_cycle_no_block(self, activity, user_a):
        _mk_people(activity, user_a, role=PeopleRole.CHAMPION, full_name='Marc Dubois')
        context = build_context_layer(activity, 'people')
        assert _IDENTIFIED_HEADER not in context

    def test_cycle_without_people_no_block(self, activity, decision_cycle):  # noqa: F811
        _attach_cycle(activity, decision_cycle)
        context = build_context_layer(activity, 'people')
        assert _IDENTIFIED_HEADER not in context

    def test_pending_and_validated_listed_rejected_excluded(
        self, activity, user_a, decision_cycle,  # noqa: F811
    ):
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.ECONOMIC_BUYER,
            full_name='Marc Dubois', department=_dept('Finance'),
            cycle=decision_cycle,
        )
        _mk_people(
            activity, user_a, role=PeopleRole.CHAMPION, full_name='Lea Martin',
            status=SignalStatus.VALIDATED, cycle=decision_cycle,
        )
        rejected = _mk_people(
            activity, user_a, role=PeopleRole.BLOCKER, full_name='Paul Rejet',
            cycle=decision_cycle,
        )
        # MANUAL create forces VALIDATED: reach REJECTED by a direct update.
        PeopleSignal.objects.filter(id=rejected.id).update(status=SignalStatus.REJECTED)

        context = build_context_layer(activity, 'people')

        assert _IDENTIFIED_HEADER in context
        assert '- Marc Dubois — role ECONOMIC_BUYER, department Finance' in context
        assert '- Lea Martin — role CHAMPION' in context
        assert 'Paul Rejet' not in context

    def test_participant_listed_with_its_reference_and_contact_name(
        self, activity, user_a, decision_cycle, contact, contact_extra,  # noqa: F811
    ):
        # Doe = P1, Smith = P2 (last_name order).
        activity.contacts.add(contact, contact_extra)
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.DECISION_MAKER,
            contact=contact_extra, cycle=decision_cycle,
        )

        context = build_context_layer(activity, 'people')

        # RGPD: the contact's FIRST name only (the session-block rule).
        assert '- P2 — John — role DECISION_MAKER' in context
        assert 'Smith' not in context

    def test_contact_first_name_only_even_when_full_name_stored(
        self, activity, user_a, decision_cycle, contact_extra,  # noqa: F811
    ):
        # The S1 builder stores full_name = contact first + last name; the
        # block must still send the first name only (non-participant here).
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.ECONOMIC_BUYER,
            contact=contact_extra, full_name='John Smith', cycle=decision_cycle,
        )

        context = build_context_layer(activity, 'people')

        assert '- John — role ECONOMIC_BUYER' in context
        assert 'Smith' not in context

    def test_cited_person_without_contact_keeps_stated_name(
        self, activity, user_a, decision_cycle,  # noqa: F811
    ):
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.CHAMPION,
            full_name='Marc Dubois', cycle=decision_cycle,
        )

        context = build_context_layer(activity, 'people')

        assert '- Marc Dubois — role CHAMPION' in context

    def test_unnamed_person_listed_with_role_and_department(
        self, activity, user_a, decision_cycle,  # noqa: F811
    ):
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.ECONOMIC_BUYER,
            department=_dept('Finance'), cycle=decision_cycle,
        )

        context = build_context_layer(activity, 'people')

        assert '- Unnamed person — role ECONOMIC_BUYER, department Finance' in context

    def test_other_cycle_people_not_listed(
        self, activity, account, user_a, decision_cycle,  # noqa: F811
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
        other.save(user=user_a, client_id=account.client_id)

        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.CHAMPION, full_name='Elsewhere Person',
            cycle=other,
        )

        context = build_context_layer(activity, 'people')

        assert 'Elsewhere Person' not in context


# =============================================================================
# OTHER STAGES UNTOUCHED
# =============================================================================

class TestOtherStagesUntouched:

    @pytest.mark.parametrize('stage', _OTHER_STAGES)
    def test_other_stage_context_unchanged_by_people_data(
        self, activity, user_a, decision_cycle, stage,  # noqa: F811
    ):
        _attach_cycle(activity, decision_cycle)
        before = build_context_layer(activity, stage)

        _mk_people(
            activity, user_a, role=PeopleRole.ECONOMIC_BUYER,
            full_name='Marc Dubois', cycle=decision_cycle,
        )
        after = build_context_layer(activity, stage)

        assert after == before
        assert _IDENTIFIED_HEADER not in after
        assert 'ECONOMIC_BUYER' not in after


# =============================================================================
# SINGLE-DEPARTMENT RESOLVER
# =============================================================================

def resolve_person_department(raw):
    # Imported at call time so a missing resolver fails per test, not at
    # collection.
    from app_modules.ai_pipelines.services.transcript_signal_extractor import (
        resolve_person_department as resolver,
    )
    return resolver(raw)


class TestResolvePersonDepartment:

    @pytest.fixture(autouse=True)
    def _departments(self, db):
        for name in (
            'Finance', 'General Management', 'Product Management',
            'Security & Risk Management', 'Customer Support',
        ):
            _dept(name)

    def test_exact_name_resolves(self):
        assert resolve_person_department('Finance').name == 'Finance'

    def test_exact_name_is_case_insensitive(self):
        assert resolve_person_department('  finance ').name == 'Finance'

    def test_general_management_is_kept(self):
        assert resolve_person_department('General Management').name == 'General Management'

    def test_unambiguous_word_resolves(self):
        assert resolve_person_department('support').name == 'Customer Support'

    def test_ambiguous_word_is_none(self):
        # "management" is in General / Product / Security & Risk Management.
        assert resolve_person_department('management') is None

    @pytest.mark.parametrize('raw', [None, '', '   ', 42, 'Martians'])
    def test_missing_or_unknown_is_none(self, raw):
        assert resolve_person_department(raw) is None
