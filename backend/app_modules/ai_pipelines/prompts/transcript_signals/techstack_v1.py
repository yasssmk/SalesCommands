# app_modules/ai_pipelines/prompts/transcript_signals/techstack_v1.py
"""
Request layer for TechStack signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'techstack') -- session grounding +
    the TECH CATALOG list (tenant-curated tools, with UUIDs) + the
    UsageScope enum.
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of tech-stack observations. Each observation has exactly 6 fields:

    tech_catalog_entry_id  string|null  -- UUID of a matching catalog entry,
                                            or null when no match exists.
    tech_name_raw          string|null  -- raw tool name from the transcript,
                                            set ONLY when no catalog match.
    usage_scope            string|null  -- "TEAM" | "COMPANY" | "UNKNOWN",
                                            or null when not discussed.
    source_quote           string       -- verbatim excerpt from the transcript.
    confidence             float        -- LLM self-declared, in [0.0, 1.0].
    is_inferred            boolean      -- LLM self-declared, true when not
                                            directly stated.

Exactly ONE of `tech_catalog_entry_id` and `tech_name_raw` is set per
signal -- never both, never neither.

Empty result is represented by {"signals": []}.

Why scope_level DEPARTMENT is excluded from v1
----------------------------------------------
UsageScope.DEPARTMENT triggers TechStackSignal.clean() rule 2 requiring
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
    tech_catalog_entry_id (UUID)  ->  tech_catalog_entry (FK)
    tech_name_raw (no match)      ->  tech_catalog_entry = NULL
                                       + metadata['pending_tech_name'] = raw
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

TechStackSignal.save() then auto-computes:

    canonical_key       =  f'techstack:{tech_catalog_entry_id}'
                            (None when no catalog match -- the signal
                             stays PENDING with no cluster identity
                             until the rep attaches a catalog entry,
                             enforced by SignalManager.validate()).

Cross-tenant isolation (defence in depth)
-----------------------------------------
The catalog UUIDs the LLM matches against come ONLY from the tenant's
own TechCatalog (see _build_techcatalog_block in context.py -- filtered
by activity.client_id). The persistence service MUST double-check that
any emitted tech_catalog_entry_id resolves to a TechCatalog row scoped
to activity.client_id, guarding against LLM hallucination of a UUID
that does not belong to this tenant. Any failure of this check ->
demote to tech_name_raw + log security warning.

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

TECH CATALOG MATCHING
Before emitting a signal, attempt to MATCH the mentioned tool against
the TECH CATALOG provided in the context.

- If a clear match exists in the catalog (same vendor / product name,
  or unambiguous alias), emit:
      "tech_catalog_entry_id": "<uuid of the matching entry>"
      "tech_name_raw":         null
- If NO match exists in the catalog, emit:
      "tech_catalog_entry_id": null
      "tech_name_raw":         "<the tool name as it appears in the transcript>"
- Exactly ONE of `tech_catalog_entry_id` / `tech_name_raw` must be set
  on every signal. Never both. Never neither.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "tech_catalog_entry_id": "<UUID of matching catalog entry, or null if no match>",
      "tech_name_raw":         "<raw tool name as mentioned in the transcript, or null if a catalog match exists>",
      "usage_scope":           "<TEAM | COMPANY | UNKNOWN, or null when scope was not discussed>",
      "source_quote":          "<verbatim excerpt from the transcript supporting this tool observation>",
      "confidence":            <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":           <boolean, true when the signal is inferred rather than directly stated>
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