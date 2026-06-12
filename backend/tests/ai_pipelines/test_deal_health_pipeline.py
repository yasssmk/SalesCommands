# tests/ai_pipelines/test_deal_health_pipeline.py
"""
Tests for DealHealthPipeline orchestration.

Covers: SUCCESS, PARSE_ERROR, LLM_ERROR (rate limit, auth, generic),
TIMEOUT, and hard crash scenarios — all with a mocked LLM provider.
"""

import pytest
from unittest.mock import patch, MagicMock

from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline
from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.ai_pipelines.providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app_modules.ai_pipelines.prompts.base import PromptParseError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline():
    """Instantiate a pipeline with a mocked provider (bypasses config)."""
    with patch(
        'app_modules.ai_pipelines.pipelines.base.get_active_provider',
    ), patch(
        'app_modules.ai_pipelines.pipelines.base.get_active_provider_config',
        return_value={'model': 'test-model', 'max_tokens': 4096, 'timeout_s': 30},
    ):
        return DealHealthPipeline()


_VALID_DIAGNOSTIC = {
    'global_reading': 'The client recognizes an operational problem.',
    'dimensions': [
        {'key': 'problem_recognized', 'status': 'confirmed', 'evidence': 'Quote A', 'missing': ''},
        {'key': 'felt_pain', 'status': 'missing_evidence', 'evidence': '', 'missing': 'Not explored'},
        {'key': 'impact_understood', 'status': 'unclear', 'evidence': 'Partial', 'missing': 'Quantification'},
        {'key': 'desired_gain', 'status': 'suggested', 'evidence': 'Mentioned goal', 'missing': ''},
        {'key': 'urgency', 'status': 'missing_evidence', 'evidence': '', 'missing': 'No timeline'},
        {'key': 'willingness_to_act', 'status': 'unclear', 'evidence': '', 'missing': 'Budget unclear'},
        {'key': 'solution_trust', 'status': 'suggested', 'evidence': 'Positive demo', 'missing': ''},
    ],
    'discovery_gaps': [
        {
            'kind': 'qualification',
            'dimension': 'felt_pain',
            'public_text': 'Pain depth not yet qualified.',
            'suggested_questions': ['How does this impact your daily work?'],
        },
    ],
    'levers': {
        'desires': [{'summary': 'Better reporting', 'theme': 'OPS:TIME'}],
        'value': [{'summary': '10h/week recoverable', 'theme': 'OPS:TIME'}],
        'cost': [{'summary': 'Budget not owned by champion'}],
        'constraints': [{'summary': 'ROI > 20%', 'rigidity': 'FIRM', 'is_metric': True}],
    },
    'themes': [{'label': 'Ops efficiency', 'summary': 'Pain recognized.'}],
    'evidence_scope': {'validated_signals_count': 5, 'note': 'Based on captured evidence.'},
}

_LLM_SUCCESS_RESPONSE = (
    _VALID_DIAGNOSTIC,
    {'attempt': 1, 'duration_ms': 100, 'input_tokens': 500, 'output_tokens': 300, 'model_used': 'test-model'},
)


def _run_kwargs():
    """Minimal kwargs for pipeline.run()."""
    dc = MagicMock()
    dc.id = 'test-cycle-id'
    dc.client_id = 'test-client-id'
    return {
        'decision_cycle': dc,
        'user': MagicMock(),
        'client_id': 'test-client-id',
    }


# ---------------------------------------------------------------------------
# SUCCESS
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_success_creates_snapshot(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    mock_snapshot = MagicMock()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')) as mock_create, \
         patch.object(pipeline, '_call_llm', return_value=_LLM_SUCCESS_RESPONSE), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock(status=AIPipelineStatus.SUCCESS)) as mock_finalize, \
         patch(
             'app_modules.ai_pipelines.services.deal_health_writer.DealHealthWriter'
         ) as mock_writer_cls:

        mock_writer_cls.return_value.write.return_value = mock_snapshot
        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.SUCCESS

        mock_writer_cls.return_value.write.assert_called_once()
        assert result['snapshot'] is mock_snapshot

        create_kwargs = mock_create.call_args[1]
        assert create_kwargs['source_activity'] is None
        assert create_kwargs['source_decision_cycle'] is not None


# ---------------------------------------------------------------------------
# PARSE_ERROR
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_parse_error_finalized(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=PromptParseError('bad JSON'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.PARSE_ERROR
        assert result['snapshot'] is None


# ---------------------------------------------------------------------------
# TIMEOUT
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_timeout_finalized(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=LLMTimeoutError('provider timed out'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.TIMEOUT
        assert result['snapshot'] is None


# ---------------------------------------------------------------------------
# LLM_ERROR (rate limit)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_rate_limit_finalized(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=LLMRateLimitError('rate limited'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert result['snapshot'] is None


# ---------------------------------------------------------------------------
# LLM_ERROR (auth)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_auth_error_finalized(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=LLMAuthError('invalid key'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert result['snapshot'] is None


# ---------------------------------------------------------------------------
# LLM_ERROR (generic provider error)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_generic_provider_error_finalized(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=LLMProviderError('unknown error'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert result['snapshot'] is None


# ---------------------------------------------------------------------------
# HARD CRASH (re-raised after finalize)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.deal_health.build_diagnostic_request',
    return_value='mock-diagnostic-request',
)
@patch(
    'app_modules.ai_pipelines.services.deal_health_evidence_builder.DealHealthEvidenceBuilder'
)
def test_hard_crash_finalizes_and_reraises(
    mock_builder_cls,
    _mock_diag_req,
    _mock_context,
):
    mock_builder_cls.return_value.build.return_value = {}
    pipeline = _make_pipeline()

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='run-1')), \
         patch.object(pipeline, '_call_llm', return_value=_LLM_SUCCESS_RESPONSE), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize, \
         patch(
             'app_modules.ai_pipelines.services.deal_health_writer.DealHealthWriter'
         ) as mock_writer_cls:

        mock_writer_cls.return_value.write.side_effect = RuntimeError('DB connection lost')

        with pytest.raises(RuntimeError, match='DB connection lost'):
            pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        assert mock_finalize.call_args[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert 'hard crash' in mock_finalize.call_args[1]['error_message']
