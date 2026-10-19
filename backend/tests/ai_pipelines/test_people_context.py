# backend/tests/ai_pipelines/test_people_context.py
"""
People stage (UX Activity — People S1): context layer + single-department
resolver.

  * build_context_layer(activity, 'people') is accepted and carries the
    People taxonomy: the 7 PeopleRole codes, the SIGNAL InfluenceLevel codes
    (never the contacts.InfluenceLevel faux-ami: GATEKEEPER / UNKNOWN), and the
    StandardDepartment vocabulary.
  * NO list of persons already known in the deal (PO rule, fix
    people-no-cross-activity-filter P2): each activity creates its signals,
    the grouping per person is the DC cluster's job.
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

# Marker of the removed "persons already known in the deal" block (P2),
# assembled from its words so the removed wording appears nowhere in backend/.
_REMOVED_BLOCK_MARKER = ' '.join(('ALREADY', 'IDENTIFIED'))

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
# NO KNOWN-PEOPLE LIST (P2) — the people known in the deal are NOT sent
# =============================================================================

class TestNoKnownPeopleList:

    def test_people_known_in_the_deal_are_not_listed_in_the_context(
        self, activity, user_a, decision_cycle,  # noqa: F811
    ):
        _attach_cycle(activity, decision_cycle)
        _mk_people(
            activity, user_a, role=PeopleRole.ECONOMIC_BUYER,
            full_name='Marc Dupont', department=_dept('Finance'),
            cycle=decision_cycle,
        )
        _mk_people(
            activity, user_a, role=PeopleRole.CHAMPION, full_name='Lea Martin',
            status=SignalStatus.VALIDATED, cycle=decision_cycle,
        )

        context = build_context_layer(activity, 'people')

        assert _REMOVED_BLOCK_MARKER not in context
        assert 'Dupont' not in context
        assert 'Lea Martin' not in context


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
        assert _REMOVED_BLOCK_MARKER not in after
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
