# backend/tests/ai_pipelines/test_pipeline_constraint_stage.py
"""
Constraint-stage integration tests for QualificationSignalsPipeline
(Constraint sprint, sub-step 2 -- EXTRACTION).

Covers the Constraint stage end-to-end through the pipeline:

  * LLM JSON is parsed, safety-filtered, and persisted as a
    ConstraintSignal row in PENDING status: summary + nature + rigidity +
    target_department (scope), source=LLM_EXTRACTED.
  * nature is validated against ConstraintNature -- an out-of-list value
    DROPS the signal (never coerced).
  * rigidity: an invalid/missing emission folds to FIRM.
  * scope: department-only, resolved by the SHARED resolver; a named
    department resolves to the FK, BUSINESS / unresolved -> None. No
    scope_level column on the model.
  * canonical_key stays None (detached from what x dimension, sub-step 1);
    what/dimension are never set.
  * Non-confusion: a pain / blocker in the same run route to their own
    models -- the constraint stage only ever emits constraints.
  * is_integration re-routing: a tech mention that would have set
    is_integration=true no longer does (the flag is retired); the required
    integration is captured as a TECHNICAL constraint instead.

Prompt-content assertions (mutation-sensitive) live at the bottom.
"""

import pytest

from app_modules.signals.constants import (
    ConstraintNature,
    Rigidity,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import (
    BlockerSignal,
    ConstraintSignal,
    TechStackSignal,
)


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

@pytest.fixture
def it_department(db):
    """Ensure the 'IT' StandardDepartment row exists for FK resolution."""
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='IT')
    return dept


def _constraint_reply(objs):
    import json
    return json.dumps({'signals': objs})


def _constraint_obj(*, summary, nature, rigidity='FIRM',
                    target_departments=None,
                    source_quote='we require it', confidence=0.9,
                    is_inferred=False):
    # sub-step 1c: scope is the multi-department target_departments LIST (no
    # scope_level, no single FK).
    return {
        'summary': summary,
        'nature': nature,
        'rigidity': rigidity,
        'target_departments': target_departments or [],
        'source_quote': source_quote,
        'confidence': confidence,
        'is_inferred': is_inferred,
    }


def _run(account, activity, user_a, transcript='A transcript about Acme.'):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    return QualificationSignalsPipeline().run(
        transcript=transcript,
        activity=activity,
        user=user_a,
        client_id=account.client_id,
    )


# =============================================================================
# PERSISTENCE
# =============================================================================

