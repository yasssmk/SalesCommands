# app_modules/ai_pipelines/prompts/prep_call/system_v2_1.py
"""
System prompt v2.1 of the Game Plan — sprint 2 Game Plan, G13d (PO decision
after the evaluation: in email_fr_profile the model wrote « Je vous envoie
une invitation de 30 minutes pour mardi 1er décembre à 10 h » — a slot and
an action it invented).

v2.1 keeps every rule of v2 (prompts/prep_call/system_v2.py, unchanged) and
adds ONE hard rule, shared by the plan AND the message (the same builder):
never a precise meeting date or time that is not in the input, never a
claimed action; an open window (« Tuesday or Wednesday? », « early next
week ») or the placeholder PREP_CALL_SLOT_PLACEHOLDERS in the language of
the text. A meeting duration stays allowed; a date given by the input (a
known board date) too.
"""

from app_modules.ai_pipelines.constants import PREP_CALL_SLOT_PLACEHOLDERS

from ..output_language import OUTPUT_LANGUAGE_RULE
from .system_v2 import (  # noqa: F401 — the v2 builder and texts, unchanged
    MESSAGE_LANGUAGE_RULE,
    _MESSAGE_INTRO,
    _PLAN_INTRO,
    _RULES,
    _system_prompt,
    GUARDRAILS,
)


SYSTEM_PROMPT_VERSION = 'v2.1'

_PLACEHOLDERS = ', '.join(
    f'{language} {label}' for language, label in PREP_CALL_SLOT_PLACEHOLDERS.items()
)

SLOT_RULE = (
    'NO INVENTED SLOT, NO CLAIMED ACTION. Never write a precise meeting date '
    'or time that is not in the input, and never claim an action was done or '
    'is being done (an invitation sent, a meeting booked, a slot blocked). '
    'Propose an open window ("Tuesday or Wednesday?", "early next week"), or '
    f'leave the placeholder {PREP_CALL_SLOT_PLACEHOLDERS["en"]} for the rep to '
    f'fill, written in the language of the text ({_PLACEHOLDERS}). A meeting '
    'duration is fine; a date the input gives is fine.'
)

# The v2 rules, the slot rule right after the guard rails.
_RULES_V2_1 = (*GUARDRAILS, SLOT_RULE, *_RULES[len(GUARDRAILS):])

SYSTEM_PROMPT = _system_prompt(_PLAN_INTRO, OUTPUT_LANGUAGE_RULE, _RULES_V2_1)
MESSAGE_SYSTEM_PROMPT = _system_prompt(_MESSAGE_INTRO, MESSAGE_LANGUAGE_RULE, _RULES_V2_1)
