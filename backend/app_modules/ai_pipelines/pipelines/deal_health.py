# app_modules/ai_pipelines/pipelines/deal_health.py
"""
DealHealthPipeline -- single-stage LLM pipeline that produces a
structured diagnostic snapshot of a DecisionCycle from validated
signals.

Single stage: one LLM call, one structural validation + snapshot
persistence, one sub-call audit entry.

Error handling mirrors NextStepsPipeline (single stage = no PARTIAL):

    PromptParseError after retry  -> PARSE_ERROR.
    LLMTimeoutError               -> TIMEOUT.
    LLMRateLimitError             -> LLM_ERROR.
    LLMAuthError                  -> LLM_ERROR.
    LLMProviderError (generic)    -> LLM_ERROR.

Return contract:
    .run(*, decision_cycle, user, client_id) -> {
        'run':      AIPipelineRun (finalised),
        'snapshot': DealHealthSnapshot | None,
    }
"""

import json

from ..constants import AIPipelineStatus, AIPipelineType, PIPELINE_TEMPERATURES
from ..prompts.base import PromptParseError
from ..prompts.deal_health import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    build_context_layer,
    CONTEXT_VERSION,
    build_diagnostic_request,
    DIAGNOSTIC_PROMPT_VERSION,
)
from ..providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .base import BasePipeline

from django.db import transaction


_STAGE_NAME = 'diagnostic'


class DealHealthPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.DEAL_HEALTH

    PROMPT_VERSIONS = {
        'system':     SYSTEM_PROMPT_VERSION,
        'context':    CONTEXT_VERSION,
        'diagnostic': DIAGNOSTIC_PROMPT_VERSION,
    }

    TEMPERATURE = PIPELINE_TEMPERATURES[AIPipelineType.DEAL_HEALTH]

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, decision_cycle, user, client_id):
        """
        Execute the single-stage deal-health diagnostic pipeline.

        Args:
            decision_cycle: DecisionCycle instance.
            user:           end_users.User -- the rep who triggered the run.
            client_id:      UUID -- tenant scope.

        Returns:
            dict: {
                'run':      AIPipelineRun (finalised),
                'snapshot': DealHealthSnapshot | None,
            }
        """
        from ..services.deal_health_evidence_builder import DealHealthEvidenceBuilder
        from ..services.deal_health_writer import DealHealthWriter

        pack = DealHealthEvidenceBuilder().build(decision_cycle)
        input_text = json.dumps(pack, default=str)

        try:
            with transaction.atomic():
                run = self._create_run(
                    user=user,
                    client_id=client_id,
                    source_activity=None,
                    source_decision_cycle=decision_cycle,
                    input_text=input_text,
                )

                try:
                    context_layer = build_context_layer(pack)
                    request_layer = build_diagnostic_request(pack)

                    parsed, sub_call_meta = self._call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        context=context_layer,
                        request=request_layer,
                    )

                    snapshot = DealHealthWriter().write(
                        parsed=parsed,
                        decision_cycle=decision_cycle,
                        run=run,
                        user=user,
                        client_id=client_id,
                    )

                    self._log_sub_call(
                        run,
                        stage=_STAGE_NAME,
                        sub_call_meta=sub_call_meta,
                        parsed=parsed,
                        error=None,
                        dropped_count=0,
                    )

                except LLMTimeoutError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.TIMEOUT,
                        error_label='timeout',
                        exc=exc,
                    )
                except LLMRateLimitError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='rate_limit',
                        exc=exc,
                    )
                except LLMAuthError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='auth_error',
                        exc=exc,
                    )
                except PromptParseError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.PARSE_ERROR,
                        error_label='parse_error',
                        exc=exc,
                    )
                except LLMProviderError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='provider_error',
                        exc=exc,
                    )

                final_run = self._finalize_run(
                    run,
                    status=AIPipelineStatus.SUCCESS,
                    created_signals_count=0,
                    error_message='',
                )
            return {'run': final_run, 'snapshot': snapshot}

        except Exception as exc:
            self._finalize_run(
                run,
                status=AIPipelineStatus.LLM_ERROR,
                created_signals_count=0,
                error_message=f'hard crash: {str(exc)[:1000]}',
            )
            raise

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _finalize_failure(self, run, *, status, error_label, exc):
        """
        Log a failed sub-call entry, finalise the run, and return the
        canonical empty-snapshot envelope.
        """
        error_message = f'{error_label}: {exc}'
        self._log_sub_call(
            run,
            stage=_STAGE_NAME,
            sub_call_meta=None,
            parsed=None,
            error=error_message,
            dropped_count=0,
        )
        final_run = self._finalize_run(
            run,
            status=status,
            created_signals_count=0,
            error_message=error_message,
        )
        return {'run': final_run, 'snapshot': None}
