# backend/tests/ai_pipelines/test_stage_provider.py
"""
TD-279 P1 — model per stage, at the central point.

  * config.STAGE_PROVIDER maps a stage to a PROVIDER_CONFIG key (People ->
    the reasoning entry, effort medium: gpt-5.6-terra since TD-279 M, the
    challenger gpt-5.4-mini-2026-03-17); unknown key or unknown stage ->
    error at load time.
  * Real pipeline path (FakeProvider): the people stage is called with the
    People model, reasoning_effort medium, NO temperature, its own max_tokens
    / timeout; the 7 other stages keep EXACTLY the default call
    (gpt-4o-mini, temperature 0.0, default max_tokens / timeout, no extra
    argument).
"""

import pytest

from app_modules.ai_pipelines import config


pytestmark = pytest.mark.django_db

PEOPLE_KEY = 'openai_people'
CHALLENGER_KEY = 'openai_people_challenger'


def _run(account, activity, user_a):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    return QualificationSignalsPipeline().run(
        transcript='A transcript for the stage provider test.',
        activity=activity, user=user_a, client_id=account.client_id,
    )


class TestConfig:

    def test_people_stage_is_mapped_to_the_reasoning_entry(self):
        assert config.STAGE_PROVIDER == {'people': PEOPLE_KEY}
        entry = config.PROVIDER_CONFIG[PEOPLE_KEY]
        assert entry['provider'] == 'openai'
        assert entry['model'] == 'gpt-5.6-terra'
        assert entry['reasoning_effort'] == 'medium'
        assert entry['max_tokens'] == 8192

    def test_challenger_is_declared_but_not_wired(self):
        entry = config.PROVIDER_CONFIG[CHALLENGER_KEY]
        assert entry['model'] == 'gpt-5.4-mini-2026-03-17'
        assert entry['reasoning_effort'] == 'medium'
        assert CHALLENGER_KEY not in config.STAGE_PROVIDER.values()

    def test_c_unknown_provider_key_is_rejected(self):
        with pytest.raises(ImportError, match='not in PROVIDER_CONFIG'):
            config.check_stage_provider({'people': 'nope'}, config.PROVIDER_CONFIG)

    def test_c_unknown_stage_is_rejected(self):
        from app_modules.ai_pipelines.pipelines import transcript_signals
        with pytest.raises(ImportError, match='unknown stage'):
            transcript_signals.check_stage_names({'peopel': PEOPLE_KEY})


class TestStageCalls:

    def test_a_people_uses_its_reasoning_model(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a)
        entry = config.PROVIDER_CONFIG[PEOPLE_KEY]
        [call] = fake_provider.calls_for('people')
        assert call['model'] == 'gpt-5.6-terra'
        assert call['temperature'] is None
        # + the strict response schema since TD-279 M.
        assert set(call['extra']) == {'reasoning_effort', 'response_schema'}
        assert call['extra']['reasoning_effort'] == 'medium'
        assert call['max_tokens'] == entry['max_tokens']
        assert call['timeout_s'] == entry['timeout_s']
        # The real model of the call is in the audit.
        models = {c['stage']: c['model_used'] for c in result['run'].sub_calls}
        assert models['people'] == 'gpt-5.6-terra'

    def test_b_the_other_stages_keep_exactly_the_default_call(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        result = _run(account, activity, user_a)
        default = config.PROVIDER_CONFIG[config.ACTIVE_PROVIDER]
        others = [c for c in fake_provider.calls if c['stage'] != 'people']
        assert {c['stage'] for c in others} == {
            'pain_impact', 'objective', 'techstack', 'blocker', 'constraint', 'competitor',
        }
        for call in others:
            assert call['model'] == default['model'] == 'gpt-4o-mini'
            assert call['temperature'] == 0.0
            assert call['max_tokens'] == default['max_tokens']
            assert call['timeout_s'] == default['timeout_s']
            assert call['extra'] == {}
        # run.model_name stays the default model (documented).
        assert result['run'].model_name == default['model']
        models = {c['stage']: c['model_used'] for c in result['run'].sub_calls}
        assert models['objective'] == 'gpt-4o-mini'
