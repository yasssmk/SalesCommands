# app_modules/ai_pipelines/prompts/next_steps/next_steps_v1.py
"""
Request layer for Next-Step signal extraction (v1) — Sprint B4.

This is the per-pipeline request module of the NextStepsPipeline. It is
combined at call time with:

  * prompts/transcript_signals/system.py
        Universal MEDDPICC-analyst system prompt (output rules, evidence
        rules, epistemic filter, privacy). Reused as-is.
  * prompts/next_steps/context.py
        Session-only context layer (tenant, account, activity, contacts).
        No taxonomy block, no techcatalog block -- NextStepSignal has
        no canonical axes.

The full assembly is performed by PromptBuilder.assemble() in
prompts/base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing
an array of next-step observations. Each observation has exactly 6
fields:

    suggested_title          string   -- proposed Activity title
                                          (max ~255 chars, mirror of
                                          Activity.title).
    suggested_activity_type  string   -- one of "CALL" / "EMAIL" /
                                          "MEETING" / "TASK" /
                                          "LINKEDIN" / "OTHER"
                                          (ActivityType DB values).
    suggested_due_date       string|null
                                       -- proposed deadline as an
                                          ISO-8601 date (YYYY-MM-DD),
                                          or null when the rep did
                                          not commit to a date.
    source_quote             string   -- JUSTIFICATION for the
                                          suggestion (see contract
                                          below).
    confidence               float    -- LLM self-declared, in
                                          [0.0, 1.0].
    is_inferred              boolean  -- LLM self-declared.

Empty result is represented by {"signals": []}.

source_quote semantic contract for NextStepSignal
-------------------------------------------------
For NextStepSignal, `source_quote` MUST carry the JUSTIFICATION /
RATIONALE for the suggestion -- the passage in the transcript that
shows WHY this next step makes sense -- NOT a verbatim of the
speaker proposing the action.

This contract is enforced AT PROMPT TIME below (see EMISSION RULES in
the request body): the Python docstring is read by humans, only the
prompt itself is read by the LLM, so the rule has to live there too.

Contrast with the other signal types:

  * BlockerSignal.source_quote (Sprint B3): VERBATIM utterance of the
    blocker -- the literal words used when raising the objection.
  * Pain / Objective / Impact source_quote (Sprint LLM v1): verbatim
    excerpt anchoring the canonical (what, dimension) diagnosis.
  * NextStepSignal.source_quote (HERE): JUSTIFICATION for the
    suggestion -- the evidence that the action is needed, not the
    speaker proposing it.

Tracked semantically in TECH_DEBT.md TD-5 so the contract does not
drift in future prompt iterations.

v1 deferred fields
------------------
The NextStepSignal model also exposes `suggested_contacts` (M2M
Contact) -- the proposed attendees / recipients of the materialised
Activity. The v1 prompt does NOT extract this field: mapping textual
mentions ("Jane", "the CTO") to Contact UUIDs is fuzzy and not
production-grade at MVP scope. Attribution happens at rep validation
time. Tracked as TD-7 in TECH_DEBT.md (Next Steps Tab UI in Sprint F6
must expose a multi-contact selector for PENDING NextStepSignals).

Persistence contract
--------------------
The downstream persistence service (NextStepExtractor) first applies
the pipeline-level safety filter (drops signals where confidence <
CONFIDENCE_MIN OR (DROP_INFERRED is True AND is_inferred is True) --
the dropped count is logged on the AIPipelineRun audit row, never
surfaced to end users). Each surviving signal is then mapped to a new
NextStepSignal row:

    LLM-emitted field         ->  NextStepSignal column
    ------------------------     -----------------------------------
    suggested_title           ->  suggested_title
    suggested_activity_type   ->  suggested_activity_type
    suggested_due_date        ->  suggested_due_date  (parsed leniently;
                                                       invalid format
                                                       -> None, the
                                                       signal still
                                                       persists)
    source_quote              ->  source_quote  (declared on BaseSignal)
    confidence                ->  confidence    (declared on BaseSignal)
    is_inferred               ->  is_inferred   (declared on BaseSignal)

Fields filled by the service from the request context:

    status              =  SignalStatus.PENDING
    source              =  SignalSource.LLM_EXTRACTED
    source_activity     =  activity (from the pipeline caller)
    account             =  activity.account
    client_id           =  activity.client_id
    created_by          =  request.user

NextStepSignal.save() forces:

    canonical_key       =  None   (NextStepSignal does not cluster)

Fields left at their model default at create:

    suggested_contacts  =  []     (deferred to rep at validation -- TD-7)
    signal_category     =  shadow-overridden to None on the model

decision_cycle / campaign are auto-propagated from source_activity by
SignalManager._propagate_activity_context.

Versioning
----------
NEXT_STEPS_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions
so the exact prompt revision used for any persisted signal can be
retrieved later for quality measurement and debugging.
"""

