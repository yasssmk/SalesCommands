# app_modules/ai_pipelines/prompts/transcript_signals/constraint_v1.py
"""
Request layer for Constraint signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'constraint') -- session grounding +
    the ConstraintNature list and the scope (scope_level +
    target_department) taxonomy. NO what/dimension block: constraint is
    detached from the business canonical axes (sub-step 1).
The full assembly is performed by PromptBuilder.assemble() in base.py.

What a constraint IS
--------------------
A CONSTRAINT is a Decision Criterion the buyer imposes on the solution --
a requirement the product MUST satisfy to be acceptable ("it must
integrate with our ERP", "budget is capped at 50k", "GDPR compliance is
mandatory"). It is the "what the solution has to meet" axis of MEDDPICC.

It is deliberately distinct from the two neighbouring free-text stages:
  * a PAIN is a problem the buyer LIVES today ("our reporting takes 3
    weeks") -- a diagnosis of the current state, not a requirement.
  * a BLOCKER/objection is what STOPS the deal from progressing ("no
    budget this quarter", "I must ask the CTO") -- a deal-side obstacle,
    not a criterion the product must meet.
A constraint pulls in a third direction: it is the yardstick the product
is measured against.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of constraint observations. Each observation has exactly 7 fields:

    summary            string       -- short rephrasing of the requirement
    nature             string       -- ONE value from ConstraintNature
                                        (see the NATURE list in the context)
    scope_level        string       -- "BUSINESS" or "DEPARTMENT"
    target_department  string|null  -- one value from the target_department
                                        list when scope_level is DEPARTMENT,
                                        else null
    rigidity           string       -- "FIRM" or "FLEXIBLE"
    source_quote       string       -- verbatim excerpt from the transcript
    confidence         float        -- LLM self-declared, in [0.0, 1.0]
    is_inferred        boolean      -- LLM self-declared

Empty result is represented by {"signals": []}.

Scope note (subject-not-speaker) -- why scope_level is emitted but not stored
----------------------------------------------------------------------------
Constraint is scoped by DEPARTMENT only (PO decision): the model emits
`scope_level` + `target_department` exactly like pain/objective/impact, so
the SHARED resolver `resolve_scope_and_department` can turn a named
department into the target_department FK. ConstraintSignal has NO
scope_level column -- only `target_department` is persisted; a BUSINESS
constraint stores target_department = None. The `scope_level` field is a
routing signal for the resolver, not a stored value.

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor) first
applies the pipeline-level safety filter (confidence / is_inferred), then
maps each surviving signal to a new ConstraintSignal row:

    LLM-emitted field   ->  ConstraintSignal column
    -------------------     ----------------------------------------
    summary             ->  summary
    nature              ->  nature      (validated against ConstraintNature;
                                         a signal with an out-of-list nature
                                         is DROPPED, never coerced)
    rigidity            ->  rigidity
    target_department   ->  target_department (resolved from scope_level +
                                         target_department by the shared
                                         resolve_scope_and_department; BUSINESS
                                         or an unresolved name -> None)
    source_quote        ->  source_quote (declared on BaseSignal)
    confidence          ->  confidence   (declared on BaseSignal)
    is_inferred         ->  is_inferred  (declared on BaseSignal)

Fields filled by the service from the request context:

    status              =  SignalStatus.PENDING
    source              =  SignalSource.LLM_EXTRACTED
    source_activity     =  activity (from the API request)
    account             =  activity.account
    client_id           =  activity.client_id
    created_by          =  request.user

ConstraintSignal.save() forces:

    canonical_key       =  None   (constraint is detached from what x dimension)

NEVER emitted (detached in sub-step 1):

    what / dimension    -- the business canonical axes. A constraint is
                           classified on `nature`, never on what/dimension.

Versioning
----------
CONSTRAINT_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions so
the exact prompt revision used for any persisted signal can be retrieved
later for quality measurement and debugging.
"""


__all__ = ['CONSTRAINT_PROMPT_VERSION', 'build_constraint_request']


CONSTRAINT_PROMPT_VERSION = 'v1'


