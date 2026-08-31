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

    tech_name              string       -- the tool's CANONICAL product
                                            name (official, stable
                                            spelling; verbatim when the
                                            tool is unknown or ambiguous).
                                            REQUIRED. See the TOOL NAME
                                            section of the request below.
    is_to_replace          boolean      -- the prospect intends to move off it.
    usage_scope            string|null  -- SCALE: "TEAM" | "COMPANY" |
                                            "UNKNOWN", or null when not
                                            discussed. HOW WIDELY the tool
                                            is used.
    usage_departments      string[]     -- WHO: the department(s) that USE
                                            the tool, drawn from the
                                            StandardDepartment vocabulary in
                                            the context layer. Multi-valued
                                            (a tool used by Sales AND
                                            Marketing lists both). EMPTY []
                                            when no department is explicitly
                                            designated as a user. See the
                                            USAGE DEPARTMENTS section below.
    source_quote           string       -- verbatim excerpt from the transcript.
    confidence             float        -- LLM self-declared, in [0.0, 1.0].
    is_inferred            boolean      -- LLM self-declared, true when not
                                            directly stated.

`is_to_replace` is the only qualification boolean now: false is the
common case ("the prospect uses this tool", no angle).

is_integration and is_competitor were RETIRED from this stage:
  * a required integration is a buyer REQUIREMENT, now captured as a
    ConstraintSignal of nature=TECHNICAL by the constraint stage;
  * a competitor is now captured as a CompetitorSignal by the competitor
    stage (sub-step 5).
Neither is a boolean on the tool anymore.