from app_modules.activities.constants import ActivityType


__all__ = ['NEXT_STEPS_PROMPT_VERSION', 'build_next_steps_request']


NEXT_STEPS_PROMPT_VERSION = 'v1'


def _activity_type_json_array():
    """
    Render ActivityType DB values as a JSON-array string for the prompt.

    Single source of truth: imported directly from
    app_modules.activities.constants. If the enum gains a new value
    (e.g. SMS), the prompt taxonomy follows automatically -- no
    duplication on the prompt side.
    """
    return '[' + ', '.join(f'"{v}"' for v in ActivityType.values) + ']'


def build_next_steps_request(transcript):
    """
    Build the request layer for the NextStepsPipeline LLM call.

    Args:
        transcript: str -- the full transcript text pasted by the rep.
            Sent verbatim to the LLM (no sanitisation here -- the
            data-exposure contract with the LLM provider is governed
            at the legal layer via DPA, not in this module).

    Returns:
        str: A ready-to-concatenate request block. Will be combined
        with the context layer by PromptBuilder.assemble() to form
        the final user message.
    """
    return f"""TASK
Extract NEXT-STEP signals from the SALES TRANSCRIPT below.

A next-step signal is a STRUCTURED PROPOSAL for a follow-up action
the seller should take after the conversation to keep the deal moving
forward -- typically a follow-up call, an email recap, a meeting
invitation, a task to send documentation, a LinkedIn message.

A next step is grounded in the conversation: the transcript carries
evidence (an explicit ask from the prospect, an open question the
seller committed to follow up on, a logical next step in the
qualification process). Do NOT invent generic next steps that the
transcript does not justify.

ACTIVITY TYPE TAXONOMY
Pick exactly ONE value for `suggested_activity_type` from this list,
or OMIT the signal if none fits:
{_activity_type_json_array()}

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "suggested_title":         "<short title for the next-step Activity, around 200 chars or less>",
      "suggested_activity_type": "<one value from the ACTIVITY TYPE TAXONOMY above>",
      "suggested_due_date":      "<YYYY-MM-DD ISO date, or null when no date can be inferred>",
      "source_quote":            "<JUSTIFICATION for the suggestion -- see EMISSION RULES below>",
      "confidence":              <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":             <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence that
  a specific follow-up action is needed. Apply the EVIDENCE RULES and
  EPISTEMIC FILTER from the system prompt: drop weak inferences and
  NEVER fabricate.
- `suggested_title` MUST be a short, action-oriented title suitable
  to populate Activity.title (e.g. "Send pricing recap to CFO",
  "Schedule technical demo with CTO"). Plain language, your own
  rephrasing -- NOT a copy of the source_quote.
- `suggested_activity_type` MUST be one value from the ACTIVITY TYPE
  TAXONOMY above. If no value fits, OMIT the signal -- do not invent
  a new value, do not coerce to "OTHER" without strong justification.
- `suggested_due_date` is OPTIONAL. Emit a YYYY-MM-DD ISO date ONLY
  when the transcript commits to a specific timeframe ("by next
  Friday", "before end of Q4") AND you can compute the actual date
  unambiguously. When in doubt, emit null -- the rep will pick a date
  at validation time. Never invent a date.
- `source_quote` MUST be the JUSTIFICATION for the suggestion -- the
  passage in the transcript that shows WHY this next step is needed
  (an explicit ask, a commitment, an open question). It is NOT a
  verbatim of the speaker proposing the action. The justification is
  the EVIDENCE that the action is warranted, not the act of proposing
  it. Quote verbatim from the transcript, preserving original
  language, punctuation, and casing. Never translate.
- Multiple distinct next steps on the same activity ARE allowed --
  emit one signal per distinct action, each anchored on its own
  justification quote.
- If NO next-step evidence is present anywhere in the transcript,
  return exactly: {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
