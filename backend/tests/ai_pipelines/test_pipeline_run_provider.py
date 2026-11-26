# backend/tests/ai_pipelines/test_pipeline_run_provider.py
"""
Sprint 2 Game Plan — sub-step G1 (defect): the run row records the provider
REALLY used.

Before: BasePipeline._create_run wrote `provider=ACTIVE_PROVIDER`
(pipelines/base.py:179) whatever the pipeline's own PROVIDER_CONFIG entry.
A deal health on Claude (config.DEAL_HEALTH_LLM_PROVIDER = 'claude' ->
PROVIDER_CONFIG['claude_deal_health']) left a run with provider='openai'
next to model_name='claude-opus-5-5'; the same for the next-steps pipeline
on its own entry (config.NEXT_STEPS_PROVIDER).

Now: the run records the provider family of the entry the pipeline calls
(`PROVIDER_CONFIG[<its key>]['provider']`, the key itself for the plain
'openai' / 'claude' entries) — BasePipeline._provider_key, set by each
pipeline that owns an entry.

Real path for the deal health: POST /module-ai-pipelines/deal-health/run/,
the real ClaudeProvider and the real anthropic SDK on a simulated transport
(the anthropic_api fixture of test_deal_health_claude.py); OpenAI through
the fake provider. The next-steps pipeline (which runs inside the extraction
flow) is checked on its run row opened by the pipeline itself.

DB: Postgres.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines import config as ai_config
from app_modules.ai_pipelines.models import AIPipelineRun

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.ai_pipelines.test_deal_health_claude import _message, anthropic_api  # noqa: F401
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


def _run_of(resp):
    assert resp.status_code == 201, resp.content
    return AIPipelineRun.objects.get(id=resp.data['data']['run']['run_id'])


def test_a_deal_health_on_claude_records_claude(authed_api_a, cycle, anthropic_api):
    anthropic_api.replies = [_message(json.dumps(copy.deepcopy(V2_DIAGNOSTIC)))]

    run = _run_of(authed_api_a.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json'))

    assert run.provider == 'claude'
    assert run.model_name == ai_config.PROVIDER_CONFIG['claude_deal_health']['model']


def test_a_deal_health_on_openai_still_records_openai(authed_api_a, cycle, patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))

    run = _run_of(authed_api_a.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json'))

    assert run.provider == 'openai'
    assert run.model_name == ai_config.PROVIDER_CONFIG['openai_deal_health']['model']


def test_the_next_steps_pipeline_records_its_own_entry_provider(
    activity, user_a, monkeypatch, patch_active_provider,
):
    """NEXT_STEPS_PROVIDER pointed at a Claude entry: the run says 'claude'
    (an injected provider serves the call; the row reads the entry)."""
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline

    monkeypatch.setattr(ai_config, 'NEXT_STEPS_PROVIDER', 'claude_deal_health')
    pipeline = NextStepsPipeline(provider=patch_active_provider)
    run = pipeline._create_run(
        user=user_a, client_id=activity.client_id,
        source_activity=activity, input_text='transcript',
    )

    assert run.provider == 'claude'
    assert run.model_name == ai_config.PROVIDER_CONFIG['claude_deal_health']['model']