class TestConstraintStagePersistence:

    def test_technical_constraint_with_department_resolves_scope(
        self, account, activity, user_a, it_department,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Must integrate with the SAP ERP',
                nature='TECHNICAL',
                rigidity='FIRM',
                target_departments=['IT'],
                source_quote='it has to plug into our SAP instance',
            )]),
        }

        result = _run(account, activity, user_a)

        constraints = result['signals_by_stage']['constraint']
        assert len(constraints) == 1
        sig = constraints[0]
        assert isinstance(sig, ConstraintSignal)
        assert sig.nature == ConstraintNature.TECHNICAL
        assert sig.rigidity == Rigidity.FIRM
        # sub-step 1c: scope is the multi-department M2M (FK no longer written).
        assert set(sig.target_departments.values_list('id', flat=True)) == {it_department.id}
        assert sig.target_department_id is None
        assert sig.status == SignalStatus.PENDING
        assert sig.source == SignalSource.LLM_EXTRACTED
        assert sig.source_activity_id == activity.id
        # Detached: no canonical_key, no what/dimension.
        assert sig.canonical_key is None
        assert sig.what is None
        assert sig.dimension is None

    def test_constraint_without_department_is_business_scoped(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='GDPR compliance is mandatory',
                nature='CONTRACTUAL',
                target_departments=[],
                source_quote='GDPR compliance is non-negotiable',
            )]),
        }

        constraints = _run(account, activity, user_a)['signals_by_stage']['constraint']
        assert len(constraints) == 1
        assert constraints[0].nature == ConstraintNature.CONTRACTUAL
        # No department named -> empty M2M (FK never written since sub-step 1c).
        assert list(constraints[0].target_departments.all()) == []
        assert constraints[0].target_department_id is None

    def test_functional_constraint_nature(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Needs real-time reporting dashboards',
                nature='FUNCTIONAL',
                source_quote='we need real-time dashboards',
            )]),
        }
        constraints = _run(account, activity, user_a)['signals_by_stage']['constraint']
        assert len(constraints) == 1
        assert constraints[0].nature == ConstraintNature.FUNCTIONAL

    def test_out_of_taxonomy_nature_is_dropped(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Some requirement with a bad nature',
                nature='NOT_A_REAL_NATURE',
                source_quote='we require something',
            )]),
        }
        result = _run(account, activity, user_a)
        # A bad nature is dropped at the builder -> no ConstraintSignal row.
        assert result['signals_by_stage']['constraint'] == []
        assert ConstraintSignal.objects.count() == 0
        # The stage itself still parsed successfully (0 persisted is not an error).
        sub = next(c for c in result['run'].sub_calls if c['stage'] == 'constraint')
        assert sub['error'] is None

    def test_invalid_rigidity_folds_to_firm(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Requirement with a junk rigidity',
                nature='SECURITY',
                rigidity='SOMETIMES',
                source_quote='data must be encrypted at rest',
            )]),
        }
        constraints = _run(account, activity, user_a)['signals_by_stage']['constraint']
        assert len(constraints) == 1
        assert constraints[0].rigidity == Rigidity.FIRM

    def test_flexible_rigidity_preserved(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Ideally under 50k a year',
                nature='FINANCIAL',
                rigidity='FLEXIBLE',
                source_quote='ideally the price stays under 50k',
            )]),
        }
        constraints = _run(account, activity, user_a)['signals_by_stage']['constraint']
        assert constraints[0].rigidity == Rigidity.FLEXIBLE


# =============================================================================
# NON-CONFUSION -- a pain / blocker does NOT become a constraint
# =============================================================================

