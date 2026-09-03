# backend/tests/ai_pipelines/test_prompt_scope_guard.py
"""
Scope emission guard -- "when in doubt -> BUSINESS" (Constraint sprint,
finition 1/3).

THE PROBLEM (proven at smoke): the LLM OVER-ATTRIBUTES a department. It
tagged a company-wide requirement to a department off a technical
theme-word ("chiffrement E2E" -> IT) or off the speaker's own department
("accompagnement au changement" -> Operations on a Finance-only call),
with no department actually DESIGNATED as the subject.

THE FIX is on the EMISSION side: the shared scope block
(context._scope_taxonomy_lines, injected into the CANONICAL TAXONOMY of
the pain / objective / impact / constraint stages) raises the DEPARTMENT
threshold -- emit DEPARTMENT only when a department is EXPLICITLY NAMED or
unambiguously DESIGNATED as the owning subject; when in doubt, BUSINESS --
with an explicit ANTI-OVER-CORRECTION clause so a genuinely designated
department is NOT folded back to BUSINESS.

What these tests CAN prove (deterministically):
  * the doubt guard + theme-word rule + anti-over-correction clause + the
    edge-case few-shot pair are present in the SHARED block, and therefore
    in EVERY stage that injects it (mutation-sensitive: deleting any of
    them re-reddens a test);
  * NON-REGRESSION: the sibling prompts' LEGITIMATE department few-shots
    (pain -> Marketing, objective -> Sales, pain_impact -> Marketing --
    each an EXPLICITLY NAMED department) are unchanged. The guard raises
    the threshold; it does NOT fold legitimate designations to BUSINESS.

What they CANNOT prove: that the live LLM stops over-attributing --
FakeProvider returns canned replies regardless of the prompt. That is
validated by the PO re-smoke on a real transcript. The resolver-side
behaviour (subject-not-speaker, folds) is covered by
test_pipeline_scope_extraction.py.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    _build_taxonomy_block,
    _scope_taxonomy_lines,
)


pytestmark = pytest.mark.django_db


# Every stage that injects the shared scope block. Hardening the block must
# reach ALL of them (pain/objective/impact via the merged and split stages).
# Constraint moved to the multi-department target_departments LIST (sub-step
# 1c) and no longer injects the shared scope_level block, so it is excluded.
_STAGES_WITH_SCOPE_BLOCK = ('pain_impact', 'pain', 'objective', 'impact')


# =============================================================================
# SHARED BLOCK — the emission guard text
# =============================================================================

class TestSharedScopeGuardText:

    def _shared_block(self):
        return '\n'.join(_scope_taxonomy_lines())

    def test_when_in_doubt_business_guard_present(self):
        # The core doubt guard: on any ambiguity, BUSINESS is the default.
        block = self._shared_block()
        assert 'WHEN IN DOUBT, emit BUSINESS' in block
        assert 'BUSINESS is the safe default' in block

    def test_explicit_designation_threshold_present(self):
        # DEPARTMENT is emitted ONLY on explicit naming / unambiguous
        # designation of the owning subject -- not on a loose "identification".
        block = self._shared_block()
        assert 'Emit DEPARTMENT ONLY when one specific department is '\
               'EXPLICITLY NAMED or unambiguously DESIGNATED' in block

    def test_technical_theme_word_does_not_designate(self):
        # A technical theme-word alone (the "chiffrement -> IT" smoke bug)
        # must NOT justify a department.
        block = self._shared_block()
        assert 'A technical theme-word alone' in block
        assert 'does NOT designate a department' in block

    def test_speaker_never_decides_in_either_direction(self):
        # The speaker's own department must not pull scope to DEPARTMENT
        # (over-attribution) NOR force BUSINESS (over-correction).
        block = self._shared_block()
        assert 'an IT lead stating a company-wide need is still BUSINESS' in block

    def test_anti_over_correction_clause_present(self):
        # The critical non-regression guard, stated IN the prompt: a
        # genuinely designated department stays that department.
        block = self._shared_block()
        assert 'ANTI-OVER-CORRECTION' in block
        assert 'MUST stay that department' in block
        assert 'fold to BUSINESS only what is genuinely undesignated' in block

    def test_edge_case_few_shot_pair_present(self):
        # The pair that TEACHES the threshold: named dept -> DEPARTMENT;
        # bare technical need -> BUSINESS.
        block = self._shared_block()
        # Named-department leg -> IT.
        assert 'the IT department requires integration with their SAP instance' in block
        # Undesignated technical-need leg -> BUSINESS.
        assert 'we need end-to-end encryption' in block
        assert 'target_department=null' in block


# =============================================================================
# WIRING — the guard reaches EVERY stage that injects the shared block
# =============================================================================

class TestGuardReachesEveryStage:
    """
    The hardening lives in ONE shared function; these tests prove it is
    actually rendered into each stage's taxonomy block. Deleting the shared
    call from any stage in _build_taxonomy_block reddens the row for that
    stage.
    """

    @pytest.mark.parametrize('stage', _STAGES_WITH_SCOPE_BLOCK)
    def test_doubt_guard_in_stage_taxonomy(self, stage):
        block = _build_taxonomy_block(stage)
        assert 'WHEN IN DOUBT, emit BUSINESS' in block

    @pytest.mark.parametrize('stage', _STAGES_WITH_SCOPE_BLOCK)
    def test_few_shot_pair_in_stage_taxonomy(self, stage):
        block = _build_taxonomy_block(stage)
        assert 'the IT department requires integration with their SAP instance' in block
        assert 'we need end-to-end encryption' in block

    @pytest.mark.parametrize('stage', _STAGES_WITH_SCOPE_BLOCK)
    def test_anti_over_correction_in_stage_taxonomy(self, stage):
        block = _build_taxonomy_block(stage)
        assert 'ANTI-OVER-CORRECTION' in block

    def test_techstack_stage_has_no_scope_block(self):
        # Sanity: techstack has no scope axis; the guard must NOT leak into it.
        block = _build_taxonomy_block('techstack')
        assert 'WHEN IN DOUBT, emit BUSINESS' not in block


# =============================================================================
# CONSTRAINT PROMPT — the ambiguous SAP few-shot was replaced (PO Option 3)
# =============================================================================

class TestConstraintFewShotReplaced:
    """
    The old few-shot `IT lead: "it has to plug into our SAP instance" -> IT`
    taught the WRONG rule (speaker "IT lead" + technical word "SAP" both
    point to IT). PO decision: replace it with a pair that separates the
    signals -- explicit designation -> IT; bare technical need -> BUSINESS.
    """

    def _constraint_prompt(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.constraint_v1 import (
            build_constraint_request,
        )
        return build_constraint_request('A TRANSCRIPT BODY')

    def test_ambiguous_speaker_led_example_is_gone(self):
        req = self._constraint_prompt()
        # The old wording (speaker "IT lead" leading the attribution) must be gone.
        assert 'IT lead: "it has to plug into our SAP instance"' not in req

    def test_replacement_named_department_leg_present(self):
        req = self._constraint_prompt()
        assert 'The IT department requires integration with their SAP instance' in req
        # sub-step 1c: the department is emitted in the target_departments LIST.
        assert 'target_departments=["IT"]' in req

    def test_replacement_business_leg_present(self):
        req = self._constraint_prompt()
        # Company-wide encryption need -> SECURITY, no department (the smoke
        # bug, corrected): an empty target_departments list.
        assert 'we need end-to-end encryption' in req
        assert 'target_departments=[]' in req


# =============================================================================
# NON-REGRESSION — legitimate department few-shots are UNCHANGED
# =============================================================================

class TestLegitimateDepartmentFewShotsUnchanged:
    """
    THE MOST IMPORTANT CHECK. The guard must not fold LEGITIMATE department
    attributions to BUSINESS. Each sibling prompt already teaches a correct
    DEPARTMENT case with an EXPLICITLY NAMED department -- those examples
    must survive the hardening verbatim.
    """

    def test_pain_marketing_example_intact(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.pain_v1 import (
            build_pain_request,
        )
        req = build_pain_request('A TRANSCRIPT BODY')
        assert 'our marketing team can\'t trust its campaign data' in req
        assert 'target_department = "Marketing"' in req

    def test_objective_sales_example_intact(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (
            build_objective_request,
        )
        req = build_objective_request('A TRANSCRIPT BODY')
        assert 'the sales team wants to cut new-rep ramp time' in req
        assert 'target_department = "Sales"' in req

    def test_pain_impact_marketing_example_intact(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (
            build_pain_impact_request,
        )
        req = build_pain_impact_request('A TRANSCRIPT BODY')
        # sub-step 2c: pain/impact emit the department as a LIST.
        assert 'target_departments=["Marketing"]' in req

    def test_subject_not_speaker_principle_intact(self):
        # The subject-not-speaker framing (the original scope invariant) must
        # remain in the shared block after hardening.
        block = '\n'.join(_scope_taxonomy_lines())
        assert 'the scope is determined by the SUBJECT of the observation' in block
        assert 'NOT by who is speaking' in block
