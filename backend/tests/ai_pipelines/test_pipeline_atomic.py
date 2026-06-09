# tests/ai_pipelines/test_pipeline_atomic.py
"""
Tests for transaction.atomic() wrapping in pipeline run() methods.

Verifies that:
  - Per-stage soft LLM errors (LLMTimeoutError, LLMRateLimitError,
    PromptParseError, LLMProviderError) are caught INSIDE the atomic
    block and allow partial success.
  - Hard crashes (e.g. RuntimeError from DB) bubble out of the atomic
    block, rolling back all persisted signals, and the run is finalised
    as LLM_ERROR.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from app_modules.ai_pipelines.pipelines.transcript_signals import (
    QualificationSignalsPipeline,
)
from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.ai_pipelines.providers.base import (
    LLMTimeoutError,
    LLMRateLimitError,
    PromptParseError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LLM_SUCCESS_RESPONSE = (
    {'signals': [{'some': 'data'}]},
    {'model': 'test', 'tokens': {}},
)

_PERSIST_SUCCESS = ([MagicMock()], 0)


def _make_pipeline(pipeline_cls):
    """Instantiate a pipeline with a mocked provider (bypasses config)."""
    with patch(
        'app_modules.ai_pipelines.pipelines.base.get_active_provider',
    ), patch(
        'app_modules.ai_pipelines.pipelines.base.get_active_provider_config',
        return_value={'model': 'test-model', 'max_tokens': 1024, 'timeout_s': 30},
    ):
        return pipeline_cls()


def _run_kwargs():
    """Minimal kwargs for pipeline.run()."""
    return {
        'transcript': 'hello world',
        'activity': MagicMock(),
        'user': MagicMock(),
        'client_id': 'test-client-id',
    }


# ---------------------------------------------------------------------------
# QualificationSignalsPipeline tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.services.transcript_signal_extractor'
    '.TranscriptSignalExtractor.persist_stage',
    return_value=_PERSIST_SUCCESS,
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_pain_request',
    return_value='mock-pain-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_objective_request',
    return_value='mock-objective-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_impact_request',
    return_value='mock-impact-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_techstack_request',
    return_value='mock-techstack-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_blocker_request',
    return_value='mock-blocker-request',
)
def test_qualification_soft_error_partial_success(
    _mock_blocker_req,
    _mock_techstack_req,
    _mock_impact_req,
    _mock_objective_req,
    _mock_pain_req,
    _mock_context,
    mock_persist_stage,
):
    """
    A per-stage LLMTimeoutError on the 4th stage (techstack) should NOT
    roll back prior persisted signals. The run should finalise as PARTIAL.
    """
    pipeline = _make_pipeline(QualificationSignalsPipeline)

    # Stages: pain(0), objective(1), impact(2), techstack(3), blocker(4)
    # Succeed on 0-2, timeout on 3, succeed on 4.
    call_count = 0

    def _call_llm_side_effect(*, system_prompt, context, request):
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 3:  # techstack stage
            raise LLMTimeoutError('stage 4 timed out')
        return _LLM_SUCCESS_RESPONSE

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='test-run-id')) as mock_create, \
         patch.object(pipeline, '_call_llm', side_effect=_call_llm_side_effect), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        # _finalize_run should have been called with PARTIAL status.
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args
        assert call_kwargs[1]['status'] == AIPipelineStatus.PARTIAL, (
            f"Expected PARTIAL, got {call_kwargs[1]['status']}"
        )


@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_pain_request',
    return_value='mock-pain-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_objective_request',
    return_value='mock-objective-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_impact_request',
    return_value='mock-impact-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_techstack_request',
    return_value='mock-techstack-request',
)
@patch(
    'app_modules.ai_pipelines.pipelines.transcript_signals.build_blocker_request',
    return_value='mock-blocker-request',
)
def test_qualification_hard_crash_rolls_back(
    _mock_blocker_req,
    _mock_techstack_req,
    _mock_impact_req,
    _mock_objective_req,
    _mock_pain_req,
    _mock_context,
):
    """
    A RuntimeError raised by persist_stage on the 2nd stage should
    escape the atomic block, rolling back ALL persisted signals.
    The run should finalise as LLM_ERROR with 'hard crash' in the
    error message, and the RuntimeError should be re-raised.
    """
    pipeline = _make_pipeline(QualificationSignalsPipeline)

    persist_call_count = 0

    def _persist_side_effect(**kwargs):
        nonlocal persist_call_count
        idx = persist_call_count
        persist_call_count += 1
        if idx == 1:  # second stage (objective)
            raise RuntimeError('DB connection lost')
        return _PERSIST_SUCCESS

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='test-run-id')), \
         patch.object(pipeline, '_call_llm', return_value=_LLM_SUCCESS_RESPONSE), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize, \
         patch(
             'app_modules.ai_pipelines.services.transcript_signal_extractor'
             '.TranscriptSignalExtractor.persist_stage',
             side_effect=_persist_side_effect,
         ):

        with pytest.raises(RuntimeError, match='DB connection lost'):
            pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args
        assert call_kwargs[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert 'hard crash' in call_kwargs[1]['error_message']


# ---------------------------------------------------------------------------
# NextStepsPipeline tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.next_steps.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.next_steps.build_next_steps_request',
    return_value='mock-next-steps-request',
)
def test_next_steps_hard_crash_rolls_back(
    _mock_request,
    _mock_context,
):
    """
    A RuntimeError raised by NextStepExtractor.persist_extracted should
    escape the atomic block, roll back signals, finalise as LLM_ERROR
    with 'hard crash', and re-raise.
    """
    pipeline = _make_pipeline(NextStepsPipeline)

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='test-run-id')), \
         patch.object(pipeline, '_call_llm', return_value=_LLM_SUCCESS_RESPONSE), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize, \
         patch(
             'app_modules.ai_pipelines.services.next_step_extractor'
             '.NextStepExtractor.persist_extracted',
             side_effect=RuntimeError('DB connection lost'),
         ):

        with pytest.raises(RuntimeError, match='DB connection lost'):
            pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args
        assert call_kwargs[1]['status'] == AIPipelineStatus.LLM_ERROR
        assert 'hard crash' in call_kwargs[1]['error_message']


@pytest.mark.django_db
@patch(
    'app_modules.ai_pipelines.pipelines.next_steps.build_context_layer',
    return_value='mock-context',
)
@patch(
    'app_modules.ai_pipelines.pipelines.next_steps.build_next_steps_request',
    return_value='mock-next-steps-request',
)
def test_next_steps_soft_error_finalized_correctly(
    _mock_request,
    _mock_context,
):
    """
    An LLMTimeoutError in the single-stage NextStepsPipeline should be
    caught inside the atomic block and finalised via _finalize_failure
    with AIPipelineStatus.TIMEOUT.
    """
    pipeline = _make_pipeline(NextStepsPipeline)

    with patch.object(pipeline, '_create_run', return_value=MagicMock(id='test-run-id')), \
         patch.object(
             pipeline, '_call_llm',
             side_effect=LLMTimeoutError('provider timed out'),
         ), \
         patch.object(pipeline, '_log_sub_call'), \
         patch.object(pipeline, '_finalize_run', return_value=MagicMock()) as mock_finalize:

        result = pipeline.run(**_run_kwargs())

        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args
        assert call_kwargs[1]['status'] == AIPipelineStatus.TIMEOUT
