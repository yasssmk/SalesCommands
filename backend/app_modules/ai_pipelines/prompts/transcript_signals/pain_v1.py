# app_modules/ai_pipelines/prompts/transcript_signals/pain_v1.py
"""
Request layer for Pain signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'pain') -- session grounding + the
    canonical (what, dimension) enums.
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of pain observations. Each observation has exactly 6 fields:

    what          string   -- value from SignalWhat (see context taxonomy)
    dimension     string   -- value from SignalDimension (see context taxonomy)
    summary       string   -- short rephrasing of the pain in plain language
    source_quote  string   -- verbatim excerpt from the transcript
    confidence    float    -- LLM self-declared, in [0.0, 1.0]
    is_inferred   boolean  -- LLM self-declared, true when not directly stated

Empty result is represented by {"signals": []}.

Schema rationale
----------------
Six fields per emitted signal:
  * Four narrative fields mapped 1:1 to PainSignal columns
    (what / dimension / summary / source_quote).
  * Two epistemic self-declaration fields (confidence / is_inferred)
    that feed the backend safety filter applied by
    TranscriptSignalExtractor before any PainSignal row is created.

Both epistemic fields exist on BaseSignal and are persisted on every
surviving signal. The pipeline's filter thresholds
(CONFIDENCE_MIN / DROP_INFERRED) live on the Pipeline class -- not in
this prompt, not in the system prompt. The LLM only knows about the
self-declaration; the backend decides what to do with the values.

The standardisation refactor removed the `source_contact` FK from
BaseSignal -- source contacts are derived at read time from
`source_activity.contacts`. The LLM emits no contact hint.

Optional PainSignal fields (notes, related_techstack_mention) are NOT
extracted in v1:
  * notes is rep-authored qualitative context, added post-validation.
  * related_techstack_mention is a cross-reference
    to the techstack sub-call. v1 leaves the cross-link to the rep
    during validation.

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor)
first applies the pipeline-level safety filter (drops signals where
confidence < CONFIDENCE_MIN OR (DROP_INFERRED is true AND is_inferred is
true) -- the dropped count is logged on the AIPipelineRun audit row,
never surfaced as REJECTED signals). Each surviving signal is then
mapped to a new PainSignal row:

    LLM-emitted field   ->  PainSignal column
    -------------------     ----------------------------------------
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

PainSignal.save() then auto-computes:

    canonical_key       =  f'pain:{what}:{dimension}'

Decision cycle / campaign are auto-propagated from source_activity by
SignalManager._propagate_activity_context at create time -- not by this
prompt.

Cluster behaviour
-----------------
Multiple emitted signals sharing the same (what, dimension) are
acceptable when each carries a DISTINCT source_quote. They will join the
same pain cluster automatically (clusters group by canonical_key on the
account); distinct quotes strengthen corroboration. The LLM does not
need to deduplicate ahead of time.

Versioning
----------
PAIN_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions so the
exact prompt revision used for any persisted signal can be retrieved
later for quality measurement and debugging.
"""


__all__ = ['PAIN_PROMPT_VERSION', 'build_pain_request']


PAIN_PROMPT_VERSION = 'v1'


def build_pain_request(transcript):
    """
    Build the request layer for one Pain extraction sub-call.

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
Extract PAIN signals from the SALES TRANSCRIPT below.

A pain signal is structured evidence that the prospect experiences friction,
cost, slowness, quality issue, scale limit, or risk in a specific area of
their business. Pain extraction captures the DIAGNOSIS only -- the
quantified impact (metrics, costs, who is personally affected) is captured
separately and is NOT part of this sub-call.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "what":         "<one value from the `what` list in the CANONICAL TAXONOMY of the context>",
      "dimension":    "<one value from the `dimension` list in the CANONICAL TAXONOMY of the context>",
      "scope_level":  "<one value from the `scope_level` list in the context: BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when scope_level is DEPARTMENT, otherwise null>",
      "summary":      "<one short sentence rephrasing the pain in your own words, around 200 chars or less>",
      "source_quote": "<verbatim excerpt from the transcript supporting this pain>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of a pain.
  Apply the EVIDENCE RULES and EPISTEMIC FILTER from the system prompt:
  drop weak inferences and NEVER fabricate.
- Multiple signals sharing the same (what, dimension) pair ARE allowed when
  each carries a DISTINCT source_quote -- distinct quotes strengthen the
  cluster automatically downstream.
- `summary` must be your own rephrasing of the pain. Never copy-paste the
  source_quote into the summary.
- `source_quote` must be a verbatim excerpt from the transcript, preserving
  the original language, punctuation, and casing. Never translate.
- `scope_level` MUST be exactly BUSINESS or DEPARTMENT. A pain felt across the
  whole company, or raised at executive / C-level / general-management level,
  is BUSINESS. A pain specific to one department is DEPARTMENT. Never emit
  PERSONAL or any other value.
- `target_department` is REQUIRED when scope_level is DEPARTMENT: pick exactly
  one value from the `target_department` list in the context. It MUST be null
  when scope_level is BUSINESS.
- If NO pain evidence is present anywhere in the transcript, return exactly:
  {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""