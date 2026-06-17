# app_modules/ai_pipelines/pipelines/next_steps.py
"""
NextStepsPipeline -- single-stage LLM pipeline that extracts proposed
follow-up actions (NextStepSignal) from a sales-call transcript
(Sprint B4).

Architectural contrast with QualificationSignalsPipeline
--------------------------------------------------------
QualificationSignalsPipeline is multi-stage: 5 stages in series, each
extracting a different qualification axis (Pain / Objective / Impact /
TechStack / Blocker). It iterates over a `_STAGES` descriptor list
inside `.run()`.

NextStepsPipeline is single-stage: one LLM call per run, one
persistence sweep, one sub-call audit entry. No descriptor list, no
loop -- just a linear sequence inside `.run()`. Keeping a separate
class (rather than overloading QualificationSignalsPipeline with a
`next_step` stage) preserves a clean separation:

  * Distinct audit lineage:    pipeline_type = AIPipelineType.NEXT_STEPS
                               (vs TRANSCRIPT_SIGNALS for qualification).
  * Distinct prompt versions:  PROMPT_VERSIONS carries the next-steps
                               request layer version independently.
  * Distinct safety thresholds (today they are equal but the knobs are
                               per-class and could diverge).
  * Distinct return shape:     {'run', 'signals'} flat (single stage)
                               vs {'run', 'signals_by_stage': {...}}
                               nested (multi-stage).

Idempotence / dedup
-------------------
`BasePipeline._hash_input(transcript)` is shared, so a Qualification
run and a NextSteps run on the SAME transcript produce the same
input_hash but distinct AIPipelineRun rows (different pipeline_type).
The view-layer dedup filter in
TranscriptSignalsExtractView._check_db_dedup currently does NOT
disambiguate by pipeline_type -- that surfaces as TD-8 in TECH_DEBT.md
and must be resolved by the unified-endpoint design in Sprint B5.
This pipeline is internal-only at B4 -- no endpoint is exposed -- so
the dedup ambiguity does not manifest in practice yet.

Safety filter
-------------
    CONFIDENCE_MIN = 0.5   -- drop LLM signals with self-declared
                              confidence below this threshold.
    DROP_INFERRED  = True  -- drop signals where the LLM self-declared
                              is_inferred=true (evidence-anchored
                              suggestions only).

The filter itself is applied by NextStepExtractor.persist_extracted,
which delegates to services/safety_filter.py (the policy module
shared with TranscriptSignalExtractor).

Error handling
--------------
Single stage means a single error path. Mapping:

    PromptParseError after retry  -> log error in sub_call.
                                      Final status = PARSE_ERROR.
    LLMTimeoutError               -> Final status = TIMEOUT.
    LLMRateLimitError             -> Final status = LLM_ERROR.
    LLMAuthError                  -> Final status = LLM_ERROR.
    LLMProviderError (generic)    -> Final status = LLM_ERROR.

There is no "partial success" state for a single-stage pipeline -- the
LLM call either yields parseable JSON (SUCCESS) or it does not (one of
the failure states). The PARTIAL status remains unused for
NextStepsPipeline runs.

Return contract
---------------
`.run(*, transcript, activity, user, client_id)` returns a dict:

    {
        'run':     AIPipelineRun (finalised),
        'signals': list[NextStepSignal],
    }

Flat, single-stage shape -- distinct from QualificationSignalsPipeline's
nested `signals_by_stage`. The B5 unified endpoint will compose the
two pipelines into a richer response payload.

Service dependency
------------------
NextStepExtractor.persist_extracted(...) is invoked once per LLM call.
Contract:

    persist_extracted(
        *, raw_signals,        # list[dict] from LLM
           activity,
           user,
           client_id,
           confidence_min,
           drop_inferred,
    ) -> tuple[list[NextStepSignal], int]   # (persisted, dropped_count)

The extractor is imported LAZILY inside .run() to keep the import
graph clean (mirror of QualificationSignalsPipeline's lazy import of
TranscriptSignalExtractor).
"""

