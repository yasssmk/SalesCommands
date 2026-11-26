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


# The pipelines that ANALYSE an activity (its transcript): a SUCCESS /
# PARTIAL run of one of them makes the activity « analysed »
# (services/analysis_state.py — last-run endpoint, transcript lock, one
# analysis per pipeline). The extraction and its advice pass only: a
# PREP_CALL brief is generated BEFORE the conversation and analyses nothing,
# a DEAL_HEALTH run is cycle-level (no source_activity). Sprint « Deal health
# v2 », step 1: an inclusion list, so a new pipeline never counts by default.
ANALYSIS_PIPELINE_TYPES = (
    AIPipelineType.TRANSCRIPT_SIGNALS,
    AIPipelineType.NEXT_STEPS,
    AIPipelineType.NEXT_STEPS_ADVICE,
)


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
# HARD CRASH — the error kept on the run
# =============================================================================
#
# An unexpected exception during a run (the « hard crash » path, re-raised to
# the view) is stored on AIPipelineRun.error_message as
# « hard crash: <str(exc)> », the exception text cut to this length
# (BasePipeline._finalize_hard_crash and the pipelines' own hard-crash
# blocks). Never sent to the client.
HARD_CRASH_ERROR_MAX_CHARS = 1000


# =============================================================================
# TECHSTACK — discontinuation, as the AI packs say it (TD-314)
# =============================================================================
#
# A discontinued TechStackSignal (is_discontinued + discontinued_date): a date
# today or in the past = the tool is no longer used; a future date = a planned
# exit (TechStackSignal.discontinued_date help text). Emitted in the AI packs
# by DealHealthEvidenceBuilder.serialize_techstack_signals (deal health step
# 3b), reused by the prep-call / Game Plan pack (sprint 2, S6). The usage
# scope labels are signals.constants.UsageScope's own.
TECHSTACK_NO_LONGER_USED = 'no longer used'
TECHSTACK_PLANNED_EXIT = 'planned exit'


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
# PEOPLE NAMED TO THE LLM (Sprint « Deal health v2 », step 3a)
# =============================================================================

# services/llm_people.py is THE point that names a person to the LLM: its
# first name only. Two people of one prompt sharing a first name are told
# apart by a reference + first name + department (amendment A4, the
# NEXT_STEPS_STEP_REF_FORMAT pattern above): "P1 Marc (Finance)",
# "P2 Marc (IT)" — "P1 Marc" when the department is unknown. The index
# follows the order the people are registered in the prompt's roster.
# P (person), never S: the steps are already S{order} in the prompts.
LLM_PERSON_REF_FORMAT = 'P{index}'
LLM_PERSON_HOMONYM_LABEL_FORMAT = '{ref} {first_name} ({department})'
LLM_PERSON_HOMONYM_LABEL_NO_DEPT_FORMAT = '{ref} {first_name}'

# The outcome of resolving a label the LLM wrote back to a stakeholder
# (llm_people.stakeholder_for_label, sub-step 5c). Only RESOLVED is written.
LABEL_RESOLVED = 'resolved'
LABEL_UNKNOWN = 'unknown'                  # not a label of this prompt
LABEL_NO_STAKEHOLDER = 'no_stakeholder'    # a person with no stakeholder row
LABEL_AMBIGUOUS = 'ambiguous'              # the stakeholder is not THAT person


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


# ============================================================================
# ONE ANALYSIS PER PIPELINE (sprint « Source / Notes », 1.6 — PO, Q4)
# ============================================================================
# The machine code of the standard refusal returned by the extraction
# endpoint when EVERYTHING requested is already analysed (a SUCCESS or
# PARTIAL run of each requested pipeline — services/analysis_state.py). The
# front reads it to display the refusal as INFORMATION, not as an error
# (frontend api/aiPipelines/activityExtraction.js). It replaces the former
# 409 ALREADY_EXTRACTED.
ANALYSIS_ALREADY_DONE_CODE = 'ANALYSIS_ALREADY_DONE'


# =============================================================================
# DEAL HEALTH — SOURCES READ (Sprint « Deal health v2 », step 3b)
# =============================================================================

