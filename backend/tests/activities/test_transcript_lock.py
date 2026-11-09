# backend/tests/activities/test_transcript_lock.py
"""
Sprint « Cycle de vie des contacts », 8g-7 (TD-25, PO decision) — an analysis
is never re-run on an activity (the wizard's MVP behaviour, kept); instead,
once an analysis SUCCEEDED (a run SUCCESS or PARTIAL — the « already
analysed » definition of the last-run endpoint, read by the wizard), the
transcript is LOCKED: PATCH /module-activities/{id}/ refuses to change it
(standard error). A failed analysis leaves it editable; the other fields of
the Source band (notes…) are unchanged. ONE rule
(ai_pipelines/services/analysis_state.py) for the endpoint and the guard.
"""

import pytest
from rest_framework import status

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType


from tests.signals.test_signal_cycle_attachment import _plain_activity


pytestmark = pytest.mark.django_db
URL = '/module-activities/'


@pytest.fixture
def activity(account, user_a):
    return _plain_activity(account, user_a)


def _run(activity, user, run_status, pipeline=AIPipelineType.TRANSCRIPT_SIGNALS):
    from app_modules.ai_pipelines.models import AIPipelineRun
    return AIPipelineRun.objects.create(
        pipeline_type=pipeline, prompt_versions={'system': 'v1'}, provider='openai',
        model_name='gpt-4o-mini', temperature=0.0, source_activity=activity, input_hash='h',
        status=run_status, sub_calls=[], total_tokens_used=1, total_duration_ms=1,
        error_message='', created_signals_count=0, client_id=activity.client_id,
        created_by=user, updated_by=user,
    )


def _patch(api, activity, **fields):
    return api.patch(f'{URL}{activity.id}/', fields, format='json')


@pytest.mark.parametrize('run_status', [AIPipelineStatus.SUCCESS, AIPipelineStatus.PARTIAL])
def test_after_a_successful_analysis_the_transcript_is_locked(authed_api_a, activity, user_a, run_status):
    _run(activity, user_a, run_status)
    r = _patch(authed_api_a, activity, transcript='A new transcript')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'analysed' in r.content.decode().lower()


def test_a_next_steps_analysis_locks_it_too(authed_api_a, activity, user_a):
    _run(activity, user_a, AIPipelineStatus.SUCCESS, pipeline=AIPipelineType.NEXT_STEPS)
    assert _patch(authed_api_a, activity, transcript='Changed').status_code == 400


def test_the_same_transcript_and_the_other_fields_stay_writable(authed_api_a, activity, user_a):
    _run(activity, user_a, AIPipelineStatus.SUCCESS)
    activity.refresh_from_db()
    assert _patch(authed_api_a, activity, transcript=activity.transcript or '').status_code == 200
    assert _patch(authed_api_a, activity, outcome_notes='Takeaways').status_code == 200


def test_after_a_failed_analysis_the_transcript_stays_editable(authed_api_a, activity, user_a):
    _run(activity, user_a, AIPipelineStatus.LLM_ERROR)
    assert _patch(authed_api_a, activity, transcript='Retry text').status_code == 200


def test_without_analysis_the_transcript_is_editable(authed_api_a, activity):
    assert _patch(authed_api_a, activity, transcript='First text').status_code == 200
