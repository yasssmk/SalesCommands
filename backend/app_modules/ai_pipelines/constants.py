# app_modules/ai_pipelines/constants.py
"""
Constants for the AI Pipelines module.

Two enums define the module's primary classification axes:

  - AIPipelineType   : identifies which pipeline business case ran.
                       One value per orchestration use case. Drives
                       audit grouping ("show me all transcript
                       extractions across the tenant") and may also
                       drive per-type rate limits or feature flags
                       in future iterations.

  - AIPipelineStatus : terminal or in-progress state of a pipeline
                       run. Mirrors the lifecycle implemented in
                       pipelines/base.py — RUNNING set at start;
                       SUCCESS / PARTIAL / PARSE_ERROR / LLM_ERROR /
                       TIMEOUT set at finalisation.

Both enums follow the `models.TextChoices` pattern used across the
project (cf. SignalStatus, SignalSource in app_modules/signals/
constants.py) so that AIPipelineRun's `pipeline_type` and `status`
columns surface the values directly in the Django admin and DRF
serializers without manual choice mapping.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


# =============================================================================
# PIPELINE TYPE
# =============================================================================

class AIPipelineType(models.TextChoices):
    """
    Identifies which pipeline business case produced an AIPipelineRun
    audit record.

    Values:
      TRANSCRIPT_SIGNALS — produced by QualificationSignalsPipeline.
                            Extracts PainSignal / ObjectiveSignal /
                            ImpactSignal / TechStackSignal /
                            BlockerSignal records from a sales-call
                            transcript. Originally introduced as a
                            4-stage pipeline (Pain / Objective / Impact
                            / TechStack) under the legacy class name
                            TranscriptSignalsPipeline; Sprint B3 added
                            the Blocker stage and renamed the class to
                            QualificationSignalsPipeline. The enum
                            VALUE is intentionally NOT renamed --
                            historical AIPipelineRun rows store the
                            string 'TRANSCRIPT_SIGNALS' and migrating
                            them carries no functional benefit.

    Adding new values:
      Each new pipeline (game plan generation, next-step extraction,
      semantic retrieval, ...) adds one value here AND a corresponding
      orchestrator module under pipelines/. The two must stay in
      lockstep — `AIPipelineRun.pipeline_type` is the audit key for
      filtering runs in support tooling and dashboards.
    """
    TRANSCRIPT_SIGNALS = 'TRANSCRIPT_SIGNALS', _('Transcript signal extraction')


# =============================================================================
# PIPELINE STATUS
# =============================================================================

class AIPipelineStatus(models.TextChoices):
    """
    Lifecycle state of an AIPipelineRun.

    Set by the pipeline orchestrator at well-defined moments:

      RUNNING      Set at pipeline.run() entry, BEFORE any provider
                   call. The audit row therefore captures the
                   attempt even if the process dies mid-call (the
                   row stays in RUNNING — a separate sweep job can
                   later flag stale RUNNING rows as failed).

      SUCCESS      All sub-calls completed AND all parsed payloads
                   yielded persisted records — zero exceptions,
                   zero partial outputs.

      PARTIAL      At least one sub-call succeeded AND at least one
                   sub-call failed (parse error, LLM error, or
                   timeout). Some signals were persisted; the rest
                   are surfaced as errors to the rep via the API
                   response. Used by TranscriptSignalsPipeline when
                   e.g. Pain + Objective extraction succeed but
                   TechStack times out.

      PARSE_ERROR  An LLM response could not be parsed as the
                   expected JSON shape, even after a re-prompt
                   attempt. The offending raw output is captured in
                   AIPipelineRun.sub_calls JSON for diagnostic
                   review.

      LLM_ERROR    The LLM provider returned an error — rate limit,
                   auth failure, unexpected status code, content
                   filter trigger. Mapped from provider-specific
                   exceptions by providers/__init__.py.

      TIMEOUT      A provider call exceeded the configured per-call
                   timeout (see config.PROVIDER_CONFIG).

    Aggregation semantics:
      PARSE_ERROR / LLM_ERROR / TIMEOUT are TERMINAL failures at the
      run level — no signals persisted. PARTIAL covers the mixed
      case. SUCCESS is reserved for the strictly happy path. RUNNING
      is the only non-terminal state.

    Deliberately absent:
      REJECTED / CANCELLED — the MVP pipeline has no human-cancel
      surface (calls are sequential and synchronous). Adding either
      state requires a cancellation mechanism in pipelines/base.py;
      deferred until concurrency is introduced.
    """
    RUNNING     = 'RUNNING',     _('Running')
    SUCCESS     = 'SUCCESS',     _('Success')
    PARTIAL     = 'PARTIAL',     _('Partial success')
    PARSE_ERROR = 'PARSE_ERROR', _('Parse error')
    LLM_ERROR   = 'LLM_ERROR',   _('LLM provider error')
    TIMEOUT     = 'TIMEOUT',     _('Timeout')