def build_constraint_request(transcript):
    """
    Build the request layer for one Constraint extraction sub-call.

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
Extract CONSTRAINT signals from the SALES TRANSCRIPT below.

A constraint signal is structured evidence that the buyer imposes a
DECISION CRITERION on the solution -- a requirement the product MUST
satisfy to be acceptable. It is the yardstick the product is measured
against ("it has to integrate with our ERP", "we can't exceed a 50k
budget", "GDPR compliance is mandatory", "we need real-time reporting").

Constraint vs. Pain (do NOT confuse the two)
- A PAIN is a problem the buyer LIVES in their current state ("our
  reporting takes three weeks", "the data is unreliable"). It describes
  what is broken today. Captured in a separate sub-call -- do NOT emit
  pains here.
- A CONSTRAINT is a requirement the buyer places ON THE SOLUTION ("the
  new tool must produce reporting in under a day"). It describes what the
  product has to meet, not what is broken. A pain often motivates a
  constraint, but only the REQUIREMENT is a constraint.

Constraint vs. Blocker/Objection (do NOT confuse the two)
- A BLOCKER/objection is what STOPS the deal from moving forward ("we
  have no budget this quarter", "I need the CTO to sign off"). It is a
  deal-side obstacle. Captured in a separate sub-call -- do NOT emit
  blockers here.
- A CONSTRAINT is a criterion the product must satisfy, independent of
  whether the deal is currently stalled. "We won't buy without SSO" is a
  constraint (a requirement: SSO); "I can't get budget approved before
  Q3" is a blocker (an obstacle to closing).

NATURE (pick EXACTLY ONE code from the `nature` list in the context)
Classify each constraint by what KIND of criterion it is:
- FUNCTIONAL  = what the product must DO (features / capabilities the
  buyer expects): "we need real-time reporting", "it must support
  multi-currency invoicing".
- TECHNICAL   = HOW it integrates or is deployed (integrations,
  compatibility, deployment model): "it has to integrate with our ERP",
  "we require SSO", "it must run on-premise".
- FINANCIAL   = budget, pricing, ROI, payment terms: "the budget is
  capped at 50k", "we need at least 20% ROI in 18 months".
- CONTRACTUAL = contract clauses, commitment, SLA, regulatory / legal
  compliance: "GDPR compliance is mandatory", "we need a 99.9% uptime
  SLA", "no multi-year lock-in".
- OPERATIONAL = process, training, change management: "our team needs
  onboarding support", "it must fit our existing approval workflow".
- SECURITY    = security requirements (encryption, certifications, access
  control): "data must be encrypted at rest", "you need SOC 2", "we
  require role-based access control".

FUNCTIONAL vs TECHNICAL -- the boundary (read carefully)
- FUNCTIONAL is WHAT the product does; TECHNICAL is HOW it connects to
  the buyer's environment.
- "we need advanced reporting"       -> FUNCTIONAL (a capability).
- "it must integrate with our ERP"   -> TECHNICAL (a connection).
- "we require SSO"                    -> TECHNICAL (auth integration).
- "we need multi-currency support"   -> FUNCTIONAL (a capability).
When a requirement is about connecting to, deploying into, or being
compatible with the buyer's systems, it is TECHNICAL -- not FUNCTIONAL.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "summary":      "<one short sentence rephrasing the requirement in your own words, around 200 chars or less>",
      "nature":       "<one code from the `nature` list in the context: FUNCTIONAL | TECHNICAL | FINANCIAL | CONTRACTUAL | OPERATIONAL | SECURITY>",
      "scope_level":  "<one value from the `scope_level` list in the context: BUSINESS or DEPARTMENT>",
      "target_department": "<one value from the `target_department` list when scope_level is DEPARTMENT, otherwise null>",
      "rigidity":     "<FIRM when the requirement is non-negotiable, FLEXIBLE when it is a preference>",
      "source_quote": "<verbatim excerpt from the transcript stating the requirement>",
      "confidence":   <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":  <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

RIGIDITY
- FIRM     = a hard, non-negotiable requirement ("must", "mandatory",
             "we won't proceed without ...").
- FLEXIBLE = a preference or nice-to-have ("ideally", "we'd prefer",
             "it would help if ...").

SCOPE (the SUBJECT decides the scope, never the speaker)
- `scope_level` MUST be exactly BUSINESS or DEPARTMENT, decided ONLY by
  the SUBJECT of the constraint -- which perimeter the requirement
  concerns -- never by who is speaking.
- DEPARTMENT = the constraint names or clearly identifies one specific
  department that owns the requirement (use that department verbatim from
  the `target_department` list), even if the speaker belongs to another
  department.
- BUSINESS = no specific department is named; the requirement is
  company-wide or cross-departmental. NEVER invent a department that was
  not clearly named -- when in doubt, emit BUSINESS with
  target_department = null. BUSINESS is the safe default.
- `target_department` is REQUIRED when scope_level is DEPARTMENT (pick
  exactly one value from the `target_department` list) and MUST be null
  when scope_level is BUSINESS.

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence of a
  requirement the buyer imposes on the solution. Apply the EVIDENCE RULES
  and EPISTEMIC FILTER from the system prompt: drop weak inferences and
  NEVER fabricate.
- `summary` MUST be your own short rephrasing of the requirement. Never
  copy-paste the source_quote into the summary.
- `source_quote` MUST be the VERBATIM excerpt where the requirement is
  stated, preserving original language, punctuation, and casing. Never
  translate, paraphrase, or summarize into the quote.
- `nature` MUST be exactly one code from the `nature` list. Never invent a
  value outside it.
- Multiple distinct constraints on the same activity ARE allowed -- emit
  one signal per requirement, each anchored on its own verbatim quote.
- If NO constraint evidence is present anywhere in the transcript, return
  exactly: {{"signals": []}}

SCOPE / NATURE EXAMPLES
- IT lead: "it has to plug into our SAP instance"
      -> nature="TECHNICAL", scope_level="DEPARTMENT", target_department="IT",
         rigidity="FIRM"
- "we need real-time dashboards for the whole company"
      -> nature="FUNCTIONAL", scope_level="BUSINESS", target_department=null
- "GDPR compliance is non-negotiable"
      -> nature="CONTRACTUAL", scope_level="BUSINESS", target_department=null,
         rigidity="FIRM"
- "ideally the price stays under 50k a year"
      -> nature="FINANCIAL", scope_level="BUSINESS", target_department=null,
         rigidity="FLEXIBLE"
- (NOT a constraint) "our reporting takes three weeks today"
      -> this is a PAIN, not a constraint -- do NOT emit it here.
- (NOT a constraint) "I can't get budget signed off before Q3"
      -> this is a BLOCKER, not a constraint -- do NOT emit it here.

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
