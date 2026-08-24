# backend/tests/ai_pipelines/test_pipeline_scope_extraction.py
"""
Scope-level extraction tests for QualificationSignalsPipeline (Step 1 / A1).

The pipeline must read scope_level (BUSINESS | DEPARTMENT) and, for
DEPARTMENT-scoped signals, resolve target_department to a StandardDepartment
FK -- replacing the previous forced-BUSINESS behaviour for pain / objective /
impact.

Guards under test (added in A1.2):
  * anti-PERSONAL: any scope_level not in {BUSINESS, DEPARTMENT} folds to
    BUSINESS.
  * unresolved department: a target_department name that does not resolve
    folds to BUSINESS + target_department=None (signal still persists).
  * general-management -> BUSINESS: a resolved "General Management" department
    folds to BUSINESS.
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


def _pain_reply(*, scope_level, target_department):
    """Build a one-pain LLM reply with the given scope + department."""
    dept = 'null' if target_department is None else f'"{target_department}"'
    return (
        '{"signals": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        f'"scope_level": "{scope_level}", '
        f'"target_department": {dept}, '
        '"summary": "Data quality issue", '
        '"source_quote": "The data cannot be trusted", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    )


def _run_pain(pipeline_cls, account, activity, user_a):
    """Run the pipeline (replies preset on the fake provider), return pains."""
    result = pipeline_cls().run(
        transcript='A transcript about data quality at Acme corp.',
        activity=activity,
        user=user_a,
        client_id=account.client_id,
    )
    return result['signals_by_stage']['pain']


class TestDepartmentScopeExtraction:
    """A DEPARTMENT-scoped emission must persist scope + resolved FK."""

    def test_department_scope_persisted_for_all_three(
        self, account, activity, user_a, marketing_department,
        fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = dict(CANNED_REPLIES_DEPARTMENT)

        result = QualificationSignalsPipeline().run(
            transcript='Marketing cannot trust the campaign data at Acme.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        for stage in ('pain', 'objective', 'impact'):
            persisted = result['signals_by_stage'][stage]
            assert len(persisted) == 1, f'stage {stage} should persist 1 signal'
            signal = persisted[0]
            assert signal.scope_level == ScopeLevel.DEPARTMENT, (
                f'stage {stage}: expected DEPARTMENT, got {signal.scope_level!r}'
            )
            assert signal.target_department_id == marketing_department.id, (
                f'stage {stage}: target_department not resolved to Marketing'
            )


class TestScopeGuards:
    """The three folds: anti-PERSONAL, unresolved department, GM -> BUSINESS."""

    def test_personal_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # GUARD 1: PERSONAL is never offered in the prompt, but a drifting
        # emission must fold to BUSINESS -- never persist a PERSONAL row.
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'pain': _pain_reply(scope_level='PERSONAL', target_department='Marketing'),
        }
        persisted = _run_pain(
            QualificationSignalsPipeline, account, activity, user_a,
        )
        assert len(persisted) == 1, 'signal must NOT be dropped'
        assert persisted[0].scope_level == ScopeLevel.BUSINESS
        assert persisted[0].target_department_id is None

    def test_unresolved_department_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # A DEPARTMENT scope whose name does not resolve folds to BUSINESS
        # + None. The signal STILL persists (no drop, no raise).
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'pain': _pain_reply(
                scope_level='DEPARTMENT',
                target_department='Totally Unknown Department',
            ),
        }
        persisted = _run_pain(
            QualificationSignalsPipeline, account, activity, user_a,
        )
        assert len(persisted) == 1, 'unresolved department must NOT drop the signal'
        assert persisted[0].scope_level == ScopeLevel.BUSINESS
        assert persisted[0].target_department_id is None

    def test_general_management_folds_to_business(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # GUARD 2: a resolved "General Management" department is a company-wide
        # / executive scope -> BUSINESS + None.
        from app_modules.core_modules.models import StandardDepartment
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        StandardDepartment.objects.get_or_create(name='General Management')

        fake_provider.replies = {
            'pain': _pain_reply(
                scope_level='DEPARTMENT',
                target_department='General Management',
            ),
        }
        persisted = _run_pain(
            QualificationSignalsPipeline, account, activity, user_a,
        )
        assert len(persisted) == 1
        assert persisted[0].scope_level == ScopeLevel.BUSINESS
        assert persisted[0].target_department_id is None

    def test_business_scope_persists_without_department(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # BUSINESS happy path: scope kept, no department.
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'pain': _pain_reply(scope_level='BUSINESS', target_department=None),
        }
        persisted = _run_pain(
            QualificationSignalsPipeline, account, activity, user_a,
        )
        assert len(persisted) == 1
        assert persisted[0].scope_level == ScopeLevel.BUSINESS
        assert persisted[0].target_department_id is None