from ..constants import AIPipelineStatus, AIPipelineType, PIPELINE_TEMPERATURES
from ..prompts.base import PromptParseError
from ..prompts.transcript_signals.system import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
)
from ..prompts.next_steps.context import (
    build_context_layer,
    CONTEXT_VERSION,
)
from ..prompts.next_steps.next_steps_v1 import (
    build_next_steps_request,
    NEXT_STEPS_PROMPT_VERSION,
)
from ..providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .base import BasePipeline

from django.db import transaction


# Stage identifier used in AIPipelineRun.sub_calls entries. Single
# stage, but the sub_calls JSON column still expects a string label.
_STAGE_NAME = 'next_steps'


class NextStepsPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.NEXT_STEPS

    PROMPT_VERSIONS = {
        'system':     SYSTEM_PROMPT_VERSION,
        'context':    CONTEXT_VERSION,
        'next_steps': NEXT_STEPS_PROMPT_VERSION,
    }

    TEMPERATURE = PIPELINE_TEMPERATURES[AIPipelineType.NEXT_STEPS]

    # Safety filter knobs -- read by NextStepExtractor.persist_extracted().
    # Same defaults as QualificationSignalsPipeline (evidence-anchored
    # suggestions only).
    CONFIDENCE_MIN = 0.5
    DROP_INFERRED = True

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, transcript, activity, user, client_id):
        """
        Execute the single-stage NextSteps pipeline.

        Args:
            transcript: str -- raw transcript. Hashed (sha256) for audit;
                               never persisted in cleartext.
            activity:   app_modules.activities.Activity -- source activity.
            user:       end_users.User -- the rep who triggered the run.
            client_id:  UUID -- tenant scope.

        Returns:
            dict: {
                'run':     AIPipelineRun (finalised),
                'signals': list[NextStepSignal],
            }
        """
        # Lazy import: extractor is in services/, avoids any risk of
        # an import cycle in future refactors.
        from ..services.next_step_extractor import NextStepExtractor

        run = self._create_run(
            user=user,
            client_id=client_id,
            source_activity=activity,
            input_text=transcript,
        )

        try:
            with transaction.atomic():
                try:
                    context_layer = build_context_layer(activity)
                    request_layer = build_next_steps_request(transcript)

                    parsed, sub_call_meta = self._call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        context=context_layer,
                        request=request_layer,
                    )

                    # Defensive: if the LLM returned a JSON shape that lacks
                    # `signals` we treat it as "zero signals emitted" rather
                    # than an error -- the safety filter then drops nothing
                    # and emitted_count=0 is logged in sub_calls.
                    if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
                        raw_signals = parsed['signals']
                    else:
                        raw_signals = []

                    persisted, dropped_count = NextStepExtractor().persist_extracted(
                        raw_signals=raw_signals,
                        activity=activity,
                        user=user,
                        client_id=client_id,
                        confidence_min=self.CONFIDENCE_MIN,
                        drop_inferred=self.DROP_INFERRED,
                        source_run=run,
                    )

                    self._log_sub_call(
                        run,
                        stage=_STAGE_NAME,
                        sub_call_meta=sub_call_meta,
                        parsed=parsed,
                        error=None,
                        dropped_count=dropped_count,
                    )

                # --- Specific subclasses first, then generic LLMProviderError ---
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

            # --- Atomic block committed: finalize the run as SUCCESS ---
            final_run = self._finalize_run(
                run,
                status=AIPipelineStatus.SUCCESS,
                created_signals_count=len(persisted),
                error_message='',
            )
            return {'run': final_run, 'signals': persisted}

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
        canonical empty-signals envelope.

        Used by every error path in `.run()` so the audit row is
        consistent regardless of which exception triggered the failure.
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
        return {'run': final_run, 'signals': []}
