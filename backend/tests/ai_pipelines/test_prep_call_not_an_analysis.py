# backend/tests/ai_pipelines/test_prep_call_not_an_analysis.py
"""
Sprint « Deal health v2 », step 1 — a prep-call brief is NOT an analysis.

THE « already analysed » rule (ai_pipelines/services/analysis_state.py) used
to count every SUCCESS / PARTIAL run of an activity, whatever its pipeline.
The prep-call pipeline opens its run with source_activity=activity
(pipelines/prep_call.py), so a generated brief made the activity
« analysed »: the last-run endpoint returned it (the Activity workspace then
folds the Preparation band, views/activities/workspace/index.jsx) and the
transcript got LOCKED (activities/serializers.py) without any extraction.

Real path only: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline (fake LLM provider, tests/ai_pipelines/conftest.py), then
GET /module-ai-pipelines/last-run/ and PATCH /module-activities/{id}/.
"""

import json

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.ai_pipelines.models import AIPipelineRun

from tests.signals.test_signal_cycle_attachment import _plain_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'
LAST_RUN_URL = '/module-ai-pipelines/last-run/'
ACTIVITIES_URL = '/module-activities/'

_VALID_BRIEF = {
    'context': 'Second call with the operations team.',
    'objectives': [
        {
            'rank': 'primary',
            'summary': 'Quantify the time lost on reporting.',
            'nature': 'VALUE',
            'success_criteria': 'A weekly figure is stated.',
        },
    ],
    'rhetoric': {
        'register': 'Lead with their own numbers.',
        'key_argument': 'Reporting takes too long.',
        'tangible_reformulation': '10h/week = one month a year.',
        'proof': 'Stated during the first call.',
    },
    'gaps': [
        {'topic': 'Budget', 'strategy': 'DIRECT', 'question': 'Who owns the budget?'},
    ],
    'next_step': {
        'what': 'Book a demo.',
        'with_whom': 'The operations lead.',
        'when': 'Propose two dates during the call.',
    },
}


@pytest.fixture
def activity(account, user_a):
    """A dated MEETING (eligible for a brief; the PATCH needs a date) — the
    activity of tests/activities/test_transcript_lock.py."""
    return _plain_activity(account, user_a)


@pytest.fixture
def prep_call_provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _run_prep_call(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    # Precondition (non-vacuity): the brief really went through the real
    # pipeline and left a SUCCESS PREP_CALL run on the activity.
    assert AIPipelineRun.objects.filter(
        source_activity=activity,
        pipeline_type=AIPipelineType.PREP_CALL,
        status=AIPipelineStatus.SUCCESS,
    ).exists()
    return resp


def _transcript_signals_run(activity, user):
    return AIPipelineRun.objects.create(
        pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS, prompt_versions={'system': 'v1'},
        provider='openai', model_name='gpt-4o-mini', temperature=0.0,
        source_activity=activity, input_hash='h', status=AIPipelineStatus.SUCCESS,
        sub_calls=[], total_tokens_used=1, total_duration_ms=1, error_message='',
        created_signals_count=0, client_id=activity.client_id,
        created_by=user, updated_by=user,
    )


def test_a_prep_call_brief_is_not_a_last_run(authed_api_a, activity, prep_call_provider):
    _run_prep_call(authed_api_a, activity)
    assert len(prep_call_provider.calls_for('prep_call')) == 1

    resp = authed_api_a.get(f'{LAST_RUN_URL}?activity_id={activity.id}')

    assert resp.status_code == 200, resp.content
    assert resp.data['last_run'] is None
    assert resp.data['runs_by_pipeline'][AIPipelineType.PREP_CALL] is None


def test_a_prep_call_brief_does_not_lock_the_transcript(authed_api_a, activity, prep_call_provider):
    _run_prep_call(authed_api_a, activity)

    resp = authed_api_a.patch(
        f'{ACTIVITIES_URL}{activity.id}/', {'transcript': 'A new transcript'}, format='json',
    )

    assert resp.status_code == 200, resp.content
    activity.refresh_from_db()
    assert activity.transcript == 'A new transcript'


def test_an_extraction_after_a_brief_still_counts_and_locks(
    authed_api_a, activity, user_a, prep_call_provider,
):
    """Regression: the brief does not hide a real analysis."""
    _run_prep_call(authed_api_a, activity)
    _transcript_signals_run(activity, user_a)

    resp = authed_api_a.get(f'{LAST_RUN_URL}?activity_id={activity.id}')
    assert resp.data['last_run']['pipeline_type'] == AIPipelineType.TRANSCRIPT_SIGNALS

    patched = authed_api_a.patch(
        f'{ACTIVITIES_URL}{activity.id}/', {'transcript': 'Changed'}, format='json',
    )
    assert patched.status_code == 400
    assert 'analysed' in patched.content.decode().lower()
