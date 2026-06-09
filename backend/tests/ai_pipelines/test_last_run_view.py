# backend/tests/ai_pipelines/test_last_run_view.py
"""
Tests for the LastRunView endpoint:
    GET /module-ai-pipelines/last-run/?activity_id=<uuid>

Coverage:
  - Happy path: returns last run metadata when a SUCCESS run exists.
  - No run found: returns { last_run: null }.
  - Multi-tenant isolation: cannot see runs from another tenant.
  - Authentication required: unauthenticated → 401.
  - Missing activity_id param → 400.
  - Activity not found → 404.
"""

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.ai_pipelines.models import AIPipelineRun


# =============================================================================
# CONSTANTS
# =============================================================================

URL = '/module-ai-pipelines/last-run/'


# =============================================================================
# HELPERS
# =============================================================================

def _create_run(activity, user, *, status='SUCCESS', pipeline_type=None, input_hash='a' * 64, error_message=''):
    return AIPipelineRun.objects.create(
        client_id=activity.client_id,
        source_activity=activity,
        created_by=user,
        updated_by=user,
        status=status,
        pipeline_type=pipeline_type or AIPipelineType.TRANSCRIPT_SIGNALS,
        prompt_versions={'system': 'v1'},
        provider='openai',
        model_name='gpt-4o-mini',
        temperature=0.0,
        input_hash=input_hash,
        sub_calls=[],
        total_tokens_used=100,
        total_duration_ms=500,
        error_message=error_message,
        created_signals_count=3,
    )


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db
class TestLastRunView:

    def test_returns_last_run_when_exists(self, authed_api_a, activity, user_a):
        run = _create_run(activity, user_a)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        data = resp.data['last_run']
        assert data is not None
        assert data['input_hash'] == 'a' * 64
        assert data['status'] == 'SUCCESS'
        assert data['created_signals_count'] == 3
        assert data['last_run_by']['id'] == str(user_a.id)
        assert data['last_run_by']['full_name'] == user_a.get_full_name()
        assert data['last_run_at'] is not None

    def test_returns_null_when_no_run(self, authed_api_a, activity):
        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run'] is None

    def test_ignores_failed_runs(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, status=AIPipelineStatus.LLM_ERROR)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run'] is None

    def test_returns_partial_run(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, status=AIPipelineStatus.PARTIAL)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run'] is not None
        assert resp.data['last_run']['status'] == 'PARTIAL'

    def test_tenant_isolation(self, authed_api_b, activity):
        resp = authed_api_b.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, api):
        resp = api.get(f'{URL}?activity_id=00000000-0000-0000-0000-000000000000')

        assert resp.status_code in (401, 403)

    def test_missing_activity_id_returns_400(self, authed_api_a):
        resp = authed_api_a.get(URL)

        assert resp.status_code == 400
        assert 'activity_id' in resp.data.get('error', '')

    def test_activity_not_found_returns_404(self, authed_api_a):
        resp = authed_api_a.get(f'{URL}?activity_id=00000000-0000-0000-0000-000000000001')

        assert resp.status_code == 404

    # ===== runs_by_pipeline tests (Sprint F3) =====

    def test_runs_by_pipeline_both_present(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS, input_hash='a' * 64)
        _create_run(activity, user_a, pipeline_type=AIPipelineType.NEXT_STEPS, input_hash='b' * 64)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        rbp = resp.data['runs_by_pipeline']
        assert rbp['TRANSCRIPT_SIGNALS'] is not None
        assert rbp['TRANSCRIPT_SIGNALS']['input_hash'] == 'a' * 64
        assert rbp['NEXT_STEPS'] is not None
        assert rbp['NEXT_STEPS']['input_hash'] == 'b' * 64

    def test_runs_by_pipeline_one_missing(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        rbp = resp.data['runs_by_pipeline']
        assert rbp['TRANSCRIPT_SIGNALS'] is not None
        assert rbp['NEXT_STEPS'] is None

    def test_runs_by_pipeline_none_when_no_runs(self, authed_api_a, activity):
        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        rbp = resp.data['runs_by_pipeline']
        assert rbp['TRANSCRIPT_SIGNALS'] is None
        assert rbp['NEXT_STEPS'] is None

    def test_last_run_is_most_recent_across_pipelines(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS, input_hash='a' * 64)
        newer = _create_run(activity, user_a, pipeline_type=AIPipelineType.NEXT_STEPS, input_hash='b' * 64)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run']['input_hash'] == 'b' * 64
        assert resp.data['last_run']['pipeline_type'] == 'NEXT_STEPS'

    # ===== latest_run & error_message tests =====

    def test_latest_run_returns_failed_run(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, status=AIPipelineStatus.LLM_ERROR)

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run'] is None
        assert resp.data['latest_run'] is not None
        assert resp.data['latest_run']['status'] == 'LLM_ERROR'

    def test_latest_run_shows_error_message(self, authed_api_a, activity, user_a):
        _create_run(
            activity, user_a,
            status=AIPipelineStatus.LLM_ERROR,
            error_message='Rate limit exceeded',
        )

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['latest_run']['error_message'] == 'Rate limit exceeded'

    def test_latest_run_with_successful_run(self, authed_api_a, activity, user_a):
        run = _create_run(activity, user_a, status='SUCCESS')

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run'] is not None
        assert resp.data['latest_run'] is not None
        assert resp.data['last_run']['input_hash'] == resp.data['latest_run']['input_hash']
        assert resp.data['last_run']['status'] == 'SUCCESS'
        assert resp.data['latest_run']['status'] == 'SUCCESS'

    def test_error_message_empty_for_success(self, authed_api_a, activity, user_a):
        _create_run(activity, user_a, status='SUCCESS', error_message='')

        resp = authed_api_a.get(f'{URL}?activity_id={activity.id}')

        assert resp.status_code == 200
        assert resp.data['last_run']['error_message'] == ''