# The deal health reads every source of the cycle that CHANGED since its last
# snapshot (DealHealthSnapshot.sources_cursor, one timestamp per type below):
#   activities     — Activity.updated_at (transcript / email content, notes,
#                    description, objective, outcome — analysed or not);
#   signals        — validated signals, updated_at;
#   manager_notes  — ManagerNote.created_at.
# Deletions / rejections after the read are not followed (known limit).
DEAL_HEALTH_CURSOR_ACTIVITIES = 'activities'
DEAL_HEALTH_CURSOR_SIGNALS = 'signals'
DEAL_HEALTH_CURSOR_MANAGER_NOTES = 'manager_notes'
# 6c: the fingerprint (sha256) of the STATIC context the prompt reads — the
# deal (description, value, step, origin campaign, products with their
# description / value proposition) and the account fields. Another
# fingerprint than the last snapshot's is new: the run happens.
DEAL_HEALTH_CURSOR_STATIC_CONTEXT = 'static_context'
# Sprint 2 Game Plan, S7 (PO Q4): the fingerprint (sha256) of the cycle's
# stakeholders — their ids and the role of their current signal — so a
# stakeholder added, REMOVED (what a timestamp cursor cannot see, TD-318) or
# whose role changed is new information (STAKEHOLDERS_CHANGED). Absent from
# the snapshots taken before S7: never compared then.
DEAL_HEALTH_CURSOR_STAKEHOLDERS = 'stakeholders'

# =============================================================================
# DEAL HEALTH — RUN GUARDS (Sprint « Deal health v2 », step 6, amendment A10)
# =============================================================================
# Business rules of a run — answered 200 with one of these codes (the front
# shows an INFORMATION, never an error; the ANALYSIS_ALREADY_DONE_CODE
# pattern), no LLM call, no snapshot:
#   NO_NEW_SOURCES — the sources cursor above finds nothing changed since the
#                    last snapshot (there is one), static context included;
#   CYCLE_CLOSED   — the decision cycle is closed (decision_cycles
#                    DEAL_HEALTH_CLOSED_OUTCOMES — ON_HOLD is not, 6c): its
#                    last diagnostic stays readable.
DEAL_HEALTH_NO_NEW_SOURCES_CODE = 'DEAL_HEALTH_NO_NEW_SOURCES'
DEAL_HEALTH_CYCLE_CLOSED_CODE = 'DEAL_HEALTH_CYCLE_CLOSED'
# Layer 1 (Redis, TD-50 — core/idempotency.py): a SUCCESS is replayed for the
# standard IDEMPOTENCY_REDIS_TTL_SECONDS (its new snapshot changes the front's
# key anyway). An INFO answer or a failure is kept only long enough to absorb
# a double click / a second tab, so the rule is evaluated again on the next
# click (a source added, a retry after an LLM error).
DEAL_HEALTH_SHORT_REPLAY_TTL_SECONDS = 10

# =============================================================================
# DEAL HEALTH — FRESHNESS (Sprint « Deal health v2 », step 8, A13)
# =============================================================================
# Why there is new information to analyse (services/deal_health_freshness.py
# reasons[]) — never « stale »:
#   NO_ANALYSIS_YET — the cycle has no snapshot;
#   NEW_SOURCES     — a source changed since the cursor, or another static
#                     context fingerprint (new_info_reasons — S7: an
#                     ANALYSED activity, never a mere activity edit);
#   STEP_CHANGED    — the current declared step differs from the last
#                     snapshot's declared_step (ignored when NULL — v1).
DEAL_HEALTH_FRESHNESS_NO_ANALYSIS_YET = 'NO_ANALYSIS_YET'
DEAL_HEALTH_FRESHNESS_NEW_SOURCES = 'NEW_SOURCES'
DEAL_HEALTH_FRESHNESS_STEP_CHANGED = 'STEP_CHANGED'
#   STAKEHOLDERS_CHANGED — the cycle's stakeholders (ids + the role of their
#                     current signal) differ from the last snapshot's
#                     fingerprint (sprint 2 Game Plan, S7 — PO Q4); a snapshot
#                     without that fingerprint (before S7) is no reason.
DEAL_HEALTH_FRESHNESS_STAKEHOLDERS_CHANGED = 'STAKEHOLDERS_CHANGED'

# Input bounds (amendment A3), in characters of the source texts. A single
# transcript / email above DEAL_HEALTH_MAX_CHARS_PER_SOURCE is cut to it (the
# extraction's own bound, config.MAX_TRANSCRIPT_LENGTH = 50 000). Above
# DEAL_HEALTH_MAX_INPUT_CHARS in total, the OLDEST transcripts are cut first;
# validated signals and notes always pass whole. Every cut is traced in the
# run's sub_calls (input_truncation). Values to confirm by the evaluation
# (step 7).
DEAL_HEALTH_MAX_CHARS_PER_SOURCE = 50_000
DEAL_HEALTH_MAX_INPUT_CHARS = 200_000
DEAL_HEALTH_TRUNCATION_MARKER = '[... truncated: {kept} of {total} characters kept]'
DEAL_HEALTH_TRUNCATION_PER_SOURCE = 'per_source_cap'
DEAL_HEALTH_TRUNCATION_INPUT_BUDGET = 'input_budget'

