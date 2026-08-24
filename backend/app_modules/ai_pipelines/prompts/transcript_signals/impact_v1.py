# app_modules/ai_pipelines/prompts/transcript_signals/impact_v1.py
"""
Request layer for Impact signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'impact') -- session grounding + the
    canonical (what, dimension) enums + the ImpactType enum.
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of impact observations. Each observation has exactly 7 fields:

    what          string   -- value from SignalWhat (see context taxonomy)
    dimension     string   -- value from SignalDimension (see context taxonomy)
    impact_type   string   -- value from ImpactType (see context taxonomy)
    summary       string   -- short rephrasing of the impact in plain language
    source_quote  string   -- verbatim excerpt from the transcript
    confidence    float    -- LLM self-declared, in [0.0, 1.0]
    is_inferred   boolean  -- LLM self-declared, true when not directly stated

Empty result is represented by {"signals": []}.

Impact vs. Pain (the diagnosis / proof distinction)
---------------------------------------------------
The transcript_signals pipeline emits Pain and Impact on the SAME
canonical axes (what x dimension). They are distinct sub-calls because
they capture different evidence shapes:

  * A PAIN is a DIAGNOSIS: "things are broken in area W along
    dimension D" -- e.g. "our reporting takes 3 weeks" (TECH x TIME).
    A pain is structured evidence that friction exists. It is NOT
    quantified, NOT attributed to a person, NOT scored as severe.
    Pain extraction is captured in the `pain` sub-call -- NOT here.

  * An IMPACT is the QUANTIFIED CONSEQUENCE or HUMAN DIMENSION of the
    pain -- e.g. "that 3-week delay costs us 30k euros per quarter"
    (TECH x TIME, impact_type=FINANCIAL); "our analyst is on the verge
    of burnout because of it" (TECH x TIME, impact_type=HUMAN).
    Impact extraction captures evidence of CONSEQUENCE: money lost,
    time lost, opportunities missed, people frustrated, strategic
    risks raised.

A passage that combines a problem AND its consequence may legitimately
produce BOTH a pain (other sub-call) AND an impact (here), each anchored
on its own quote. They share canonical_key axes but live in distinct
cluster perspectives downstream.

Why impact_type is extracted but human_impact / metric_text are not
-------------------------------------------------------------------
ImpactType is a CLOSED ENUM with 9 unambiguous values
(FINANCIAL / TIME / PRODUCTIVITY / REVENUE / RISK / CUSTOMER / HUMAN /
STRATEGIC / METRIC). Each emitted impact carries an unambiguous nature
that the LLM can derive reliably from a quantified-consequence quote.
ImpactSignal.clean() does NOT enforce conditional logic between
impact_type and other fields, so emission is single-pass with no
brittle orchestration.

human_impact (FRUSTRATION / OVERLOAD / STRESS / DEMOTIVATION / CONFLICT)
is intentionally NOT extracted in v1. It is a fuzzy human-emotion
qualifier that pairs with impact_type=HUMAN. Mapping a quote like
"our analyst is exhausted" to OVERLOAD vs. STRESS vs. DEMOTIVATION
yields too much noise at MVP scope. The rep refines this during
validation.

metric_text (free-text quantified value like "30k euros/quarter",
"3 FTE-weeks", "15% churn risk") is similarly NOT extracted in v1.
LLM normalisation of fuzzy units is brittle and the rep can paste
the exact phrasing from the transcript during validation.

scope_level is NOT extracted either -- same stance as the objective
sub-call: the persistence service hardcodes scope_level=BUSINESS at
create, and the rep promotes to DEPARTMENT or PERSONAL during
validation. Asking the LLM to orchestrate scope inference adds
complexity for marginal MVP value.

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor)
first applies the pipeline-level safety filter (drops signals where
confidence < CONFIDENCE_MIN OR (DROP_INFERRED is true AND is_inferred is
true) -- the dropped count is logged on the AIPipelineRun audit row,
never surfaced as REJECTED signals). Each surviving signal is then
mapped to a new ImpactSignal row:

    LLM-emitted field   ->  ImpactSignal column
    -------------------     ---------------------------------------
    what                ->  what
    dimension           ->  dimension
    impact_type         ->  impact_type
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

Hardcoded defaults at create:

    scope_level         =  ScopeLevel.BUSINESS  (rep promotes during validation)
    metric_text         =  None                 (rep adds during validation)
    human_impact        =  None                 (rep adds during validation)

These defaults satisfy ImpactSignal.clean()'s required-fields rule
(source_activity NOT NULL; impact_type / what / dimension / summary /
scope_level all populated).

ImpactSignal.save() then auto-computes:

    canonical_key       =  f'impact:{what}:{dimension}'

Decision cycle / campaign are auto-propagated from source_activity by
SignalManager._propagate_activity_context at create time -- not by this
prompt. Same mechanism as Pain and Objective.

Cluster behaviour
-----------------
Multiple emitted signals sharing the same (what, dimension) are
acceptable when each carries a DISTINCT source_quote -- distinct quotes
strengthen the cluster automatically downstream. Different impact_type
values on the same canonical_key are ALSO acceptable: two impacts at
"TECH x TIME" with one FINANCIAL and one HUMAN coexist in the same
cluster, each preserving its own observation-level classification on
the member card.

Versioning
----------
IMPACT_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions so
the exact prompt revision used for any persisted signal can be retrieved
later for quality measurement and debugging.
"""


__all__ = ['IMPACT_PROMPT_VERSION', 'build_impact_request']


IMPACT_PROMPT_VERSION = 'v1'


