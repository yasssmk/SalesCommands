# backend/tests/ai_pipelines/test_constraint_extraction_departments_m2m.py
"""
Sub-step 1c — Constraint EXTRACTION emits a LIST of departments.

The constraint prompt now asks the LLM for `target_departments` (a list of
department names, cloned from TechStack.usage_departments), and the builder
resolves that list into the ConstraintSignal.target_departments M2M. These
tests drive the real pipeline with a FakeProvider whose constraint reply
carries TWO departments and assert the persisted signal has BOTH in its M2M.

RED before the fix (the builder resolves a single FK via
resolve_scope_and_department and never reads the list) — GREEN once the
prompt + builder move to the multi-department list.

Only Constraint is exercised here; pain/impact/objective extraction (the
shared resolve_scope_and_department) is covered by its own untouched tests.
"""

import json

import pytest

from app_modules.signals.constants import ConstraintNature, SignalStatus
from app_modules.signals.models import ConstraintSignal


pytestmark = pytest.mark.django_db


@pytest.fixture
def it_department(db):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='IT')
    return dept


@pytest.fixture
def finance_department(db):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='Finance')
    return dept


def _constraint_reply(objs):
    return json.dumps({'signals': objs})


def _constraint_obj(*, summary, nature, target_departments,
                    rigidity='FIRM', source_quote='we require it',
                    confidence=0.9, is_inferred=False):
    return {
        'summary': summary,
        'nature': nature,
        'rigidity': rigidity,
        'target_departments': target_departments,
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


class TestConstraintExtractionMultiDepartment:

    def test_two_departments_persist_into_m2m(
        self, account, activity, user_a, it_department, finance_department,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'constraint': _constraint_reply([_constraint_obj(
                summary='Integration owned jointly by IT and Finance',
                nature='TECHNICAL',
                target_departments=['IT', 'Finance'],
                source_quote='IT and Finance both own this integration',
            )]),
        }

        result = _run(account, activity, user_a)

        constraints = result['signals_by_stage']['constraint']
        assert len(constraints) == 1
        sig = constraints[0]
        assert isinstance(sig, ConstraintSignal)
        assert sig.status == SignalStatus.PENDING
        assert set(sig.target_departments.values_list('id', flat=True)) == {
            it_department.id, finance_department.id,
        }

    def test_no_department_yields_empty_m2m(
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
        assert list(constraints[0].target_departments.all()) == []
