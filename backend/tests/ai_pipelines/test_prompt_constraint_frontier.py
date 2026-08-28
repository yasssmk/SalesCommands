# backend/tests/ai_pipelines/test_prompt_constraint_frontier.py
"""
Constraint frontier in the objective / pain_impact prompts (Constraint
sprint, DÉFAUT 2 fix).

A requirement the prospect imposes ON THE SOLUTION ("we need X", "it must
integrate with Y", "budget cap 80k") must be captured by the constraint
stage ONLY -- not ALSO as an objective or a pain/impact. The stages are
independent LLM calls with no cross-stage state, so the only lever is a
prompt-level exclusion boundary added to objective_v1 and pain_impact_v1.

What these tests CAN prove (deterministically):
  * the exclusion boundary text is present in both prompts (mutation-
    sensitive: deleting it re-reddens a test);
  * the boundary carries a non-over-exclusion guard (a genuine objective /
    pain / impact must still be emitted);
  * at the WIRING level, a canned objective + pain + impact + constraint
    each route to their own model -- the frontier prompts did not break the
    stages' handling of real signals.

What they CANNOT prove: that the live LLM stops emitting requirements as
objectives -- FakeProvider returns canned replies regardless of the prompt.
That is validated by the PO re-smoke on a real transcript.
"""

import pytest

from app_modules.signals.constants import ConstraintNature
from app_modules.signals.models import (
    ConstraintSignal,
    ImpactSignal,
    ObjectiveSignal,
    PainSignal,
)


pytestmark = pytest.mark.django_db


# =============================================================================
# PROMPT CONTENT — objective_v1
# =============================================================================

class TestObjectiveConstraintFrontier:

    def _objective_prompt(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (
            build_objective_request,
        )
        return build_objective_request('A TRANSCRIPT BODY')

    def test_has_objective_vs_constraint_boundary(self):
        req = self._objective_prompt()
        assert 'Objective vs. Constraint' in req
        # A requirement on the solution is NOT an objective.
        assert 'REQUIREMENT the prospect imposes ON THE SOLUTION' in req

    def test_boundary_has_requirement_examples(self):
        req = self._objective_prompt()
        assert 'we need real-time reporting' in req
        assert 'it has to integrate with our ERP' in req

    def test_boundary_keeps_real_objectives(self):
        # Non-over-exclusion: a genuine business goal stays an objective.
        req = self._objective_prompt()
        assert 'we want to grow revenue 20% this year' in req
        assert 'do not silently drop a genuine goal' in req


# =============================================================================
# PROMPT CONTENT — pain_impact_v1
# =============================================================================

class TestPainImpactConstraintFrontier:

    def _pain_impact_prompt(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (
            build_pain_impact_request,
        )
        return build_pain_impact_request('A TRANSCRIPT BODY')

    def test_has_pain_impact_vs_constraint_boundary(self):
        req = self._pain_impact_prompt()
        assert 'Pain / Impact vs. Constraint' in req
        assert 'REQUIREMENT the prospect imposes on the solution' in req

    def test_boundary_distinguishes_lived_from_requirement(self):
        req = self._pain_impact_prompt()
        # Lived consequence / difficulty stays pain/impact.
        assert 'we lose 40k a quarter because of X' in req
        assert 'our teams are overwhelmed' in req
        # Requirement -> constraint.
        assert 'the budget is capped at 80k' in req
        assert 'GDPR compliance is mandatory' in req

    def test_boundary_keeps_real_pains_and_impacts(self):
        # Non-over-exclusion guard present.
        req = self._pain_impact_prompt()
        assert 'do not silently drop it' in req


# =============================================================================
# WIRING — non-over-exclusion: real objective/pain/impact still route through
# =============================================================================

class TestFrontierDoesNotOverExclude:
    """
    With the frontier prompts in place, a canned objective + pain + impact +
    constraint each persist to their OWN model. Proves the boundary edits did
    not break the stages' routing of genuine signals (the FakeProvider replies
    stand in for what a well-behaved LLM would return AFTER the frontier).
    """

    def test_genuine_signals_of_each_type_all_persist(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            # A real lived pain + a real measured impact.
            'pain_impact': (
                '{"pains": [{'
                '"what": "OPS", "dimension": "TIME", '
                '"scope_level": "BUSINESS", "target_department": null, '
                '"summary": "Manual reconciliation is slow", '
                '"source_quote": "reconciling by hand takes days", '
                '"confidence": 0.9, "is_inferred": false}], '
                '"impacts": [{'
                '"what": "OPS", "dimension": "COST", "impact_type": "FINANCIAL", '
                '"scope_level": "BUSINESS", "target_department": null, '
                '"summary": "Costs 40k a quarter", '
                '"source_quote": "it costs us about 40k a quarter", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
            # A real business objective (NOT a requirement).
            'objective': (
                '{"signals": [{'
                '"what": "GROWTH", "dimension": "SCALE", '
                '"scope_level": "BUSINESS", "target_department": null, '
                '"summary": "Grow revenue 20% this year", '
                '"source_quote": "we want to grow revenue 20% this year", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
            # A requirement on the solution -> constraint only.
            'constraint': (
                '{"signals": [{'
                '"summary": "Real-time reporting is required", '
                '"nature": "FUNCTIONAL", "rigidity": "FIRM", '
                '"scope_level": "BUSINESS", "target_department": null, '
                '"source_quote": "we need real-time reporting", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
        }

        result = QualificationSignalsPipeline().run(
            transcript='Discovery call with Acme covering goals and needs.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        # Each genuine signal persisted to its OWN model -- none dropped.
        assert len(result['signals_by_stage']['pain']) == 1
        assert len(result['signals_by_stage']['impact']) == 1
        assert len(result['signals_by_stage']['objective']) == 1
        assert len(result['signals_by_stage']['constraint']) == 1

        assert PainSignal.objects.count() == 1
        assert ImpactSignal.objects.count() == 1
        assert ObjectiveSignal.objects.count() == 1
        assert ConstraintSignal.objects.count() == 1
        assert result['signals_by_stage']['constraint'][0].nature == (
            ConstraintNature.FUNCTIONAL
        )
