# app_modules/ai_pipelines/prompts/next_steps/next_steps_v2.py
"""
Request layer for Next-Step signal extraction (v2) — Sprint Next steps 3.3.

Combined at call time, like v1 (next_steps_v1.py, kept unchanged: the
measured baseline), with prompts/transcript_signals/system.py and the
next_steps context layer -- v6: session block + the decision cycle block
(steps with `ref`, derived status, `current` / `conversation` marks; open
activities).

What v2 changes (PO rules, Sprint Next steps 3.3)
-------------------------------------------------
  a) ONE distinct action = ONE next step: preparing something and meeting
     about it are two; a first version and the final version are two.
  b) Relative dates: the shared RELATIVE_DATE_RULE
     (transcript_signals/date_rules.py), and the date AS SAID in
     `suggested_date_text`.
  c) A step of the prospect's own internal process -> a TASK with
     `carried_by_prospect` true and the stated deadline, PLUS a seller
     follow-up (a CALL only when explicitly planned, else a TASK titled as a
     follow-up -- a follow-up not explicitly said is `is_inferred` true).
  d) New fields: `suggested_decision_step` (a `ref` of the context, chosen
     from the CONTENT of the action -- a correspondence covering the 5
     generic steps -- with the `conversation` / `current` marks; null when
     none clearly matches), `suggested_people_names` (prospect side, as
     written), `suggested_internal_names` (seller side), `suggested_topics`,
     `suggested_success_criterion` (only when said or deducible from what is
     said, else "").
  e) The model never chooses an activity to link: the server ranks the
     candidates (signals/services/next_step_link_service.py, 2.3).
  f) Every free text (title, objective, topics, success criterion) in the
     language of the transcript (LANGUAGE paragraph).

The PO review corrections (rule 3 is_inferred, rule 4 on the 5 generic
steps, the LANGUAGE paragraph) came before any v2 measure: same version v2.

No example comes from the eval transcripts (evals/next_steps leak guard,
checked in tests/ai_pipelines/test_next_steps_prompt_v2.py). The v1 TD-5
example (justification vs act of proposing) is kept, with a neutral role.

Schema (v2) -- NEXT_STEPS_RESPONSE_SCHEMA, strict
-------------------------------------------------
One JSON object {"signals": [...]}, each observation with exactly these 14
fields (every one required, no other field):

    suggested_title              string
    suggested_activity_type      string  -- ActivityType value
    carried_by_prospect          boolean
    suggested_due_date           string|null -- YYYY-MM-DD
    suggested_date_text          string  -- the date as said, "" if none
    suggested_decision_step      string|null -- a step `ref` of the context
    suggested_people_names       string[] -- prospect side, as written
    suggested_internal_names     string[] -- seller side, as written
    suggested_objective          string
    suggested_success_criterion  string
    suggested_topics             string
    source_quote                 string  -- the JUSTIFICATION (TD-5)
    confidence                   number
    is_inferred                  boolean

The field names are the NextStepSignal columns (Sprint Next steps 1.1).
`suggested_decision_step` is a ref string, not an enum: the refs depend on
the cycle; the server maps it to the step (NEXT_STEPS_STEP_REF_FORMAT) and
drops an unknown one.

Versioning
----------
NEXT_STEPS_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions.
"""

from app_modules.activities.constants import ActivityType

from ..transcript_signals.date_rules import RELATIVE_DATE_RULE


__all__ = [
    'NEXT_STEPS_PROMPT_VERSION',
    'NEXT_STEPS_RESPONSE_SCHEMA',
    'build_next_steps_request',
]


NEXT_STEPS_PROMPT_VERSION = 'v2'

_FIELDS = (
    'suggested_title', 'suggested_activity_type', 'carried_by_prospect',
    'suggested_due_date', 'suggested_date_text', 'suggested_decision_step',
    'suggested_people_names', 'suggested_internal_names', 'suggested_objective',
    'suggested_success_criterion', 'suggested_topics', 'source_quote',
    'confidence', 'is_inferred',
)

_NAMES = {'type': 'array', 'items': {'type': 'string'}}

