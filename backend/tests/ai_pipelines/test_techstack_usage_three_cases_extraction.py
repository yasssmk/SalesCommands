# backend/tests/ai_pipelines/test_techstack_usage_three_cases_extraction.py
"""
TechStack usage in THREE cases — extraction side (Sprint TechStack, T0).

PO rule: usage at the prospect is DEPARTMENT (+ departments), COMPANY or
UNKNOWN. TEAM disappears, "not said" is UNKNOWN (never null), and
DEPARTMENT <=> at least one RESOLVED usage department.

Two proof surfaces (mirror of test_techstack_usage_departments_extraction.py):
  * PIPELINE PATH (persist_stage): the builder normalises whatever the model
    emits into the three cases, the resolved departments deciding DEPARTMENT.
  * PROMPT / CONTEXT content: techstack prompt v2 and CONTEXT v4 describe the
    three cases and no longer offer TEAM.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    CONTEXT_VERSION,
    build_context_layer,
)
from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    TECHSTACK_PROMPT_VERSION,
    build_techstack_request,
)
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def dept_marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


def _raw(tech_name, **overrides):
    payload = {
        'tech_name':         tech_name,
        'usage_departments': [],
        'source_quote':      f'We use {tech_name}',
        'confidence':        0.9,
        'is_inferred':       False,
    }
    payload.update(overrides)
    return payload


def _persist(activity, account, user, raw_signals):
    persisted, _dropped = TranscriptSignalExtractor().persist_stage(
        stage='techstack',
        raw_signals=raw_signals,
        activity=activity,
        user=user,
        client_id=account.client_id,
        confidence_min=0.5,
        drop_inferred=True,
    )
    return persisted


# (label, emitted usage_scope or '<absent>', emitted departments, expected)
CASES = [
    ('team_with_dept',       'TEAM',       ['Marketing'], 'DEPARTMENT'),
    ('team_no_dept',         'TEAM',       [],            'UNKNOWN'),
    ('department_with_dept', 'DEPARTMENT', ['Marketing'], 'DEPARTMENT'),
    ('department_no_dept',   'DEPARTMENT', [],            'UNKNOWN'),
    ('department_unresolved', 'DEPARTMENT', ['Nowhere'],  'UNKNOWN'),
    ('company_no_dept',      'COMPANY',    [],            'COMPANY'),
    ('company_with_dept',    'COMPANY',    ['Marketing'], 'DEPARTMENT'),
    ('unknown_no_dept',      'UNKNOWN',    [],            'UNKNOWN'),
    ('unknown_with_dept',    'UNKNOWN',    ['Marketing'], 'DEPARTMENT'),
    ('null_no_dept',         None,         [],            'UNKNOWN'),
    ('absent_no_dept',       '<absent>',   [],            'UNKNOWN'),
    ('garbage_no_dept',      'EVERYONE',   [],            'UNKNOWN'),
]


class TestBuilderNormalisesUsageToThreeCases:

    @pytest.mark.parametrize(
        'label, emitted, depts, expected', CASES, ids=[c[0] for c in CASES],
    )
    def test_usage_scope_is_one_of_the_three_cases(
        self, label, emitted, depts, expected,
        account, activity, user_a, dept_marketing,
    ):
        raw = _raw(f'Tool {label}', usage_departments=depts)
        if emitted != '<absent>':
            raw['usage_scope'] = emitted

        persisted = _persist(activity, account, user_a, [raw])

        assert len(persisted) == 1
        sig = persisted[0]
        assert sig.usage_scope == expected
        # DEPARTMENT <=> at least one resolved usage department.
        assert (sig.usage_scope == 'DEPARTMENT') == sig.usage_departments.exists()


class TestPromptAndContextDescribeThreeCases:

    def test_prompt_version_is_v2(self):
        assert TECHSTACK_PROMPT_VERSION == 'v2'

    def test_prompt_no_longer_offers_team(self):
        prompt = build_techstack_request('transcript')
        assert 'TEAM' not in prompt

    def test_prompt_states_the_three_cases_and_unknown_default(self):
        prompt = build_techstack_request('transcript')
        assert '"usage_scope":     "<DEPARTMENT | COMPANY | UNKNOWN>' in prompt
        assert 'never null' in prompt

    def test_context_version_is_v4(self):
        assert CONTEXT_VERSION == 'v4'

    def test_context_taxonomy_lists_exactly_the_three_cases(self, activity):
        context = build_context_layer(activity, 'techstack')
        line = next(
            l for l in context.splitlines() if l.startswith('- usage_scope')
        )
        assert '"TEAM"' not in line
        for value in ('"DEPARTMENT"', '"COMPANY"', '"UNKNOWN"'):
            assert value in line
