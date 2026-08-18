# app_modules/ai_pipelines/prompts/transcript_signals/techstack_v1.py
"""
Request layer for TechStack signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'techstack') -- session grounding +
    the UsageScope enum. The TECH CATALOG list is no longer injected
    (the catalogue was removed in S10).
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1 — S10 revision)
--------------------------
The LLM emits one JSON object with a single key `signals` containing an
array of tech-stack observations. Each observation has exactly 8 fields:

    tech_name              string       -- tool name verbatim from the
                                            transcript. REQUIRED.
    is_competitor          boolean      -- overlaps with what the seller sells.
    is_integration         boolean      -- the seller's product connects to it.
    is_to_replace          boolean      -- the prospect intends to move off it.
    usage_scope            string|null  -- "TEAM" | "COMPANY" | "UNKNOWN",
                                            or null when not discussed.
    source_quote           string       -- verbatim excerpt from the transcript.
    confidence             float        -- LLM self-declared, in [0.0, 1.0].
    is_inferred            boolean      -- LLM self-declared, true when not
                                            directly stated.

The three booleans are INDEPENDENT: any combination is valid, and
all-false is the common case ("the prospect uses this tool", no angle).

What replaced the catalogue match (S10)
---------------------------------------
Until S10 the schema was a XOR: `tech_catalog_entry_id` (a UUID from the
tenant's TechCatalog, injected into the context layer) OR
`tech_name_raw` when nothing matched. The catalogue has been removed, so
identity is carried by free text: the model reports the name it
heard, and the backend derives a normalised grouping key from it in
TechStackSignal.save(). Nothing in this prompt needs to know about
tenant reference data anymore.

Empty result is represented by {"signals": []}.

Why scope_level DEPARTMENT is excluded from v1
----------------------------------------------
UsageScope.DEPARTMENT triggers TechStackSignal.clean() rule 1 requiring
`usage_department` (FK to StandardDepartment). Resolving a department
reference from free text would require either an LLM second-pass or
fuzzy text matching, neither of which is MVP material. We instruct the
LLM to emit "UNKNOWN" for any department-scoped mention -- the rep
promotes the scope and attaches the department FK during validation.

Why is_discontinued / cost_description / renewal_date are NOT extracted
----------------------------------------------------------------------
These fields exist on TechStackSignal but their extraction is fuzzy:

  * is_discontinued requires distinguishing "they stopped using X" (PAST)
    from "they are considering replacing X" (FUTURE intent, not yet
    discontinued). Misclassification is costly -- the cluster priority
    scorer applies a strong negative weight to discontinued tools.
  * cost_description is free text but reps describe costs with widely
    varying units ("$3k/mo", "120k/year", "free tier"). LLM normalisation
    risks false precision.
  * renewal_date / usage_start_year require unambiguous date parsing
    that the LLM does not reliably perform on hedged transcript text
    ("around three years ago", "later this year").

All four are left to rep refinement post-validation.

Epistemic self-declaration (confidence / is_inferred)
-----------------------------------------------------
BaseSignal carries `confidence` and `is_inferred` columns that
TechStackSignal inherits. The LLM emits both on every signal:
self-declared confidence in [0.0, 1.0] and is_inferred boolean.

These fields feed the backend safety filter applied by
TranscriptSignalExtractor before any TechStackSignal row is created.
The pipeline's filter thresholds (CONFIDENCE_MIN / DROP_INFERRED) live
on the Pipeline class -- not in this prompt, not in the system prompt.
The LLM only knows about the self-declaration; the backend decides
what to do with the values.

Both fields are persisted on every surviving signal. Defense in depth:
even when the system prompt's EPISTEMIC FILTER fails to suppress a
weak signal at emission time, the backend filter catches it before
persistence (dropped silently, count logged in the AIPipelineRun audit
row).

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor)
first applies the pipeline-level safety filter (drops signals where
confidence < CONFIDENCE_MIN OR (DROP_INFERRED is true AND is_inferred is
true) -- the dropped count is logged on the AIPipelineRun audit row,
never surfaced as REJECTED signals). Each surviving signal is then
mapped to a new TechStackSignal row:

    LLM-emitted field             ->  TechStackSignal column
    -------------------------------    --------------------------------
    tech_name                     ->  tech_name (verbatim)
    is_competitor                 ->  is_competitor
    is_integration                ->  is_integration
    is_to_replace                 ->  is_to_replace
    usage_scope                   ->  usage_scope (NULL when null/missing)
    source_quote                  ->  source_quote (declared on BaseSignal)
    confidence                    ->  confidence   (declared on BaseSignal)
    is_inferred                   ->  is_inferred  (declared on BaseSignal)

Fields filled by the service from the request context:

    status              =  SignalStatus.PENDING
    source              =  SignalSource.LLM_EXTRACTED
    source_activity     =  activity (from the API request)
    account             =  activity.account
    client_id           =  activity.client_id
    created_by          =  request.user

Hardcoded defaults at create:

    is_discontinued     =  False
    discontinued_date   =  None
    usage_department    =  None    (DEPARTMENT scope excluded in v1)
    usage_start_year    =  None
    renewal_date        =  None
    cost_description    =  ''
    notes               =  ''

TechStackSignal.save() then derives:

    tech_name_normalized =  tech_name lowercased, trimmed, internal
                            whitespace collapsed. This is the grouping /
                            filtering / de-duplication key. The extractor
                            does NOT normalise -- `tech_name` keeps the
                            raw text for display.

    canonical_key        =  untouched (stays None). TechStack is not
                            clusterable.

Cross-tenant isolation
----------------------
No tenant-owned identifier is sent to the model on this stage anymore.
The previous design injected the tenant's TechCatalog UUIDs into the
context and had to re-validate every returned UUID against
activity.client_id (hallucination / cross-tenant exfiltration guard).
With free-text identity there is no id to leak or forge: the model sees
the transcript and returns text.

Versioning
----------
TECHSTACK_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions
so the exact prompt revision used for any persisted signal can be
retrieved later for quality measurement and debugging.
"""