def build_impact_request(transcript):
    """
    Build the request layer for one Impact extraction sub-call.

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
Extract IMPACT signals from the SALES TRANSCRIPT below.

An impact signal is structured evidence of the QUANTIFIED CONSEQUENCE
or HUMAN DIMENSION of a pain experienced by the prospect: money lost,
time wasted, opportunities missed, productivity dropped, revenue at
risk, customers affected, people frustrated or overloaded, strategic
risks raised.

Impact vs. Pain (important distinction)
- A PAIN is a "things are broken" statement (e.g. "our reporting takes
  3 weeks"). It is captured in a separate sub-call -- do NOT emit pains
  here.
- An IMPACT is the CONSEQUENCE of the pain (e.g. "that 3-week delay
  costs us 30k euros per quarter", "our analyst is on the verge of
  burnout because of it"). Emit these here.
- A passage that combines a problem AND its consequence may produce
  a pain (other sub-call) AND an impact (here), each anchored on its
  own quote -- they share canonical axes but live in distinct cluster
  perspectives downstream. They are not duplicates.

Impact vs. Objective (important distinction)
- An OBJECTIVE is a "we want to achieve" statement (captured in a
  separate sub-call -- do NOT emit objectives here).
- An IMPACT is an OBSERVED state, NOT a desired one. "We lose 100k
  euros per year on this" is an impact (consequence already happening).
  "We want to reduce our losses by 50%" is an objective (future
  outcome).

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "what":         "<one value from the `what` list in the CANONICAL TAXONOMY of the context>",
      "dimension":    "<one value from the `dimension` list in the CANONICAL TAXONOMY of the context>",
      "impact_type":  "<one value from the `impact_type` list in the CANONICAL TAXONOMY of the context>",
      "scope_level":  "<one value from the `scope_level` list in the context: BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when scope_level is DEPARTMENT, otherwise null>",
      "summary":      "<one short sentence rephrasing the impact in your own words, around 200 chars or less>",
      "source_quote": "<verbatim excerpt from the transcript supporting this impact>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

IMPACT_TYPE GUIDANCE
- "FINANCIAL"    -- direct money cost (e.g. "costs us 30k per quarter",
                     "we are over budget by 15%").
- "TIME"         -- time wasted on a task or process (e.g. "takes us
                     3 weeks", "the team spends 10 hours per week on
                     manual reporting").
- "PRODUCTIVITY" -- output reduction or efficiency loss (e.g. "we only
                     ship half the features we used to").
- "REVENUE"      -- revenue at risk, lost, or under-realised (e.g.
                     "we are losing 200k of ARR per year because of it",
                     "we cannot upsell").
- "RISK"         -- operational, regulatory, security, or compliance
                     risk (e.g. "we are not GDPR-compliant on this",
                     "if the system goes down we lose the day").
- "CUSTOMER"     -- customer-side impact: churn, satisfaction drop,
                     escalations (e.g. "two key accounts threatened to
                     leave", "NPS dropped 20 points").
- "HUMAN"        -- impact on the team's human dimension: morale,
                     frustration, overload, burnout, conflict (e.g.
                     "the analyst is on the verge of burnout",
                     "the team is demotivated").
- "STRATEGIC"    -- impact on the prospect's strategic positioning,
                     differentiation, or competitive standing.
- "METRIC"       -- a quantified observation that does not cleanly fit
                     another category (e.g. "our error rate is 3 times
                     the industry standard").

Pick the SINGLE most-fitting category. If a quote could plausibly fit
multiple categories, prefer the most specific one (HUMAN over METRIC,
FINANCIAL over METRIC, etc.).

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of a
  consequence ALREADY OBSERVED by the prospect. Apply the EVIDENCE
  RULES and EPISTEMIC FILTER from the system prompt: drop weak
  inferences and NEVER fabricate.
- Multiple signals sharing the same (what, dimension) pair ARE allowed
  when each carries a DISTINCT source_quote -- distinct quotes
  strengthen the cluster automatically downstream. Different
  impact_type values on the same (what, dimension) are also acceptable
  (e.g. one FINANCIAL impact and one HUMAN impact on the same area).
- `summary` must be your own rephrasing of the impact. Never copy-paste
  the source_quote into the summary.
- `source_quote` must be a verbatim excerpt from the transcript,
  preserving the original language, punctuation, and casing. Never
  translate.
- `scope_level` MUST be exactly BUSINESS or DEPARTMENT, decided ONLY by the
  SUBJECT of the impact -- which perimeter it concerns -- never by who is
  speaking. DEPARTMENT = the impact names or clearly identifies one specific
  department (use that department verbatim, no interpretation), even if the
  speaker belongs to another department and even if the financial consequence
  hits the whole company. BUSINESS = no specific department is named; the
  impact is company-wide or cross-departmental. A senior person (CEO, GM,
  C-level) describing one department's impact is still DEPARTMENT. Never emit
  PERSONAL or any other value.
- `target_department` is REQUIRED when scope_level is DEPARTMENT: pick exactly
  one value from the `target_department` list in the context. It MUST be null
  when scope_level is BUSINESS.
- If NO impact evidence is present anywhere in the transcript, return
  exactly: {{"signals": []}}

SCOPE EXAMPLES (the SUBJECT decides the scope, never the speaker)
- The IT lead says "marketing loses 40k per quarter on misallocated ad spend"
  -> scope_level = "DEPARTMENT", target_department = "Marketing"
     (the subject is Marketing, even though the speaker is from IT and the
      cost is financial)
- Someone says "company-wide, downtime costs us 200k a year"
  -> scope_level = "BUSINESS", target_department = null
     (no single department is the subject)

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""