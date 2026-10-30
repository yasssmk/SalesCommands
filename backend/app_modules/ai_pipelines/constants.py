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

      NEXT_STEPS         — produced by NextStepsPipeline (Sprint B4).
                            Extracts NextStepSignal records (proposed
                            follow-up actions) from a sales-call
                            transcript. Single-stage pipeline -- no
                            taxonomy block, no clustering, no contact
                            attribution at v1 (deferred to the rep
                            during validation, tracked as TD-7).
                            Co-exists with TRANSCRIPT_SIGNALS runs on
                            the same transcript: both pipelines share
                            the same input_hash but distinct
                            pipeline_type values, so AIPipelineRun
                            rows are not deduplicated against each
                            other -- see TD-8 for the view-layer
                            dedup filter that must learn about
                            pipeline_type in Sprint B5.

      DEAL_HEALTH         — produced by DealHealthPipeline.
                            Produces a single structured diagnostic
                            snapshot (DealHealthSnapshot) for a
                            DecisionCycle. Cycle-level pipeline — no
                            source_activity, no signal creation (output
                            is a JSON diagnostic, not individual signal
                            rows). Single-stage, single LLM call.
                            created_signals_count is always 0; the
                            deliverable is the snapshot, not signals.

      NEXT_STEPS_ADVICE   — produced by the next steps advice pass (Sprint
                            Next steps): a 2nd LLM read, after the
                            extraction, that proposes the next steps the
                            follow-up is missing. Its NextStepSignal rows
                            carry source_run = this run, which is how the
                            "Conseillé" mark is read (no column).

    Adding new values:
      Each new pipeline (game plan generation, semantic retrieval,
      ...) adds one value here AND a corresponding orchestrator
      module under pipelines/. The two must stay in lockstep --
      `AIPipelineRun.pipeline_type` is the audit key for filtering
      runs in support tooling and dashboards.
    """
    TRANSCRIPT_SIGNALS = 'TRANSCRIPT_SIGNALS', _('Transcript signal extraction')
    NEXT_STEPS         = 'NEXT_STEPS',         _('Next steps extraction')
    DEAL_HEALTH        = 'DEAL_HEALTH',        _('Deal health diagnostic')
    PREP_CALL          = 'PREP_CALL',          _('Prep call brief')
    NEXT_STEPS_ADVICE  = 'NEXT_STEPS_ADVICE',  _('Next steps advice')


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


# =============================================================================
# PIPELINE TEMPERATURES
# =============================================================================

PIPELINE_TEMPERATURES = {
    AIPipelineType.TRANSCRIPT_SIGNALS: 0.0,
    AIPipelineType.NEXT_STEPS:         0.0,
    AIPipelineType.DEAL_HEALTH:        0.2,
    AIPipelineType.PREP_CALL:          0.3,
}


# =============================================================================
# SAFETY FILTER THRESHOLDS
# =============================================================================
#
# Applied by the extractors (services/safety_filter.passes_safety_filter) to
# every LLM-emitted signal before persistence. One entry per FILTERING
# pipeline (mirror of PIPELINE_TEMPERATURES): each pipeline owns its policy,
# even when the values coincide today. Deal health / prep call do not filter
# (BasePipeline neutral defaults: 0.0 / False).

# Drop a signal whose self-declared confidence is missing or below this floor.
PIPELINE_CONFIDENCE_MIN = {
    AIPipelineType.TRANSCRIPT_SIGNALS: 0.5,
    AIPipelineType.NEXT_STEPS:         0.5,
}

# Drop a signal whose self-declared is_inferred is True (verbatim-anchored).
# TRANSCRIPT_SIGNALS: False since TD-279 C1 (PO decision) -- a deduction from
# what the transcript says is a legitimate observation the rep validates, for
# EVERY stage (People already kept it since S1); a weak deduction is still
# dropped by PIPELINE_CONFIDENCE_MIN. NEXT_STEPS: False since TD-282 (1) --
# same policy, an inferred next step is kept and the rep validates it.
PIPELINE_DROP_INFERRED = {
    AIPipelineType.TRANSCRIPT_SIGNALS: False,
    AIPipelineType.NEXT_STEPS:         False,
}


# =============================================================================
# TRANSCRIPT HEADER DATE (D7 / TD-281)
# =============================================================================

# A meeting export opens with a header line that carries the meeting's REAL
# date -- "Atelier business case SalesCommands – Logistix - 2026/10/20 14:00
# CEST - Transcript" (evals/td279/transcript_atelier.txt:1). That date is the
# reference of every relative date said in the transcript; the activity's date
# in the app is only the fallback (services/transcript_text.header_date).
# ONLY this proven format is read, on the FIRST non-empty line; groups =
# year, month, day.
TRANSCRIPT_HEADER_DATE_PATTERN = (
    r' - (\d{4})/(\d{2})/(\d{2}) \d{1,2}:\d{2}\b[^\n]* - Transcript\s*$'
)


# =============================================================================
# NEXT STEPS CONTEXT -- DECISION CYCLE (Sprint Next steps 3.2, context v6)
# =============================================================================

# Reference of a decision-cycle step in the next_steps context ("S4" = the
# step of order 4): unique within a cycle, stable, short. The server maps a
# reference the model returns back to the step through the same format.
NEXT_STEPS_STEP_REF_FORMAT = 'S{order}'


# =============================================================================
# NEXT STEPS PERSISTENCE -- DEDUP WITHIN ONE ANSWER (Sprint Next steps 3.4)
# =============================================================================

# Two next steps of the SAME LLM answer (one transcript) with the same values
# on these fields -- text compared normalised (transcript_text.normalize_text:
# case, whitespace, quotes) -- are one action: the first is kept, the others
# are dropped (counted). Never applied across activities. Conservative on
# purpose: a paraphrased title is NOT merged (one distinct action = one next
# step, prompt v2 rule 1); the eval measures what remains.
NEXT_STEP_DEDUP_KEY = ('suggested_title', 'suggested_activity_type', 'suggested_due_date')


# =============================================================================
# PEOPLE ROLE IN THE PROMPT PACKS (prep_call / deal_health)
# =============================================================================

# TD-279 U (PO): a PeopleSignal of role UNKNOWN reaches the prep_call and
# deal_health packs as a role still to qualify -- never filtered out, never
# as the bare "UNKNOWN" code (read as "no role" / "no stakeholder").
PEOPLE_ROLE_TO_QUALIFY = 'role to qualify'


def people_role_for_prompt(role):
    """The PeopleSignal role as sent to an LLM pack: the code, or
    PEOPLE_ROLE_TO_QUALIFY for UNKNOWN."""
    from app_modules.signals.constants import PeopleRole
    return PEOPLE_ROLE_TO_QUALIFY if role == PeopleRole.UNKNOWN else role


# =============================================================================
# PEOPLE EVIDENCE CHECK (TD-279 V)
# =============================================================================

class PeopleEvidenceStatus(models.TextChoices):
    """
    Server check of a People observation's source_quote, stored in
    PeopleSignal.metadata.evidence_check.status (services/people_evidence.py).

    OK                     -- the quote is in the transcript and, for a
                              SPEAKER, said by them or naming them.
    QUOTE_NOT_FOUND        -- the quote is not in the transcript.
    QUOTE_NOT_ABOUT_PERSON -- the person speaks, but the quote is neither
                              theirs nor names them.

    A rejected proof never drops the person: role -> PeopleRole.UNKNOWN.
    """
    OK                     = 'ok',                     _('Ok')
    QUOTE_NOT_FOUND        = 'quote_not_found',        _('Quote not found')
    QUOTE_NOT_ABOUT_PERSON = 'quote_not_about_person', _('Quote not about the person')