__all__ = ['TECHSTACK_PROMPT_VERSION', 'build_techstack_request']


TECHSTACK_PROMPT_VERSION = 'v1'


def build_techstack_request(transcript):
    """
    Build the request layer for one TechStack extraction sub-call.

    Args:
        transcript: str -- the full transcript text pasted by the rep.
            Sent verbatim to the LLM (no sanitisation here -- the
            data-exposure contract with the LLM provider is governed
            at the legal layer via DPA, not in this module).

    Returns:
        str: A ready-to-concatenate request block. Will be combined
        with the context layer (which includes the TECH CATALOG list)
        by PromptBuilder.assemble() to form the final user message.
    """
    return f"""TASK
Extract TECH STACK signals from the SALES TRANSCRIPT below.

A tech stack signal is structured evidence that the PROSPECT (the
account-side) uses a specific tool, software, or product at their
company.

DO NOT emit:
- Tools the SELLER uses or sells (e.g. the prospect describing the
  seller's product is not a tech stack observation about the prospect).
- Tools mentioned only HYPOTHETICALLY ("we could try X", "what about Y?")
  without confirmed current adoption by the prospect.
- Tools the seller suggests in passing, unless the prospect confirms
  they currently use them.

TOOL NAME
Emit the tool name as it appears in the transcript, in `tech_name`.
Do not normalise casing or spacing, do not expand abbreviations, do not
map it onto a reference list -- the backend handles all of that.
`tech_name` is REQUIRED on every signal; a signal without it is dropped.

QUALIFICATION
Each signal carries three INDEPENDENT booleans. Any combination is
valid, including all three false, which simply means the prospect uses
the tool with no further commercial angle.

- "is_competitor"  -- the tool overlaps with what the SELLER sells.
- "is_integration" -- the tool is one the SELLER's product connects to.
- "is_to_replace"  -- the prospect intends to move off this tool.

Set a flag ONLY when the transcript supports it; default to false.

# TODO(S10 -> AI-sprint): the three definitions above are deliberately
# one line each. This is the anchor point for the full qualification
# wording, which is NOT written in S10:
#   * is_competitor  -- how to decide overlap without knowing the
#     seller's catalogue in the prompt (today the model only sees the
#     seller NAME via the SESSION CONTEXT block). Decide whether to
#     inject the seller's product catalogue (app_modules.product_catalog)
#     into the context layer, and how to phrase "overlaps with".
#   * is_integration -- same question: the model cannot know the
#     seller's integration surface from the transcript alone.
#   * is_to_replace  -- needs the PAST vs FUTURE distinction that
#     `is_discontinued` extraction was deferred for (see the
#     "Why is_discontinued ... NOT extracted" section above):
#     "we dropped X" (past, not to-replace) vs "we are looking to
#     replace X" (future intent, to-replace) vs "we are unhappy with X"
#     (dissatisfaction, not yet intent). Add worked examples.
#   * Add few-shot examples covering the combinations that matter
#     (competitor + to_replace, integration only, all-false).
# Until that sprint lands, expect the model to under-set these flags.
# Under-setting is the safe failure mode: a rep can tick a box, whereas
# a wrong competitor tag misleads the deal strategy.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "tech_name":       "<tool name exactly as mentioned in the transcript>",
      "is_competitor":   <boolean, see QUALIFICATION>,
      "is_integration":  <boolean, see QUALIFICATION>,
      "is_to_replace":   <boolean, see QUALIFICATION>,
      "usage_scope":     "<TEAM | COMPANY | UNKNOWN, or null when scope was not discussed>",
      "source_quote":    "<verbatim excerpt from the transcript supporting this tool observation>",
      "confidence":      <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":     <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

USAGE SCOPE GUIDANCE
- "TEAM"     -- the tool is used by a single team inside a department
                (e.g. "the SDR team uses Outreach").
- "COMPANY"  -- the tool is used company-wide across multiple departments
                (e.g. "everyone here uses Slack").
- "UNKNOWN"  -- usage scope was discussed but not clarified.
- null       -- usage scope was not discussed at all.

Do NOT emit "DEPARTMENT" in v1. Department-scoped tooling requires
resolving the specific department, which is performed downstream by
the rep during validation. Treat any "department X uses tool Y"
mention as "UNKNOWN" -- the rep will refine.

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of
  prospect-side CURRENT usage of a specific tool. Apply the EVIDENCE
  RULES and EPISTEMIC FILTER from the system prompt: drop weak
  inferences and NEVER fabricate.
- Multiple signals for the SAME tool on the same activity ARE allowed
  when each carries a DISTINCT source_quote -- distinct quotes
  strengthen the cluster automatically downstream.
- `source_quote` must be a verbatim excerpt from the transcript,
  preserving the original language, punctuation, and casing. Never
  translate.
- If NO tech stack evidence is present anywhere in the transcript,
  return exactly: {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""