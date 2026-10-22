# backend/tests/ai_pipelines/test_techstack_prompt_v4_context_v5.py
"""
Sprint TechStack T4b (commit 1) — corrections of the PO smoke on T4.

  1a. TechStack has its OWN taxonomy header (mirror of People): usage_scope
      picked from its list, usage_departments may be empty, never omit a tool
      because no department fits. The other stages keep "or OMIT the signal".
  1b. Identity / infra / security / collaboration tools ARE tech stack; a used
      tool that is ALSO an integration requirement is still emitted here; the
      "we need SSO" counter-example is gone.
  2.  SHARED context (all stages + next_steps): the date is the "Conversation
      date", the reference of EVERY relative date; without it, every relative
      date is null. CONTEXT_VERSION v5 (next_steps context v2).
  3.  COMPANY only when the transcript says the WHOLE company uses the tool;
      "on est sur X" is UNKNOWN.
  4.  The D2 note text is a module constant.

These tests prove the TEXT sent to the model (and the D2 builder), not the
LLM behaviour.
"""

import datetime

import pytest

from app_modules.ai_pipelines.prompts.next_steps import context as next_steps_context
from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    CONTEXT_VERSION,
    build_context_layer,
)
from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    TECHSTACK_PROMPT_VERSION,
    build_techstack_request,
)
from app_modules.ai_pipelines.services import transcript_signal_extractor
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


pytestmark = pytest.mark.django_db

PIPELINE_STAGES = (
    'pain_impact', 'objective', 'techstack', 'blocker', 'constraint',
    'competitor', 'people',
)
RELATIVE_DATE_EXAMPLES = ('"this year"', '"next year"', '"end of the year"', '"in June"')


def _dated(activity, day):
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(
        completed_at=datetime.datetime(day.year, day.month, day.day, 10, tzinfo=datetime.timezone.utc),
        scheduled_date=None,
    )
    activity.refresh_from_db()
    return activity


def _undated(activity):
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(completed_at=None, scheduled_date=None)
    activity.refresh_from_db()
    return activity


def _flat(text):
    """Whitespace-normalised text: phrase assertions survive the line wrap."""
    return ' '.join(text.split())


def _taxonomy_header(context):
    return next(l for l in context.splitlines() if 'TAXONOMY' in l)


# =============================================================================
# 1a — dedicated techstack header
# =============================================================================

class TestTechstackTaxonomyHeader:

    def test_techstack_header_never_offers_to_omit(self, activity):
        header = _taxonomy_header(build_context_layer(activity, 'techstack'))
        assert header.startswith('TECH STACK TAXONOMY')
        assert 'OMIT' not in header
        assert 'pick `usage_scope` from its list' in header
        assert 'usage_departments may be empty' in header
        assert 'NEVER omit a tool because no department fits' in header

    @pytest.mark.parametrize('stage', ('pain_impact', 'objective', 'constraint'))
    def test_other_stages_keep_the_omit_header(self, stage, activity):
        header = _taxonomy_header(build_context_layer(activity, stage))
        assert header == (
            'CANONICAL TAXONOMY '
            '(pick exactly one value from each list, or OMIT the signal)'
        )


# =============================================================================
# 2 — shared "Conversation date"
# =============================================================================

class TestConversationDate:

    def test_context_version_is_v10(self):
        # v9 (TD-279 M) only changes the People branch; v10 (D7) the source
        # of the Conversation date.
        assert CONTEXT_VERSION == 'v10'

    def test_next_steps_context_version_is_v5(self):
        assert next_steps_context.CONTEXT_VERSION == 'v5'

    @pytest.mark.parametrize('stage', PIPELINE_STAGES)
    def test_dated_activity_gives_the_reference_for_relative_dates(self, stage, activity):
        context = build_context_layer(_dated(activity, datetime.date(2026, 10, 19)), stage)
        line = next(l for l in context.splitlines() if l.startswith('- Conversation date:'))
        assert line.startswith('- Conversation date: 2026-10-19 ')
        assert 'EVERY relative date' in line
        for example in RELATIVE_DATE_EXAMPLES:
            assert example in line, example
        assert '- Activity: Meeting\n' in context + '\n'
        assert ' on 2026-10-19' not in context

    @pytest.mark.parametrize('stage', PIPELINE_STAGES)
    def test_undated_activity_says_so_and_relative_dates_are_null(self, stage, activity):
        context = build_context_layer(_undated(activity), stage)
        line = next(l for l in context.splitlines() if l.startswith('- Conversation date:'))
        assert line.startswith('- Conversation date: not provided')
        assert 'EVERY relative date' in line
        assert 'null' in line
        for example in RELATIVE_DATE_EXAMPLES:
            assert example in line, example

    def test_next_steps_context_carries_the_same_line(self, activity):
        context = next_steps_context.build_context_layer(
            _dated(activity, datetime.date(2026, 10, 19)),
        )
        assert '- Conversation date: 2026-10-19 ' in context


