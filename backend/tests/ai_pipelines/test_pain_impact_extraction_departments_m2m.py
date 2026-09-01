# backend/tests/ai_pipelines/test_pain_impact_extraction_departments_m2m.py
"""
Sub-step 2c — Pain + Impact EXTRACTION emits a LIST of departments per item.

The combined pain_impact prompt now asks the LLM for `target_departments` (a
list of department names) on each pain AND each impact, resolved into the
PainSignal / ImpactSignal target_departments M2M. scope_level is KEPT
(descriptive) — contrast with Constraint 1c, which dropped it.

These tests drive the real pipeline with a FakeProvider whose pain_impact reply
carries TWO departments on the pain and TWO on the impact, and assert both
persisted signals have BOTH in their M2M AND scope_level still set. RED before
the fix (the builders resolve a single FK via resolve_scope_and_department and
never read the list). Objective (a separate stage / prompt) is untouched.
"""

import json

import pytest

from app_modules.signals.constants import ScopeLevel
from app_modules.signals.models import PainSignal, ImpactSignal


pytestmark = pytest.mark.django_db


@pytest.fixture
def it_department(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='IT')
    return d


@pytest.fixture
def finance_department(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Finance')
    return d


def _pain_impact_reply(*, pains, impacts):
    return json.dumps({'pains': pains, 'impacts': impacts})


def _pain_obj(*, scope_level, target_departments):
    return {
        'what': 'DATA', 'dimension': 'QUALITY',
        'scope_level': scope_level, 'target_departments': target_departments,
        'summary': 'Data quality issue', 'source_quote': 'the data cannot be trusted',
        'confidence': 0.9, 'is_inferred': False,
    }


def _impact_obj(*, scope_level, target_departments):
    return {
        'what': 'DATA', 'dimension': 'QUALITY', 'impact_type': 'FINANCIAL',
        'scope_level': scope_level, 'target_departments': target_departments,
        'summary': 'Costly data issue', 'source_quote': 'it costs 40k a quarter',
        'confidence': 0.9, 'is_inferred': False,
    }


def _run(account, activity, user_a):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    return QualificationSignalsPipeline().run(
        transcript='A transcript about data quality at Acme.',
        activity=activity, user=user_a, client_id=account.client_id,
    )


class TestPainImpactExtractionMultiDepartment:

    def test_two_departments_persist_into_both_m2ms_and_scope_kept(
        self, account, activity, user_a, it_department, finance_department,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'pain_impact': _pain_impact_reply(
                pains=[_pain_obj(
                    scope_level='DEPARTMENT',
                    target_departments=['IT', 'Finance'],
                )],
                impacts=[_impact_obj(
                    scope_level='DEPARTMENT',
                    target_departments=['IT', 'Finance'],
                )],
            ),
        }

        result = _run(account, activity, user_a)

        pains = result['signals_by_stage']['pain']
        impacts = result['signals_by_stage']['impact']
        assert len(pains) == 1 and len(impacts) == 1

        expected = {it_department.id, finance_department.id}
        assert set(pains[0].target_departments.values_list('id', flat=True)) == expected
        assert set(impacts[0].target_departments.values_list('id', flat=True)) == expected

        # scope_level is KEPT (descriptive) — not dropped like Constraint.
        assert pains[0].scope_level == ScopeLevel.DEPARTMENT
        assert impacts[0].scope_level == ScopeLevel.DEPARTMENT

    def test_no_department_yields_empty_m2m_and_business_scope(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'pain_impact': _pain_impact_reply(
                pains=[_pain_obj(scope_level='BUSINESS', target_departments=[])],
                impacts=[_impact_obj(scope_level='BUSINESS', target_departments=[])],
            ),
        }

        result = _run(account, activity, user_a)
        pains = result['signals_by_stage']['pain']
        impacts = result['signals_by_stage']['impact']
        assert len(pains) == 1 and len(impacts) == 1

        assert list(pains[0].target_departments.all()) == []
        assert list(impacts[0].target_departments.all()) == []
        assert pains[0].scope_level == ScopeLevel.BUSINESS
        assert impacts[0].scope_level == ScopeLevel.BUSINESS
