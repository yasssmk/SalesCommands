# backend/tests/ai_pipelines/test_deal_health_claude.py
"""
Sprint « Deal health v2 », sub-step 5b — the deal health on Claude, ready to
use: a key (ANTHROPIC_API_KEY, a secret of the .env) + ONE value of the
module's configuration (ai_pipelines/config.py DEAL_HEALTH_LLM_PROVIDER =
'claude' — amendment A11: a setting, never an environment variable).

Real path: POST /module-ai-pipelines/deal-health/run/ through the real view,
the real DealHealthPipeline and the REAL ClaudeProvider + anthropic SDK 1.x;
only the HTTP layer is simulated — an httpx2.MockTransport given to the SDK
client (no network call, no real key).

  (a) 'claude' + a key → the schema goes in output_config.format, no
      temperature, the dedicated model and effort, the refusal fallback;
      a v2 snapshot is written;
  (b) 'claude' without a key → a clear configuration message at load
      (pipelines/deal_health.check_deal_health_provider), the pattern of
      the provider guard;
  (c) Anthropic errors (timeout, rate limit, a non-conforming answer, a
      refusal) → the same run statuses and the same response as OpenAI;
  (d) the choice lives in ai_pipelines/config.py only: 'openai' by default,
      an environment variable has NO effect.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines import config as ai_config
from app_modules.ai_pipelines.constants import (
    AIPipelineStatus,
    DEAL_HEALTH_MAX_TOKENS,
    DEAL_HEALTH_PROVIDER_KEYS,
)
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v2 import (
    DEAL_HEALTH_RESPONSE_SCHEMA,
)
from app_modules.decision_cycles.models import DealHealthSnapshot

from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'


# =============================================================================
# The Anthropic HTTP layer, simulated under the real SDK
# =============================================================================

def _message(text, *, stop_reason='end_turn', model='claude-opus-5-5'):
    return {
        'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': model,
        'content': [{'type': 'text', 'text': text}],
        'stop_reason': stop_reason, 'stop_sequence': None,
        'usage': {'input_tokens': 1200, 'output_tokens': 800},
    }


class _Anthropic:
    """Records each request the SDK sends; answers with the queued replies
    (a dict → 200 JSON, an int → that HTTP status, an exception → raised)."""

    def __init__(self):
        self.requests = []
        self.replies = []

    def handler(self, request):
        import httpx2
        self.requests.append({
            'url': str(request.url),
            'headers': dict(request.headers),
            'body': json.loads(request.content or b'{}'),
        })
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, int):
            return httpx2.Response(reply, json={
                'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'slow down'},
            })
        return httpx2.Response(200, json=reply)


@pytest.fixture
def anthropic_api(monkeypatch):
    """config.DEAL_HEALTH_LLM_PROVIDER = 'claude' (the module's value) + a
    dummy key; the real ClaudeProvider builds the real SDK client, on a
    simulated transport."""
    import anthropic
    import httpx2
    from app_modules.ai_pipelines import providers as providers_pkg
    from app_modules.ai_pipelines.providers import claude_provider

    fake = _Anthropic()
    real_client = anthropic.Anthropic

    def client_on_mock_transport(*args, **kwargs):
        return real_client(
            *args, max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(fake.handler)),
            **kwargs,
        )

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-not-a-real-key')
    monkeypatch.setattr(claude_provider, 'Anthropic', client_on_mock_transport)
    monkeypatch.setattr(ai_config, 'DEAL_HEALTH_LLM_PROVIDER', 'claude')
    monkeypatch.setattr(providers_pkg, '_provider_instances', {})
    return fake


def _post(api, cycle):
    return api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')


def _run_of(resp):
    return AIPipelineRun.objects.get(id=resp.data['data']['run']['run_id'])


# =============================================================================
# (a) — the deal health on Claude
# =============================================================================

def test_a_claude_gets_the_schema_in_output_config_without_temperature(
    authed_api_a, cycle, anthropic_api,
):
    anthropic_api.replies = [_message(json.dumps(copy.deepcopy(V2_DIAGNOSTIC)))]

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 201, resp.content
    [sent] = anthropic_api.requests
    body = sent['body']
    assert body['model'] == ai_config.PROVIDER_CONFIG['claude_deal_health']['model'] == 'claude-opus-5-5'
    assert body['output_config']['format'] == {
        'type': 'json_schema', 'schema': DEAL_HEALTH_RESPONSE_SCHEMA['schema'],
    }
    assert body['output_config']['effort'] == 'medium'
    assert 'temperature' not in body
    assert body['max_tokens'] == DEAL_HEALTH_MAX_TOKENS
    assert body['system'] and body['messages'][0]['role'] == 'user'
    # The server-side refusal fallback (recommended default for this model).
    assert body['fallbacks'] == 'default'
    assert 'server-side-fallback-2026-07-01' in sent['headers'].get('anthropic-beta', '')
    # The v2 snapshot, written as with OpenAI.
    snapshot = DealHealthSnapshot.objects.get(id=resp.data['data']['snapshot']['id'])
    assert snapshot.schema_version == 2
    run = _run_of(resp)
    assert run.status == AIPipelineStatus.SUCCESS
    assert run.model_name == 'claude-opus-5-5'


# =============================================================================
# (b) — 'claude' without a key: a clear configuration message
# =============================================================================

def test_b_claude_without_a_key_is_a_clear_configuration_error(monkeypatch):
    from app_modules.ai_pipelines.pipelines.deal_health import check_deal_health_provider

    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(ImportError) as err:
        check_deal_health_provider('claude', ai_config.PROVIDER_CONFIG)
    message = str(err.value)
    assert 'ANTHROPIC_API_KEY' in message
    assert 'DEAL_HEALTH_LLM_PROVIDER' in message


def test_b_claude_with_a_key_is_accepted(monkeypatch):
    from app_modules.ai_pipelines.pipelines.deal_health import check_deal_health_provider

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-not-a-real-key')
    assert check_deal_health_provider('claude', ai_config.PROVIDER_CONFIG) == 'claude_deal_health'


# =============================================================================
# (c) — Anthropic errors → the same statuses / response as OpenAI
# =============================================================================

def _timeout():
    import httpx2
    return httpx2.ReadTimeout('simulated read timeout')


@pytest.mark.parametrize('reply, status, label', [
    (_timeout, AIPipelineStatus.TIMEOUT, 'timeout'),
    (lambda: 429, AIPipelineStatus.LLM_ERROR, 'rate_limit'),
    (lambda: _message('This is not JSON at all.'), AIPipelineStatus.PARSE_ERROR, 'parse_error'),
    (lambda: _message('{}', stop_reason='refusal'), AIPipelineStatus.LLM_ERROR, 'provider_error'),
    (lambda: _message('{"summary": "cut', stop_reason='max_tokens'),
     AIPipelineStatus.LLM_ERROR, 'provider_error'),
])
def test_c_anthropic_errors_map_to_the_openai_statuses(
    authed_api_a, cycle, anthropic_api, reply, status, label,
):
    anthropic_api.replies = [reply()]

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 502, resp.content          # as OpenAI (deal_health_view)
    assert resp.data['success'] is False
    run = _run_of(resp)
    assert run.status == status
    assert run.error_message.startswith(f'{label}:')
    assert DealHealthSnapshot.objects.filter(decision_cycle=cycle).count() == 0


# =============================================================================
# (d) — the choice lives in the module's configuration, never in the env
# =============================================================================

def test_d_the_choice_is_read_in_the_module_config_and_the_env_has_no_effect(monkeypatch):
    import importlib
    from django.conf import settings
    from app_modules.ai_pipelines import constants

    # ONE source: ai_pipelines/config.py — no setting, no constant beside it.
    assert ai_config.DEAL_HEALTH_LLM_PROVIDER == 'openai'
    assert not hasattr(settings, 'DEAL_HEALTH_LLM_PROVIDER')
    assert not hasattr(constants, 'DEAL_HEALTH_LLM_PROVIDER')
    assert DEAL_HEALTH_PROVIDER_KEYS['openai'] == 'openai_deal_health'

    # An environment variable of that name changes nothing, even when the
    # configuration is (re)loaded with it set.
    monkeypatch.setenv('DEAL_HEALTH_LLM_PROVIDER', 'claude')
    try:
        importlib.reload(ai_config)
        assert ai_config.DEAL_HEALTH_LLM_PROVIDER == 'openai'
    finally:
        monkeypatch.delenv('DEAL_HEALTH_LLM_PROVIDER')
        importlib.reload(ai_config)