# =============================================================================
# 1b / 2 / 3 — techstack prompt v4 content
# =============================================================================

class TestTechstackPromptV4:

    def test_version_is_v4_or_later(self):
        # v5 (T4c) keeps the v4 content asserted below.
        assert TECHSTACK_PROMPT_VERSION == 'v5'

    def test_sso_counter_example_replaced_by_a_neutral_one(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert 'we need SSO' not in prompt
        assert '"we have a ticketing tool" names no user' in prompt

    def test_identity_infra_security_collaboration_tools_are_tech_stack(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert (
            'Identity, infrastructure, security and collaboration tools '
            '(SSO, Azure AD, Okta, AWS, ...) ARE tech stack'
        ) in prompt

    def test_a_used_tool_also_required_as_integration_is_still_emitted(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert 'can ALSO be an integration requirement' in prompt
        assert 'STILL emit it here' in prompt

    def test_relative_dates_use_the_conversation_date_or_null(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert '"Conversation date"' in prompt
        assert 'Activity: ... on <date>' not in prompt
        assert 'every relative date is null' in prompt

    def test_french_this_year_example(self):
        prompt = build_techstack_request('transcript')
        assert '« on arrête X le 31 décembre de cette année »' in prompt
        assert '"discontinued_date": "<conversation year>-12-31"' in prompt

    def test_company_only_when_the_whole_company_uses_the_tool(self):
        prompt = _flat(build_techstack_request('transcript'))
        assert 'no department designated' not in prompt
        assert 'the transcript says the WHOLE company / everyone uses the tool' in prompt
        assert '"we use X" / "on est sur X" is NOT company-wide -> "UNKNOWN"' in prompt

    @pytest.mark.parametrize('quote, outcome', [
        ('« On est sur Salesforce. »',
         'usage_scope="UNKNOWN", usage_departments=[]'),
        ('« Salesforce, c\'est pour le pilotage du pipeline commercial. »',
         'usage_scope="DEPARTMENT", usage_departments=["Sales"]'),
        ('« Côté support, on est sur Zendesk. »',
         'usage_scope="DEPARTMENT", usage_departments=["Customer Support"]'),
    ])
    def test_po_usage_examples(self, quote, outcome):
        prompt = build_techstack_request('transcript')
        assert f'- {quote}\n      -> {outcome}' in prompt


# =============================================================================
# Real path — the assembled techstack call carries the corrections
# =============================================================================

class TestAssembledTechstackCall:

    def test_techstack_call_has_its_header_and_the_conversation_date(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        _dated(activity, datetime.date(2026, 10, 19))
        QualificationSignalsPipeline().run(
            transcript='On est sur Salesforce et on a un SSO Azure AD.',
            activity=activity, user=user_a, client_id=account.client_id,
        )
        (call,) = fake_provider.calls_for('techstack')
        assert 'TECH STACK TAXONOMY' in call['user']
        assert '- Conversation date: 2026-10-19 ' in call['user']
        assert 'ARE tech stack' in call['user']


# =============================================================================
# 4 — D2 note text is a module constant
# =============================================================================

class TestUndatedDiscontinuationNoteConstant:

    def test_the_note_is_rendered_from_the_module_constant(self, account, activity, user_a):
        template = transcript_signal_extractor._TECHSTACK_UNDATED_DISCONTINUATION_NOTE
        quote = 'We are going to drop HubSpot at some point.'
        persisted, _ = TranscriptSignalExtractor().persist_stage(
            stage='techstack',
            raw_signals=[{
                'tech_name': 'HubSpot', 'usage_scope': 'UNKNOWN',
                'usage_departments': [], 'is_discontinued': True,
                'discontinued_date': None, 'source_quote': quote,
                'confidence': 0.9, 'is_inferred': False,
            }],
            activity=activity, user=user_a, client_id=account.client_id,
            confidence_min=0.5, drop_inferred=True,
        )
        sig = persisted[0]
        sig.refresh_from_db()
        assert sig.notes == template.format(quote=quote)
