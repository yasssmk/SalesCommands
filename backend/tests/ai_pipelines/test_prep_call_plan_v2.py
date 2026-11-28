# backend/tests/ai_pipelines/test_prep_call_plan_v2.py
"""
Sprint 2 Game Plan — sub-step G10: the prompts v2 and the strict « plan »
schema, the heart of the sprint.

Before: the prep call sent the v1 prompts (a coach's tactical brief, a brief
mode resolved from a SECOND read of the deal-health snapshot in the view, a
rhetoric register named to the LLM) WITHOUT any response_schema, validated
the v1 keys only (objectives.nature ETHOS...), and wrote schema_version 1.

Now:
  * prompts/prep_call/system_v2 / context_v2 / outline_v2 (v1 kept, frozen);
    the deal health v2's output-language rule, imported
    (prompts/output_language.py);
  * PREP_CALL_OUTLINE_SCHEMA sent as the strict response schema — the 7
    sections, product_pitch, participants [{ref, angle}],
    campaign_diagnostic;
  * validated server side (services/prep_call/plan_validator.py): a
    last name of the roster is REFUSED (a classical rhetoric label too until
    G13g — no longer)
    (PARSE_ERROR, nothing written); a ref that is not one participant's
    exact label (G4 roster) is DROPPED, never guessed — traced;
    campaign_diagnostic is null except for a campaign activity outside a
    cycle;
  * persisted in schema_version 2 with its deal-health trace, no brief_mode;
  * no brief mode: the mode resolver and the view's second deal-health read
    are gone.

Real path: POST /module-ai-pipelines/prep-call/run/ (real view and
pipeline); the fake provider records the call options it receives.

DB: Postgres.
"""

import copy
import json
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot

from tests.ai_pipelines.test_prep_call_activity_roster import scene  # noqa: F401
from tests.ai_pipelines.test_prep_call_campaign_context import sequence  # noqa: F401
from tests.ai_pipelines.test_prep_call_dh_snapshot_tenant import _snapshot


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'

# A valid Game Plan v2 — the participants' refs are filled per scene.
_PLAN = {
    'context': 'Business case review with the finance team.',
    'objective': {'plans': [
        {'label': 'A', 'goal': 'Validate the business case.',
         'success_criteria': 'They agree on the figures to present.'},
        {'label': 'B', 'goal': 'Learn who signs.', 'success_criteria': 'The signer is named.'},
    ]},
    'client_expectations': ['A clear view of the month-end close.'],
    'opening': {
        'objective': 'Agree on the business case.', 'time': 'Ask for 45 minutes.',
        'client_agenda': 'Ask what they need to decide.', 'our_agenda': 'The close, then the case.',
        'expected_outcome': 'A date to present it to the board.',
    },
    'discovery': {
        'missing_info': [{'item': 'The signer', 'question': 'Who signs this?'}],
        'conviction': {
            'needs_and_urgency': {'reading': 'The close takes ten days.',
                                  'question': 'What does a late close cost you?'},
            'credibility': {'reading': 'Unknown.', 'question': 'What proof do you need?'},
            'fit_and_value': {'reading': 'Unknown.', 'question': 'Which step hurts most?'},
        },
    },
    'argumentation': [],
    'closing': {
        'next_step': 'Present the case to the board.', 'with_whom': 'Marc.',
        'when': 'Two dates next week.', 'keep_control': 'Send the invitation today.',
    },
    'product_pitch': [],
    'participants': [],
    'campaign_diagnostic': None,
}


def _answer(**overrides):
    answer = copy.deepcopy(_PLAN)
    answer.update(copy.deepcopy(overrides))
    return answer


def _labels(activity):
    """The participants' labels — the G4 roster the pack is built from."""
    from app_modules.ai_pipelines.services.llm_people import activity_roster
    return [p['label'] for p in activity_roster(activity).participants]


def _post(api, activity, provider, answer, status=201):
    """A refused answer is a failed run: the view's existing 502 (a real
    technical error — the run is PARSE_ERROR, nothing written)."""
    provider.replies['prep_call'] = json.dumps(answer)
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == status, resp.content
    return AIPipelineRun.objects.filter(source_activity=activity).latest('created_at')


def _snapshot_of(activity):
    return PrepCallSnapshot.objects.filter(activity=activity).first()


# =============================================================================
# REPRO 1 — the plan schema is sent
# =============================================================================

def test_the_plan_schema_is_sent_as_the_response_schema(authed_api_a, scene, patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_answer())
    resp = authed_api_a.post(RUN_URL, {'activity_id': str(scene['meeting'].id)}, format='json')

    [call] = patch_active_provider.calls_for('prep_call')
    sent = call['extra'].get('response_schema')
    assert sent is not None, call['extra']                 # before G10: none was sent
    assert resp.status_code == 201, resp.content
    from app_modules.ai_pipelines.prompts.prep_call import PREP_CALL_OUTLINE_SCHEMA
    assert sent == PREP_CALL_OUTLINE_SCHEMA
    schema = PREP_CALL_OUTLINE_SCHEMA['schema']
    assert set(schema['required']) == {
        'context', 'objective', 'client_expectations', 'opening', 'discovery',
        'argumentation', 'closing', 'product_pitch', 'participants', 'campaign_diagnostic',
    }
    assert 'nature' not in json.dumps(schema)          # the ETHOS nature is gone


