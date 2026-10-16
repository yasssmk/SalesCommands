# backend/tests/ai_pipelines/test_techstack_competitor_boundary.py
"""
Sprint TechStack T4b (commit 2) — TechStack / Competitor boundary.

PO rule:
  * TechStack = CONFIRMED usage only. « on regarde / évalue / teste X » is
    NEVER a tech stack signal.
  * Competitor (prompt v2) = a tool the prospect is looking at / evaluating
    is a competitor BY DEFAULT, even when its link to the project is in
    doubt. ONLY exception: the transcript says CLEARLY it is unrelated
    (« on regarde aussi un outil de paie, mais c'est un autre sujet ») ->
    emit nothing. "When in doubt, do NOT emit" is gone.

Proof surfaces: the prompt TEXT of both stages, and the real pipeline path
where the SAME sentences reach both stages (simulated LLM). These tests prove
the text sent to the model, not the LLM behaviour.
"""

import json

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.competitor_v1 import (
    COMPETITOR_PROMPT_VERSION,
    build_competitor_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    build_techstack_request,
)


pytestmark = pytest.mark.django_db

EVALUATED = 'On commence à regarder HubSpot pour remplacer Salesforce.'
UNRELATED = 'On regarde aussi un nouvel outil de paie, mais c\'est un tout autre sujet.'
TRANSCRIPT = f'On est sur Salesforce. {EVALUATED} {UNRELATED}'


def _flat(text):
    """Whitespace-normalised text: phrase assertions survive the line wrap."""
    return ' '.join(text.split())


# =============================================================================
# TechStack — confirmed usage only
# =============================================================================

class TestTechstackConfirmedUsageOnly:

    def test_evaluated_tool_is_never_tech_stack(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert (
            'A tool the prospect is only LOOKING AT, EVALUATING or TESTING '
            '(« on regarde / évalue / teste X », "we\'re evaluating X") is '
            'NEVER tech stack'
        ) in prompt

    def test_emission_requires_confirmed_usage(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert 'CONFIRMED usage only' in prompt
        assert 'prospect-side CONFIRMED CURRENT usage' in prompt


# =============================================================================
# Competitor v2 — evaluated tool = competitor by default
# =============================================================================

class TestCompetitorPromptV2:

    def test_version_is_v2(self):
        assert COMPETITOR_PROMPT_VERSION == 'v2'

    def test_when_in_doubt_do_not_emit_is_gone(self):
        prompt = _flat(build_competitor_request('transcript'))
        assert 'When in doubt, do NOT emit' not in prompt

    def test_evaluated_tool_is_a_competitor_by_default(self):
        prompt = _flat(build_competitor_request('transcript'))
        assert (
            'A tool or vendor the prospect is LOOKING AT, EVALUATING or '
            'TESTING (« on regarde / évalue / teste X ») is a COMPETITOR BY DEFAULT'
        ) in prompt
        assert 'even when its link to the seller\'s project is in doubt' in prompt

    def test_the_only_exception_is_a_clearly_unrelated_tool(self):
        prompt = _flat(build_competitor_request('transcript'))
        assert (
            'The ONLY exception: the transcript says CLEARLY that the tool is '
            'unrelated to the project'
        ) in prompt
        assert (
            '« On regarde aussi un outil de paie, mais c\'est un autre sujet. » '
            '-> NOT a competitor: emit nothing'
        ) in prompt

    def test_evaluated_replacement_example(self):
        prompt = _flat(build_competitor_request('transcript'))
        assert (
            '« On commence à regarder HubSpot pour remplacer Salesforce. » '
            '-> competitor_name="HubSpot"'
        ) in prompt


# =============================================================================
# Real path — the same sentences reach BOTH stages (simulated LLM)
# =============================================================================

class TestSameSentenceThroughBothStages:

    def test_both_stages_get_the_sentences_and_their_boundary_rule(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        from app_modules.signals.models import CompetitorSignal, TechStackSignal

        # Simulated LLM replies = what each prompt instructs for TRANSCRIPT.
        fake_provider.replies = {
            'techstack': json.dumps({'signals': [{
                'tech_name': 'Salesforce', 'usage_scope': 'UNKNOWN',
                'usage_departments': [], 'source_quote': 'On est sur Salesforce.',
                'confidence': 0.95, 'is_inferred': False,
            }]}),
            'competitor': json.dumps({'signals': [{
                'summary': 'The prospect starts looking at HubSpot to replace Salesforce',
                'competitor_name': 'HubSpot', 'source_quote': EVALUATED,
                'confidence': 0.9, 'is_inferred': False,
            }]}),
        }

        QualificationSignalsPipeline().run(
            transcript=TRANSCRIPT, activity=activity, user=user_a,
            client_id=account.client_id,
        )

        (tech_call,) = fake_provider.calls_for('techstack')
        (comp_call,) = fake_provider.calls_for('competitor')
        for call in (tech_call, comp_call):
            assert EVALUATED in call['user']
            assert UNRELATED in call['user']
        assert 'is NEVER tech stack' in _flat(tech_call['user'])
        assert 'COMPETITOR BY DEFAULT' in _flat(comp_call['user'])
        assert 'When in doubt, do NOT emit' not in _flat(comp_call['user'])

        tech = set(TechStackSignal.objects.filter(source_activity=activity)
                   .values_list('tech_name', flat=True))
        competitors = set(CompetitorSignal.objects.filter(source_activity=activity)
                          .values_list('competitor_name', flat=True))
        assert tech == {'Salesforce'}
        assert competitors == {'HubSpot'}
