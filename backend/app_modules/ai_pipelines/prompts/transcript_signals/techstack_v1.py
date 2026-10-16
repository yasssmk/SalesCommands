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
array of tech-stack observations (v3). Each observation has these fields:

    tech_name              string       -- the tool's CANONICAL product
                                            name (official, stable
                                            spelling; verbatim when the
                                            tool is unknown or ambiguous).
                                            REQUIRED. See the TOOL NAME
                                            section of the request below.
    usage_scope            string       -- three cases: "DEPARTMENT" (one
                                            or more departments designated
                                            as users) | "COMPANY" (company-
                                            wide) | "UNKNOWN" (not said).
                                            Never null (v2).
    usage_departments      string[]     -- WHO: the department(s) that USE
                                            the tool, drawn from the
                                            StandardDepartment vocabulary in
                                            the context layer. Multi-valued
                                            (a tool used by Sales AND
                                            Marketing lists both). EMPTY []
                                            when no department is explicitly
                                            designated as a user. See the
                                            USAGE DEPARTMENTS section below.
    usage_start_year       int|null     -- year the prospect started using it.
    renewal_date           date|null    -- next renewal, YYYY-MM-DD.
    cost_description       string|null  -- the cost as stated (verbatim).
    is_discontinued        boolean      -- the prospect stopped / will stop
                                            using it, with a stated date.
    discontinued_date      date|null    -- that stop date, YYYY-MM-DD.
    notes                  string|null  -- HOW the tool is used + what the
                                            prospect thinks of it.
    source_quote           string       -- verbatim excerpt from the transcript.
    confidence             float        -- LLM self-declared, in [0.0, 1.0].
    is_inferred            boolean      -- LLM self-declared, true when not
                                            directly stated.

The lifecycle fields and notes are emitted ONLY when the transcript says
them, else null -- never guessed (same rule as the People department, v3).

is_to_replace, is_integration and is_competitor were RETIRED from this stage
(is_to_replace in v3: the column stays in the DB, always False on extraction
-- its replacement is a cluster-level "replacement considered", TD-199):
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

Usage in three cases (v2): usage_scope + usage_departments
-----------------------------------------------------------
PO rule (Sprint TechStack): at the prospect we speak of DEPARTMENTS, never
of teams. Usage is exactly one of three cases:

  * DEPARTMENT -- one or more departments are designated as users; they
                  are listed in `usage_departments`.
  * COMPANY    -- the transcript says the WHOLE company / everyone uses the
                  tool (v4: "we use X" / "on est sur X" is NOT company-wide).
  * UNKNOWN    -- usage not said. "Not said" is UNKNOWN, never null.

  * "everyone here is on Slack"          -> usage_scope="COMPANY",
                                            usage_departments=[].
  * "the marketing team lives in HubSpot"-> usage_scope="DEPARTMENT",
                                            usage_departments=["Marketing"].
  * "Sales and Marketing both use X"      -> usage_scope="DEPARTMENT",
                                            usage_departments=["Sales",
                                            "Marketing"].
  * "we use Datadog" (nothing more)       -> usage_scope="UNKNOWN",
                                            usage_departments=[].
  * "on est sur Salesforce" (nothing more)-> usage_scope="UNKNOWN" (v4).

DEPARTMENT <=> at least one department: the backend derives the final
usage_scope from the RESOLVED departments (_techstack_usage_scope in the
extractor), so an unresolvable department name falls back to UNKNOWN.

Department names are drawn from the StandardDepartment vocabulary injected
in the context layer; the backend resolves each by EXACT name match (no
fuzzy matching) to a StandardDepartment row and assigns them to the
multi-department M2M TechStackSignal.usage_departments. An unresolved or
"General Management" name is dropped by the backend, never invented.

