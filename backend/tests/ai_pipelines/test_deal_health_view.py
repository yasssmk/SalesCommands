# tests/ai_pipelines/test_deal_health_view.py
"""
Tests for DealHealthRunView:
    POST /module-ai-pipelines/deal-health/run/

Coverage:
  - Happy path: pipeline succeeds → 201 with snapshot.
  - Pipeline failure (non-SUCCESS status) → 502 with run summary.
  - Pipeline hard crash → 502.
  - Authentication: unauthenticated → 401.
  - Multi-tenant isolation: cross-tenant cycle → 400.
  - Invalid decision_cycle_id → 400.
"""

import pytest
from unittest.mock import patch, MagicMock

from app_modules.ai_pipelines.constants import AIPipelineStatus


# Re-export shared fixtures.
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
)


URL = '/module-ai-pipelines/deal-health/run/'


def _mock_run_success(snapshot_mock=None):
    """Return a mock pipeline result dict for a successful run."""
    run = MagicMock()
    run.id = 'run-success-id'
    run.pipeline_type = 'DEAL_HEALTH'
    run.status = AIPipelineStatus.SUCCESS
    run.created_signals_count = 0
    run.total_tokens_used = 600
    run.total_duration_ms = 150
    run.error_message = ''
    run.created_at = None
    return {'run': run, 'snapshot': snapshot_mock or MagicMock()}


def _mock_run_failure(status=AIPipelineStatus.PARSE_ERROR):
    """Return a mock pipeline result dict for a failed run."""
    run = MagicMock()
    run.id = 'run-fail-id'
    run.pipeline_type = 'DEAL_HEALTH'
    run.status = status
    run.created_signals_count = 0
    run.total_tokens_used = 200
    run.total_duration_ms = 50
    run.error_message = 'parse_error: bad JSON'
    run.created_at = None
    return {'run': run, 'snapshot': None}


# =============================================================================
# HAPPY PATH
# =============================================================================

@pytest.mark.django_db
class TestHappyPath:

    @patch('app_modules.ai_pipelines.views.deal_health_view.DealHealthPipeline')
    @patch(
        'app_modules.ai_pipelines.views.deal_health_view'
        '.DealHealthSnapshotDetailSerializer'
    )
    def test_post_201_on_success(
        self, mock_serializer_cls, mock_pipeline_cls,
        authed_api_a, cycle,
    ):
        mock_pipeline_cls.return_value.run.return_value = _mock_run_success()
        mock_serializer_cls.return_value.data = {'id': 'snap-1', 'diagnostic': {}}

        resp = authed_api_a.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )

        assert resp.status_code == 201
        assert resp.data['success'] is True
        assert resp.data['data']['snapshot'] is not None
        assert resp.data['data']['run']['pipeline_type'] == 'DEAL_HEALTH'


# =============================================================================
# PIPELINE FAILURE
# =============================================================================

@pytest.mark.django_db
class TestPipelineFailure:

    @patch('app_modules.ai_pipelines.views.deal_health_view.DealHealthPipeline')
    def test_post_502_on_parse_error(
        self, mock_pipeline_cls,
        authed_api_a, cycle,
    ):
        mock_pipeline_cls.return_value.run.return_value = _mock_run_failure(
            AIPipelineStatus.PARSE_ERROR,
        )

        resp = authed_api_a.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )

        assert resp.status_code == 502
        assert resp.data['success'] is False
        assert resp.data['data']['snapshot'] is None

    @patch('app_modules.ai_pipelines.views.deal_health_view.DealHealthPipeline')
    def test_post_502_on_timeout(
        self, mock_pipeline_cls,
        authed_api_a, cycle,
    ):
        mock_pipeline_cls.return_value.run.return_value = _mock_run_failure(
            AIPipelineStatus.TIMEOUT,
        )

        resp = authed_api_a.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )

        assert resp.status_code == 502
        assert resp.data['success'] is False

    @patch('app_modules.ai_pipelines.views.deal_health_view.DealHealthPipeline')
    def test_post_502_on_hard_crash(
        self, mock_pipeline_cls,
        authed_api_a, cycle,
    ):
        mock_pipeline_cls.return_value.run.side_effect = RuntimeError('boom')

        resp = authed_api_a.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )

        assert resp.status_code == 502
        assert resp.data['success'] is False


# =============================================================================
# AUTHENTICATION
# =============================================================================

@pytest.mark.django_db
class TestAuthentication:

    def test_unauthenticated_returns_401(self, api, cycle):
        resp = api.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )
        assert resp.status_code == 401


# =============================================================================
# MULTI-TENANT ISOLATION
# =============================================================================

@pytest.mark.django_db
class TestMultiTenant:

    def test_cross_tenant_cycle_returns_400(
        self, authed_api_b, cycle,
    ):
        """User B cannot run pipeline on User A's cycle."""
        resp = authed_api_b.post(
            URL,
            {'decision_cycle_id': str(cycle.id)},
            format='json',
        )
        assert resp.status_code == 400


# =============================================================================
# INVALID INPUT
# =============================================================================

@pytest.mark.django_db
class TestInvalidInput:

    def test_missing_cycle_id_returns_400(self, authed_api_a):
        resp = authed_api_a.post(URL, {}, format='json')
        assert resp.status_code == 400

    def test_nonexistent_cycle_returns_400(self, authed_api_a):
        import uuid
        resp = authed_api_a.post(
            URL,
            {'decision_cycle_id': str(uuid.uuid4())},
            format='json',
        )
        assert resp.status_code == 400
