# backend/tests/ai_pipelines/test_pipeline_scope_extraction.py
"""
Scope extraction + merged pain/impact stage tests for
QualificationSignalsPipeline (Step 1 -- A1 scope, A2 merge).

A1 (scope): the pipeline reads scope_level (BUSINESS | DEPARTMENT) and, for
DEPARTMENT-scoped signals, resolves target_department to a StandardDepartment
FK; guards fold PERSONAL / unresolved / General-Management back to BUSINESS.

A2 (merge): pain and impact are extracted in ONE LLM call (the 'pain_impact'
stage) returning {"pains": [...], "impacts": [...]}. The pipeline persists
each list separately into signals_by_stage['pain'] / ['impact'], and each
signal resolves its OWN scope -- a department's problem (pain=DEPARTMENT)
can cost the whole company (impact=BUSINESS).

The FakeProvider infers the merged stage from the "Extract PAIN and IMPACT
signals" marker and returns the canned 'pain_impact' reply.
"""

import pytest

from app_modules.signals.constants import ScopeLevel

from .conftest import CANNED_REPLIES_DEPARTMENT


pytestmark = pytest.mark.django_db


@pytest.fixture
def marketing_department(db):
    """Ensure the 'Marketing' StandardDepartment row exists for resolution."""
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return dept


def _pain_impact_reply(*, pains=None, impacts=None):
    """Build a merged pain_impact LLM reply from pain/impact object strings."""
    import json
    return json.dumps({'pains': pains or [], 'impacts': impacts or []})


def _pain_obj(*, scope_level, target_department):
    """One pain object with the given scope + department (or null)."""
    return {
        'what': 'DATA', 'dimension': 'QUALITY',
        'scope_level': scope_level, 'target_department': target_department,
        'summary': 'Data quality issue', 'source_quote': 'The data cannot be trusted',
        'confidence': 0.9, 'is_inferred': False,
    }


def _run(pipeline_cls, account, activity, user_a):
    """Run the pipeline (replies preset on the fake provider)."""
    return pipeline_cls().run(
        transcript='A transcript about data quality at Acme corp.',
        activity=activity,
        user=user_a,
        client_id=account.client_id,
    )


# =============================================================================
# A2 — MERGED STAGE + INDEPENDENT SCOPE
# =============================================================================

class TestMergedPainImpactStage:
    """
    ONE merged LLM call must populate BOTH signals_by_stage['pain'] and
    ['impact'], and pain / impact resolve scope INDEPENDENTLY.
    """

    def test_merged_stage_populates_both_with_independent_scope(
        self, account, activity, user_a, marketing_department,
        fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        # The DEPARTMENT fixture's 'pain_impact' reply carries, from one
        # passage: pain=DEPARTMENT/Marketing, impact=BUSINESS/FINANCIAL.
        fake_provider.replies = dict(CANNED_REPLIES_DEPARTMENT)

        result = _run(QualificationSignalsPipeline, account, activity, user_a)

        pains = result['signals_by_stage']['pain']
        impacts = result['signals_by_stage']['impact']

        # Both populated from the SINGLE merged stage.
        assert len(pains) == 1, 'the merged stage must persist the pain'
        assert len(impacts) == 1, 'the merged stage must persist the impact'

        # Independent scope: the pain is Marketing's, the cost is the company's.
        assert pains[0].scope_level == ScopeLevel.DEPARTMENT
        assert pains[0].target_department_id == marketing_department.id

        assert impacts[0].scope_level == ScopeLevel.BUSINESS
        assert impacts[0].target_department_id is None

    def test_only_one_llm_sub_call_for_pain_and_impact(
        self, account, activity, user_a, marketing_department,
        fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = dict(CANNED_REPLIES_DEPARTMENT)

        _run(QualificationSignalsPipeline, account, activity, user_a)

        # One LLM call for pain+impact (merged), plus
        # objective/techstack/blocker/constraint.
        assert fake_provider.stages_in_order() == [
            'pain_impact', 'objective', 'techstack', 'blocker', 'constraint',
        ]


# =============================================================================
# A1 — SCOPE GUARDS (resolver behaviour, now driven through the merged stage)
# =============================================================================

class TestScopeGuards:
    """The three folds: anti-PERSONAL, unresolved department, GM -> BUSINESS."""

    def _run_single_pain(self, account, activity, user_a, fake_provider, pain):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'pain_impact': _pain_impact_reply(pains=[pain], impacts=[]),
        }
        result = _run(QualificationSignalsPipeline, account, activity, user_a)
        return result['signals_by_stage']['pain']

    def test_personal_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # GUARD 1: PERSONAL is never offered in the prompt, but a drifting
        # emission must fold to BUSINESS -- never persist a PERSONAL row.
        pains = self._run_single_pain(
            account, activity, user_a, fake_provider,
            _pain_obj(scope_level='PERSONAL', target_department='Marketing'),
        )
        assert len(pains) == 1, 'signal must NOT be dropped'
        assert pains[0].scope_level == ScopeLevel.BUSINESS
        assert pains[0].target_department_id is None

    def test_unresolved_department_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # A DEPARTMENT scope whose name does not resolve folds to BUSINESS
        # + None. The signal STILL persists (no drop, no raise).
        pains = self._run_single_pain(
            account, activity, user_a, fake_provider,
            _pain_obj(scope_level='DEPARTMENT',
                      target_department='Totally Unknown Department'),
        )
        assert len(pains) == 1, 'unresolved department must NOT drop the signal'
        assert pains[0].scope_level == ScopeLevel.BUSINESS
        assert pains[0].target_department_id is None

    def test_general_management_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # GUARD 2: a resolved "General Management" department is a company-wide
        # / executive scope -> BUSINESS + None.
        from app_modules.core_modules.models import StandardDepartment
        StandardDepartment.objects.get_or_create(name='General Management')

        pains = self._run_single_pain(
            account, activity, user_a, fake_provider,
            _pain_obj(scope_level='DEPARTMENT',
                      target_department='General Management'),
        )
        assert len(pains) == 1
        assert pains[0].scope_level == ScopeLevel.BUSINESS
        assert pains[0].target_department_id is None

    def test_department_happy_path_resolves_fk(
        self, account, activity, user_a, marketing_department,
        fake_provider, patch_active_provider,
    ):
        # DEPARTMENT happy path: scope kept, FK resolved.
        pains = self._run_single_pain(
            account, activity, user_a, fake_provider,
            _pain_obj(scope_level='DEPARTMENT', target_department='Marketing'),
        )
        assert len(pains) == 1
        assert pains[0].scope_level == ScopeLevel.DEPARTMENT
        assert pains[0].target_department_id == marketing_department.id

    def test_business_scope_persists_without_department(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # BUSINESS happy path: scope kept, no department.
        pains = self._run_single_pain(
            account, activity, user_a, fake_provider,
            _pain_obj(scope_level='BUSINESS', target_department=None),
        )
        assert len(pains) == 1
        assert pains[0].scope_level == ScopeLevel.BUSINESS
        assert pains[0].target_department_id is None