What replaced the catalogue match (S10)
---------------------------------------
Until S10 the schema was a XOR: `tech_catalog_entry_id` (a UUID from the
tenant's TechCatalog, injected into the context layer) OR
`tech_name_raw` when nothing matched. The catalogue has been removed, so
identity is carried by free text: the model reports the tool's canonical
name (official, stable spelling -- see the TOOL NAME rules below), and
the backend derives a normalised grouping key from it in
TechStackSignal.save(). Canonicity comes from a PROMPT instruction, not a
tenant reference table: nothing in this prompt needs tenant reference
data anymore.

Empty result is represented by {"signals": []}.

Two orthogonal axes: SCALE (usage_scope) and WHO (usage_departments)
-------------------------------------------------------------------
`usage_scope` answers HOW WIDELY the tool is used (TEAM / COMPANY /
UNKNOWN) -- a scale, unchanged by this revision. `usage_departments`
answers WHO uses it: the specific department(s), multi-valued. The two
are independent and both are emitted per tool:

  * "everyone here is on Slack"          -> usage_scope="COMPANY",
                                            usage_departments=[]
                                            (company-wide, no single dept
                                            designated).
  * "the marketing team lives in HubSpot"-> usage_scope="TEAM",
                                            usage_departments=["Marketing"].
  * "Sales and Marketing both use X"      -> usage_scope="TEAM",
                                            usage_departments=["Sales",
                                            "Marketing"].

Department names are drawn from the StandardDepartment vocabulary injected
in the context layer; the backend resolves each by EXACT name match (no
fuzzy matching) to a StandardDepartment row and assigns them to the
multi-department M2M TechStackSignal.usage_departments. An unresolved or
"General Management" name is dropped by the backend, never invented.

Why usage_scope="DEPARTMENT" is still NOT emitted
-------------------------------------------------
The scale axis keeps only TEAM / COMPANY / UNKNOWN. "which department"
is no longer a scale value -- it moved to the dedicated multi-valued
`usage_departments` field above. So the model never emits
usage_scope="DEPARTMENT".

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
    is_to_replace                 ->  is_to_replace
    usage_scope                   ->  usage_scope (NULL when null/missing)
    usage_departments             ->  usage_departments (M2M; each name
                                       resolved by exact match to a
                                       StandardDepartment row via
                                       resolve_tech_usage_departments,
                                       deduped, unresolved / General
                                       Management dropped; [] when none)
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
    usage_department    =  None    (legacy single-FK; being retired --
                                    the WHO is carried by usage_departments)
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
Emit each tool under its CANONICAL name in `tech_name` -- the tool's
official product name, spelled the standard way, so the SAME tool always
comes out identical no matter how the speakers phrased it. Downstream the
backend groups every mention of one tool on that name, so a stable
spelling is what lets two mentions of the same tool land together.

Canonical rules:
- Use the official product name with its official, stable casing
  (e.g. "HubSpot", "Salesforce", "GitHub" -- never "hubspot",
  "SALESFORCE", "salesforce crm").
- Drop a descriptive word the speaker appended that is NOT part of the
  product's own name: "HubSpot CRM" -> "HubSpot", "Salesforce CRM" ->
  "Salesforce", "Slack messaging" -> "Slack". Keep such a word ONLY when
  it is genuinely part of the official name (e.g. "Google Analytics",
  "Microsoft Teams", "Jira Service Management").
- Resolve a common, UNAMBIGUOUS acronym or nickname to the canonical
  name: "SFDC" -> "Salesforce", "GSheets" -> "Google Sheets".
- When the SAME tool is named several ways in one transcript ("HubSpot"
  then "Hubspot CRM"; "Salesforce" then "SFDC"), emit the SAME canonical
  `tech_name` on every one of its signals.

Stay verbatim when unsure. If you do not recognise the tool, or the
mapping is at all ambiguous (an acronym that could stand for several
products, an in-house or unnamed tool), keep the name exactly as spoken
rather than inventing a mapping. A faithful raw name is always better
than a wrong canonical one. No reference list is provided -- rely only on
well-known, unambiguous product knowledge, never on a guess.

`tech_name` is REQUIRED on every signal; a signal without it is dropped.

CANONICAL NAME EXAMPLES
- "we run everything on Hubspot" ... later "our HubSpot CRM is a mess"
      -> both signals emit  "tech_name": "HubSpot"
         (one tool, one canonical spelling, descriptor "CRM" dropped).
- "we're a SFDC shop" ... "Salesforce is our source of truth"
      -> both emit  "tech_name": "Salesforce"
         (unambiguous acronym resolved to the same canonical name).
- "the team lives in Salesforce CRM"
      -> emit  "tech_name": "Salesforce"  ("CRM" is a descriptor here,
         not part of the product name).
- "we built an in-house tool we call Pyramid"
      -> emit  "tech_name": "Pyramid"  (unknown / in-house: keep verbatim,
         do NOT map it to the BI product "Pyramid Analytics").

QUALIFICATION
Each signal carries ONE qualification boolean, `is_to_replace`. False is
the common case: the prospect uses the tool with no further angle.

- "is_to_replace"  -- the prospect intends to move off this tool.

Set the flag ONLY when the transcript supports it; default to false.

Do NOT emit a competitor flag here: whether a tool competes with what the
SELLER sells is captured as a CompetitorSignal by the competitor stage
(sub-step 5), not as a boolean on the tool.

Do NOT emit an integration flag here: whether the SELLER's product must
connect to a tool is a buyer REQUIREMENT, captured as a TECHNICAL
constraint by the constraint stage, not as a boolean on the tool.

# TODO(Competitors sprint): the definition above is deliberately one
# line. This is the anchor point for the full is_to_replace wording,
# which is NOT written yet:
#   * is_to_replace  -- needs the PAST vs FUTURE distinction that
#     `is_discontinued` extraction was deferred for (see the
#     "Why is_discontinued ... NOT extracted" section above):
#     "we dropped X" (past, not to-replace) vs "we are looking to
#     replace X" (future intent, to-replace) vs "we are unhappy with X"
#     (dissatisfaction, not yet intent). Add worked examples.
# Until that sprint lands, expect the model to under-set this flag.
# Under-setting is the safe failure mode: a rep can tick a box.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "tech_name":       "<canonical product name -- see TOOL NAME: official stable spelling, verbatim when the tool is unknown or ambiguous>",
      "is_to_replace":   <boolean, see QUALIFICATION>,
      "usage_scope":     "<TEAM | COMPANY | UNKNOWN, or null when scope was not discussed>",
      "usage_departments": ["<zero or more department names from the CANONICAL TAXONOMY usage_departments list -- see USAGE DEPARTMENTS; [] when none is explicitly designated>"],
      "source_quote":    "<verbatim excerpt from the transcript supporting this tool observation>",
      "confidence":      <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":     <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

USAGE SCOPE GUIDANCE (SCALE -- how widely, one value)
- "TEAM"     -- the tool is used by a single team inside a department
                (e.g. "the SDR team uses Outreach").
- "COMPANY"  -- the tool is used company-wide across multiple departments
                (e.g. "everyone here uses Slack").
- "UNKNOWN"  -- usage scope was discussed but not clarified.
- null       -- usage scope was not discussed at all.

Never emit "DEPARTMENT" for usage_scope -- it is a SCALE, not a WHO.
"which department uses it" is captured separately and multi-valued in
`usage_departments` (next section). usage_scope stays the scale even when
one or more departments are named (e.g. "the marketing team is on HubSpot"
-> usage_scope="TEAM", usage_departments=["Marketing"]).

USAGE DEPARTMENTS (WHO -- which department(s) USE the tool; multi-valued)
Emit in `usage_departments` every department that is EXPLICITLY DESIGNATED
as a USER of this tool, drawn EXACTLY from the usage_departments list in
the CANONICAL TAXONOMY block above. Several departments are allowed on one
tool.

DESIGNATION RULE (the bar for adding a department -- calqued on the
constraint scope guard):
- Add a department ONLY when the transcript explicitly designates it as
  USING the tool: "the marketing team is on HubSpot", "Sales and Marketing
  both live in the CRM", "our finance department runs everything in SAP".
- A technical theme-word, the tool's category, or the SPEAKER's own
  department do NOT designate a user. "we need SSO" names no user; an IT
  lead saying "everyone uses Slack" does not make it an IT tool.
- When NO department is explicitly designated as a user, emit an EMPTY
  list []. NEVER invent or guess a department. A company-wide tool with no
  single owner is []  (with usage_scope="COMPANY").
- Use the exact StandardDepartment strings from the taxonomy list; a name
  not in that list, or a company-wide / "General Management" catch-all, is
  dropped downstream -- so prefer [] over a non-listed guess.

USAGE DEPARTMENTS EXAMPLES (designation decides -- not the speaker, not a
technical word):
- "the marketing team has been on HubSpot for three years"
      -> usage_scope="TEAM", usage_departments=["Marketing"]
         (one department explicitly designated as the user).
- "both Sales and Marketing run their pipeline in the CRM"
      -> usage_scope="TEAM", usage_departments=["Sales", "Marketing"]
         (two departments explicitly designated -- multi-valued).
- "honestly everyone in the company is on Slack"
      -> usage_scope="COMPANY", usage_departments=[]
         (company-wide, no single department designated -- empty, not a guess).
- "we use Zendesk for support tickets"
      -> usage_scope="TEAM", usage_departments=["Customer Support"]
         (the support function is designated as the user).
- "our CTO mentioned we run Datadog"
      -> usage_departments=[]  (the SPEAKER's role does not designate a
         using department; nobody is named as the user).

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