# Strict Structured Outputs schema of the answer: the exact shape of the
# OUTPUT SCHEMA below -- every field required, no other field, nullables
# typed [..., "null"]; the activity type enum is ActivityType.
NEXT_STEPS_RESPONSE_SCHEMA = {
    'name': 'next_steps_signals_v2',
    'schema': {
        'type': 'object',
        'additionalProperties': False,
        'required': ['signals'],
        'properties': {
            'signals': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': list(_FIELDS),
                    'properties': {
                        'suggested_title':             {'type': 'string'},
                        'suggested_activity_type':     {
                            'type': 'string', 'enum': list(ActivityType.values),
                        },
                        'carried_by_prospect':         {'type': 'boolean'},
                        'suggested_due_date':          {'type': ['string', 'null']},
                        'suggested_date_text':         {'type': 'string'},
                        'suggested_decision_step':     {'type': ['string', 'null']},
                        'suggested_people_names':      _NAMES,
                        'suggested_internal_names':    _NAMES,
                        'suggested_objective':         {'type': 'string'},
                        'suggested_success_criterion': {'type': 'string'},
                        'suggested_topics':            {'type': 'string'},
                        'source_quote':                {'type': 'string'},
                        'confidence':                  {'type': 'number'},
                        'is_inferred':                 {'type': 'boolean'},
                    },
                },
            },
        },
    },
}


def _activity_type_json_array():
    """ActivityType DB values as a JSON-array string (single source of truth)."""
    return '[' + ', '.join(f'"{v}"' for v in ActivityType.values) + ']'


