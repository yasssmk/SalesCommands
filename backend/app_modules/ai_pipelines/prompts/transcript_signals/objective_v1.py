# app_modules/ai_pipelines/prompts/transcript_signals/objective_v1.py
"""
Request layer for Objective signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'objective') -- session grounding + the
    canonical (what, dimension) enums.
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1 -- symmetric with pain_v1)
-------------------------------------
The LLM emits one JSON object with a single key `signals` containing an
array of objective observations. Each observation has exactly 6 fields:

    what          string   -- value from SignalWhat (see context taxonomy)
    dimension     string   -- value from SignalDimension (see context taxonomy)
    summary       string   -- short rephrasing of the objective in plain language
    source_quote  string   -- verbatim excerpt from the transcript
    confidence    float    -- LLM self-declared, in [0.0, 1.0]
    is_inferred   boolean  -- LLM self-declared, true when not directly stated

Empty result is represented by {"signals": []}.

Schema rationale
----------------
Six fields per emitted signal:
  * Four narrative fields mapped 1:1 to ObjectiveSignal columns
    (what / dimension / summary / source_quote).
  * Two epistemic self-declaration fields (confidence / is_inferred)
    that feed the backend safety filter applied by
    TranscriptSignalExtractor before any ObjectiveSignal row is created.

Both epistemic fields exist on BaseSignal and are persisted on every
surviving signal. The pipeline's filter thresholds
(CONFIDENCE_MIN / DROP_INFERRED) live on the Pipeline class -- not in
this prompt, not in the system prompt. The LLM only knows about the
self-declaration; the backend decides what to do with the values.

ObjectiveSignal exposes additional axes that are NOT extracted in v1:
scope_level, target_contact, target_department, target_date,
success_criteria. Rationale per axis:

  * scope_level is conditional (PERSONAL requires target_contact FK,
    DEPARTMENT requires target_department FK, BUSINESS forbids both).
    Asking the LLM to orchestrate this conditional logic + resolve
    contact / department references would produce a brittle prompt with
    high parse-failure risk for marginal MVP value.

  * scope / target refinement is REP WORK -- the rep validating the
    extracted objective knows which specific person or team drives it
    and can promote BUSINESS to PERSONAL / DEPARTMENT in the validation UI.

  * target_date / success_criteria are fuzzy free-text extractions
    ("by Q4", "ASAP", "30% reduction") that need normalisation. The rep
    is the right author for those refinements.

The persistence service hardcodes the deferred fields at create time:

    scope_level         = ScopeLevel.BUSINESS
    target_contact      = None
    target_department   = None
    target_date         = None     (rep adds later)
    success_criteria    = ''       (rep adds later)
    notes               = ''       (rep adds later)

These defaults satisfy ObjectiveSignal.clean()'s BUSINESS branch:
"neither target_contact nor target_department".

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor)
first applies the pipeline-level safety filter (drops signals where
confidence < CONFIDENCE_MIN OR (DROP_INFERRED is true AND is_inferred is
true) -- the dropped count is logged on the AIPipelineRun audit row,
never surfaced as REJECTED signals). Each surviving signal is then
mapped to a new ObjectiveSignal row:

    LLM-emitted field   ->  ObjectiveSignal column
    -------------------     -------------------------------------------
    what                ->  what
    dimension           ->  dimension
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

ObjectiveSignal.save() then auto-computes:

    canonical_key       =  f'objective:{what}:{dimension}'

Cluster behaviour
-----------------
Multiple emitted signals sharing the same (what, dimension) are
acceptable when each carries a DISTINCT source_quote. They will join the
same objective cluster automatically (clusters group by canonical_key on
the account); distinct quotes strengthen corroboration.

Versioning
----------
OBJECTIVE_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions
so the exact prompt revision used for any persisted signal can be
retrieved later for quality measurement and debugging.
"""


__all__ = ['OBJECTIVE_PROMPT_VERSION', 'build_objective_request']


OBJECTIVE_PROMPT_VERSION = 'v1'


def build_objective_request(transcript):
    """
    Build the request layer for one Objective extraction sub-call.

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
Extract OBJECTIVE signals from the SALES TRANSCRIPT below.

An objective signal is structured evidence that the prospect WANTS to
achieve a specific outcome in a specific area of their business: growth
target, efficiency gain, cost reduction, quality improvement, scale
improvement, risk mitigation.

Objective vs. Pain (important distinction)
- A PAIN is a "things are broken" statement (e.g. "our reporting takes 3
  weeks"). It is captured in a separate sub-call -- do NOT emit pains here.
- An OBJECTIVE is a "we want to achieve" statement (e.g. "we want to cut
  reporting time in half by Q4"). Emit these here.
- A passage that contains BOTH a problem AND a goal may produce a pain
  (other sub-call) AND an objective (here), each anchored on its own
  quote -- they are not duplicates.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "what":         "<one value from the `what` list in the CANONICAL TAXONOMY of the context>",
      "dimension":    "<one value from the `dimension` list in the CANONICAL TAXONOMY of the context>",
      "scope_level":  "<one value from the `scope_level` list in the context: BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when scope_level is DEPARTMENT, otherwise null>",
      "summary":      "<one short sentence rephrasing the objective in your own words, around 200 chars or less>",
      "source_quote": "<verbatim excerpt from the transcript supporting this objective>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence that the
  prospect WANTS to achieve a specific outcome. Apply the EVIDENCE RULES
  and EPISTEMIC FILTER from the system prompt: drop weak inferences and
  NEVER fabricate.
- Multiple signals sharing the same (what, dimension) pair ARE allowed
  when each carries a DISTINCT source_quote -- distinct quotes strengthen
  the cluster automatically downstream.
- `summary` must be your own rephrasing of the objective. Never copy-paste
  the source_quote into the summary.
- `source_quote` must be a verbatim excerpt from the transcript, preserving
  the original language, punctuation, and casing. Never translate.
- `scope_level` MUST be exactly BUSINESS or DEPARTMENT. An objective pursued
  across the whole company, or set at executive / C-level / general-management
  level, is BUSINESS. An objective specific to one department is DEPARTMENT.
  Never emit PERSONAL or any other value.
- `target_department` is REQUIRED when scope_level is DEPARTMENT: pick exactly
  one value from the `target_department` list in the context. It MUST be null
  when scope_level is BUSINESS.
- If NO objective evidence is present anywhere in the transcript, return
  exactly: {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""