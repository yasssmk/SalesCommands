# backend/tests/ai_pipelines/test_activity_extraction_view.py
"""
Tests for the unified ActivityExtractionView endpoint:
    POST /module-ai-pipelines/activity-extraction/run/

Coverage:
  - Happy path: both pipelines succeed, unified response.
  - TD-8 resolution: prior Qualif run does NOT block NextSteps extraction.
  - Both already extracted → 409 with cached payload.
  - Qualif PARTIAL + NextSteps SUCCESS → global PARTIAL.
  - Qualif KO + NextSteps OK → global PARTIAL.
  - Qualif OK + NextSteps KO → global PARTIAL.
  - Both KO → global FAILED (raises).
  - Idempotency-key replay.
  - Permissions: unauthenticated → 401/403.
  - Multi-tenant isolation: cross-tenant activity → 400.
  - Regression: old /transcript-signals/extract/ still works.
  - Deprecation headers on old endpoint.
"""

import hashlib
from unittest.mock import patch

import pytest

from app_modules.ai_pipelines.constants import (
    AIPipelineStatus,
    AIPipelineType,
)
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.ai_pipelines.config import TRANSCRIPT_SIGNALS_SUNSET_DATE

from .conftest import (
    CANNED_REPLIES_HAPPY,
    CANNED_REPLY_NEXT_STEPS_HAPPY,
    FakeProvider,
)


# =============================================================================
# CONSTANTS
# =============================================================================

URL = '/module-ai-pipelines/activity-extraction/run/'
OLD_URL = '/module-ai-pipelines/transcript-signals/extract/'

TRANSCRIPT = (
    'Pierre: Bonjour, notre reporting prend 3 semaines chaque trimestre. '
    'Marie: On utilise Salesforce mais c\'est limité. '
    'Pierre: On a pas de budget pour Q4. '
    'Marie: Il faudrait envoyer un récap au CFO. '
    'Pierre: OK, on planifie un call de suivi mercredi.'
)


def _make_idempotency_key(activity_id, transcript):
    return hashlib.sha256(
        f'{activity_id}{transcript.strip()}'.encode()
    ).hexdigest()


def _noop_start_op(*args, **kwargs):
    return None


def _noop_complete_op(*args, **kwargs):
    pass


def _noop_fail_op(*args, **kwargs):
    pass


# Stack all Redis idempotency mocks in one decorator
_bypass_redis = [
    patch(
        'app_modules.ai_pipelines.views.activity_extraction_view.start_op',
        side_effect=_noop_start_op,
    ),
    patch(
        'app_modules.ai_pipelines.views.activity_extraction_view.complete_op',
        side_effect=_noop_complete_op,
    ),
    patch(
        'app_modules.ai_pipelines.views.activity_extraction_view.fail_op',
        side_effect=_noop_fail_op,
    ),
]

_bypass_redis_old = [
    patch(
        'app_modules.ai_pipelines.views.transcript_signals_view.start_op',
        side_effect=_noop_start_op,
    ),
    patch(
        'app_modules.ai_pipelines.views.transcript_signals_view.complete_op',
        side_effect=_noop_complete_op,
    ),
    patch(
        'app_modules.ai_pipelines.views.transcript_signals_view.fail_op',
        side_effect=_noop_fail_op,
    ),
]


def _apply_patches(patches):
    """Context manager that stacks multiple mock patches."""
    from contextlib import ExitStack
    stack = ExitStack()
    mocks = []
    for p in patches:
        mocks.append(stack.enter_context(p))
    return stack


# =============================================================================
# HAPPY PATH
# =============================================================================