# =============================================================================
# REPRO 2 — a last name is refused; a rhetoric label no longer is (G13g)
# =============================================================================

@pytest.mark.parametrize('label', ['ethos', 'Pathos', 'LOGOS'])
def test_a_rhetoric_label_is_no_longer_refused(authed_api_a, scene, patch_active_provider, label):
    """G13g (PO decision of 28/11): ethos / pathos / logos are the prompt's
    INTERNAL frame — the evaluation measures they do not show in the output;
    the server no longer refuses them (renamed from
    test_a_rhetoric_label_is_refused)."""
    answer = _answer(context=f'Lead with {label}: their own story first.')

    run = _post(authed_api_a, scene['meeting'], patch_active_provider, answer)

    assert run.status == AIPipelineStatus.SUCCESS, run.error_message
    assert _snapshot_of(scene['meeting']) is not None


@pytest.mark.parametrize('name', ['Dupont', 'durand', 'Martin'])
def test_a_last_name_is_refused(authed_api_a, scene, patch_active_provider, name):
    """Dupont / Durand: the participants' contacts; Martin: Lea Martin, a
    stakeholder without contact — whatever the case."""
    answer = _answer(closing={**_PLAN['closing'], 'with_whom': f'Marc {name}.'})

    run = _post(authed_api_a, scene['meeting'], patch_active_provider, answer, status=502)

    assert run.status == AIPipelineStatus.PARSE_ERROR
    assert 'last name' in run.error_message
    assert name.lower() not in run.error_message.lower()   # never logged
    assert _snapshot_of(scene['meeting']) is None


# =============================================================================
# REPRO 3 — a ref outside the roster is dropped, never guessed
# =============================================================================

def test_a_ref_outside_the_roster_is_dropped(authed_api_a, scene, patch_active_provider):
    marc_1, marc_2, lea = _labels(scene['meeting'])
    answer = _answer(
        participants=[
            {'ref': marc_1, 'angle': 'The numbers of the close.'},
            {'ref': 'Bill', 'angle': 'Another account.'},        # outside the roster
            {'ref': 'Marc', 'angle': 'Which Marc?'},             # homonym: no exact label
            {'ref': lea, 'angle': 'The users.'},
            {'ref': lea, 'angle': 'Twice.'},                      # ambiguous
        ],
        argumentation=[
            {'ref': marc_2, 'arguments': [{'benefit': 'A faster close.',
                                           'advantage': 'No manual export.',
                                           'feature': 'The reporting module.'}]},
            {'ref': 'Zoe', 'arguments': []},
        ],
    )

    run = _post(authed_api_a, scene['meeting'], patch_active_provider, answer)

    assert run.status == AIPipelineStatus.SUCCESS, run.error_message
    plan = _snapshot_of(scene['meeting']).brief
    assert [p['ref'] for p in plan['participants']] == [marc_1]
    assert [a['ref'] for a in plan['argumentation']] == [marc_2]
    [sub_call] = run.sub_calls
    assert sub_call['persist_counts'] == {
        'unknown_refs': ['Bill', 'Marc', 'Zoe'], 'ambiguous_refs': [lea, lea],
    }


# =============================================================================
# REPRO 4 — a valid plan is persisted in schema_version 2 with its DH trace
# =============================================================================

def test_a_valid_plan_is_persisted_in_schema_v2_with_its_deal_health_trace(
    authed_api_a, scene, patch_active_provider, user_a,
):
    meeting = scene['meeting']
    dh = _snapshot(scene['cycle'], user_a, 'The close is the pain.', 'confirmed',
                   client_id=meeting.client_id)
    marc_1, _marc_2, lea = _labels(meeting)
    answer = _answer(participants=[{'ref': marc_1, 'angle': 'Figures.'},
                                   {'ref': lea, 'angle': 'Users.'}])

    run = _post(authed_api_a, meeting, patch_active_provider, answer)

    assert run.status == AIPipelineStatus.SUCCESS, run.error_message
    assert run.prompt_versions == {'system': 'v2.2', 'context': 'v2', 'outline': 'v2.1'}
    snapshot = _snapshot_of(meeting)
    assert snapshot.schema_version == 2
    assert snapshot.brief_mode is None
    assert snapshot.brief == answer
    assert snapshot.deal_health_snapshot_id == dh.id
    assert snapshot.deal_health_schema_version == dh.schema_version


# =============================================================================
# campaign_diagnostic — null except for a campaign activity outside a cycle
# =============================================================================

_DIAGNOSTIC = {'reading': 'Two unanswered calls.', 'next_move': 'Try an email.'}