Lifecycle + notes ARE extracted since v3 (Sprint TechStack T4)
---------------------------------------------------------------
Until v2 these fields were left to the rep (fuzzy extraction). PO decision:
extract them, but ONLY when the transcript says them -- never guessed:

  * usage_start_year -- a year; relative statements ("for three years")
    are resolved with the "Conversation date" of the context layer (v4;
    no conversation date -> every relative date is null).
  * renewal_date / discontinued_date -- YYYY-MM-DD; relative dates ("next
    March", "end of the year", "cette année") resolved with the
    Conversation date. A partial or hedged date the model cannot resolve is
    null.
  * cost_description -- verbatim (no normalisation, no false precision).
  * is_discontinued -- the prospect stopped or will stop using the tool,
    with its stop date. Intent alone ("we are unhappy with X") is NOT a
    discontinuation; it belongs in the notes.
  * notes -- HOW the tool is used (e.g. Azure AD "used for SSO") and what
    the prospect thinks of it (satisfaction, pain points).

The backend re-checks everything (TranscriptSignalExtractor._build_techstack_
data): a year outside the bounds or an unparseable date is dropped to null;
discontinued without a valid date is NOT discontinued (the phrase is kept in
the notes, D2); a second mention of the same tool completes the empty fields
of the first (D3). No consumer scores these fields today (the former "cluster
priority scorer" weight on is_discontinued is not wired).

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
    usage_scope                   ->  usage_scope (three cases; DEPARTMENT
                                       iff departments resolved, else
                                       COMPANY when emitted, else UNKNOWN)
    usage_departments             ->  usage_departments (M2M; each name
                                       resolved by exact match to a
                                       StandardDepartment row via
                                       resolve_tech_usage_departments,
                                       deduped, unresolved / General
                                       Management dropped; [] when none)
    usage_start_year              ->  usage_start_year (int in bounds, else NULL)
    renewal_date                  ->  renewal_date (valid ISO date, else NULL)
    cost_description              ->  cost_description (stripped, '' if none)
    is_discontinued +
      discontinued_date           ->  is_discontinued / discontinued_date
                                       (D2: no valid date -> False / NULL,
                                       phrase appended to notes)
    notes                         ->  notes (stripped, '' if none)
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

Hardcoded at create:

    is_to_replace       =  False   (out of the v3 schema, see above)

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

  v1 -- S10 free-text identity + usage_departments (Tech scope sprint).
  v2 -- Sprint TechStack T0: usage in three cases (DEPARTMENT / COMPANY /
        UNKNOWN), TEAM retired, "not said" = UNKNOWN (never null).
  v3 -- Sprint TechStack T4: lifecycle + notes extracted (only when said),
        one technology = one signal (Salesforce / Azure AD example),
        is_to_replace out of the output schema.
  v4 -- Sprint TechStack T4b (PO smoke on T4): identity / infra / security /
        collaboration tools ARE tech stack, a used tool also required as an
        integration is still emitted here, the "we need SSO" counter-example
        replaced by a neutral one; relative dates resolved with the
        "Conversation date" (null without it, FR "cette année" example);
        COMPANY only when the WHOLE company is said to use the tool ("on est
        sur X" -> UNKNOWN). Goes with CONTEXT v5 (dedicated TECH STACK
        TAXONOMY header, no "or OMIT the signal").
"""


__all__ = ['TECHSTACK_PROMPT_VERSION', 'build_techstack_request']


TECHSTACK_PROMPT_VERSION = 'v4'


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
        with the context layer (session grounding, activity date, usage
        taxonomy) by PromptBuilder.assemble() to form the final user message.
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

Identity, infrastructure, security and collaboration tools (SSO, Azure AD,
Okta, AWS, ...) ARE tech stack: emit them like any other tool the prospect
uses.

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

ONE technology = ONE signal
Each distinct tool, software or product gets its OWN signal, even when
several are named in the same sentence. Never merge two tools into one
signal, never fold one tool into another's notes.
- "On est sur Salesforce et on a un SSO Azure AD."
      -> 2 signals:
         {{"tech_name": "Salesforce", "notes": null, ...}}
         {{"tech_name": "Azure AD", "notes": "SSO", ...}}
         (two tools; HOW Azure AD is used -- for SSO -- goes in its notes).

Do NOT emit a competitor flag here: whether a tool competes with what the
SELLER sells is captured as a CompetitorSignal by the competitor stage, not
as a boolean on the tool.

Do NOT emit an integration flag here: whether the SELLER's product must
connect to a tool is a buyer REQUIREMENT, captured as a TECHNICAL
constraint by the constraint stage, not as a boolean on the tool. A tool the
prospect uses can ALSO be an integration requirement: STILL emit it here as
a tech stack signal (the constraint stage captures the requirement apart).

LIFECYCLE AND NOTES
Fill each of these fields ONLY when the transcript says it; otherwise emit
null -- never guess, never infer from the tool's category or the company.
Every relative date ("this year", "next year", "end of the year", "in June",
"for three years") is resolved with the "Conversation date" given in the
context. When the context says the conversation date is not provided, every
relative date is null.
- "usage_start_year" -- the year the prospect STARTED using the tool, as an
  integer (e.g. 2019). "We've been on it for three years" -> the
  Conversation date's year minus 3.
- "renewal_date"     -- the next contract renewal, YYYY-MM-DD. Resolve a
  relative date ("next March", "at the end of the year") with the
  Conversation date; if it cannot be resolved to a precise day, emit null.
- "cost_description" -- the cost EXACTLY as stated ("around 3k a month",
  "120k$/year", "free tier"). Never convert or normalise.
- "is_discontinued"  -- true ONLY when the prospect says they stopped or
  will stop using the tool, AND the stop date is stated; false otherwise.
  Dissatisfaction or an intent to look elsewhere is NOT a discontinuation:
  put it in the notes.
- "discontinued_date" -- the stop date, YYYY-MM-DD (resolved with the
  Conversation date); null when is_discontinued is false.
  « on arrête X le 31 décembre de cette année »
      -> "is_discontinued": true,
         "discontinued_date": "<conversation year>-12-31"
         ("cette année" = the year of the Conversation date).
- "notes" -- HOW the prospect uses the tool (e.g. "SSO", "pipeline
  management", "support tickets") and what the prospect THINKS of it
  (satisfaction, pain points), in one or two short sentences. null when the
  transcript says nothing of it.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "tech_name":       "<canonical product name -- see TOOL NAME: official stable spelling, verbatim when the tool is unknown or ambiguous>",
      "usage_scope":     "<DEPARTMENT | COMPANY | UNKNOWN>",
      "usage_departments": ["<zero or more department names from the CANONICAL TAXONOMY usage_departments list -- see USAGE DEPARTMENTS; [] when none is explicitly designated>"],
      "usage_start_year": <integer year, or null -- see LIFECYCLE AND NOTES>,
      "renewal_date":    "<YYYY-MM-DD, or null>",
      "cost_description": "<the cost exactly as stated, or null>",
      "is_discontinued": <boolean -- true only with a stated stop date>,
      "discontinued_date": "<YYYY-MM-DD, or null>",
      "notes":           "<how the tool is used + what the prospect thinks of it, or null>",
      "source_quote":    "<verbatim excerpt from the transcript supporting this tool observation>",
      "confidence":      <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":     <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

USAGE (exactly one of three cases)
At the prospect we speak of DEPARTMENTS, never of teams.
- "DEPARTMENT" -- one or more departments are explicitly designated as
                  users of the tool; list them in `usage_departments`
                  (e.g. "the SDR team in Sales uses Outreach" -> Sales).
- "COMPANY"    -- ONLY when
                  the transcript says the WHOLE company / everyone uses the tool
                  (e.g. "everyone here uses Slack").
                  "we use X" / "on est sur X" is NOT company-wide -> "UNKNOWN".
- "UNKNOWN"    -- how the tool is used is not said. Usage not said is
                  UNKNOWN, never null and never a guess.

"DEPARTMENT" always comes with at least one department in
`usage_departments`; "COMPANY" and "UNKNOWN" always come with [].

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
  department do NOT designate a user. "we have a ticketing tool" names no
  user; an IT lead saying "everyone uses Slack" does not make it an IT tool.
- When NO department is explicitly designated as a user, emit an EMPTY
  list [] -- and still emit the tool. NEVER invent or guess a department. A
  tool the transcript says the whole company uses is []  (with
  usage_scope="COMPANY"); a tool whose usage is not said is []  (with
  usage_scope="UNKNOWN").
- Use the exact StandardDepartment strings from the taxonomy list; a name
  not in that list, or a company-wide / "General Management" catch-all, is
  dropped downstream -- so prefer [] over a non-listed guess.

USAGE DEPARTMENTS EXAMPLES (designation decides -- not the speaker, not a
technical word):
- "the marketing team has been on HubSpot for three years"
      -> usage_scope="DEPARTMENT", usage_departments=["Marketing"]
         (one department explicitly designated as the user).
- "both Sales and Marketing run their pipeline in the CRM"
      -> usage_scope="DEPARTMENT", usage_departments=["Sales", "Marketing"]
         (two departments explicitly designated -- multi-valued).
- "honestly everyone in the company is on Slack"
      -> usage_scope="COMPANY", usage_departments=[]
         (company-wide, no single department designated -- empty, not a guess).
- "we use Zendesk for support tickets"
      -> usage_scope="DEPARTMENT", usage_departments=["Customer Support"]
         (the support function is designated as the user).
- « On est sur Salesforce. »
      -> usage_scope="UNKNOWN", usage_departments=[]
         ("on est sur" is not company-wide: the usage is not said).
- « Salesforce, c'est pour le pilotage du pipeline commercial. »
      -> usage_scope="DEPARTMENT", usage_departments=["Sales"]
         (the commercial pipeline designates Sales as the user).
- « Côté support, on est sur Zendesk. »
      -> usage_scope="DEPARTMENT", usage_departments=["Customer Support"]
         ("côté support" designates the support function).
- "our CTO mentioned we run Datadog"
      -> usage_scope="UNKNOWN", usage_departments=[]  (the SPEAKER's role
         does not designate a using department; nobody is named as the user
         and the usage is not said).

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of
  prospect-side CURRENT usage of a specific tool (a tool the prospect uses
  today, including one whose stop date is stated -- is_discontinued). Apply the EVIDENCE
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