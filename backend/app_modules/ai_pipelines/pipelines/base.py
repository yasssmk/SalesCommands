# app_modules/ai_pipelines/pipelines/base.py
"""
Abstract base for AI pipelines.

Provides the SHARED orchestration scaffolding that every pipeline subclass
relies on: audit-run creation, single-call LLM invocation with parse-retry,
sub-call audit logging, and final-state finalisation. The specific
stage-by-stage orchestration logic lives in each subclass's `run()`
implementation.

Pipeline contract
-----------------
A subclass MUST override:
  * PIPELINE_TYPE       -- a value from AIPipelineType (enum).
  * PROMPT_VERSIONS     -- dict mapping each prompt-layer key to its
                           version string (e.g. {'system': 'v1',
                           'context': 'v1', 'pain': 'v1', ...}).
                           Captured in AIPipelineRun.prompt_versions
                           for audit traceability.
  * run(**kwargs)       -- the actual orchestration of LLM calls and
                           persistence. Receives stable kwargs defined
                           by the subclass.

A subclass MAY override:
  * TEMPERATURE         -- default 0.0 (extraction). Generation
                           pipelines may bump.
  * CONFIDENCE_MIN      -- safety filter threshold on LLM-emitted
                           confidence. Default 0.0 = no filtering;
                           extraction pipelines override.
  * DROP_INFERRED       -- if True, drop signals where is_inferred is
                           true. Default False; extraction pipelines
                           override per stance.

These two filter knobs are READ by downstream services that persist
signals (see TranscriptSignalExtractor). BasePipeline does
not apply them directly -- it merely exposes them as class attributes
so the downstream service can read them per-pipeline.

Run lifecycle
-------------
1. `_create_run(...)`     -- inserts an AIPipelineRun row in
                              status=RUNNING. Returns the row.
2. Per stage:
     `_call_llm(...)`     -- assembles prompts via PromptBuilder,
                              calls the provider, parses the response,
                              retries once on PromptParseError with
                              corrective feedback. Returns
                              (parsed_content, sub_call_meta).
3. Per stage:
     `_log_sub_call(...)` -- appends one entry to run.sub_calls
                              (stage, attempt, tokens, duration,
                              emitted_count, dropped_count, error).
                              Aggregates token / duration counters
                              on the run.
4. End:
     `_finalize_run(...)` -- sets final status (SUCCESS / PARTIAL /
                              PARSE_ERROR / LLM_ERROR / TIMEOUT),
                              created_signals_count, error_message.

Privacy / RGPD
--------------
The raw input (transcript or other prompt input) is NEVER persisted on
AIPipelineRun -- only its SHA-256 hash via the `input_hash` column.
Helper `_hash_input(text)` produces the hash; subclasses pass the raw
text through `_create_run(input_text=...)` and the helper hashes it
before storage.

This keeps audit trails RGPD-friendly: enough to detect retries on the
same input (correlate runs), not enough to reconstruct content. The
DPA with the LLM provider covers the in-flight transcript exposure.

Exception propagation
---------------------
`_call_llm` will:
  * Raise `PromptParseError` if BOTH attempts fail to parse.
  * Propagate any `LLMProviderError` subclass (LLMTimeoutError,
    LLMRateLimitError, LLMAuthError, generic LLMProviderError) without
    catching -- it's up to the subclass `.run()` to decide PARTIAL vs
    LLM_ERROR vs TIMEOUT based on which stage failed and how.
"""

from abc import ABC, abstractmethod
import hashlib
import logging

from ..config import ACTIVE_PROVIDER, get_active_provider_config
from ..constants import AIPipelineStatus
from ..models import AIPipelineRun
from ..prompts.base import PromptBuilder, PromptParseError
from ..providers import get_active_provider


logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """
    Abstract template for AI pipelines.

    See module docstring for the subclass contract and run lifecycle.
    """

    # --- subclass overrides (required) ---
    PIPELINE_TYPE: str = None
    PROMPT_VERSIONS: dict = {}

    # --- subclass overrides (optional, defaults below) ---
    TEMPERATURE: float = 0.0
    CONFIDENCE_MIN: float = 0.0
    DROP_INFERRED: bool = False

    def __init__(self, provider=None):
        """
        Args:
            provider: An LLMProvider instance. Defaults to the active
                provider resolved by get_active_provider() (singleton).
        """
        if not self.PIPELINE_TYPE:
            raise ValueError(
                f'{self.__class__.__name__} must define PIPELINE_TYPE.'
            )
        if not self.PROMPT_VERSIONS:
            raise ValueError(
                f'{self.__class__.__name__} must define PROMPT_VERSIONS.'
            )

        self.provider = provider or get_active_provider()
        self._provider_config = get_active_provider_config()

    @abstractmethod
    def run(self, **kwargs):
        """
        Execute the pipeline. Each subclass implements its own signature.

        Implementations are expected to:
            1. call self._create_run(...) to open the audit row,
            2. invoke LLM calls per stage via self._call_llm(...),
            3. log each sub-call via self._log_sub_call(...),
            4. close with self._finalize_run(...).
        """
        raise NotImplementedError

    # =========================================================================
    # AUDIT HELPERS
    # =========================================================================

    @staticmethod
    def _hash_input(text):
        """SHA-256 hex digest of UTF-8 encoded text. Stable, RGPD-friendly."""
        if text is None:
            text = ''
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _create_run(self, *, user, client_id, source_activity, input_text,
                    source_decision_cycle=None):
        """
        Open an AIPipelineRun row in RUNNING state.

        Args:
            user:                    end_users.User -- the rep who triggered the call.
            client_id:               UUID -- tenant scope (from request auth).
            source_activity:         app_modules.activities.Activity or None.
            input_text:              str -- the raw input. Hashed (sha256), not stored.
            source_decision_cycle:   DecisionCycle or None -- for cycle-level pipelines.

        Returns:
            AIPipelineRun: persisted row, status=RUNNING, sub_calls=[].
        """
        return AIPipelineRun.objects.create(
            pipeline_type=self.PIPELINE_TYPE,
            prompt_versions=dict(self.PROMPT_VERSIONS),
            provider=ACTIVE_PROVIDER,
            model_name=self._provider_config['model'],
            temperature=self.TEMPERATURE,
            source_activity=source_activity,
            source_decision_cycle=source_decision_cycle,
            input_hash=self._hash_input(input_text),
            status=AIPipelineStatus.RUNNING,
            sub_calls=[],
            total_tokens_used=0,
            total_duration_ms=0,
            error_message='',
            created_signals_count=0,
            client_id=client_id,
            created_by=user,
            updated_by=user,
        )

    def _log_sub_call(self, run, *, stage, sub_call_meta=None,
                      parsed=None, error=None, dropped_count=0):
        """
        Append one sub-call entry to run.sub_calls and aggregate counters.

        Args:
            run:           AIPipelineRun being updated.
            stage:         str -- e.g. 'pain', 'objective', 'techstack'.
            sub_call_meta: dict from _call_llm (None on early failure).
            parsed:        parsed LLM response (None on parse / call failure).
            error:         str -- error message; None on success.
            dropped_count: int -- signals dropped by the downstream safety
                                  filter (counted by the persistence service
                                  and passed in here for audit).
        """
        emitted = 0
        if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
            emitted = len(parsed['signals'])

        meta = sub_call_meta or {}
        entry = {
            'stage': stage,
            'attempt': meta.get('attempt', 0),
            'duration_ms': meta.get('duration_ms', 0),
            'input_tokens': meta.get('input_tokens', 0),
            'output_tokens': meta.get('output_tokens', 0),
            'model_used': meta.get('model_used'),
            'emitted_count': emitted,
            'dropped_by_safety_filter': dropped_count,
            'error': error,
        }

        # JSONField list mutation: re-bind to force change detection.
        current = list(run.sub_calls or [])
        current.append(entry)
        run.sub_calls = current

        # Aggregate token + duration counters on the run.
        run.total_tokens_used = (
            (run.total_tokens_used or 0)
            + entry['input_tokens']
            + entry['output_tokens']
        )
        run.total_duration_ms = (
            (run.total_duration_ms or 0)
            + entry['duration_ms']
        )

        run.save()

    def _finalize_run(self, run, *, status, created_signals_count=0,
                      error_message=''):
        """
        Set final status + summary counters on the run.

        Args:
            run:                    AIPipelineRun.
            status:                 AIPipelineStatus value
                                    (SUCCESS / PARTIAL / PARSE_ERROR /
                                     LLM_ERROR / TIMEOUT).
            created_signals_count:  int -- total surviving signals
                                    persisted across all sub-calls.
            error_message:          str -- truncated to 5000 chars.

        Returns:
            AIPipelineRun: refreshed.
        """
        run.status = status
        run.created_signals_count = created_signals_count
        if error_message:
            run.error_message = error_message[:5000]
        run.save()
        return run

    # =========================================================================
    # LLM CALL HELPER (with one retry on parse failure)
    # =========================================================================

    def _call_llm(self, *, system_prompt, context, request,
                  max_tokens=None, timeout_s=None):
        """
        One LLM call with one parse retry on PromptParseError.

        The prompts are assembled by PromptBuilder.assemble() into a
        (system_str, user_str) tuple, sent to the active provider, and
        the response is parsed via PromptBuilder.parse_response()
        (strip_fences + parse_json).

        On a first parse failure, the user prompt is decorated with a
        corrective feedback footer and re-sent ONCE. At temperature 0.0,
        a plain retry would yield the same broken output -- the
        corrective feedback gives the LLM a chance to correct its
        mistake. If the second attempt also fails, PromptParseError is
        propagated to the caller.

        Args:
            system_prompt: str -- the system layer (from system.py).
            context:       str -- the context layer (from context.py).
            request:       str -- the request layer (from <stage>_v1.py).
            max_tokens:    int -- defaults to provider config max_tokens.
            timeout_s:     int -- defaults to provider config timeout_s.

        Returns:
            tuple (parsed_content, sub_call_meta)
                parsed_content: Any -- JSON-parsed LLM response.
                sub_call_meta:  dict -- duration/tokens/model/attempt
                                          for _log_sub_call.

        Raises:
            PromptParseError:  both attempts failed to parse.
            LLMProviderError:  provider-level failure (timeout, rate
                               limit, auth, generic) -- propagated
                               untouched. The caller decides what to do.
        """
        if max_tokens is None:
            max_tokens = self._provider_config['max_tokens']
        if timeout_s is None:
            timeout_s = self._provider_config['timeout_s']

        sys_text, user_text = PromptBuilder.assemble(
            system=system_prompt,
            context=context,
            request=request,
        )

        # --- Attempt 1 ---
        result_1 = self.provider.call(
            system=sys_text,
            user=user_text,
            temperature=self.TEMPERATURE,
            model=self._provider_config['model'],
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        try:
            parsed = PromptBuilder.parse_response(result_1.content)
            return parsed, self._meta_from_result(result_1, attempt=1)
        except PromptParseError as err_1:
            logger.warning(
                'pipeline_parse_failed_attempt_1',
                extra={
                    'pipeline_type': self.PIPELINE_TYPE,
                    'error': str(err_1),
                    'event': 'ai_pipeline_parse',
                },
            )

        # --- Attempt 2 (with corrective feedback) ---
        corrective_user = (
            f"{user_text}\n\n"
            f"---\n\n"
            f"YOUR PREVIOUS RESPONSE FAILED TO PARSE AS JSON.\n"
            f"Return ONLY valid JSON matching the OUTPUT SCHEMA above. "
            f"No markdown fences, no preamble, no commentary. "
            f"Re-emit the response now."
        )

        result_2 = self.provider.call(
            system=sys_text,
            user=corrective_user,
            temperature=self.TEMPERATURE,
            model=self._provider_config['model'],
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

        # If this still raises PromptParseError, propagate to caller.
        parsed = PromptBuilder.parse_response(result_2.content)
        return parsed, self._meta_from_result(result_2, attempt=2)

    @staticmethod
    def _meta_from_result(llm_result, *, attempt):
        """Pack a sub-call metadata dict from an LLMCallResult."""
        return {
            'attempt': attempt,
            'duration_ms': llm_result.duration_ms,
            'input_tokens': llm_result.input_tokens,
            'output_tokens': llm_result.output_tokens,
            'model_used': llm_result.model_used,
        }