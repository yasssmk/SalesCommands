# backend/tests/ai_pipelines/test_next_steps_structured_output.py
"""
Sprint Next steps 3.1 -- the next_steps pipeline on gpt-5.6-terra +
Structured Outputs, prompt v1 UNCHANGED, through the REAL pipeline path
(FakeProvider -> NextStepExtractor).

  * config: the pipeline's own PROVIDER_CONFIG key, `openai_next_steps`
    (config.NEXT_STEPS_PROVIDER): gpt-5.6-terra, reasoning medium.
  * The call: Terra, reasoning_effort medium, NO temperature, the entry's
    max_tokens / timeout, a STRICT response schema of the v1 output
    ({"signals": [...]}, every field required, no other field, the activity
    type enum = ActivityType); the audit row carries the real model.
  * Prompt v1 unchanged: request and system text byte-identical to 3.0.
  * Guard schema <-> provider PROPER to the pipeline: a provider without
    response-schema support (Claude) or an unknown key fails at load time.
  * The qualification stages are untouched (test_stage_provider.py).
"""

import hashlib
import json

import pytest

from app_modules.activities.constants import ActivityType
from app_modules.ai_pipelines import config


pytestmark = pytest.mark.django_db

KEY = 'openai_next_steps'
TERRA = 'gpt-5.6-terra'
FIELDS = {
    'suggested_title', 'suggested_activity_type', 'suggested_due_date',
    'suggested_objective', 'source_quote', 'confidence', 'is_inferred',
}
# sha256 of the v1 texts as shipped in 3.0 (commit 388f0b75), before 3.1.
REQUEST_V1_SHA256 = '6aed4bd1d738c868e867b3dcd142322b09804d04be2dc1e94a3c954c5a1ad846'
SYSTEM_V1_SHA256 = 'a2dcb8d8fa6f4cc5207d585057f72a6665aec16919e1f72fc3627e8de06e6a4f'

TRANSCRIPT = 'Jordan Lee: envoyez-nous la grille tarifaire avant vendredi.'


def _run(account, activity, user_a, fake_provider, signals=None):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    if signals is not None:
        fake_provider.replies = {'next_steps': json.dumps({'signals': signals})}
    return NextStepsPipeline().run(
        transcript=TRANSCRIPT, activity=activity, user=user_a,
        client_id=account.client_id,
    )


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class TestConfig:

    def test_the_pipeline_has_its_own_terra_entry(self):
        assert config.NEXT_STEPS_PROVIDER == KEY
        entry = config.PROVIDER_CONFIG[KEY]
        assert entry['provider'] == 'openai'
        assert entry['model'] == TERRA
        assert entry['reasoning_effort'] == 'medium'
        assert entry['max_tokens'] == 8192
        assert entry['timeout_s'] == 90

    def test_the_qualification_mapping_is_untouched(self):
        assert config.STAGE_PROVIDER == {'people': 'openai_people'}
        assert KEY not in config.STAGE_PROVIDER.values()