# A ManagerNote's author is named by the ROLE only, never by name.
DEAL_HEALTH_NOTE_AUTHOR_ADMIN = 'Admin'
DEAL_HEALTH_NOTE_AUTHOR_MANAGER = 'Manager'


# =============================================================================
# DEAL HEALTH v2 — MODEL, PROVIDER, FORMAT (Sprint « Deal health v2 », step 5)
# =============================================================================

# The deal health's provider choice -> its PROVIDER_CONFIG entry. THE switch
# itself is config.DEAL_HEALTH_LLM_PROVIDER (amendment A11).
DEAL_HEALTH_PROVIDER_KEYS = {
    'openai': 'openai_deal_health',
    'claude': 'claude_deal_health',
}

# =============================================================================
# CLAUDE PROVIDER (sub-step 5b — anthropic SDK 1.x)
# =============================================================================
# Sampling parameters: the 1.x SDK no longer takes `temperature`, and Claude
# Opus 4.7 and later models answer 400 when a request carries one. It is sent
# (as extra_body, API version 2023-06-01) ONLY to the models of this list,
# which still accept it — never to any other model.
CLAUDE_MODELS_ACCEPTING_TEMPERATURE = frozenset({
    'claude-haiku-4-5', 'claude-haiku-4-5-20251001',
    'claude-sonnet-4-6', 'claude-opus-4-6',
})
# Server-side refusal fallback (beta): when a safety classifier declines the
# request, the API re-runs it on a fallback model inside the same call
# ('default' routes by refusal category). Sent for these models only; if the
# whole chain declines (stop_reason 'refusal'), the provider raises
# LLMProviderError, as for an OpenAI refusal.
CLAUDE_REFUSAL_FALLBACK_BETA = 'server-side-fallback-2026-07-01'
CLAUDE_REFUSAL_FALLBACKS = 'default'
CLAUDE_REFUSAL_FALLBACK_MODELS = frozenset({
    'claude-fable-5-2', 'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5',
    'claude-sonnet-5-5',
})

# The deal health's own call timeout (amendment A6), in seconds. The view is
# synchronous; the front polls ~180 s for the snapshot after a client
# timeout (core/timeout_conventions.py POLLING_MAX_ATTEMPTS x
# POLLING_INTERVAL_SECONDS), so a call must end within that window.
# Provisional — measured at step 7.
DEAL_HEALTH_TIMEOUT_S = 150
# Room for the v2 answer and the reasoning tokens (they count in max_tokens).
DEAL_HEALTH_MAX_TOKENS = 16_000

# How the v2 context is sent (compared at step 7, amendment A5):
#   'sections' — labelled sections + compact JSON (the next_steps pattern);
#   'json'     — the whole context as ONE JSON document.
DEAL_HEALTH_INPUT_FORMAT_SECTIONS = 'sections'
DEAL_HEALTH_INPUT_FORMAT_JSON = 'json'
DEAL_HEALTH_INPUT_FORMAT = DEAL_HEALTH_INPUT_FORMAT_SECTIONS

# The diagnostic v2 value lists (the strict schema and the writer).
DEAL_HEALTH_DIMENSION_STATUSES = (
    'confirmed', 'suggested', 'unclear', 'missing_evidence', 'contradictory',
)
DEAL_HEALTH_BANT_LETTERS = ('budget', 'authority', 'need', 'timeline')
DEAL_HEALTH_BANT_STATUSES = ('validated', 'not_validated', 'unknown')
DEAL_HEALTH_MISSING_INFO_LEVELS = ('BUSINESS', 'DEPARTMENT', 'CONTACT')
DEAL_HEALTH_TOP_ARGUMENTS_MAX = 3

# Step 7 (prompt v2.1, PO decision of 18/11) — the guard rails stay INTERNAL:
# none of these phrases may appear in the text of a diagnostic (the prompt's
# examples included). Lower-case, matched as substrings of the lower-cased
# text. Read by the v2.1 prompt test and by evals/deal_health/scoring.py.
DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES = (
    'do not invent', "don't invent", 'never invent', 'must not invent',
    'without inventing', 'not invent',
    'unsupported capabilit', 'unverified capabilit', 'capability not supported',
    'hard rule', 'evidence-only', 'as instructed', 'per the rules',
    'i cannot', 'as an ai',
)
# Classical rhetoric labels — never in a diagnostic (sales vocabulary only:
# needs and urgency, credibility, fit and value). Whole words, any case.
DEAL_HEALTH_RHETORIC_LABELS = ('ethos', 'pathos', 'logos')
