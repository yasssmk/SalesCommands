# backend/tests/ai_pipelines/test_analysis_once_per_pipeline.py
"""
Sprint « Source / Notes » 1.6 (PO, Q4 — option B): an analysis is NEVER
re-run. A pipeline of an activity that already SUCCEEDED (a run SUCCESS or
PARTIAL — THE « analysed » rule, ai_pipelines/services/analysis_state.py) is
SKIPPED whatever the transcript posted; the other requested pipeline runs.
When EVERYTHING requested is already analysed, the endpoint answers the
standard error (400, centralised message, code ANALYSIS_ALREADY_DONE) — it
replaces the former 409 ALREADY_EXTRACTED. A failed run (PARSE_ERROR /
LLM_ERROR / TIMEOUT) does not count. Through the real endpoint.
"""

import pytest

from app_modules.ai_pipelines.constants import (
    ANALYSIS_ALREADY_DONE_CODE,
    AIPipelineStatus,
    AIPipelineType,
)
from app_modules.ai_pipelines.models import AIPipelineRun
from core.error_messages import AIPipelineErrorMessages

from .conftest import CANNED_REPLIES_HAPPY, CANNED_REPLY_NEXT_STEPS_HAPPY
from .test_activity_extraction_view import (  # noqa: F401  (fixtures)
    TRANSCRIPT, URL, _apply_patches, _bypass_redis, activity, activity_without_cycle,
)


pytestmark = pytest.mark.django_db

OTHER_TRANSCRIPT = TRANSCRIPT + ' Pierre: Et on ajoute un point sur la sécurité.'


def _run(activity, user, pipeline, run_status=AIPipelineStatus.SUCCESS):
    return AIPipelineRun.objects.create(
        pipeline_type=pipeline, prompt_versions={'system': 'v1'}, provider='openai',
        model_name='gpt-4o-mini', temperature=0.0, source_activity=activity,
        input_hash='a-previous-transcript', status=run_status, sub_calls=[],
        total_tokens_used=1, total_duration_ms=1, error_message='',
        created_signals_count=0, client_id=activity.client_id,
        created_by=user, updated_by=user,
    )


def _post(api, activity, transcript=TRANSCRIPT, **flags):
    with _apply_patches(_bypass_redis):
        return api.post(URL, {'activity_id': str(activity.id), 'transcript': transcript, **flags},
                        format='json')


def _runs(activity, pipeline):
    return AIPipelineRun.objects.filter(source_activity=activity, pipeline_type=pipeline).count()


def _assert_already_done(resp):
    assert resp.status_code == 400, resp.content
    body = resp.json()
    assert body['code'] == ANALYSIS_ALREADY_DONE_CODE
    assert body['error'] == str(AIPipelineErrorMessages.ANALYSIS_ALREADY_DONE)


@pytest.mark.parametrize('run_status', [AIPipelineStatus.SUCCESS, AIPipelineStatus.PARTIAL])
def test_an_analysed_activity_is_never_rerun_whatever_the_transcript(
    authed_api_a, activity, user_a, patch_active_provider, fake_provider, run_status,
):
    _run(activity, user_a, AIPipelineType.TRANSCRIPT_SIGNALS, run_status)
    _run(activity, user_a, AIPipelineType.NEXT_STEPS, run_status)
    fake_provider.replies = {**CANNED_REPLIES_HAPPY, 'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

    _assert_already_done(_post(authed_api_a, activity, OTHER_TRANSCRIPT))
    assert _runs(activity, AIPipelineType.TRANSCRIPT_SIGNALS) == 1
    assert _runs(activity, AIPipelineType.NEXT_STEPS) == 1


def test_a_second_post_after_a_real_analysis_is_refused(
    authed_api_a, activity, patch_active_provider, fake_provider,
):
    fake_provider.replies = {**CANNED_REPLIES_HAPPY, 'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}
    assert _post(authed_api_a, activity).status_code == 200
    _assert_already_done(_post(authed_api_a, activity, OTHER_TRANSCRIPT))
    assert _runs(activity, AIPipelineType.TRANSCRIPT_SIGNALS) == 1
    assert _runs(activity, AIPipelineType.NEXT_STEPS) == 1


def test_the_analysed_pipeline_is_skipped_the_other_runs(
    authed_api_a, activity, user_a, patch_active_provider, fake_provider,
):
    _run(activity, user_a, AIPipelineType.TRANSCRIPT_SIGNALS)
    fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

    resp = _post(authed_api_a, activity, OTHER_TRANSCRIPT)

    assert resp.status_code == 200, resp.content
    data = resp.json()['data']
    assert data['qualification_run']['from_cache'] is True
    assert data['next_steps_run']['from_cache'] is False
    assert _runs(activity, AIPipelineType.TRANSCRIPT_SIGNALS) == 1
    assert _runs(activity, AIPipelineType.NEXT_STEPS) == 1


def test_only_the_analysed_pipeline_requested_is_refused(
    authed_api_a, activity, user_a, patch_active_provider, fake_provider,
):
    _run(activity, user_a, AIPipelineType.NEXT_STEPS)
    fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}
    _assert_already_done(_post(authed_api_a, activity, OTHER_TRANSCRIPT,
                               run_qualification=False, run_next_steps=True))
    assert _runs(activity, AIPipelineType.NEXT_STEPS) == 1


def test_a_campaign_activity_without_next_steps_analysed_is_refused(
    authed_api_a, activity_without_cycle, user_a, patch_active_provider, fake_provider,
):
    # Next steps skipped by the DC-only guard: what is requested = qualification.
    _run(activity_without_cycle, user_a, AIPipelineType.TRANSCRIPT_SIGNALS)
    fake_provider.replies = {**CANNED_REPLIES_HAPPY}
    _assert_already_done(_post(authed_api_a, activity_without_cycle, OTHER_TRANSCRIPT))


@pytest.mark.parametrize('run_status', [
    AIPipelineStatus.PARSE_ERROR, AIPipelineStatus.LLM_ERROR, AIPipelineStatus.TIMEOUT,
])
def test_a_failed_run_does_not_count(
    authed_api_a, activity, user_a, patch_active_provider, fake_provider, run_status,
):
    _run(activity, user_a, AIPipelineType.TRANSCRIPT_SIGNALS, run_status)
    _run(activity, user_a, AIPipelineType.NEXT_STEPS, run_status)
    fake_provider.replies = {**CANNED_REPLIES_HAPPY, 'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}
    resp = _post(authed_api_a, activity, OTHER_TRANSCRIPT)
    assert resp.status_code == 200, resp.content
    data = resp.json()['data']
    assert data['qualification_run']['from_cache'] is False
    assert data['next_steps_run']['from_cache'] is False
