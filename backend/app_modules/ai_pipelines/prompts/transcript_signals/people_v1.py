# app_modules/ai_pipelines/prompts/transcript_signals/people_v1.py
"""
Request layer for People signal extraction (UX Activity, People S1;
v2 -- People S1-bis: unlisted prospect speakers + explicit seller side;
v3 -- People S6: department strictly from what is said of the person;
v4 -- no list of the persons already known in the deal;
v5 -- TD-279: a listed contact is evidence of nothing, attribution only on
evidence about THAT participant;
v6 -- TD-279 B4b: no participant reference, names as written;
v7 -- TD-279 C5: speakers always extracted, role from what is said of them,
seller side = the solution, department from the job title;
v8 -- TD-279 M: role UNKNOWN offered, never guess a role; the answer is
constrained by a strict JSON schema, PEOPLE_RESPONSE_SCHEMA;
v9 -- TD-279 D: job_title as said, department = the function it designates).

This is the per-stage request module of the transcript_signals pipeline
family. It is combined at call time with:
  * system.py        -- universal output / evidence / taxonomy rules.
  * build_context_layer(activity, 'people') -- session grounding (no
    contact list since context v8), the People taxonomy (role, influence,
    department). No list of the persons already known in the deal (removed
    in v4).
The full assembly is performed by PromptBuilder.assemble() in base.py.

Schema (v1)
-----------
The LLM emits one JSON object with a single key `signals` containing an
array of person observations. Each observation has these fields:

    full_name        string|null -- the name as written (speaker label, else
                                    as cited), null when not named
    job_title        string|null -- the job title as said, else null (v9)
    role             string      -- one PeopleRole code (UNKNOWN when nothing
                                    establishes the role, v8)
    influence        string|null -- one InfluenceLevel code (HIGH / MEDIUM /
                                    LOW), null when it cannot be assessed
    department       string|null -- one StandardDepartment name, else null
    notes            string      -- one short sentence justifying the role
    source_quote     string      -- verbatim utterance the role rests on
    confidence       float       -- LLM self-declared, in [0.0, 1.0]
    is_inferred      boolean     -- LLM self-declared

Empty result is represented by {"signals": []}.

Since v8 the provider enforces this shape (Structured Outputs, strict):
PEOPLE_RESPONSE_SCHEMA, its enums built from the SAME enums as the context
taxonomy (PeopleRole, InfluenceLevel, StandardDepartment.DepartmentChoices).

Persistence contract
--------------------
TranscriptSignalExtractor applies the confidence floor of the safety
filter; an inferred role is KEPT (a Champion is rarely stated -- a
legitimate observation the rep validates; since TD-279 C1 no stage drops
is_inferred, PIPELINE_DROP_INFERRED). Each surviving observation maps to a new PeopleSignal row:

    LLM-emitted field   ->  PeopleSignal column
    -----------------       -----------------------------------------------
    full_name           ->  target_contact (linked by the server to a contact
                            registered on the activity, resolve_participant_by_name;
                            ambiguous / none -> None) and full_name (DERIVED
                            from the contact when linked: first + last name)
    role                ->  role (out-of-list value -> signal dropped)
    influence           ->  influence (invalid -> None)
    department          ->  target_department (the contact's standard
                            department when set, else the resolved name,
                            else -- v9 safety net -- the job_title resolved
                            by the same resolver)
    job_title           ->  metadata.job_title
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

from app_modules.core_modules.models import StandardDepartment
from app_modules.signals.constants import InfluenceLevel, PeopleRole


__all__ = ['PEOPLE_PROMPT_VERSION', 'PEOPLE_RESPONSE_SCHEMA', 'build_people_request']


# v2 (People S1-bis): a prospect who SPEAKS without being a listed contact is
# extracted (participant_ref null, name from the speaker label); the seller
# side is defined by who presents / sells the solution. File name unchanged.
# v3 (People S6): `department` strictly from what the transcript says about
# the person; never inferred from other sources; null otherwise.
# v4 (fix people-no-cross-activity-filter P2): the list of the persons already
# identified in the deal is no longer sent, nor its "never emit them again"
# rule -- every activity re-observes its persons.
# v5 (TD-279 B3): a listed contact is extracted ONLY when the transcript shows
# them; participant_ref ONLY on evidence about that participant (a different
# name is never them); never transfer what is said of another named person;
# full_name of a reference entry = the name as written (checked server-side by
# stated_name_matches_contact); deduction allowed, unfounded conclusion not.
# v6 (TD-279 B4b): no participant reference -- participant_ref, the ATTRIBUTION
# RULES and every mention of a participant list are removed; full_name is the
# name as written and the SERVER links it to a registered contact. Patch
# measured by the B2 eval (people_noP) and validated by the PO.
# v7 (TD-279 C5): every prospect SPEAKER is extracted (the weight rule only
# concerns cited persons); a speaker's role rests only on what is said of THEM
# (the NEVER transfer rule applies to the speaker); the seller side is whoever
# presents / sells THE SOLUTION -- a prospect presenting the project internally
# stays prospect; an unnamed cited person's department comes from the job title.
# The two examples inherited from test transcripts (a speaker label, a team
# lead -> Sales) were replaced by neutral ones before any v7 run (C5-bis).
# v8 (TD-279 M): the role list offers UNKNOWN (context v9); when nothing in
# the transcript establishes a person's role -- speaker included -- role is
# UNKNOWN, never a guess (replaces "pick the best-supported role with
# is_inferred"); a role DEDUCED from evidence stays allowed (is_inferred).
# The answer is constrained by PEOPLE_RESPONSE_SCHEMA (strict).
# v9 (TD-279 D): a `job_title` field (the title as said, else null); the
# department of a person whose job title is said is the function that title
# designates -- a deduction from what is SAID (neutral examples: payroll
# manager -> HR, accounts payable clerk -> Finance), the "nothing said ->
# null" rule unchanged otherwise. The cited-unnamed-person examples (HR
# director, logistics manager) gave the department word itself; replaced.
PEOPLE_PROMPT_VERSION = 'v9'

# Codes / names quoted in the worked examples, taken from the enums.
_ECONOMIC_BUYER = PeopleRole.ECONOMIC_BUYER.value
_DECISION_MAKER = PeopleRole.DECISION_MAKER.value
_ROLE_PROCUREMENT = PeopleRole.PROCUREMENT.value
_ROLE_UNKNOWN = PeopleRole.UNKNOWN.value
_DEPT_GENERAL_MANAGEMENT = StandardDepartment.DepartmentChoices.GENERAL_MANAGEMENT.value
_DEPT_HR = StandardDepartment.DepartmentChoices.HR.value
_DEPT_FINANCE = StandardDepartment.DepartmentChoices.FINANCE.value
_DEPT_PROCUREMENT = StandardDepartment.DepartmentChoices.PROCUREMENT.value
_DEPT_SALES = StandardDepartment.DepartmentChoices.SALES.value



def _nullable_enum(enum_values):
    return {'type': ['string', 'null'], 'enum': [*enum_values, None]}


# Strict Structured Outputs schema of the answer (TD-279 M): the exact shape
# of the OUTPUT SCHEMA below -- every field required, no other field,
# nullables typed [..., "null"]. Its enums come from the SAME enums as the
# context taxonomy (context.py, people branch); the department list is a
# static TextChoices enum, no database read.
PEOPLE_RESPONSE_SCHEMA = {
    'name': 'people_signals',
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
                    'required': [
                        'full_name', 'job_title', 'role', 'influence', 'department',
                        'notes', 'source_quote', 'confidence', 'is_inferred',
                    ],
                    'properties': {
                        'full_name':    {'type': ['string', 'null']},
                        'job_title':    {'type': ['string', 'null']},
                        'role':         {'type': 'string', 'enum': list(PeopleRole.values)},
                        'influence':    _nullable_enum(InfluenceLevel.values),
                        'department':   _nullable_enum(
                            StandardDepartment.DepartmentChoices.values),
                        'notes':        {'type': 'string'},
                        'source_quote': {'type': 'string'},
                        'confidence':   {'type': 'number'},
                        'is_inferred':  {'type': 'boolean'},
                    },
                },
            },
        },
    },
}

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
  in the transcript (a speaker label such as "Jordan Lee: ...") is ALWAYS
  extracted -- even when they say they do not decide. The weight rule of
  DO NOT emit never applies to a speaker.
- `full_name` = the person's name exactly as written in the transcript:
  the speaker label for a person who speaks, the name as cited otherwise.
- Persons only CITED but absent ("our CFO Marc will decide").
- A cited person without a name ("our CFO") is STILL extracted:
  full_name = null, `job_title` = the title as said, and the department
  that title designates (see `department` below).
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
  prospect side ONLY. The SELLER side is the person who presents or sells
  THE SOLUTION being offered (the Seller organization of the SESSION
  CONTEXT), and their colleagues, even when their organization is not named
  next to their name. A prospect who presents THE PROJECT internally (to
  their management, to a committee) stays on the PROSPECT side.
- A CITED person (who does not speak) with no observable weight in the
  decision and no step to clear.

OUTPUT SCHEMA
Return a single JSON object with this exact shape:

{{
  "signals": [
    {{
      "full_name":       <the person's name exactly as stated in the transcript, or null when the person is not named>,
      "job_title":       <the person's job title exactly as said in the transcript, or null when no title is said>,
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
- `role` MUST be one code of the role list. A role DEDUCED from evidence in
  the transcript is allowed (a champion is rarely named as such): set
  `is_inferred` to true and calibrate `confidence` honestly.
- When NOTHING in the transcript establishes the person's role, set `role`
  to "{_ROLE_UNKNOWN}" -- NEVER guess a role. With "{_ROLE_UNKNOWN}",
  `is_inferred` is false and `confidence` rates how clearly the transcript
  shows this person taking part in the deal.
- `influence` and `department` MAY be null. This overrides the system
  prompt's taxonomy rule: a missing influence or department is NEVER a
  reason to omit the person.
- The department "{_DEPT_PROCUREMENT}" is a DEPARTMENT, not the role
  "{_ROLE_PROCUREMENT}": pick each from its own list.
- `job_title` = the person's job title exactly as said in the transcript
  (e.g. "our accounts payable clerk"), or null when no title is said.
- `department` is the function of THIS person in the prospect's
  organization, taken ONLY from what the transcript says about THIS person
  (their team, their job title, their trade): "manager of the inside sales
  team" -> department "{_DEPT_SALES}". When the transcript gives the
  person's job title, `department` is the function that title designates --
  a deduction from what is SAID, not a guess: "the payroll manager" ->
  department "{_DEPT_HR}", "our accounts payable clerk" -> department
  "{_DEPT_FINANCE}". NEVER infer it from the company name, the meeting title,
  the prospect's industry, the department of the SPEAKER, or the other
  persons. WHEN NOTHING is said about this person's function (no team, no
  job title, no trade), set `department` to null -- null is the safe
  default; never fill it with a guess.
- `full_name` is the name as stated; NEVER invent, complete or guess a name.
- NEVER transfer to one person what the transcript says about ANOTHER named
  person: "Paul Martin, our head of IT, signs off on security" describes Paul
  Martin only -- never another person, never the speaker.
- The role of a SPEAKER rests ONLY on what the transcript says about THIS
  speaker (what they say about themselves, what others say about them) --
  never on what they say about other persons: the NEVER transfer rule above
  applies to the speaker too. A speaker who says "our managing director will
  sign" does not become the decision maker -- the managing director does.
  When nothing establishes the speaker's role, the role is
  "{_ROLE_UNKNOWN}" (rule above) -- the speaker is still extracted.
- A DEDUCTION from what the transcript says is allowed (e.g. a role implied
  by what a named person decides or does); a conclusion with NO evidence in
  the transcript is not.
- `notes` MUST be your own short sentence -- never a copy of the quote.
- `source_quote` MUST be the VERBATIM utterance where the person's role or
  weight appears, exactly as in the transcript, preserving original
  language, punctuation, and casing. Never translate, never paraphrase.
- If NO such person is present anywhere in the transcript, return exactly:
  {{"signals": []}}

TRANSCRIPT
<<<TRANSCRIPT_START>>>
{transcript}
<<<TRANSCRIPT_END>>>
"""
