# app_modules/ai_pipelines/prompts/transcript_signals/people_v1.py
"""
Request layer for People signal extraction (UX Activity, People S1;
v2 -- People S1-bis: unlisted prospect speakers + explicit seller side;
v3 -- People S6: department strictly from what is said of the person).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'people') -- session grounding (the
    participants, each prefixed with its reference "P1", "P2", ... -- the
    closed list `participant_ref` picks from), the People taxonomy (role,
    influence, department) and the persons ALREADY identified in the deal,
    which must not be emitted again.
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of person observations. Each observation has these fields:

    participant_ref  string|null -- reference ("P1", ...) when the person is
                                    a listed participant, else null
    full_name        string|null -- the name as stated, null when not named
    role             string      -- one PeopleRole code
    influence        string|null -- one InfluenceLevel code (HIGH / MEDIUM /
                                    LOW), null when it cannot be assessed
    department       string|null -- one StandardDepartment name, else null
    notes            string      -- one short sentence justifying the role
    source_quote     string      -- verbatim utterance the role rests on
    confidence       float       -- LLM self-declared, in [0.0, 1.0]
    is_inferred      boolean     -- LLM self-declared

Empty result is represented by {"signals": []}.

Persistence contract
--------------------
TranscriptSignalExtractor applies the confidence floor of the safety
filter; the is_inferred drop is NOT applied to this stage
(QualificationSignalsPipeline.DROP_INFERRED_EXEMPT_STAGES): a Champion is
rarely stated, an inferred role is a legitimate observation the rep
validates. Each surviving observation maps to a new PeopleSignal row:

    LLM-emitted field   ->  PeopleSignal column
    -----------------       -----------------------------------------------
    participant_ref     ->  target_contact (resolved participant, else None)
    full_name           ->  full_name (DERIVED from the contact when the
                            participant resolves: first + last name)
    role                ->  role (out-of-list value -> signal dropped)
    influence           ->  influence (invalid -> None)
    department          ->  target_department (the contact's standard
                            department when set, else the resolved name)
    notes               ->  notes
    source_quote        ->  source_quote
    confidence          ->  confidence
    is_inferred         ->  is_inferred

Fields filled by the service: status PENDING, source LLM_EXTRACTED,
source_activity, account; decision_cycle / campaign are propagated from the
activity by SignalManager. A person with no contact, no name and no
department after resolution is dropped (PeopleSignal identity invariant).

Versioning
----------
PEOPLE_PROMPT_VERSION is captured in AIPipelineRun.prompt_versions.
"""

from app_modules.ai_pipelines.services.participant_refs import (
    PARTICIPANT_REF_PREFIX,
    format_participant_ref,
)
from app_modules.core_modules.models import StandardDepartment
from app_modules.signals.constants import PeopleRole


__all__ = ['PEOPLE_PROMPT_VERSION', 'build_people_request']


# v2 (People S1-bis): a prospect who SPEAKS without being a listed contact is
# extracted (participant_ref null, name from the speaker label); the seller
# side is defined by who presents / sells the solution. File name unchanged.
# v3 (People S6): `department` strictly from what the transcript says about
# the person; never inferred from other sources; null otherwise.
PEOPLE_PROMPT_VERSION = 'v3'

# Reference shapes rendered in the prompt, derived from the single
# definition in participant_refs.py ("P<n>", "P1").
_REF_SHAPE = f'{PARTICIPANT_REF_PREFIX}<n>'
_FIRST_REF = format_participant_ref(0)

# Codes / names quoted in the worked examples, taken from the enums.
_ECONOMIC_BUYER = PeopleRole.ECONOMIC_BUYER.value
_DECISION_MAKER = PeopleRole.DECISION_MAKER.value
_ROLE_PROCUREMENT = PeopleRole.PROCUREMENT.value
_DEPT_GENERAL_MANAGEMENT = StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT.value
_DEPT_FINANCE = StandardDepartment.DepartmentChoices.FINANCE.value
_DEPT_PROCUREMENT = StandardDepartment.DepartmentChoices.PROCUREMENT.value
_DEPT_SALES = StandardDepartment.DepartmentChoices.SALES.value


