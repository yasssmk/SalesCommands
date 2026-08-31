# app_modules/ai_pipelines/prompts/transcript_signals/competitor_v1.py
"""
Request layer for Competitor signal extraction (v1).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'competitor') -- session grounding only.
    NO taxonomy block: competitor has no what/dimension, no nature, no
    scope taxonomy (treated like the blocker stage in context.py).
The full assembly is performed by PromptBuilder.assemble() in base.py.

What a competitor IS
--------------------
A COMPETITOR is a tool/vendor the buyer is weighing as an ALTERNATIVE to,
or in COMPETITION with, the solution the seller is pitching in THIS
conversation -- the buyer is considering it INSTEAD OF / AGAINST the
seller's offering. It is the C ("Competition") of MEDDPICC.

It is deliberately distinct from the two neighbouring tech stages:
  * a TECH-STACK signal is a tool the prospect merely USES today
    ("we run on Zendesk") -- an incumbent, not an alternative to us.
  * a CONSTRAINT (nature=TECHNICAL) is a tool named only as an
    INTEGRATION requirement ("it has to plug into our Salesforce") -- a
    requirement the product must meet, not a competing option.
The SAME tool may legitimately appear in those other signals; here it is
emitted ONLY for its competition facet, and only when the transcript
frames it as a competing option.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of competitor observations. Each observation has these fields:

    summary          string   -- short rephrasing of the competitive framing
    competitor_name  string   -- name of the competing tool/vendor as stated
    source_quote     string   -- verbatim excerpt from the transcript
    confidence       float     -- LLM self-declared, in [0.0, 1.0]
    is_inferred      boolean   -- LLM self-declared

Empty result is represented by {"signals": []}.

Persistence contract
--------------------
The downstream persistence service (TranscriptSignalExtractor) first
applies the pipeline-level safety filter (confidence / is_inferred), then
maps each surviving signal to a new CompetitorSignal row:

    LLM-emitted field   ->  CompetitorSignal column
    -------------------     ----------------------------------------
    summary             ->  summary
    competitor_name     ->  competitor_name
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

CompetitorSignal.save() forces:

    canonical_key               =  None   (detached from what x dimension)
    competitor_name_normalized  =  derived from competitor_name

NEVER emitted (detached / not on this model):

    nature / rigidity           -- competitor is not a constraint.
    scope_level / target_department -- competitor carries no scope axis.
    what / dimension            -- the business canonical axes.

Versioning
----------
COMPETITOR_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions so
the exact prompt revision used for any persisted signal can be retrieved
later for quality measurement and debugging.
"""


__all__ = ['COMPETITOR_PROMPT_VERSION', 'build_competitor_request']


COMPETITOR_PROMPT_VERSION = 'v1'


def build_competitor_request(transcript):
    """
    Build the request layer for one Competitor extraction sub-call.

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
Extract COMPETITOR signals from the SALES TRANSCRIPT below.

A competitor signal is structured evidence that the buyer is weighing a
tool or vendor as an ALTERNATIVE to, or in COMPETITION with, the solution
the seller is pitching in THIS conversation -- the buyer is considering it
INSTEAD OF / AGAINST the seller's offering ("we're also evaluating
Intercom instead of you", "we're comparing you against HubSpot", "the
other option on the table is Gong").

Extract a tool/vendor ONLY when the transcript frames it as a competing
option to the seller's solution. When in doubt, do NOT emit.

Competitor vs. Tech-stack (do NOT confuse the two)
- A TOOL THE PROSPECT MERELY USES today is a tech-stack signal, NOT a
  competitor ("we currently use Zendesk for support", "our CRM is
  Salesforce"). An incumbent tool is not an alternative to us unless the
  transcript explicitly frames it as one. Captured in a separate sub-call
  -- do NOT emit used tools here.

Competitor vs. Integration requirement (do NOT confuse the two)
- A TOOL NAMED ONLY AS AN INTEGRATION REQUIREMENT is a constraint, NOT a
  competitor ("it has to integrate with our Salesforce", "you'd need to
  plug into our ERP"). A required connection is not a competing option.
  Captured in a separate sub-call -- do NOT emit integration targets here.

Same tool, several roles
- The SAME tool may legitimately appear in other signals (used, and/or an
  integration target). Here, emit it ONLY for its COMPETITION facet, and
  only if the transcript frames it as a competing option in this deal. Do
  NOT emit it here for its usage or integration facets.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "summary":         "<one short sentence rephrasing the competitive framing in your own words, around 200 chars or less>",
      "competitor_name": "<the name of the competing tool or vendor exactly as stated in the transcript>",
      "source_quote":    "<verbatim excerpt from the transcript framing the tool as a competitor / alternative>",
      "confidence":      <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":     <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- Emit a signal ONLY when the transcript provides clear evidence that the
  tool is positioned as an alternative to / in competition with the
  seller's solution. Apply the EVIDENCE RULES and EPISTEMIC FILTER from
  the system prompt: drop weak inferences and NEVER fabricate.
- `summary` MUST be your own short rephrasing of the competitive framing.
  Never copy-paste the source_quote into the summary.
- `competitor_name` MUST be the tool/vendor name as stated, preserving its
  original casing and wording. Never invent a name that is not present.
- `source_quote` MUST be the VERBATIM excerpt where the tool is framed as a
  competitor / alternative, preserving original language, punctuation, and
  casing. Never translate, paraphrase, or summarize into the quote.
- Multiple distinct competitors on the same activity ARE allowed -- emit
  one signal per competing tool, each anchored on its own verbatim quote.
- If NO competitor evidence is present anywhere in the transcript, return
  exactly: {{"signals": []}}

EXAMPLES (the FRAMING decides -- not the mere presence of a tool name)
- "We currently use Zendesk for support"
      -> NOT a competitor (a tool merely USED -- that is a tech-stack
         signal). Do NOT emit it here.
- "It has to integrate with our Salesforce"
      -> NOT a competitor (an INTEGRATION requirement -- that is a
         constraint). Do NOT emit it here.
- "We're also evaluating Intercom instead of you"
      -> competitor_name="Intercom" (framed as an alternative to us).
- "We run on Zendesk, you'd need to plug into it, and frankly we're
   weighing just expanding Zendesk rather than buying your tool"
      -> emit ONLY competitor_name="Zendesk" for the COMPETITION facet
         ("weighing ... rather than buying your tool"). Ignore its usage
         and integration facets here -- those belong to the tech-stack and
         constraint stages.

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
