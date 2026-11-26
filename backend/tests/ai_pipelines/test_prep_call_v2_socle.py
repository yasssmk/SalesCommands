# backend/tests/ai_pipelines/test_prep_call_v2_socle.py
"""
Sprint 2 Game Plan — sub-step G2 (the socle).

1. The prep call's LLM provider is chosen in ai_pipelines/config.py, on the
   deal health's exact pattern: config.PREP_CALL_LLM_PROVIDER ('openai' |
   'claude') -> constants.PREP_CALL_PROVIDER_KEYS -> its own PROVIDER_CONFIG
   entry (openai_prep_call / claude_prep_call), checked at load
   (pipelines/prep_call.check_prep_call_provider). Before: the prep call ran
   on the ACTIVE provider, whatever its needs, with no check (TD-319).
2. PrepCallSnapshot v2: schema_version (default 1), output_kind (PLAN /
   MESSAGE), the deal-health snapshot read (FK SET_NULL) and its
   schema_version, brief_mode optional with its choices in constants. The
   existing snapshots stay readable as v1 PLAN.

Real path: POST /module-ai-pipelines/prep-call/run/ (real view, real
PrepCallPipeline) and GET /module-ai-pipelines/prep-call/by-activity/<id>/;
OpenAI through the fake provider, Claude through the real ClaudeProvider and
the real anthropic SDK on a simulated transport (test_deal_health_claude.py's
fixture). The MESSAGE snapshot (written by the pipeline only from G11) is
seeded through the ORM.

DB: Postgres.
"""

import json

import pytest

from app_modules.ai_pipelines import config as ai_config
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot

from tests.ai_pipelines.test_deal_health_claude import _message, anthropic_api  # noqa: F401
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


@pytest.fixture
def activity(account, user_a):
    return _preparable_activity(account, user_a)


def _run(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return resp


def _served(api, activity):
    resp = api.get(f'/module-ai-pipelines/prep-call/by-activity/{activity.id}/')
    assert resp.status_code == 200, resp.content
    return resp.json()['data']


# =============================================================================
# 1 — the provider, chosen in config.py like the deal health
# =============================================================================

def test_on_openai_the_prep_call_uses_its_own_entry(authed_api_a, activity, patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)

    resp = _run(authed_api_a, activity)

    run = AIPipelineRun.objects.get(id=resp.json()['data']['run']['run_id'])
    entry = ai_config.PROVIDER_CONFIG.get('openai_prep_call')
    assert entry is not None, 'no PROVIDER_CONFIG entry of its own'
    assert run.provider == 'openai'
    assert run.model_name == entry['model']


def test_on_claude_the_prep_call_runs_on_its_claude_entry(
    authed_api_a, activity, anthropic_api, monkeypatch, patch_active_provider,
):
    # patch_active_provider: the ACTIVE (OpenAI) path is a fake — never a real call.
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    monkeypatch.setattr(ai_config, 'PREP_CALL_LLM_PROVIDER', 'claude', raising=False)
    anthropic_api.replies = [_message(json.dumps(_VALID_BRIEF))]

    resp = _run(authed_api_a, activity)

    run = AIPipelineRun.objects.get(id=resp.json()['data']['run']['run_id'])
    entry = ai_config.PROVIDER_CONFIG.get('claude_prep_call')
    assert entry is not None, 'no PROVIDER_CONFIG entry of its own'
    assert run.provider == 'claude'
    assert run.model_name == entry['model']
    [sent] = anthropic_api.requests                  # the call really went to Claude
    assert sent['body']['model'] == entry['model']
    assert patch_active_provider.calls == []


def test_an_unknown_provider_choice_is_a_clear_configuration_error():
    from app_modules.ai_pipelines.pipelines.prep_call import check_prep_call_provider

    with pytest.raises(ImportError) as err:
        check_prep_call_provider('mistral', ai_config.PROVIDER_CONFIG)
    assert 'PREP_CALL_LLM_PROVIDER' in str(err.value)


def test_claude_without_a_key_is_a_clear_configuration_error(monkeypatch):
    from app_modules.ai_pipelines.pipelines.prep_call import check_prep_call_provider

    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(ImportError) as err:
        check_prep_call_provider('claude', ai_config.PROVIDER_CONFIG)
    assert 'ANTHROPIC_API_KEY' in str(err.value)
    assert 'PREP_CALL_LLM_PROVIDER' in str(err.value)


def test_claude_with_a_key_is_accepted(monkeypatch):
    from app_modules.ai_pipelines.pipelines.prep_call import check_prep_call_provider

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-not-a-real-key')
    assert check_prep_call_provider('claude', ai_config.PROVIDER_CONFIG) == 'claude_prep_call'


def test_the_shipped_choice_is_openai():
    assert ai_config.PREP_CALL_LLM_PROVIDER == 'openai'


# =============================================================================
# 2 — PrepCallSnapshot v2, the existing snapshots readable as v1
# =============================================================================

def test_a_snapshot_written_today_reads_as_v1_plan(authed_api_a, activity, patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    _run(authed_api_a, activity)

    served = _served(authed_api_a, activity)

    assert served['schema_version'] == 1
    assert served['output_kind'] == 'PLAN'
    assert served['deal_health_snapshot'] is None
    assert served['deal_health_schema_version'] is None
    assert served['brief_mode'] == 'DISCOVERY'
    assert served['brief'] == _VALID_BRIEF


def test_a_message_snapshot_has_no_brief_mode(authed_api_a, activity, user_a):
    """brief_mode is optional (v2 drops the mode, G10); a MESSAGE snapshot
    (written by the pipeline from G11 — seeded here) is stored and served."""
    snap = PrepCallSnapshot(activity=activity, brief={'messages': []}, input_hash='h' * 64,
                            schema_version=2, output_kind='MESSAGE')
    snap.save(user=user_a, client_id=activity.client_id)

    served = _served(authed_api_a, activity)

    assert served['id'] == str(snap.id)
    assert served['schema_version'] == 2
    assert served['output_kind'] == 'MESSAGE'
    assert served['brief_mode'] is None
