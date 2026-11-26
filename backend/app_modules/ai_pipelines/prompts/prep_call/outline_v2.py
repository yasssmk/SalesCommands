# app_modules/ai_pipelines/prompts/prep_call/outline_v2.py
"""
Request layer v2 of the Game Plan (prep call) — sprint 2 Game Plan, G10.

The task, the field rules and the strict Structured Outputs schema
PREP_CALL_OUTLINE_SCHEMA (the deal health's pattern,
prompts/deal_health/diagnostic_v2.py: every field required, no other field).

The outline follows the 7 sections of the vision doc:
  1. context;
  2. objective — plans A / B / C (3 at most);
  3. client_expectations;
  4. opening — objective, time, the client's agenda, our agenda, the
     expected outcome;
  5. discovery — the missing information + the reading of the conviction
     (needs and urgency, credibility, fit and value);
  6. argumentation — the top 3 arguments per participant, benefit /
     advantage / feature;
  7. closing — the next step accepted, and how we keep control;
plus product_pitch, participants [{ref, angle}] and campaign_diagnostic
(null except for a campaign activity outside a decision cycle).

Validated server side by services/prep_call/plan_validator.py (refs against
the activity's roster, labels, last names, the bounds).
"""

from app_modules.ai_pipelines.constants import (
    PREP_CALL_ARGUMENTS_MAX,
    PREP_CALL_PLAN_LABELS,
)

from ..deal_health.diagnostic_v2 import _STR, _STRS, _arr, _obj  # the strict-schema helpers


__all__ = [
    'OUTLINE_PROMPT_VERSION',
    'PREP_CALL_OUTLINE_SCHEMA',
    'TASK_HEADER',
    'build_outline_request',
]

OUTLINE_PROMPT_VERSION = 'v2'

TASK_HEADER = 'TASK: Produce the Game Plan of the upcoming conversation.'


# =============================================================================
# STRICT RESPONSE SCHEMA
# =============================================================================

def _nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


_READING = _obj({'reading': _STR, 'question': _STR})

PREP_CALL_OUTLINE_SCHEMA = {
    'name': 'prep_call_game_plan_v2',
    'schema': _obj({
        # 1. context
        'context': _STR,
        # 2. objective — plans A / B / C
        'objective': _obj({
            'plans': _arr(_obj({
                'label': {'type': 'string', 'enum': list(PREP_CALL_PLAN_LABELS)},
                'goal': _STR,
                'success_criteria': _STR,
            })),
        }),
        # 3. the client's expectations
        'client_expectations': _STRS,
        # 4. opening
        'opening': _obj({
            'objective': _STR,
            'time': _STR,
            'client_agenda': _STR,
            'our_agenda': _STR,
            'expected_outcome': _STR,
        }),
        # 5. discovery
        'discovery': _obj({
            'missing_info': _arr(_obj({'item': _STR, 'question': _STR})),
            'conviction': _obj({
                'needs_and_urgency': _READING,
                'credibility': _READING,
                'fit_and_value': _READING,
            }),
        }),
        # 6. argumentation — per participant
        'argumentation': _arr(_obj({
            'ref': _STR,
            'arguments': _arr(_obj({'benefit': _STR, 'advantage': _STR, 'feature': _STR})),
        })),
        # 7. closing
        'closing': _obj({
            'next_step': _STR,
            'with_whom': _STR,
            'when': _STR,
            'keep_control': _STR,
        }),
        'product_pitch': _arr(_obj({'product': _STR, 'pitch': _STR})),
        'participants': _arr(_obj({'ref': _STR, 'angle': _STR})),
        'campaign_diagnostic': _nullable(_obj({'reading': _STR, 'next_move': _STR})),
    }),
}


# =============================================================================
# REQUEST
# =============================================================================

_FIELD_RULES = f"""\
FIELD RULES:

1. context: 2-4 sentences — who, where the deal or the sequence stands,
   what is at stake in THIS conversation.

2. objective.plans: plan A (what you aim for), then B and C as fallbacks —
   {len(PREP_CALL_PLAN_LABELS)} at most, labels {" / ".join(PREP_CALL_PLAN_LABELS)} in that order. Each with
   an observable success_criteria.

3. client_expectations: what THEY expect from this conversation, from the
   input (the activity's agenda, the previous conversations). [] if
   nothing in the input says it.

4. opening: the objective you announce, the time you ask for, their
   agenda (ask for it), our agenda, the outcome you propose for the end.

5. discovery.missing_info: what is still unknown and blocks the deal, each
   with the exact question to ask. discovery.conviction: for needs and
   urgency, credibility, fit and value — your reading from the input, and
   the question that moves it.

6. argumentation: for each participant (ref = their label, exactly as
   given in PARTICIPANTS), at most {PREP_CALL_ARGUMENTS_MAX} arguments, the strongest first:
   benefit (for them), advantage (versus their current way), feature (what
   makes it possible — only a capability the input gives).

7. closing: the next step to get accepted during the conversation, with
   whom, when (two date options), and keep_control: what the seller sends
   or books right after, so the seller keeps the lead.

8. product_pitch: one short pitch per product of the deal, from its
   description and value proposition. [] without a product.

9. participants: one entry per participant (ref = their label, exactly as
   given), with the angle to take with that person.

10. campaign_diagnostic: ONLY when a CAMPAIGN block is given — your reading
    of the sequence so far and the next move. Otherwise null.
"""


def build_outline_request(input_pack):
    """
    The request layer v2: the task, the field rules. The schema itself is
    sent as the strict response schema (PREP_CALL_OUTLINE_SCHEMA).

    Args:
        input_pack: dict returned by PrepInputPackAssembler.build().

    Returns:
        str
    """
    sections = [TASK_HEADER]
    activity = input_pack.get('activity') or {}
    if activity.get('type'):
        sections.append(f"Conversation: {activity['type']} on {activity.get('date') or 'unscheduled'}.")
    sections.append(_FIELD_RULES)
    sections.append('Return ONLY the JSON object of the response schema.')
    return '\n\n'.join(sections)
