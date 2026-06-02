# app_modules/ai_pipelines/prompts/transcript_signals/blocker_v1.py
"""
Request layer for Blocker signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'blocker') -- session grounding only
    (Blocker carries NO canonical taxonomy axes, so the context layer
    skips the taxonomy block entirely; the techcatalog block is also
    omitted).
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of blocker observations. Each observation has exactly 4 fields:

    summary       string   -- short rephrasing of the blocker in plain language
    source_quote  string   -- verbatim utterance expressing the blocker
    confidence    float    -- LLM self-declared, in [0.0, 1.0]
    is_inferred   boolean  -- LLM self-declared, true when not directly stated

Empty result is represented by {"signals": []}.

Schema rationale
----------------
Four fields per emitted signal, deliberately minimal:
  * One narrative field (`summary`) mapped 1:1 to BlockerSignal.summary
    (free text -- no canonical taxonomy).
  * One verbatim anchor (`source_quote`) -- see semantic contract below.
  * Two epistemic self-declaration fields (confidence / is_inferred)
    that feed the backend safety filter applied by
    TranscriptSignalExtractor before any BlockerSignal row is created.

Optional BlockerSignal fields NOT extracted in v1:

  * `contact` (FK Contact, nullable) -- attribution of the blocker to
    a specific contact (e.g. "the CFO raised this"). Deferred to the
    validation UI (rep selects the contact when validating the PENDING
    signal). Rationale: fuzzy mapping from "the CFO" to a Contact UUID
    via LLM is brittle; mirror of Impact v1 which defers metric_text /
    human_impact for the same robustness reason. Tracked as TD-6 in
    TECH_DEBT.md (validation UI exposes a contact selector for Blocker
    PENDING signals).

source_quote semantic contract for BlockerSignal
------------------------------------------------
For BlockerSignal, `source_quote` MUST carry the VERBATIM UTTERANCE
where the blocker was expressed -- the literal words the speaker used
when raising the objection / surfacing the hesitation / stating the
missing piece. NOT a paraphrase, NOT a justification, NOT a summary
of the surrounding context.

This contract is enforced AT PROMPT TIME below (see EMISSION RULES in
the request body): the docstring is read by humans, only the prompt
itself is read by the LLM, so the rule has to live there too.

Contrast with NextStepSignal.source_quote (Sprint B2 / TD-5)
------------------------------------------------------------
NextStepSignal.source_quote carries the JUSTIFICATION / RATIONALE for
the suggested follow-up (why this next step makes sense). BlockerSignal
takes the opposite stance: source_quote is the literal moment of the
blocker, not a rationale around it. Both signals inherit the same
`source_quote` column from BaseSignal but encode different semantics
-- documented in their respective prompts and model docstrings.

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor)
first applies the pipeline-level safety filter (drops signals where
confidence < CONFIDENCE_MIN OR (DROP_INFERRED is true AND is_inferred
is true) -- the dropped count is logged on the AIPipelineRun audit row,
never surfaced as REJECTED signals). Each surviving signal is then
mapped to a new BlockerSignal row:

    LLM-emitted field   ->  BlockerSignal column
    -------------------     ----------------------------------------
    summary             ->  summary
    source_quote        ->  source_quote   (declared on BaseSignal)
    confidence          ->  confidence     (declared on BaseSignal)
    is_inferred         ->  is_inferred    (declared on BaseSignal)

Fields filled by the service from the request context:

    status              =  SignalStatus.PENDING
    source              =  SignalSource.LLM_EXTRACTED
    source_activity     =  activity (from the API request)
    account             =  activity.account
    client_id           =  activity.client_id
    created_by          =  request.user

BlockerSignal.save() forces:

    canonical_key       =  None   (BlockerSignal does not cluster)

Fields left at their model default at create:

    contact             =  None   (deferred to rep at validation -- TD-6)
    signal_category     =  shadow-overridden to None on the model
    decision_cycle / campaign  =  auto-propagated from source_activity
                                  by SignalManager._propagate_activity_context

No cluster behaviour
--------------------
BlockerSignal does not participate in cluster aggregation (no
canonical_key, no signal_category, no clustering pass). Multiple
emitted signals on the same activity ARE allowed when each carries a
DISTINCT source_quote -- the rep validates / rejects each one
independently in the Activity workspace.

Versioning
----------
BLOCKER_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions so
the exact prompt revision used for any persisted signal can be retrieved
later for quality measurement and debugging.
"""


__all__ = ['BLOCKER_PROMPT_VERSION', 'build_blocker_request']


BLOCKER_PROMPT_VERSION = 'v1'


def build_blocker_request(transcript):
    """
    Build the request layer for one Blocker extraction sub-call.

    Args:
        transcript: str -- the full transcript text pasted by the rep.
            Sent verbatim to the LLM (no sanitisation here -- the
            data-exposure contract with the LLM provider is governed
            at the legal layer via DPA, not in this module).

    Returns:
        str: A ready-to-concatenate request block. Will be combined
        with the context layer by PromptBuilder.assemble() to form the
        final user message.
    """
    return f"""TASK
Extract BLOCKER signals from the SALES TRANSCRIPT below.

A blocker signal is structured evidence that the prospect raised an
OBSTACLE, OBJECTION, HESITATION, MISSING INFORMATION, BUDGET CONCERN,
TIMING CONSTRAINT, STAKEHOLDER ISSUE, or any other concrete impediment
that stands in the way of moving the deal forward.

Blocker vs. Pain (important distinction)
- A PAIN is a "things are broken in our current state" statement about
  the prospect's existing operations (e.g. "our reporting takes 3 weeks").
  Captured in a separate sub-call -- do NOT emit pains here.
- A BLOCKER is an obstacle to the DEAL ITSELF moving forward -- something
  the prospect raises against your solution, your timing, your pricing,
  your approval process, or your fit (e.g. "we have no budget allocated
  for Q4", "I need to discuss this with our CTO before going further",
  "your security questionnaire is too long for our timeline").
- A passage that combines an operational pain AND a deal-side objection
  may produce a pain (other sub-call) AND a blocker (here), each anchored
  on its own quote. They are not duplicates -- they live on distinct
  cluster perspectives downstream.

Blocker vs. Objective (important distinction)
- An OBJECTIVE is a "we want to achieve" statement (captured in a separate
  sub-call -- do NOT emit objectives here).
- A BLOCKER is what currently STOPS the deal from progressing. The two
  are conceptually opposite: an objective pulls the deal forward, a
  blocker holds it back.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "summary":      "<one short sentence rephrasing the blocker in your own words, around 200 chars or less>",
      "source_quote": "<VERBATIM utterance expressing the blocker -- see EMISSION RULES below>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of a
  blocker against the deal. Apply the EVIDENCE RULES and EPISTEMIC FILTER
  from the system prompt: drop weak inferences and NEVER fabricate.
- `summary` MUST be your own short rephrasing of the blocker in plain
  language. Never copy-paste the source_quote into the summary.
- `source_quote` MUST be the VERBATIM utterance where the blocker was
  expressed -- the literal words the speaker used when raising the
  objection, hesitation, missing piece, budget concern, or timing
  constraint. Do NOT paraphrase, do NOT summarize, do NOT supply
  surrounding context as the quote. The quote is the moment the
  blocker was voiced, exactly as it appears in the transcript,
  preserving original language, punctuation, and casing. Never translate.
- Multiple distinct blockers on the same activity ARE allowed -- emit one
  signal per blocker, each anchored on its own verbatim quote. Blockers
  do not cluster downstream; each one stands on its own.
- If NO blocker evidence is present anywhere in the transcript, return
  exactly: {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
