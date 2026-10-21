# backend/tests/ai_pipelines/test_provider_contract.py
"""
TD-279 P0 — extended LLMProvider contract (real provider classes, SDK client
mocked; no network).

  * OpenAI, structured + reasoning call: response_format json_schema strict,
    reasoning_effort, max_completion_tokens, NO temperature / max_tokens;
    reasoning tokens reported.
  * OpenAI, default call: EXACTLY the arguments sent today (non-regression).
  * OpenAI, structured / reasoning mode: truncation (finish_reason "length")
    and refusal -> LLMProviderError (standard exception); the default mode
    keeps returning the content (parse retry downstream, unchanged).
  * Claude: a schema or a reasoning effort -> LLMProviderError "not
    supported"; default call unchanged.
  * Pipeline audit: reasoning tokens recorded in the sub_call only when the
    API reports some (default entries unchanged).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app_modules.ai_pipelines.providers.base import LLMCallResult, LLMProviderError
from app_modules.ai_pipelines.providers.claude_provider import ClaudeProvider
from app_modules.ai_pipelines.providers.openai_provider import OpenAIProvider


SCHEMA = {
    'name': 'people_inventory',
    'schema': {
        'type': 'object',
        'properties': {'persons': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['persons'],
        'additionalProperties': False,
    },
}
BASE_ARGS = dict(system='SYS', user='USR', model='a-model', max_tokens=123, timeout_s=9)


def _openai_response(*, content='{"persons": []}', finish_reason='stop', refusal=None,
                     reasoning_tokens=None):
    details = (SimpleNamespace(reasoning_tokens=reasoning_tokens)
               if reasoning_tokens is not None else None)
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, refusal=refusal),
            finish_reason=finish_reason,
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20,
                              completion_tokens_details=details),
        model='a-model-2026',
    )


def _openai(response):
    provider = OpenAIProvider.__new__(OpenAIProvider)   # no OPENAI_API_KEY needed
    provider._client = MagicMock()
    provider._client.chat.completions.create.return_value = response
    return provider


def _sent(provider):
    return provider._client.chat.completions.create.call_args.kwargs


class TestOpenAIStructuredReasoning:

    def test_a_schema_and_effort(self):
        provider = _openai(_openai_response(reasoning_tokens=7))
        result = provider.call(**BASE_ARGS, temperature=0.0,
                               response_schema=SCHEMA, reasoning_effort='medium')
        sent = _sent(provider)
        assert sent['response_format'] == {
            'type': 'json_schema',
            'json_schema': {'name': SCHEMA['name'], 'schema': SCHEMA['schema'], 'strict': True},
        }
        assert sent['reasoning_effort'] == 'medium'
        assert sent['max_completion_tokens'] == 123
        assert 'temperature' not in sent
        assert 'max_tokens' not in sent
        assert result.reasoning_tokens == 7

    def test_temperature_none_is_not_sent(self):
        provider = _openai(_openai_response())
        provider.call(**BASE_ARGS, temperature=None)
        assert 'temperature' not in _sent(provider)

    @pytest.mark.parametrize('extra', [
        {'response_schema': SCHEMA}, {'reasoning_effort': 'medium'},
    ])
    def test_c_truncated_answer_is_a_provider_error(self, extra):
        provider = _openai(_openai_response(finish_reason='length'))
        with pytest.raises(LLMProviderError, match='truncated'):
            provider.call(**BASE_ARGS, temperature=0.0, **extra)

    def test_c_refusal_is_a_provider_error(self):
        provider = _openai(_openai_response(content=None, refusal='I cannot help with that.'))
        # The refusal itself is named -- not the generic empty-content error.
        with pytest.raises(LLMProviderError, match='refused'):
            provider.call(**BASE_ARGS, temperature=0.0, response_schema=SCHEMA)


class TestOpenAIDefaultUnchanged:

    def test_b_default_call_sends_exactly_todays_arguments(self):
        provider = _openai(_openai_response())
        result = provider.call(**BASE_ARGS, temperature=0.0)
        assert _sent(provider) == {
            'model': 'a-model',
            'messages': [
                {'role': 'system', 'content': 'SYS'},
                {'role': 'user', 'content': 'USR'},
            ],
            'temperature': 0.0,
            'max_tokens': 123,
            'timeout': 9,
        }
        assert result.content == '{"persons": []}'

    def test_default_call_reports_zero_reasoning_tokens(self):
        provider = _openai(_openai_response())
        assert provider.call(**BASE_ARGS, temperature=0.0).reasoning_tokens == 0

    def test_b_default_truncated_answer_still_returns_the_content(self):
        provider = _openai(_openai_response(content='{"persons": [', finish_reason='length'))
        assert provider.call(**BASE_ARGS, temperature=0.0).content == '{"persons": ['


def _claude():
    provider = ClaudeProvider.__new__(ClaudeProvider)   # no ANTHROPIC_API_KEY needed
    provider._client = MagicMock()
    provider._client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text='{"persons": []}')],
        usage=SimpleNamespace(input_tokens=1, output_tokens=2),
        model='a-model',
    )
    return provider


class TestClaude:

    @pytest.mark.parametrize('extra', [
        {'response_schema': SCHEMA}, {'reasoning_effort': 'medium'},
    ])
    def test_d_schema_or_effort_is_not_supported(self, extra):
        provider = _claude()
        with pytest.raises(LLMProviderError, match='not supported'):
            provider.call(**BASE_ARGS, temperature=0.0, **extra)
        provider._client.messages.create.assert_not_called()

    def test_default_call_unchanged(self):
        provider = _claude()
        provider.call(**BASE_ARGS, temperature=0.0)
        sent = provider._client.messages.create.call_args.kwargs
        assert sent == {
            'model': 'a-model', 'system': 'SYS',
            'messages': [{'role': 'user', 'content': 'USR'}],
            'temperature': 0.0, 'max_tokens': 123, 'timeout': 9,
        }


class TestReasoningTokensAudit:

    @staticmethod
    def _result(**extra):
        return LLMCallResult(content='{}', input_tokens=1, output_tokens=2,
                             model_used='m', duration_ms=3, **extra)

    def test_meta_carries_reasoning_tokens_only_when_reported(self):
        from app_modules.ai_pipelines.pipelines.base import BasePipeline
        assert BasePipeline._meta_from_result(self._result(reasoning_tokens=5), attempt=1)[
            'reasoning_tokens'] == 5
        assert 'reasoning_tokens' not in BasePipeline._meta_from_result(self._result(), attempt=1)

    def test_sub_call_entry_records_them_and_default_entry_is_unchanged(self):
        from app_modules.ai_pipelines.pipelines.base import BasePipeline
        pipeline = SimpleNamespace()  # _log_sub_call only uses its arguments
        run = SimpleNamespace(sub_calls=[], total_tokens_used=0, total_duration_ms=0,
                              save=lambda: None)
        BasePipeline._log_sub_call(pipeline, run, stage='people', sub_call_meta=BasePipeline._meta_from_result(
            self._result(reasoning_tokens=5), attempt=1))
        BasePipeline._log_sub_call(pipeline, run, stage='pain', sub_call_meta=BasePipeline._meta_from_result(
            self._result(), attempt=1))
        assert run.sub_calls[0]['reasoning_tokens'] == 5
        assert 'reasoning_tokens' not in run.sub_calls[1]
