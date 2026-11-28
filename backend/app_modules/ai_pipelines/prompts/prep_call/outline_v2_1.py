# app_modules/ai_pipelines/prompts/prep_call/outline_v2_1.py
"""
Request layer v2.1 of the Game Plan — sprint 2 Game Plan, G13f (PO decisions
of 28/11). outline_v2.py is kept unchanged.

The SAME keys as v2 (PREP_CALL_OUTLINE_SCHEMA): no migration, the v2
snapshots stay readable. What changes is what the fields mean, said in the
field rules and in the schema's descriptions:
  * closing — the next step is the next logical step of the client's buying
    process (the one that validates the current step); `when` is the moment
    IN the conversation to ask for it (never a date, a time or a duration);
    `keep_control` is the agreement to get and to lock in before the end of
    the conversation;
  * opening.time — confirm the time the person has (a duration only when the
    input gives one);
  * every item one short line, at most PREP_CALL_LINE_MAX_WORDS words, opening
    on an action verb; the context 2 to 3 sentences.
"""

import copy

from app_modules.ai_pipelines.constants import (
    PREP_CALL_ARGUMENTS_MAX,
    PREP_CALL_LINE_MAX_WORDS,
    PREP_CALL_PLAN_LABELS,
)

from .outline_v2 import PREP_CALL_OUTLINE_SCHEMA as _V2_SCHEMA
from .outline_v2 import TASK_HEADER


__all__ = [
    'OUTLINE_PROMPT_VERSION',
    'PREP_CALL_OUTLINE_SCHEMA',
    'TASK_HEADER',
    'build_outline_request',
]

OUTLINE_PROMPT_VERSION = 'v2.1'

_LINE = f'One short line, at most {PREP_CALL_LINE_MAX_WORDS} words, opening on an action verb.'

_DESCRIPTIONS = {
    ('opening', 'time'): 'Confirm the time the person has. No invented duration.',
    ('closing', 'next_step'): ('The next logical step of their buying process, the one that '
                               'validates the current step. No date, time or duration.'),
    ('closing', 'with_whom'): 'Who must agree to it (first names or roles).',
    ('closing', 'when'): ('The moment in this conversation to ask for it (e.g. after the recap). '
                          'Never a date, a time or a duration.'),
    ('closing', 'keep_control'): ('The agreement to get on the next step, locked in before the end '
                                  'of the conversation.'),
}


def _with_descriptions(schema):
    """The v2 schema, the same keys, with the v2.1 descriptions."""
    schema = copy.deepcopy(schema)
    schema['name'] = 'prep_call_game_plan_v2_1'
    properties = schema['schema']['properties']
    for (section, field), description in _DESCRIPTIONS.items():
        properties[section]['properties'][field] = {
            **properties[section]['properties'][field], 'description': f'{description} {_LINE}',
        }
    properties['context'] = {**properties['context'], 'description': '2 to 3 short sentences.'}
    return schema


PREP_CALL_OUTLINE_SCHEMA = _with_descriptions(_V2_SCHEMA)


_FIELD_RULES = f"""\
FIELD RULES (every item is ONE short line, at most {PREP_CALL_LINE_MAX_WORDS} words, opening on an
action verb — the rep reads it in the middle of the meeting):

1. context: 2 to 3 short sentences — who, where the deal or the sequence
   stands, what is at stake in THIS conversation.

2. objective.plans: plan A (what you aim for), then B and C as fallbacks —
   {len(PREP_CALL_PLAN_LABELS)} at most, labels {" / ".join(PREP_CALL_PLAN_LABELS)} in that order. Each with
   an observable success_criteria.

3. client_expectations: what THEY expect from this conversation, from the
   input (the activity's agenda, the previous conversations). [] if
   nothing in the input says it.

4. opening: the objective you announce; time: confirm the time the person
   has (a duration only when the input gives one); their agenda (ask for
   it); our agenda; the outcome you propose for the end.

5. discovery.missing_info: what is still unknown and blocks the deal, each
   with the exact question to ask. discovery.conviction: for needs and
   urgency, credibility, fit and value — your reading from the input, and
   the question that moves it.

6. argumentation: for each participant (ref = their label, exactly as
   given in PARTICIPANTS), at most {PREP_CALL_ARGUMENTS_MAX} arguments, the strongest first:
   benefit (for them), advantage (versus their current way), feature (what
   makes it possible — only a capability the input gives).

7. closing: next_step — the next logical step of their buying process, the
   one that validates the current step (its criteria, the missing
   information); with_whom — who must agree to it; when — the moment in
   this conversation to ask for it; keep_control — the agreement to get and
   to lock in before the end of the conversation ("Get agreement on the
   security review and book it before hanging up"). No date, no time, no
   duration, no detailed content of the next meeting.

8. product_pitch: one short pitch per product of the deal, from its
   description and value proposition. [] without a product.

9. participants: one entry per participant (ref = their label, exactly as
   given), with the angle to take with that person.

10. campaign_diagnostic: ONLY when a CAMPAIGN block is given — your reading
    of the sequence so far and the next move. Otherwise null.
"""


def build_outline_request(input_pack):
    """
    The request layer v2.1: the task, the field rules. The schema itself is
    sent as the strict response schema (PREP_CALL_OUTLINE_SCHEMA).
    """
    sections = [TASK_HEADER]
    activity = input_pack.get('activity') or {}
    if activity.get('type'):
        sections.append(f"Conversation: {activity['type']} on {activity.get('date') or 'unscheduled'}.")
    sections.append(_FIELD_RULES)
    sections.append('Return ONLY the JSON object of the response schema.')
    return '\n\n'.join(sections)
