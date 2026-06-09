# app_modules/ai_pipelines/pipelines/transcript_signals.py

"""
QualificationSignalsPipeline -- the concrete pipeline that extracts
Pain / Objective / Impact / TechStack / Blocker signals from a sales
transcript via 5 sequential LLM sub-calls.

Naming note (Sprint B3 rename)
------------------------------
This class was originally named TranscriptSignalsPipeline. It was
renamed to QualificationSignalsPipeline when the Blocker stage landed
(Sprint B3) to better reflect the MEDDPICC-style scope of the pipeline
(qualification axes across the whole conversation, not "raw transcript
signals"). The previous name is kept as an alias at the bottom of this
module for backwards compatibility -- both class names resolve to the
same class.

The underlying AIPipelineType.TRANSCRIPT_SIGNALS enum value is
DELIBERATELY unchanged: historical AIPipelineRun rows store that string,
and renaming it would require a data migration with no functional
benefit. The "qualification" framing lives in Python; the DB and the
URL surface keep the legacy name. The endpoint URL
(/module-ai-pipelines/transcript-signals/extract/) also stays
operational this sprint -- deprecation deferred to Sprint B5.

Sub-call sequence
-----------------
    pain      -> Pain signals       (4 narrative + 2 epistemic fields)
    objective -> Objective signals  (4 narrative + 2 epistemic; service
                                       forces scope_level=BUSINESS)
    impact    -> Impact signals     (5 narrative + 2 epistemic; service
                                       forces scope_level=BUSINESS and
                                       leaves metric_text / human_impact
                                       unset -- rep fills during
                                       validation)
    techstack -> TechStack signals  (4 techstack + 2 epistemic; catalog
                                       matching via context layer)
    blocker   -> Blocker signals    (2 narrative + 2 epistemic; no
                                       canonical taxonomy axes; contact
                                       attribution deferred to rep at
                                       validation -- see TD-6)

Each sub-call shares system prompt + context, varying only the request
layer. The context layer includes the TechCatalog UUIDs only on the
techstack stage (token economy). The context layer SKIPS the taxonomy
block entirely on the blocker stage (BlockerSignal has no canonical
axes).

Safety filter
-------------
    CONFIDENCE_MIN = 0.5   -- drop LLM signals with self-declared
                              confidence below this threshold.
    DROP_INFERRED  = True  -- drop signals where the LLM self-declared
                              is_inferred=true (verbatim-anchored only).

The filter itself is applied by TranscriptSignalExtractor, per stage.
The pipeline only OWNS the thresholds and propagates them
into the extractor; it does not see the dropped signals -- only the
dropped count, which is logged into AIPipelineRun.sub_calls for audit.
End users never see dropped signals.

Error handling per stage
------------------------
    * PromptParseError after retry  -> log error, continue.
                                        Stage contributes 0 signals.
    * LLMTimeoutError               -> log "timeout", continue.
    * LLMRateLimitError             -> log "rate_limit", continue.
                                        (Other stages may still succeed.)
    * LLMAuthError                  -> FATAL. Abort the pipeline,
                                        subsequent stages NOT attempted
                                        (the credential is dead).
                                        Run finalised as LLM_ERROR.
    * LLMProviderError (generic)    -> log, continue.

Final status determination
--------------------------
    All 5 stages succeeded               -> SUCCESS
    1, 2, 3 or 4 stages succeeded        -> PARTIAL
    0 succeeded, all 'parse_error'       -> PARSE_ERROR
    0 succeeded, all 'timeout'           -> TIMEOUT
    0 succeeded, mixed failures          -> LLM_ERROR
    Aborted on LLMAuthError              -> LLM_ERROR

Return contract
---------------
`.run(*, transcript, activity, user, client_id)` returns a dict:

    {
        'run':                AIPipelineRun (finalised),
        'signals_by_stage': {
            'pain':       list[PainSignal],
            'objective':  list[ObjectiveSignal],
            'impact':     list[ImpactSignal],
            'techstack':  list[TechStackSignal],
            'blocker':    list[BlockerSignal],
        }
    }

The API view consumes this directly, grouping signals by type for the
frontend wizard.

Service dependency
------------------
TranscriptSignalExtractor.persist_stage(...) is invoked once per
successful LLM stage. Contract:

    persist_stage(
        *, stage,           # 'pain' | 'objective' | 'impact' | 'techstack'
                            # | 'blocker'
           raw_signals,     # list[dict] from LLM
           activity,
           user,
           client_id,
           confidence_min,
           drop_inferred,
    ) -> tuple[list[BaseSignal], int]   # (persisted, dropped_count)

The extractor is imported LAZILY inside .run() to avoid any risk of
an import cycle if a future refactor has F.3 reading pipeline class
attributes.
"""