@pytest.mark.django_db
class TestHappyPath:
    """POST → both pipelines execute → unified response with signals."""

    def test_both_pipelines_succeed(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        fake_provider.replies = {
            **CANNED_REPLIES_HAPPY,
            'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY,
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True

        data = body['data']
        assert data['status'] == 'SUCCESS'

        # Qualification run
        assert data['qualification_run'] is not None
        assert data['qualification_run']['from_cache'] is False
        assert data['qualification_run']['status'] in ('SUCCESS', 'PARTIAL')

        # Next steps run
        assert data['next_steps_run'] is not None
        assert data['next_steps_run']['from_cache'] is False
        assert data['next_steps_run']['status'] == 'SUCCESS'

        # Qualification signals present
        qs = data['qualification_signals']
        assert 'pain' in qs
        assert 'objective' in qs
        assert 'impact' in qs
        assert 'tech-stack' in qs
        assert 'blocker' in qs

        # Next step signals present
        assert len(data['next_step_signals']) >= 1

        # 2 AIPipelineRun rows created (one per pipeline)
        runs = AIPipelineRun.objects.filter(source_activity=activity)
        assert runs.count() == 2
        types = set(runs.values_list('pipeline_type', flat=True))
        assert types == {
            AIPipelineType.TRANSCRIPT_SIGNALS,
            AIPipelineType.NEXT_STEPS,
        }


# =============================================================================
# TD-8 RESOLUTION — prior Qualif does NOT block NextSteps
# =============================================================================

@pytest.mark.django_db
class TestTD8Resolution:
    """
    A prior Qualif run (SUCCESS) in DB should NOT block NextSteps
    extraction via the unified endpoint. The response should contain
    Qualif from cache + fresh NextSteps.
    """

    def test_qualif_already_extracted_unified_run_still_extracts_next_steps(
        self, authed_api_a, activity, user_a, client_account_a,
        patch_active_provider, fake_provider,
    ):
        # Pre-create a Qualif run
        input_hash = hashlib.sha256(TRANSCRIPT.encode('utf-8')).hexdigest()
        AIPipelineRun.objects.create(
            pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS,
            prompt_versions={'system': 'v1'},
            provider='openai',
            model_name='gpt-4o-mini',
            temperature=0.0,
            source_activity=activity,
            input_hash=input_hash,
            status=AIPipelineStatus.SUCCESS,
            sub_calls=[],
            total_tokens_used=100,
            total_duration_ms=500,
            error_message='',
            created_signals_count=5,
            client_id=client_account_a.id,
            created_by=user_a,
            updated_by=user_a,
        )

        fake_provider.replies = {
            'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY,
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        data = body['data']

        # Qualif came from cache
        assert data['qualification_run']['from_cache'] is True
        # NextSteps is fresh
        assert data['next_steps_run']['from_cache'] is False
        assert data['next_steps_run']['status'] == 'SUCCESS'
        assert len(data['next_step_signals']) >= 1

        # Only 1 new run created (NextSteps), existing Qualif untouched
        runs = AIPipelineRun.objects.filter(source_activity=activity)
        assert runs.count() == 2


# =============================================================================
# BOTH ALREADY EXTRACTED → 409
# =============================================================================

@pytest.mark.django_db
class TestBothAlreadyExtracted:
    """When both pipelines have prior successful runs → 409 with full payload."""

    def test_both_already_extracted_returns_409_with_cached_payload(
        self, authed_api_a, activity, user_a, client_account_a,
        patch_active_provider,
    ):
        input_hash = hashlib.sha256(TRANSCRIPT.encode('utf-8')).hexdigest()
        common = dict(
            prompt_versions={'system': 'v1'},
            provider='openai',
            model_name='gpt-4o-mini',
            temperature=0.0,
            source_activity=activity,
            input_hash=input_hash,
            status=AIPipelineStatus.SUCCESS,
            sub_calls=[],
            total_tokens_used=100,
            total_duration_ms=500,
            error_message='',
            created_signals_count=3,
            client_id=client_account_a.id,
            created_by=user_a,
            updated_by=user_a,
        )

        AIPipelineRun.objects.create(
            pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS,
            **common,
        )
        AIPipelineRun.objects.create(
            pipeline_type=AIPipelineType.NEXT_STEPS,
            **common,
        )

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 409
        body = resp.json()
        assert body['code'] == 'ALREADY_EXTRACTED'
        assert body['data']['qualification_run']['from_cache'] is True
        assert body['data']['next_steps_run']['from_cache'] is True


# =============================================================================
# PARTIAL STATUS
# =============================================================================

@pytest.mark.django_db
class TestPartialStatus:
    """Global status derivation with mixed pipeline outcomes."""

    def test_qualif_partial_next_steps_success_yields_partial_global_status(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        from app_modules.ai_pipelines.providers.base import LLMTimeoutError

        # Qualif: techstack stage times out → PARTIAL overall
        fake_provider.replies = {
            **CANNED_REPLIES_HAPPY,
            'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY,
        }
        fake_provider.raise_per_stage = {
            'techstack': LLMTimeoutError('timeout on techstack'),
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()['data']
        # Qualif is PARTIAL (4/5 stages OK), NextSteps is SUCCESS
        # → global should be PARTIAL (strict rule: both must be SUCCESS)
        assert data['status'] == 'PARTIAL'
        assert data['qualification_run']['status'] == 'PARTIAL'
        assert data['next_steps_run']['status'] == 'SUCCESS'

    def test_qualif_ok_next_steps_ko_yields_partial(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        from app_modules.ai_pipelines.providers.base import LLMTimeoutError

        fake_provider.replies = {**CANNED_REPLIES_HAPPY}
        fake_provider.raise_per_stage = {
            'next_steps': LLMTimeoutError('timeout on next_steps'),
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['status'] == 'PARTIAL'
        assert data['qualification_run']['status'] == 'SUCCESS'
        assert data['next_steps_run']['status'] == 'TIMEOUT'

    def test_qualif_ko_next_steps_ok_yields_partial(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        from app_modules.ai_pipelines.providers.base import LLMAuthError

        fake_provider.replies = {
            'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY,
        }
        # Auth error on first qualif stage → fatal abort → LLM_ERROR
        fake_provider.raise_per_stage = {
            'pain': LLMAuthError('auth failed'),
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['status'] == 'PARTIAL'
        assert data['next_steps_run']['status'] == 'SUCCESS'


# =============================================================================
# BOTH KO → FAILED
# =============================================================================

@pytest.mark.django_db
class TestBothFailed:
    """When both pipelines fail, the view returns 200 with FAILED status."""

    def test_both_pipelines_fail_returns_failed(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        from app_modules.ai_pipelines.providers.base import LLMTimeoutError

        fake_provider.raise_per_stage = {
            'pain': LLMTimeoutError('timeout'),
            'objective': LLMTimeoutError('timeout'),
            'impact': LLMTimeoutError('timeout'),
            'techstack': LLMTimeoutError('timeout'),
            'blocker': LLMTimeoutError('timeout'),
            'next_steps': LLMTimeoutError('timeout'),
        }

        with _apply_patches(_bypass_redis):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        # Both pipelines created runs (with failure statuses) but neither
        # crashed — the view catches pipeline-level errors internally.
        # The global status is FAILED.
        assert resp.status_code == 200
        data = resp.json()['data']
        assert data['status'] == 'FAILED'


# =============================================================================
# DEDUP INTRA — same endpoint called twice
# =============================================================================

@pytest.mark.django_db
class TestDedupIntra:
    """Two identical calls → second returns 409 ALREADY_EXTRACTED."""

    def test_second_call_returns_already_extracted(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        fake_provider.replies = {
            **CANNED_REPLIES_HAPPY,
            'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY,
        }

        with _apply_patches(_bypass_redis):
            resp1 = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )
        assert resp1.status_code == 200

        with _apply_patches(_bypass_redis):
            resp2 = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp2.status_code == 409
        assert resp2.json()['code'] == 'ALREADY_EXTRACTED'


# =============================================================================
# IDEMPOTENCY KEY — Redis replay
# =============================================================================

@pytest.mark.django_db
class TestIdempotencyReplay:
    """start_op returns a cached 'succeeded' state → replay without pipeline."""

    def test_idempotency_replay_returns_cached_response(
        self, authed_api_a, activity, patch_active_provider,
    ):
        cached_body = {
            'success': True,
            'data': {'status': 'SUCCESS', 'replayed': True},
        }

        def mock_start_op(*args, **kwargs):
            return {
                'status': 'succeeded',
                'result': {
                    'http_status': 200,
                    'data': cached_body,
                },
            }

        with patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.start_op',
            side_effect=mock_start_op,
        ):
            resp = authed_api_a.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        assert resp.json() == cached_body


# =============================================================================
# PERMISSIONS
# =============================================================================

@pytest.mark.django_db
class TestPermissions:
    """Unauthenticated user → 401 or 403."""

    def test_unauthenticated_returns_401(self, api, activity):
        resp = api.post(
            URL,
            {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
            format='json',
        )
        assert resp.status_code in (401, 403)


# =============================================================================
# MULTI-TENANT ISOLATION
# =============================================================================

@pytest.mark.django_db
class TestMultiTenantIsolation:
    """User from tenant B cannot extract on tenant A's activity."""

    def test_cross_tenant_activity_returns_400(
        self, authed_api_b, activity, patch_active_provider,
    ):
        with _apply_patches(_bypass_redis):
            resp = authed_api_b.post(
                URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )
        assert resp.status_code == 400


# =============================================================================
# OLD ENDPOINT REGRESSION
# =============================================================================

@pytest.mark.django_db
class TestOldEndpointRegression:
    """The legacy /transcript-signals/extract/ still works."""

    def test_old_endpoint_still_functional(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        fake_provider.replies = {**CANNED_REPLIES_HAPPY}

        with _apply_patches(_bypass_redis_old):
            resp = authed_api_a.post(
                OLD_URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert 'signals_by_stage' in body['data']

    def test_deprecation_header_on_old_endpoint(
        self, authed_api_a, activity, patch_active_provider, fake_provider,
    ):
        fake_provider.replies = {**CANNED_REPLIES_HAPPY}

        with _apply_patches(_bypass_redis_old):
            resp = authed_api_a.post(
                OLD_URL,
                {'activity_id': str(activity.id), 'transcript': TRANSCRIPT},
                format='json',
            )

        assert resp.status_code == 200
        assert resp['Deprecation'] == 'true'
        assert resp['Sunset'] == TRANSCRIPT_SIGNALS_SUNSET_DATE
        assert 'activity-extraction/run/' in resp['Link']
