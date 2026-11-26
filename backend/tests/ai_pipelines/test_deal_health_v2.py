# backend/tests/ai_pipelines/test_deal_health_v2.py
"""
Sprint « Deal health v2 », step 5 — the « manager / coach » diagnostic v2:
Structured Outputs, the deal health's own model entry, stakeholder profiles
wired through stakeholder_service.apply_ai_profile.

Real path only: POST /module-ai-pipelines/deal-health/run/ with the real
DealHealthPipeline and the fake provider (tests/ai_pipelines/conftest.py),
which records the model, the response schema and the prompts it receives.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.decision_cycles.constants import PipelineStep
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus

from tests.ai_pipelines.test_deal_health_pipeline import _VALID_DIAGNOSTIC
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
    five_steps,
    planned_activity_on_step,
    completed_activity_on_step,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'


def _bant_item(status, reason):
    return {'status': status, 'reason': reason}


# A valid v2 answer: every v1 key kept as is (A5) + the v2 keys.
VALID_V2 = {
    **copy.deepcopy(_VALID_DIAGNOSTIC),
    'summary': 'Finance wants faster closing; budget owner not met yet.',
    'needs_and_urgency': {
        'status': 'suggested',
        'assessment': 'The need is recognised by finance; urgency is not proven.',
        'cost_of_inaction': 'Unknown',
    },
    'credibility': {'status': 'unclear', 'assessment': 'No proof shared yet.'},
    'fit_and_value': {
        'status': 'missing_evidence',
        'assessment': 'Requirements are not documented.',
        'requirements': ['SOC 2 report'],
        'competitive_position': 'Unknown',
    },
    'buying_process': {
        'assessment': 'Procurement involved after a business case.',
        'steps': ['Business case', 'Procurement review'],
        'timeline': 'Unknown',
    },
    'bant': {
        'budget': _bant_item('not_validated', 'No budget this fiscal year.'),
        'authority': _bant_item('unknown', 'Final decision-maker not identified.'),
        'need': _bant_item('validated', 'Finance confirmed the pain.'),
        'timeline': _bant_item('unknown', 'No date mentioned.'),
    },
    'strategic_conclusion': (
        'Find out when and by whom budgets are reallocated, then meet that '
        'person before the reallocation.'
    ),
    'levers_to_invest': [{'lever': 'value', 'why': 'Quantify the closing time.'}],
    'objectives': {
        'deal': 'Unknown',
        'next_activity': ['Identify the budget owner'],
    },
    'missing_info': [{
        'level': 'BUSINESS', 'item': 'Budget owner',
        'why_it_matters': 'BANT budget is not validated.',
        'suggested_question': 'Who decides on next year\'s budget?',
    }],
    'estimated_step': {
        'step': 'SOLUTION_VALIDATION',
        'reason': 'Technical criteria met; solution fit reached, validation not yet.',
    },
    'top_arguments': [{
        'target': 'Marc',
        'arguments': [{
            'need': 'Close faster', 'value': '5 days saved per month',
            'benefit': 'Less overtime', 'advantage': 'Automated matching',
            'feature': 'Reconciliation engine',
        }],
    }],
    'stakeholders': [
        {
            'ref': 'Marc',
            'conviction_state': 'SKEPTICAL',
            'convincing_metrics': 'Days to close',
            'frustrations': 'Manual reconciliation',
            'conviction_strategy': 'Show a peer case with numbers',
            'communication_style': 'Direct, numbers first',
            'communication_language': 'en',
        },
        {   # a label the server does not know: ignored, traced
            'ref': 'P9 Zed',
            'conviction_state': 'NEUTRAL',
            'convincing_metrics': '', 'frustrations': '', 'conviction_strategy': '',
            'communication_style': '', 'communication_language': '',
        },
    ],
}


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def technical_fit_cycle(cycle, five_steps, planned_activity_on_step, completed_activity_on_step):
    completed_activity_on_step(five_steps[0])
    planned_activity_on_step(five_steps[1])
    return cycle


@pytest.fixture
def marc(account, user_a, technical_fit_cycle):
    """« Marc Dupont », a validated stakeholder of the deal whose language
    was entered BY HAND ("fr")."""
    from app_modules.contacts.models import Contact
    from app_modules.decision_cycles.services.stakeholder_service import (
        apply_manual_profile,
        get_or_create_contact_stakeholder,
    )
    from app_modules.signals.models import PeopleSignal

    c = Contact(account=account, first_name='Marc', last_name='Dupont')
    c.save(user=user_a, client_id=account.client_id)
    s = PeopleSignal(
        account=account, decision_cycle=technical_fit_cycle, source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED, role=PeopleRole.CHAMPION, target_contact=c,
    )
    s.save(user=user_a, client_id=account.client_id)
    stakeholder = get_or_create_contact_stakeholder(technical_fit_cycle, c, user_a)
    apply_manual_profile(stakeholder, 'communication_language', 'fr', user_a)
    return stakeholder


def _provider(fake, reply):
    fake.replies['deal_health'] = json.dumps(reply)
    return fake


def _current_stage(cycle):
    from app_modules.activities.services.next_step_materialization import (
        current_decision_step,
    )
    step = current_decision_step(cycle)
    return step.stage if step else None


def _post(api, cycle):
    return api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')


# =============================================================================
# THE v2 RUN
# =============================================================================

def test_a_v2_run_persists_the_v2_snapshot_and_the_profiles(
    authed_api_a, technical_fit_cycle, marc, patch_active_provider,
):
    provider = _provider(patch_active_provider, VALID_V2)
    stage_before = _current_stage(technical_fit_cycle)

    resp = _post(authed_api_a, technical_fit_cycle)
    assert resp.status_code == 201, resp.content
    snapshot = resp.data['data']['snapshot']
    run = AIPipelineRun.objects.get(id=resp.data['data']['run']['run_id'])

    # The v2 snapshot
    assert snapshot['schema_version'] == 2
    assert snapshot['estimated_step'] == PipelineStep.SOLUTION_VALIDATION
    assert 'solution fit reached' in snapshot['estimated_step_reason']
    assert snapshot['diagnostic']['bant']['budget']['status'] == 'not_validated'

    # The profiles — through apply_ai_profile, with the run id
    marc.refresh_from_db()
    conviction = marc.profile['conviction_state']
    assert conviction['value'] == 'SKEPTICAL'
    assert conviction['source'] == SignalSource.LLM_EXTRACTED
    assert conviction['run_id'] == str(run.id)
    # ...never over a manual entry
    language = marc.profile['communication_language']
    assert (language['value'], language['source']) == ('fr', SignalSource.MANUAL)

    # The deal's step is NEVER changed
    assert _current_stage(technical_fit_cycle) == stage_before == PipelineStep.TECHNICAL_FIT

    # The deal health's own entry: the dedicated model, Structured Outputs
    [call] = provider.calls_for('deal_health')
    assert call['model'] == 'gpt-5.6-terra'
    assert call['extra'].get('reasoning_effort') == 'medium'
    schema = call['extra'].get('response_schema')
    assert schema and schema['name'] == 'deal_health_diagnostic_v2'

    # The unknown label: ignored, traced
    counts = run.sub_calls[-1]['persist_counts']
    assert counts['unknown_stakeholder_refs'] == ['P9 Zed']
    assert counts['profiles_written'] == 1


def test_b_the_v2_prompt_is_a_sales_coach_in_english_with_the_grid(
    authed_api_a, technical_fit_cycle, marc, patch_active_provider,
):
    provider = _provider(patch_active_provider, VALID_V2)
    assert _post(authed_api_a, technical_fit_cycle).status_code == 201

    [call] = provider.calls_for('deal_health')
    prompt = call['system'] + '\n' + call['user']
    lowered = prompt.lower()
    for term in ('needs and urgency', 'credibility', 'fit and value'):
        assert term in lowered
    for banned in ('ethos', 'pathos', 'logos'):
        assert banned not in lowered
    assert 'english' in lowered
    assert 'never invent' in lowered
    assert 'Declared step: TECHNICAL_FIT' in prompt
    assert 'SOLUTION_VALIDATION' in prompt and 'BUSINESS_CASE' in prompt   # the grid
    assert 'Dupont' not in prompt                                         # first names only


# =============================================================================
# AN INVALID v2: standard PARSE error, nothing written
# =============================================================================

def test_c_an_invalid_bant_is_a_parse_error_and_nothing_is_written(
    authed_api_a, technical_fit_cycle, marc, patch_active_provider,
):
    from app_modules.decision_cycles.models import DealHealthSnapshot

    invalid = copy.deepcopy(VALID_V2)
    invalid['bant']['budget']['status'] = 'maybe'
    _provider(patch_active_provider, invalid)

    resp = _post(authed_api_a, technical_fit_cycle)

    assert resp.status_code == 502, resp.content
    run = AIPipelineRun.objects.filter(source_decision_cycle=technical_fit_cycle).latest('created_at')
    assert run.status == AIPipelineStatus.PARSE_ERROR
    assert not DealHealthSnapshot.objects.filter(decision_cycle=technical_fit_cycle).exists()
    marc.refresh_from_db()
    assert 'conviction_state' not in marc.profile


# =============================================================================
# THE CURRENT PREP CALL STILL READS A v2 SNAPSHOT
# =============================================================================

def test_d_the_prep_call_reads_dimensions_and_global_reading_of_a_v2_snapshot(
    authed_api_a, technical_fit_cycle, marc, patch_active_provider,
):
    from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
        DealHealthEvidenceBuilder,
    )
    from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
        PrepInputPackAssembler,
    )

    _provider(patch_active_provider, VALID_V2)
    assert _post(authed_api_a, technical_fit_cycle).status_code == 201

    # The pack's maturity view (the prep call's single read of the snapshot —
    # since G10 no brief mode is resolved from it: the resolver is removed).
    maturity = PrepInputPackAssembler._maturity_of(
        DealHealthEvidenceBuilder.latest_snapshot(technical_fit_cycle),
    )
    assert maturity['global_reading'] == VALID_V2['global_reading']
    assert maturity['dimensions'] == VALID_V2['dimensions']


# =============================================================================
# PROVIDER SWITCH: « claude » is refused until its provider supports a schema
# =============================================================================

def test_e_a_provider_without_schema_support_is_refused_at_load(monkeypatch):
    # 5b: ClaudeProvider supports a schema now ('claude' with its key is
    # accepted — test_deal_health_claude.py); the schema guard is exercised
    # on a provider class that does not.
    from app_modules.ai_pipelines import config as ai_config
    from app_modules.ai_pipelines.pipelines import deal_health
    from app_modules.ai_pipelines.providers.claude_provider import ClaudeProvider

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-not-a-real-key')
    monkeypatch.setattr(ClaudeProvider, 'SUPPORTS_RESPONSE_SCHEMA', False)
    with pytest.raises(ImportError) as refused:
        deal_health.check_deal_health_provider('claude', ai_config.PROVIDER_CONFIG)
    assert 'SUPPORTS_RESPONSE_SCHEMA' in str(refused.value)

    # The current choice passes.
    deal_health.check_deal_health_provider('openai', ai_config.PROVIDER_CONFIG)


# =============================================================================
# THE TWO INPUT FORMATS (compared at step 7): same view, no id, first names
# =============================================================================

@pytest.mark.parametrize('input_format', ['sections', 'json'])
def test_f_both_input_formats_send_the_same_safe_view(
    technical_fit_cycle, marc, input_format,
):
    from app_modules.ai_pipelines.prompts.deal_health.context_v2 import (
        build_context_layer,
        llm_view,
    )
    from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
        DealHealthEvidenceBuilder,
    )

    pack = DealHealthEvidenceBuilder().build(technical_fit_cycle)
    rendered = build_context_layer(pack, input_format=input_format)

    assert str(technical_fit_cycle.id) not in rendered        # no id
    assert str(marc.id) not in rendered
    assert 'Dupont' not in rendered                            # first names only
    assert '"ref":"Marc"' in rendered                          # the stakeholder, by label
    assert '"communication_language":"fr"' in rendered        # its known profile
    if input_format == 'json':
        body = rendered.split('\n', 1)[1]
        assert json.loads(body) == json.loads(json.dumps(llm_view(pack), default=str))