from ..constants import AIPipelineStatus, AIPipelineType
from ..prompts.base import PromptParseError
from ..prompts.transcript_signals.system import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
)
from ..prompts.transcript_signals.context import (
    build_context_layer,
    CONTEXT_VERSION,
)
from ..prompts.transcript_signals.pain_v1 import (
    build_pain_request,
    PAIN_PROMPT_VERSION,
)
from ..prompts.transcript_signals.objective_v1 import (
    build_objective_request,
    OBJECTIVE_PROMPT_VERSION,
)
from ..prompts.transcript_signals.impact_v1 import (
    build_impact_request,
    IMPACT_PROMPT_VERSION,
)
from ..prompts.transcript_signals.techstack_v1 import (
    build_techstack_request,
    TECHSTACK_PROMPT_VERSION,
)
from ..prompts.transcript_signals.blocker_v1 import (
    build_blocker_request,
    BLOCKER_PROMPT_VERSION,
)
from ..providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .base import BasePipeline

from django.db import transaction


# Stage descriptors: (stage_name, request_builder).
# Ordered list = call order. Future stage insertions go here.
#
# The blocker stage is intentionally LAST: it is the only non-canonical
# stage (no taxonomy, no clustering, no catalog matching), and running
# it after the canonical-axis stages keeps the prompt sequence aligned
# with the rep's mental flow (qualification first, then "what stands
# in the way").
_STAGES = [
    ('pain', build_pain_request),
    ('objective', build_objective_request),
    ('impact', build_impact_request),
    ('techstack', build_techstack_request),
    ('blocker', build_blocker_request),
]


class QualificationSignalsPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.TRANSCRIPT_SIGNALS

    PROMPT_VERSIONS = {
        'system':    SYSTEM_PROMPT_VERSION,
        'context':   CONTEXT_VERSION,
        'pain':      PAIN_PROMPT_VERSION,
        'objective': OBJECTIVE_PROMPT_VERSION,
        'impact':    IMPACT_PROMPT_VERSION,
        'techstack': TECHSTACK_PROMPT_VERSION,
        'blocker':   BLOCKER_PROMPT_VERSION,
    }

    TEMPERATURE = 0.0

    # Safety filter knobs -- read by TranscriptSignalExtractor.persist_stage().
    # Strict defaults for signal extraction (vs. e.g. sentiment analysis):
    # we want verbatim-anchored signals only.
    CONFIDENCE_MIN = 0.5
    DROP_INFERRED = True

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, transcript, activity, user, client_id):
        """
        Execute the 5-stage pipeline.

        Args:
            transcript: str -- raw transcript. Hashed (sha256) for audit;
                               never persisted in cleartext.
            activity:   app_modules.activities.Activity -- source activity.
            user:       end_users.User -- the rep who triggered the run.
            client_id:  UUID -- tenant scope.

        Returns:
            dict: {
                'run':              AIPipelineRun (finalised),
                'signals_by_stage': {
                    'pain':      list[PainSignal],
                    'objective': list[ObjectiveSignal],
                    'impact':    list[ImpactSignal],
                    'techstack': list[TechStackSignal],
                    'blocker':   list[BlockerSignal],
                },
            }
        """
        # Lazy import: extractor is in services/, may evolve to read pipeline
        # class attributes -- defensive against future import cycles.
        from ..services.transcript_signal_extractor import (
            TranscriptSignalExtractor,
        )

        run = self._create_run(
            user=user,
            client_id=client_id,
            source_activity=activity,
            input_text=transcript,
        )

        extractor = TranscriptSignalExtractor()
        signals_by_stage = {name: [] for name, _ in _STAGES}
        stage_outcomes = {}     # stage_name -> outcome string
        total_persisted = 0
        fatal_aborted = False

        try:
            with transaction.atomic():
                for stage_name, request_builder in _STAGES:
                    try:
                        context_layer = build_context_layer(activity, target_stage=stage_name)
                        request_layer = request_builder(transcript)

                        parsed, sub_call_meta = self._call_llm(
                            system_prompt=SYSTEM_PROMPT,
                            context=context_layer,
                            request=request_layer,
                        )

                        # Defensive: if the LLM returned a JSON shape that lacks
                        # `signals` we treat it as "zero signals emitted" rather
                        # than an error -- the safety filter will then drop nothing
                        # and we log emitted_count=0 in sub_calls.
                        if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
                            raw_signals = parsed['signals']
                        else:
                            raw_signals = []

                        persisted, dropped_count = extractor.persist_stage(
                            stage=stage_name,
                            raw_signals=raw_signals,
                            activity=activity,
                            user=user,
                            client_id=client_id,
                            confidence_min=self.CONFIDENCE_MIN,
                            drop_inferred=self.DROP_INFERRED,
                        )

                        signals_by_stage[stage_name] = persisted
                        total_persisted += len(persisted)
                        stage_outcomes[stage_name] = 'success'

                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=sub_call_meta,
                            parsed=parsed,
                            error=None,
                            dropped_count=dropped_count,
                        )

                    # --- Specific subclasses first, then generic LLMProviderError ---

                    except LLMAuthError as exc:
                        # Credential is dead -- abort the pipeline, do NOT attempt
                        # subsequent stages. The fatal flag is consumed in the
                        # final-status derivation.
                        stage_outcomes[stage_name] = 'auth_error'
                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=None,
                            parsed=None,
                            error=f'auth_error: {exc}',
                            dropped_count=0,
                        )
                        fatal_aborted = True
                        break

                    except LLMTimeoutError as exc:
                        stage_outcomes[stage_name] = 'timeout'
                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=None,
                            parsed=None,
                            error=f'timeout: {exc}',
                            dropped_count=0,
                        )

                    except LLMRateLimitError as exc:
                        stage_outcomes[stage_name] = 'rate_limit'
                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=None,
                            parsed=None,
                            error=f'rate_limit: {exc}',
                            dropped_count=0,
                        )

                    except PromptParseError as exc:
                        stage_outcomes[stage_name] = 'parse_error'
                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=None,
                            parsed=None,
                            error=f'parse_error: {exc}',
                            dropped_count=0,
                        )

                    except LLMProviderError as exc:
                        # Generic provider failure -- catch-all for the
                        # LLMProviderError hierarchy AFTER the specific subclasses
                        # above. Order matters: Python catches the first matching
                        # except clause.
                        stage_outcomes[stage_name] = 'provider_error'
                        self._log_sub_call(
                            run,
                            stage=stage_name,
                            sub_call_meta=None,
                            parsed=None,
                            error=f'provider_error: {exc}',
                            dropped_count=0,
                        )

        except Exception as exc:
            self._finalize_run(
                run,
                status=AIPipelineStatus.LLM_ERROR,
                created_signals_count=0,
                error_message=f'hard crash: {str(exc)[:1000]}',
            )
            raise

        # --- Final status derivation + finalisation ---
        final_status, final_error = self._derive_final_status(
            stage_outcomes,
            fatal_aborted=fatal_aborted,
        )

        final_run = self._finalize_run(
            run,
            status=final_status,
            created_signals_count=total_persisted,
            error_message=final_error,
        )

        return {
            'run': final_run,
            'signals_by_stage': signals_by_stage,
        }

    # =========================================================================
    # FINAL STATUS DERIVATION
    # =========================================================================

    @staticmethod
    def _derive_final_status(stage_outcomes, *, fatal_aborted):
        """
        Map per-stage outcomes to a single AIPipelineStatus + error message.

        Priority:
            1. fatal_aborted (LLMAuthError) -> LLM_ERROR.
            2. All stages succeeded         -> SUCCESS.
            3. At least one succeeded       -> PARTIAL.
            4. All stages failed:
                * all 'parse_error'  -> PARSE_ERROR
                * all 'timeout'      -> TIMEOUT
                * mixed / other      -> LLM_ERROR

        Args:
            stage_outcomes: dict mapping stage_name -> outcome string.
            fatal_aborted:  bool -- True if pipeline was aborted on auth error.

        Returns:
            tuple (AIPipelineStatus value, error_message string)
        """
        if fatal_aborted:
            return AIPipelineStatus.LLM_ERROR, 'aborted on authentication error'

        outcomes = list(stage_outcomes.values())
        if not outcomes:
            # No stage ever executed -- shouldn't happen with _STAGES non-empty,
            # but defensive for future single-stage pipelines.
            return AIPipelineStatus.LLM_ERROR, 'no stage executed'

        total = len(outcomes)
        success_count = sum(1 for o in outcomes if o == 'success')

        if success_count == total:
            return AIPipelineStatus.SUCCESS, ''

        if success_count > 0:
            failed = {s: o for s, o in stage_outcomes.items() if o != 'success'}
            return AIPipelineStatus.PARTIAL, f'failed stages: {failed}'

        # success_count == 0 -- every stage failed.
        failures = [o for o in outcomes if o != 'success']
        if all(f == 'parse_error' for f in failures):
            return AIPipelineStatus.PARSE_ERROR, 'all stages failed to parse'
        if all(f == 'timeout' for f in failures):
            return AIPipelineStatus.TIMEOUT, 'all stages timed out'
        return AIPipelineStatus.LLM_ERROR, f'all stages failed: {stage_outcomes}'


# =============================================================================
# BACKWARDS-COMPAT ALIAS
# =============================================================================
#
# Sprint B3 renamed the class from TranscriptSignalsPipeline to
# QualificationSignalsPipeline to reflect the broader MEDDPICC framing
# (Pain / Objective / Impact / TechStack + Blocker). The legacy name is
# preserved as an alias so any external import that still spells
# `TranscriptSignalsPipeline` keeps resolving to the same class without
# behavioural change.
#
# Internal callers updated to the new name during the same sprint:
#   - views/transcript_signals_view.py
#
# Remove this alias once no internal caller spells the legacy name and
# the deprecation window (B5) has closed.
TranscriptSignalsPipeline = QualificationSignalsPipeline