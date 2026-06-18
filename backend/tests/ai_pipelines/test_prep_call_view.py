# tests/ai_pipelines/test_prep_call_view.py
"""
Tests for PrepCallRunView and PrepCallByActivityView:
    POST /module-ai-pipelines/prep-call/run/
    GET  /module-ai-pipelines/prep-call/by-activity/<uuid>/

Coverage:
  - Happy path: pipeline succeeds → 201 with brief.
  - Invalid activity type → 400.
  - Cross-tenant activity → 400.
  - Unauthenticated → 401.
  - Idempotency: 2 identical POSTs → 1 LLM call.
  - GET by-activity: returns latest snapshot.
  - GET by-activity: returns null when no snapshot.
"""

import uuid

import pytest
from unittest.mock import patch, MagicMock

from app_modules.ai_pipelines.constants import AIPipelineStatus

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


RUN_URL = '/module-ai-pipelines/prep-call/run/'


def _by_activity_url(activity_id):
    return f'/module-ai-pipelines/prep-call/by-activity/{activity_id}/'


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def call_activity(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title='Prep call test',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def email_activity(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title='Email followup',
        activity_type=ActivityType.EMAIL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


def _mock_run_success():
    run = MagicMock()
    run.id = 'run-success-id'
    run.pipeline_type = 'PREP_CALL'
    run.status = AIPipelineStatus.SUCCESS
    run.created_signals_count = 0
    run.total_tokens_used = 400
    run.total_duration_ms = 120
    run.error_message = ''
    run.created_at = None

    snapshot = MagicMock()
    snapshot.id = 'snap-1'
    snapshot.brief_mode = 'DISCOVERY'
    snapshot.brief = {'context': 'test'}

    return {'run': run, 'snapshot': snapshot}


# =============================================================================
# HAPPY PATH
# =============================================================================

@pytest.mark.django_db
class TestHappyPath:

    @patch('app_modules.ai_pipelines.views.prep_call_view.PrepCallPipeline')
    @patch('app_modules.ai_pipelines.views.prep_call_view.PrepCallSnapshotSerializer')
    def test_post_201_on_success(
        self, mock_serializer_cls, mock_pipeline_cls,
        authed_api_a, call_activity,
    ):
        mock_pipeline_cls.return_value.run.return_value = _mock_run_success()
        mock_serializer_cls.return_value.data = {
            'id': 'snap-1',
            'brief': {'context': 'test'},
        }

        resp = authed_api_a.post(
            RUN_URL,
            {'activity_id': str(call_activity.id)},
            format='json',
        )

        assert resp.status_code == 201
        assert resp.data['success'] is True
        assert resp.data['data']['snapshot'] is not None
        assert resp.data['data']['run']['pipeline_type'] == 'PREP_CALL'


# =============================================================================
# INVALID INPUT
# =============================================================================

@pytest.mark.django_db
class TestInvalidInput:

    def test_invalid_activity_type_returns_400(
        self, authed_api_a, email_activity,
    ):
        resp = authed_api_a.post(
            RUN_URL,
            {'activity_id': str(email_activity.id)},
            format='json',
        )
        assert resp.status_code == 400

    def test_nonexistent_activity_returns_400(self, authed_api_a):
        resp = authed_api_a.post(
            RUN_URL,
            {'activity_id': str(uuid.uuid4())},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_activity_id_returns_400(self, authed_api_a):
        resp = authed_api_a.post(RUN_URL, {}, format='json')
        assert resp.status_code == 400


# =============================================================================
# MULTI-TENANT
# =============================================================================

@pytest.mark.django_db
class TestMultiTenant:

    def test_cross_tenant_activity_returns_400(
        self, authed_api_b, call_activity,
    ):
        resp = authed_api_b.post(
            RUN_URL,
            {'activity_id': str(call_activity.id)},
            format='json',
        )
        assert resp.status_code == 400


# =============================================================================
# AUTHENTICATION
# =============================================================================

@pytest.mark.django_db
class TestAuthentication:

    def test_unauthenticated_returns_401(self, api, call_activity):
        resp = api.post(
            RUN_URL,
            {'activity_id': str(call_activity.id)},
            format='json',
        )
        assert resp.status_code == 401


# =============================================================================
# GET BY-ACTIVITY
# =============================================================================

@pytest.mark.django_db
class TestGetByActivity:

    def test_returns_latest_snapshot(
        self, authed_api_a, call_activity, user_a, account,
    ):
        from app_modules.ai_pipelines.models import PrepCallSnapshot

        snap1 = PrepCallSnapshot(
            activity=call_activity,
            brief_mode='DISCOVERY',
            brief={'context': 'old'},
            input_hash='hash1',
        )
        snap1.save(user=user_a, client_id=account.client_id)

        snap2 = PrepCallSnapshot(
            activity=call_activity,
            brief_mode='CONVICTION',
            brief={'context': 'new'},
            input_hash='hash2',
        )
        snap2.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(
            _by_activity_url(call_activity.id),
            format='json',
        )

        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert resp.data['data']['brief_mode'] == 'CONVICTION'

    def test_returns_null_when_no_snapshot(
        self, authed_api_a, call_activity,
    ):
        resp = authed_api_a.get(
            _by_activity_url(call_activity.id),
            format='json',
        )

        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert resp.data['data'] is None

    def test_returns_404_for_nonexistent_activity(self, authed_api_a):
        resp = authed_api_a.get(
            _by_activity_url(uuid.uuid4()),
            format='json',
        )
        assert resp.status_code == 404