def build_next_steps_request(transcript):
    """
    Build the request layer (v2) for the NextStepsPipeline LLM call.

    Args:
        transcript: str -- the full transcript, sent verbatim.

    Returns:
        str: the request block, combined with the context layer by
        PromptBuilder.assemble().
    """
    return f"""TASK
Extract NEXT-STEP signals from the SALES TRANSCRIPT below.

A next-step signal is a STRUCTURED PROPOSAL for a follow-up action that
keeps the deal moving forward after the conversation: an action of the
seller (a call, an email, a meeting, a task to send or prepare something,
a LinkedIn message), or a step of the prospect's own internal process that
the seller must track.

A next step is grounded in the conversation: the transcript carries
evidence (an explicit ask from the prospect, a commitment of either side,
an open question someone committed to follow up on). Do NOT invent generic
next steps that the transcript does not justify.

ACTIVITY TYPE TAXONOMY
Pick exactly ONE value for `suggested_activity_type` from this list,
or OMIT the signal if none fits:
{_activity_type_json_array()}

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "suggested_title":             "<short, action-oriented title, around 200 chars or less>",
      "suggested_activity_type":     "<one value from the ACTIVITY TYPE TAXONOMY above>",
      "carried_by_prospect":         <boolean: true when the PROSPECT carries the action -- see rule 3>,
      "suggested_due_date":          "<YYYY-MM-DD, or null -- see DATES>",
      "suggested_date_text":         "<the date AS SAID in the transcript, or \\"\\" -- see DATES>",
      "suggested_decision_step":     "<a step `ref` of the DECISION CYCLE context, or null -- see rule 4>",
      "suggested_people_names":      ["<prospect-side person involved, name as written>", ...],
      "suggested_internal_names":    ["<seller-side person involved, name as written>", ...],
      "suggested_objective":         "<OBJECTIVE of the action -- see rule 5>",
      "suggested_success_criterion": "<what makes the action a success, or \\"\\" -- see rule 5>",
      "suggested_topics":            "<topics to cover in the action, or \\"\\" -- see rule 5>",
      "source_quote":                "<JUSTIFICATION for the action -- see rule 6>",
      "confidence":                  <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":                 <boolean, true when the signal is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
1. ONE distinct action = ONE next step. Preparing something and meeting
   about it are two next steps; a first version and the final version are
   two next steps; two actions said in the same sentence are two next
   steps. Never merge two actions into one title. Conversely, the same
   action repeated several times in the conversation is ONE next step.
   EXAMPLE: "We will prepare the onboarding plan, then walk your support
   team through it" -> "Prepare the onboarding plan" (TASK) AND "Walk the
   support team through the onboarding plan" (MEETING). "You get a draft of
   the data migration plan this week, the final plan once your IT has
   reviewed it" -> "Send the draft data migration plan" AND "Send the final
   data migration plan" -- each with its own date.

2. Emit a signal ONLY when the transcript provides clear evidence that the
   action is needed. Apply the EVIDENCE RULES and EPISTEMIC FILTER from the
   system prompt: drop weak inferences and NEVER fabricate.
   `suggested_title` is a short, action-oriented title for the activity
   (e.g. "Send the reference customer list", "Book an onsite visit with the
   plant manager"), your own rephrasing -- NOT a copy of the
   source_quote. `suggested_activity_type` is one value of the TAXONOMY;
   if none fits, OMIT the signal -- do not coerce to "OTHER" without
   strong justification.

3. A step of the PROSPECT's own internal process -> a TASK with
   `carried_by_prospect`: true (an internal approval, a legal review, a
   budget decision, a signature on their side), with the deadline they
   stated as its date. PLUS a seller follow-up as a SEPARATE next step,
   `carried_by_prospect`: false: a CALL only when the transcript explicitly
   plans that call, with `is_inferred`: false; otherwise a TASK whose title
   starts with "Follow up on" in the transcript's language (e.g. French
   "Retour sur ..."), dated on or right after the prospect's deadline when
   one is said -- a follow-up the transcript does not explicitly state is
   inferred: `is_inferred`: true, its confidence set per the EPISTEMIC
   FILTER. Every other next step has `carried_by_prospect`: false.
   EXAMPLE: "Our legal team must approve the terms before the 30th" ->
   "Legal approval of the terms" (TASK, carried_by_prospect: true, due the
   30th) AND "Follow up on the legal approval" (TASK, carried_by_prospect:
   false, is_inferred: true -- nobody said it).

4. `suggested_decision_step` is the `ref` of the step of the DECISION
   CYCLE context the action belongs to, chosen from the CONTENT of the
   action, matched against the step NAMES of the context: a qualification
   step for a first contact or a discovery; a technical fit step for
   integration, security, technical requirements or questionnaires; a
   solution validation step for a demo, a trial or a pilot; a business case
   step for value, ROI, pricing or budget; a closing step for a
   negotiation, procurement, the contract or the signature. Use the marks: "conversation" is the
   step of THIS conversation, "current" is the step the deal is at; an
   action that continues the work of the conversation usually stays on its
   step. null when no step clearly matches, or when the context shows no
   decision cycle. Never invent a ref.
   `suggested_people_names` lists the PROSPECT-side persons involved in the
   action (attendees, recipients, the person who carries it), each name as
   written in the transcript; `suggested_internal_names` lists the
   SELLER-side persons involved, as written. [] when nobody is named.

5. `suggested_objective` is the OBJECTIVE of the action: what it achieves
   and why it matters -- the stakes from BOTH angles, the prospect's (what
   they get out of it) and the seller's (how it advances the deal). 1-3
   concise sentences in the transcript's language; NOT a restatement of the
   title, NOT a quote. Emit "" only when the transcript gives no basis.
   `suggested_success_criterion` is what makes the action a success, ONLY
   when it is said, or deducible from what is said; otherwise "". Never a
   generic criterion.
   `suggested_topics` are the topics to cover in the action (the questions
   raised, the points to present), as said or directly implied; "" when
   none.

6. `source_quote` MUST be the JUSTIFICATION for the action -- the passage
   in the transcript that shows WHY it is needed (an explicit ask, a
   commitment, an open question). It is NOT a verbatim of the speaker
   proposing the action: the justification is the EVIDENCE that the action
   is warranted, not the act of proposing it. Quote verbatim from the
   transcript, preserving original language, punctuation and casing. Never
   translate.

   EXAMPLE -- Suppose the transcript contains:
     Head of Operations: "My team loses 15 hours per week on manual reporting, it's untenable."
     AE: "I can send you a sector benchmark tomorrow."

   The extracted next step would be:
     suggested_title:         "Send the sector benchmark"
     suggested_activity_type: "EMAIL"
     source_quote:            "My team loses 15 hours per week on manual reporting,
                               it's untenable."        <- JUSTIFICATION

   The following would be INCORRECT:
     source_quote:            "I can send you a sector benchmark tomorrow."
                                                      <- verbatim of the act of
                                                         proposing, NOT the
                                                         justification

7. NEVER choose, name or reference an existing activity to link the next
   step to: the open activities of the DECISION CYCLE context are
   information only; the server proposes the link. When an open activity
   already covers an action of the conversation, still emit that next
   step.

8. If NO next-step evidence is present anywhere in the transcript, return
   exactly: {{"signals": []}}

LANGUAGE
Write every free text -- `suggested_title`, `suggested_objective`,
`suggested_topics`, `suggested_success_criterion` -- in the language of the
transcript. The examples of this prompt are in English: transpose them,
never copy their language. `source_quote` and `suggested_date_text` stay
verbatim.

DATES
{RELATIVE_DATE_RULE}
`suggested_due_date` is a YYYY-MM-DD date ONLY when the transcript commits
to a timeframe ("by Thursday", "within ten days", "before the end of the
quarter") AND you can compute the actual date unambiguously; when in doubt,
null -- the rep picks a date at validation. Never invent a date.
`suggested_date_text` is the date AS SAID in the transcript, verbatim in
its language ("" when no date is said); keep it even when
`suggested_due_date` is null.

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
