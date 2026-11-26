# backend/tests/ai_pipelines/test_objective_success_criteria_notes.py
"""
Sprint 2 Game Plan — sub-step G5 (TD-219): the extraction emits the
Objective's `success_criteria` and `notes`.

Before: the Objective prompt (objective_v1.py, version v2) had neither field
in its output schema, and the parser (transcript_signal_extractor.py
_build_objective_data) never mapped them: an extracted Objective always had
success_criteria = '' and notes = '' — the « How is success measured? »
section of the objective stayed empty unless the rep typed it.

Now: prompt objective_v3.py (v1 kept, the next_steps_v3 pattern — built from
the previous text) asks for
  * success_criteria — what the prospect SAID would show the objective is
    met, verbatim or near-verbatim, else "" — never invented;
  * notes — the context STATED around the objective (who, why, by when), else
    "" — never invented;
the objective stage sends a strict response schema (Structured Outputs, the
people stage's pattern) carrying both fields; the parser maps them — absent
or invalid -> "", and the signal is KEPT. No migration: ObjectiveSignal
already has both columns.

Real path: POST /module-ai-pipelines/activity-extraction/run/ (the real
view, the real pipelines); the fake provider answers the objective stage
and records the request.

DB: Postgres.
"""

import json

import pytest

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.signals.models import ObjectiveSignal

from tests.signals.test_signal_cycle_attachment import TODAY


pytestmark = pytest.mark.django_db

EXTRACT_URL = '/module-ai-pipelines/activity-extraction/run/'
TRANSCRIPT = (
    'Claire: We want to close the month in three days instead of ten by the end of '
    'next year. Success for us is a close signed off on day three. The board reviews '
    'it in June.'
)
CRITERIA = 'A month-end close signed off on day three.'
NOTES = 'The board reviews the close time in June.'


def _objective(**overrides):
    payload = {
        'what': 'OPS', 'dimension': 'TIME', 'scope_level': 'BUSINESS',
        'target_department': None,
        'summary': 'Cut the month-end close from ten days to three',
        'source_quote': 'We want to close the month in three days instead of ten',
        'target_date': None, 'confidence': 0.9, 'is_inferred': False,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def meeting(account, user_a):
    a = Activity(title='Finance discovery', activity_type=ActivityType.MEETING,
                 status=ActivityStatus.COMPLETED, account=account, owner=user_a,
                 scheduled_date=TODAY)
    a.save(user=user_a, client_id=account.client_id)
    return a


def _extract(api, provider, activity, objective):
    provider.replies['objective'] = json.dumps({'signals': [objective]})
    resp = api.post(EXTRACT_URL, {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                    format='json')
    assert resp.status_code == 200, resp.content
    [signal] = ObjectiveSignal.objects.filter(source_activity=activity)
    return signal


# =============================================================================
# THE REPRO — emitted, then persisted
# =============================================================================

def test_the_success_criteria_and_the_notes_are_persisted(
    authed_api_a, meeting, patch_active_provider,
):
    signal = _extract(authed_api_a, patch_active_provider, meeting,
                      _objective(success_criteria=CRITERIA, notes=NOTES))

    assert signal.success_criteria == CRITERIA
    assert signal.notes == NOTES


def test_absent_fields_are_empty_and_the_signal_is_kept(
    authed_api_a, meeting, patch_active_provider,
):
    signal = _extract(authed_api_a, patch_active_provider, meeting, _objective())

    assert signal.success_criteria == ''
    assert signal.notes == ''


@pytest.mark.parametrize('bad', [None, 42, ['a', 'b'], {'k': 'v'}, '   '])
def test_invalid_fields_are_empty_and_the_signal_is_kept(
    bad, authed_api_a, meeting, patch_active_provider,
):
    signal = _extract(authed_api_a, patch_active_provider, meeting,
                      _objective(success_criteria=bad, notes=bad))

    assert signal.success_criteria == ''
    assert signal.notes == ''


def test_the_objective_stage_sends_a_strict_schema_with_both_fields(
    authed_api_a, meeting, patch_active_provider,
):
    _extract(authed_api_a, patch_active_provider, meeting,
             _objective(success_criteria=CRITERIA, notes=NOTES))

    [call] = [c for c in patch_active_provider.calls if c['stage'] == 'objective']
    schema = call['extra'].get('response_schema')
    assert schema is not None, 'the objective stage sends no response schema'
    item = schema['schema']['properties']['signals']['items']
    assert {'success_criteria', 'notes'} <= set(item['properties'])
    assert {'success_criteria', 'notes'} <= set(item['required'])   # strict: all keys


# =============================================================================
# THE PROMPT — versioned, the previous one kept
# =============================================================================

def _prompt_v3():
    from app_modules.ai_pipelines.prompts.transcript_signals.objective_v3 import (
        build_objective_request,
    )
    return ' '.join(build_objective_request('TRANSCRIPT').split())


def test_the_v3_prompt_asks_for_both_fields_and_never_to_invent():
    prompt = _prompt_v3()

    assert '"success_criteria":' in prompt and '"notes":' in prompt
    # The rules themselves (the schema lines only point to them).
    assert 'SUCCESS CRITERIA AND NOTES - "success_criteria" -- how the PROSPECT said' in prompt
    assert 'Never invent a figure, a threshold or a measure' in prompt
    assert '"notes" -- the context STATED around the objective only' in prompt
    assert 'Never add your own analysis, advice or guess' in prompt


def test_the_pipeline_runs_v3_and_v1_is_kept():
    from app_modules.ai_pipelines.pipelines.transcript_signals import QualificationSignalsPipeline
    from app_modules.ai_pipelines.prompts.transcript_signals import objective_v1

    assert QualificationSignalsPipeline.PROMPT_VERSIONS['objective'] == 'v3'
    assert objective_v1.OBJECTIVE_PROMPT_VERSION == 'v2'       # the previous text, untouched