class TestConstraintNonConfusion:
    """
    Each stage routes to its OWN model. A blocker reply produces a
    BlockerSignal, a constraint reply produces a ConstraintSignal; they do
    not cross over, even when both are present in the same run.
    """

    def test_blocker_and_constraint_route_to_distinct_models(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'blocker': (
                '{"signals": [{'
                '"summary": "No budget approved before Q3", '
                '"source_quote": "I can\'t get budget signed off before Q3", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
            'constraint': _constraint_reply([_constraint_obj(
                summary='SSO is required',
                nature='TECHNICAL',
                source_quote='we require SSO',
            )]),
        }

        result = _run(account, activity, user_a)

        # The blocker is a BlockerSignal, NOT a constraint.
        assert len(result['signals_by_stage']['blocker']) == 1
        assert isinstance(result['signals_by_stage']['blocker'][0], BlockerSignal)

        # The constraint is a ConstraintSignal, NOT a blocker.
        assert len(result['signals_by_stage']['constraint']) == 1
        assert isinstance(
            result['signals_by_stage']['constraint'][0], ConstraintSignal
        )

        # No cross-contamination in the DB.
        assert BlockerSignal.objects.count() == 1
        assert ConstraintSignal.objects.count() == 1

    def test_constraint_stage_empty_when_only_a_pain_is_present(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        # A run whose only signal is a pain must yield ZERO constraints:
        # the constraint stage returns the default empty reply.
        fake_provider.replies = {
            'pain_impact': (
                '{"pains": [{'
                '"what": "OPS", "dimension": "TIME", '
                '"scope_level": "BUSINESS", "target_department": null, '
                '"summary": "Reporting takes 3 weeks", '
                '"source_quote": "Our reporting takes 3 weeks", '
                '"confidence": 0.9, "is_inferred": false}], "impacts": []}'
            ),
        }
        result = _run(account, activity, user_a)
        assert len(result['signals_by_stage']['pain']) == 1
        assert result['signals_by_stage']['constraint'] == []
        assert ConstraintSignal.objects.count() == 0


# =============================================================================
# is_integration RE-ROUTING
# =============================================================================

class TestIsIntegrationReRouting:
    """
    A required integration is no longer a tech boolean: the tech stage no
    longer sets is_integration, and the requirement is captured as a
    TECHNICAL constraint.
    """

    def test_tech_no_longer_sets_is_integration_and_constraint_captures_it(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            # A tech mention that, under the old contract, would have set
            # is_integration=true. The extractor now ignores that key.
            'techstack': (
                '{"signals": [{'
                '"tech_name": "SAP", '
                '"is_competitor": false, '
                '"is_integration": true, '
                '"is_to_replace": false, '
                '"usage_scope": "COMPANY", '
                '"source_quote": "our product must connect to SAP", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
            # The same requirement, captured where it now belongs.
            'constraint': _constraint_reply([_constraint_obj(
                summary='The solution must integrate with SAP',
                nature='TECHNICAL',
                source_quote='our product must connect to SAP',
            )]),
        }

        result = _run(account, activity, user_a)

        # Tech signal persisted; is_integration is no longer a field (dropped
        # in 9c) so an emitted value cannot land on the tech row.
        techs = result['signals_by_stage']['techstack']
        assert len(techs) == 1

        # The integration requirement lives as a TECHNICAL constraint.
        constraints = result['signals_by_stage']['constraint']
        assert len(constraints) == 1
        assert constraints[0].nature == ConstraintNature.TECHNICAL


# =============================================================================
# PROMPT CONTENT (mutation-sensitive)
# =============================================================================

class TestConstraintPromptContent:
    """
    The rules the LLM actually reads live in the prompt, not the docstring.
    These assertions fail loudly if a rule is deleted.
    """

    def _constraint_user_prompt(self, activity):
        from app_modules.ai_pipelines.prompts.transcript_signals.constraint_v1 import (
            build_constraint_request,
        )
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            build_context_layer,
        )
        req = build_constraint_request('A TRANSCRIPT BODY')
        ctx = build_context_layer(activity, target_stage='constraint')
        return req, ctx

    def test_prompt_has_functional_vs_technical_boundary(self, activity):
        req, _ = self._constraint_user_prompt(activity)
        assert 'FUNCTIONAL vs TECHNICAL' in req
        # The boundary rule: FUNCTIONAL is what it does, TECHNICAL is how it
        # connects.
        assert 'FUNCTIONAL is WHAT the product does' in req
        assert 'TECHNICAL is HOW it connects' in req

    def test_prompt_lists_all_six_natures(self, activity):
        req, _ = self._constraint_user_prompt(activity)
        for nature in ('FUNCTIONAL', 'TECHNICAL', 'FINANCIAL',
                       'CONTRACTUAL', 'OPERATIONAL', 'SECURITY'):
            assert nature in req

    def test_prompt_has_subject_not_speaker_scope_rule(self, activity):
        req, _ = self._constraint_user_prompt(activity)
        assert 'the SUBJECT decides the scope, never the speaker' in req
        # BUSINESS is the safe default -- never invent a department.
        assert 'NEVER invent a department' in req

    def test_prompt_distinguishes_constraint_from_pain_and_blocker(self, activity):
        req, _ = self._constraint_user_prompt(activity)
        assert 'Constraint vs. Pain' in req
        assert 'Constraint vs. Blocker' in req

    def test_context_has_nature_list_and_departments_but_not_what_dimension(self, activity):
        _, ctx = self._constraint_user_prompt(activity)
        # nature list + the multi-department target_departments vocab present
        # (sub-step 1c: a LIST of names, no scope_level).
        assert 'nature' in ctx
        assert 'target_departments' in ctx
        assert 'scope_level' not in ctx
        # The business what x dimension block must NOT be injected for
        # constraint (it is detached).
        assert 'DOMAIN vs DIMENSION' not in ctx