def build_people_request(transcript):
    """
    Build the request layer for one People extraction sub-call.

    Args:
        transcript: str -- the full transcript text pasted by the rep,
            sent verbatim (same data-exposure contract as the other stages).

    Returns:
        str: A ready-to-concatenate request block.
    """
    return f"""TASK
Extract PEOPLE signals from the SALES TRANSCRIPT below.

A people signal records a person on the PROSPECT side who carries weight
in the buying decision and/or embodies a step the deal must clear (an
approval, a sign-off, a validation, a meeting to hold with them).

WHO TO EXTRACT
- Persons PRESENT in the conversation: every PROSPECT-side person who SPEAKS
  in the transcript (a speaker label such as "Claire Dubois: ...") OR who is
  listed as a prospect contact in the SESSION CONTEXT.
- A prospect speaker NOT listed in the SESSION CONTEXT is STILL extracted:
  participant_ref = null and full_name = the name exactly as written in the
  speaker label.
- Persons only CITED but absent ("our CFO Marc will decide").
- A cited person without a name ("our CFO") is STILL extracted:
  full_name = null, with the department when it can be identified.
- Examples:
  * "The final decision maker is the CEO, who has to approve the quote"
    -> the CEO, role "{_ECONOMIC_BUYER}", department "{_DEPT_GENERAL_MANAGEMENT}".
  * "Before signing we will need a meeting with the CFO"
    -> the CFO, department "{_DEPT_FINANCE}", with the role the transcript
    supports (e.g. "{_DECISION_MAKER}"). The meeting itself is captured by
    another sub-call -- emit only the PERSON here.

DO NOT emit
- Anyone from the SELLER organization named in the SESSION CONTEXT (the
  seller's account executive, colleagues, solution engineers, managers):
  prospect side ONLY. The person who presents or sells the solution, and
  their colleagues, are on the SELLER side even when their organization is
  not named next to their name.
- Any person listed under PEOPLE ALREADY IDENTIFIED IN THIS DEAL in the
  context: they already have their role -- never emit them again.
- A person with no observable weight in the decision and no step to clear.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "participant_ref": <"{_REF_SHAPE}" reference of the listed participant, or null -- see ATTRIBUTION RULES>,
      "full_name":       <the person's name exactly as stated in the transcript, or null when the person is not named>,
      "role":            "<EXACTLY ONE role code from the context list>",
      "influence":       <one influence code from the context list, or null>,
      "department":      <one department value from the context list, exact string, or null>,
      "notes":           "<one short sentence, in your own words, explaining why this person holds this role>",
      "source_quote":    "<VERBATIM utterance the role rests on>",
      "confidence":      <float in [0.0, 1.0], self-declared per the EPISTEMIC FILTER in the system prompt>,
      "is_inferred":     <boolean, true when the role is inferred rather than directly stated>
    }}
  ]
}}

EMISSION RULES
- ONE entry per person. A person cited several times, or showing several
  roles, gets a SINGLE entry carrying the most decision-relevant role.
- `role` MUST be one code of the role list. An INFERRED role is allowed (a
  champion is rarely named as such): set `is_inferred` to true and calibrate
  `confidence` honestly. Never emit a role on a weak guess.
- `influence` and `department` MAY be null. This overrides the system
  prompt's taxonomy rule: a missing influence or department is NEVER a
  reason to omit the person.
- The department "{_DEPT_PROCUREMENT}" is a DEPARTMENT, not the role
  "{_ROLE_PROCUREMENT}": pick each from its own list.
- `department` is the function of THIS person in the prospect's
  organization, taken ONLY from what the transcript says about THIS person
  (their team, their job title, their trade): "head of the key accounts
  team" -> department "{_DEPT_SALES}". NEVER infer it from the company name,
  the meeting title, the prospect's industry, the department of the SPEAKER,
  or the other persons (including those listed under PEOPLE ALREADY
  IDENTIFIED IN THIS DEAL). WHEN NOTHING is said about this person's
  function, set `department` to null -- null is the safe default; never
  fill it with a guess.
- `full_name` is the name as stated; NEVER invent, complete or guess a name.
- `notes` MUST be your own short sentence -- never a copy of the quote.
- `source_quote` MUST be the VERBATIM utterance where the person's role or
  weight appears, exactly as in the transcript, preserving original
  language, punctuation, and casing. Never translate, never paraphrase.
- If NO such person is present anywhere in the transcript, return exactly:
  {{"signals": []}}

ATTRIBUTION RULES (participant_ref)
- The SESSION CONTEXT lists the prospect contacts in this conversation,
  each prefixed with a reference ({_REF_SHAPE}).
- When the person is one of the listed participants, set `participant_ref`
  to that participant's reference (e.g. "{_FIRST_REF}").
- When the person is only cited (absent from the list), or is a prospect
  speaker who is NOT a listed participant, set `participant_ref` to null and
  give the name in `full_name`.
- `participant_ref` MUST be one of the listed references, copied exactly.
  NEVER output a name, an email, a job title, or a reference that is not in
  the list. NEVER invent a reference.

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