class TestNextStepsCall:

    def test_terra_in_reasoning_mode_with_the_entry_limits(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a, fake_provider)
        entry = config.PROVIDER_CONFIG[KEY]
        [call] = fake_provider.calls_for('next_steps')
        assert call['model'] == TERRA
        assert call['temperature'] is None
        assert set(call['extra']) == {'reasoning_effort', 'response_schema'}
        assert call['extra']['reasoning_effort'] == 'medium'
        assert (call['max_tokens'], call['timeout_s']) == (entry['max_tokens'], entry['timeout_s'])
        # The audit row carries the real model of the pipeline.
        run = result['run']
        assert run.model_name == TERRA
        assert [c['model_used'] for c in run.sub_calls] == [TERRA]

    def test_a_strict_schema_of_the_v1_output(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        [call] = fake_provider.calls_for('next_steps')
        schema = call['extra']['response_schema']
        assert schema['name'] == 'next_steps_signals'
        root = schema['schema']
        assert root['additionalProperties'] is False
        assert root['required'] == ['signals']
        item = root['properties']['signals']['items']
        assert item['additionalProperties'] is False
        assert set(item['properties']) == FIELDS
        assert set(item['required']) == FIELDS
        props = item['properties']
        assert props['suggested_activity_type'] == {
            'type': 'string', 'enum': list(ActivityType.values)}
        assert props['suggested_due_date'] == {'type': ['string', 'null']}
        assert props['confidence'] == {'type': 'number'}
        assert props['is_inferred'] == {'type': 'boolean'}
        for text in ('suggested_title', 'suggested_objective', 'source_quote'):
            assert props[text] == {'type': 'string'}

    def test_every_schema_field_is_the_one_the_prompt_asks_for(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        [call] = fake_provider.calls_for('next_steps')
        for field in FIELDS:
            assert f'"{field}":' in call['user']
        for code in ActivityType.values:
            assert f'"{code}"' in call['user']

    def test_an_answer_is_persisted_as_before(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, signals=[{
            'suggested_title': 'Envoyer la grille tarifaire',
            'suggested_activity_type': 'EMAIL',
            'suggested_due_date': None,
            'suggested_objective': '',
            'source_quote': 'Jordan Lee: envoyez-nous la grille tarifaire avant vendredi.',
            'confidence': 0.9, 'is_inferred': False,
        }])['signals']
        signal.refresh_from_db()
        assert (signal.suggested_title, signal.suggested_activity_type) == \
            ('Envoyer la grille tarifaire', 'EMAIL')
        assert signal.source_quote == 'envoyez-nous la grille tarifaire avant vendredi.'


class TestPromptUnchanged:

    def test_versions(self):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        assert NextStepsPipeline.PROMPT_VERSIONS == {
            'system': 'v1', 'context': 'v6', 'next_steps': 'v1'}   # context v6: 3.2

    def test_request_and_system_text_are_byte_identical_to_3_0(self):
        from app_modules.ai_pipelines.prompts.next_steps.next_steps_v1 import (
            build_next_steps_request,
        )
        from app_modules.ai_pipelines.prompts.transcript_signals.system import SYSTEM_PROMPT
        assert _sha(build_next_steps_request('<<T>>')) == REQUEST_V1_SHA256
        assert _sha(SYSTEM_PROMPT) == SYSTEM_V1_SHA256


class TestSchemaProviderGuard:
    """The next_steps pipeline's own load-time guard."""

    def _check(self, key):
        from app_modules.ai_pipelines.pipelines import next_steps
        next_steps.check_next_steps_provider(
            key, next_steps.NEXT_STEPS_RESPONSE_SCHEMA, config.PROVIDER_CONFIG)

    def test_the_production_entry_passes(self):
        self._check(config.NEXT_STEPS_PROVIDER)

    def test_a_provider_without_schema_support_is_refused(self):
        with pytest.raises(ImportError, match='does not support a response schema'):
            self._check('claude')

    def test_an_unknown_key_is_refused(self):
        with pytest.raises(ImportError, match='not in PROVIDER_CONFIG'):
            self._check('openai_next_stpes')

    def test_no_schema_needs_no_support(self):
        from app_modules.ai_pipelines.pipelines import next_steps
        next_steps.check_next_steps_provider('claude', None, config.PROVIDER_CONFIG)


def test_the_settings_override_restores_the_baseline_model(
    account, activity, user_a, fake_provider, patch_active_provider, monkeypatch,
):
    """AI_PIPELINES_NEXT_STEPS_PROVIDER = 'openai' -> gpt-4o-mini, temperature
    0.0, the schema still sent (OpenAI supports it)."""
    monkeypatch.setattr(config, 'NEXT_STEPS_PROVIDER', 'openai')
    result = _run(account, activity, user_a, fake_provider)
    [call] = fake_provider.calls_for('next_steps')
    assert (call['model'], call['temperature']) == ('gpt-4o-mini', 0.0)
    assert set(call['extra']) == {'response_schema'}
    assert result['run'].model_name == 'gpt-4o-mini'
