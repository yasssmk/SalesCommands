# app_modules/ai_pipelines/prompts/transcript_signals/blocker_v1.py
"""
Request layer for Blocker signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'blocker') -- session grounding only
    (Blocker carries NO canonical taxonomy axes, so the context layer
    skips the taxonomy block entirely; the techcatalog block is also
    omitted). No contact list since context v8 (TD-279 B4b).
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v3)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of blocker observations. Each observation has exactly 5 fields:

    summary       string   -- short rephrasing of the blocker in plain language
    source_quote  string   -- verbatim utterance expressing the blocker
    confidence    float    -- LLM self-declared, in [0.0, 1.0]
    is_inferred   boolean  -- LLM self-declared, true when not directly stated
    raised_by_name string|null -- name of the PROSPECT-side speaker who
                                 voiced the blocker, as written in the
                                 speaker label (v3)

Empty result is represented by {"signals": []}.

Schema rationale
----------------
Five fields per emitted signal, deliberately minimal:
  * One narrative field (`summary`) mapped 1:1 to BlockerSignal.summary
    (free text -- no canonical taxonomy).
  * One verbatim anchor (`source_quote`) -- see semantic contract below.
  * Two epistemic self-declaration fields (confidence / is_inferred)
    that feed the backend safety filter applied by
    TranscriptSignalExtractor before any BlockerSignal row is created.
  * One attribution field (`raised_by_name`, v3 -- TD-279 B4b).

`contact` attribution (v3 -- TD-279 B4b)
---------------------------------------
v2 (Objection S3) had the LLM pick a participant REFERENCE ("P1") from a
contact list in the context; the model filled it even for a registered
contact who never spoke (TD-279: 40/40 blockers on a silent contact). v3:
the LLM returns the speaker's NAME as written; the server links it to a
contact registered on the activity (services/participant_refs.py,
resolve_participant_by_name -- tenant + account filtered, word match, an
ambiguous name is never linked). An absent / null / unknown name leaves
`contact` None and the signal is STILL persisted; the server never forces
an attribution. The rep can still set / correct the contact in the edit
drawer (Objection S2).

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
    raised_by_name      ->  contact        (registered contact linked by name, else None)

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

    contact             =  None   when `raised_by_name` is absent / null /
                                  unknown / ambiguous (never forced)
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


# v2 (Objection S3): `raised_by` participant attribution. File name unchanged.
# v3 (TD-279 B4b): `raised_by` (participant reference) -> `raised_by_name`
# (the speaker's name as written, linked by the server); the "exactly ONE
# listed participant -> P1" rule is removed. Patch measured by the B2 eval
# (blocker_noP) and validated by the PO, plus the "never the seller" line.
# v4 (TD-279 C6): a blocker is what STOPS the deal today OR what can SLOW it --
# a concern, an objection or a future risk the PROSPECT expresses (adoption,
# resistance to change, doubt on an integration), always said, never imagined;
# a firm requirement stays a CONSTRAINT, the blocking threat that follows from
# it is a blocker. raised_by_name unchanged.
BLOCKER_PROMPT_VERSION = 'v4'


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
that stands in the way of moving the deal forward -- what STOPS the deal
today OR what can SLOW it: a concern, an objection or a future risk the
PROSPECT expresses (adoption by the users, resistance to change, doubt
about an integration...).
- A risk is emitted ONLY when the PROSPECT says it in the transcript --
  never a risk you imagine yourself (a new tool MAY face low adoption, but
  emit it only if a prospect raises that concern).
  "half of our technicians will never open a new app" -> BLOCKER (an
  adoption risk the prospect states).

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
- A BLOCKER is what stops or slows the deal. The two are conceptually
  opposite: an objective pulls the deal forward, a blocker holds it back.

Blocker vs. Constraint (important distinction)
- A firm REQUIREMENT the solution must meet is a CONSTRAINT (captured in a
  separate sub-call -- do NOT emit it here); the THREAT of blocking the deal
  that follows from it is a BLOCKER (emit it here, on its own quote).
  "the contract must be governed by French law" -> CONSTRAINT (not here)
  "if the contract is not under French law, our legal team will stop
  everything" -> BLOCKER

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "summary":      "<one short sentence rephrasing the blocker in your own words, around 200 chars or less>",
      "source_quote": "<VERBATIM utterance expressing the blocker -- see EMISSION RULES below>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>,
      "raised_by_name": <name of the PROSPECT-side speaker who voiced the blocker, exactly as written in the speaker label, or null -- see ATTRIBUTION RULES below>
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

ATTRIBUTION RULES (raised_by_name)
- Set `raised_by_name` to the name of the PROSPECT-side speaker who
  voiced the blocker, exactly as written in the speaker label.
- Set `raised_by_name` to null when the person who voiced the blocker
  cannot be identified from the transcript.
- NEVER output a name that does not appear in the transcript.
- Prospect side only: never the seller (the person who presents or
  sells the solution, or one of their colleagues).

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