def test_campaign_diagnostic_is_null_in_a_cycle(authed_api_a, scene, patch_active_provider):
    run = _post(authed_api_a, scene['meeting'], patch_active_provider,
                _answer(campaign_diagnostic=_DIAGNOSTIC))

    assert run.status == AIPipelineStatus.SUCCESS, run.error_message
    assert _snapshot_of(scene['meeting']).brief['campaign_diagnostic'] is None


def test_campaign_diagnostic_is_kept_for_a_campaign_activity_outside_a_cycle(
    authed_api_a, sequence, patch_active_provider,
):
    run = _post(authed_api_a, sequence['current'], patch_active_provider,
                _answer(campaign_diagnostic=_DIAGNOSTIC))

    assert run.status == AIPipelineStatus.SUCCESS, run.error_message
    assert _snapshot_of(sequence['current']).brief['campaign_diagnostic'] == _DIAGNOSTIC


# =============================================================================
# THE PROMPT v2 — posture, rules, no brief mode, no classical label
# =============================================================================

def test_the_prompt_is_the_v2(authed_api_a, scene, patch_active_provider):
    from app_modules.ai_pipelines.prompts.output_language import OUTPUT_LANGUAGE_RULE

    _post(authed_api_a, scene['meeting'], patch_active_provider, _answer())

    [call] = patch_active_provider.calls_for('prep_call')
    system, user = call['system'], call['user']
    assert 'excellent B2B account executive' in system
    assert '70%' in system and '30%' in system
    assert OUTPUT_LANGUAGE_RULE in system                 # the deal health v2's rule
    assert 'NEVER INVENT' in system and 'percentage' in system
    assert 'BRIEF MODE' not in user and 'DOMINANT REGISTER' not in user
    for text in (system, user):
        assert not re.search(r'\b(ethos|pathos|logos)\b', text, re.IGNORECASE)


def test_the_persuasion_guide_names_no_classical_label():
    import inspect

    from app_modules.ai_pipelines.services.prep_call import rhetoric_guide
    source = inspect.getsource(rhetoric_guide).lower()
    for word in ('ethos', 'pathos', 'logos', 'epideictic', 'deliberative',
                 'demonstrative', 'aphoristic', 'brief_mode', 'discovery_mode'):
        assert word not in source, word


def test_the_deal_health_reads_the_shared_language_rule():
    from app_modules.ai_pipelines.prompts.deal_health.system_v2_1 import SYSTEM_PROMPT
    from app_modules.ai_pipelines.prompts.output_language import OUTPUT_LANGUAGE_RULE
    assert f'10. {OUTPUT_LANGUAGE_RULE}\n' in SYSTEM_PROMPT


def test_the_view_reads_the_deal_health_snapshot_once(
    authed_api_a, scene, patch_active_provider, user_a,
):
    _snapshot(scene['cycle'], user_a, 'Reading.', 'confirmed', client_id=scene['meeting'].client_id)
    patch_active_provider.replies['prep_call'] = json.dumps(_answer())

    with CaptureQueriesContext(connection) as ctx:
        resp = authed_api_a.post(RUN_URL, {'activity_id': str(scene['meeting'].id)}, format='json')

    assert resp.status_code == 201, resp.content
    reads = [q['sql'] for q in ctx.captured_queries
             if q['sql'].startswith('SELECT') and 'FROM "deal_health_snapshots"' in q['sql']]
    assert len(reads) == 1, reads


def test_the_mode_resolver_is_gone():
    import importlib.util
    assert importlib.util.find_spec(
        'app_modules.ai_pipelines.services.prep_call.mode_resolver') is None


# =============================================================================
# THE BOUNDS — validate_plan
# =============================================================================

def _validate(answer):
    from app_modules.ai_pipelines.services.prep_call.plan_validator import validate_plan
    return validate_plan(answer, people=None, last_names=frozenset(), has_campaign=False)


@pytest.mark.parametrize('labels', [[], ['B'], ['A', 'C'], ['A', 'B', 'C', 'C']])
def test_the_plans_are_a_b_c_in_order_three_at_most(labels):
    from app_modules.ai_pipelines.prompts.base import PromptParseError
    plans = [{'label': x, 'goal': 'g', 'success_criteria': 's'} for x in labels]
    with pytest.raises(PromptParseError):
        _validate(_answer(objective={'plans': plans}))


def test_three_plans_pass():
    plans = [{'label': x, 'goal': 'g', 'success_criteria': 's'} for x in 'ABC']
    plan, _counts = _validate(_answer(objective={'plans': plans}))
    assert [p['label'] for p in plan['objective']['plans']] == ['A', 'B', 'C']


def test_at_most_three_arguments_per_participant():
    from app_modules.ai_pipelines.prompts.base import PromptParseError
    argument = {'benefit': 'b', 'advantage': 'a', 'feature': 'f'}
    with pytest.raises(PromptParseError):
        _validate(_answer(argumentation=[{'ref': 'Marc', 'arguments': [argument] * 4}]))


def test_without_a_roster_every_ref_is_dropped():
    plan, counts = _validate(_answer(participants=[{'ref': 'Marc', 'angle': 'a'}]))
    assert plan['participants'] == [] and counts['unknown_refs'] == ['Marc']
