# app_modules/ai_pipelines/prompts/prep_call/system_v2_2.py
"""
System prompt v2.2 of the Game Plan — sprint 2 Game Plan, G13f (PO decisions
of 28/11, before the UI).

v2.2 keeps every rule of v2.1 (prompts/prep_call/system_v2_1.py, unchanged —
the no-invented-slot rule included) with:
  * decision 1 — the next step is the next logical step of the client's
    buying process (the one that validates the current step); the closing
    gets the person's agreement on it and locks it in during the
    conversation; no date, time, duration nor detailed content of the next
    meeting (it REPLACES v2's « two date options » next-step rule); the
    opening confirms the time the person has, never an invented duration;
  * decision 2 (the plan only) — readable in the middle of a meeting: each
    item one short line, at most constants.PREP_CALL_LINE_MAX_WORDS words,
    opening on an action verb; the context 2 to 3 sentences;
  * the message proposes to agree on a next exchange, with no invented
    precision.
"""

from app_modules.ai_pipelines.constants import PREP_CALL_LINE_MAX_WORDS
from app_modules.ai_pipelines.services.prep_call.rhetoric_guide import (
    MESSAGE_NEXT_EXCHANGE_RULE,
    NEXT_STEP_RULE,
    OPENING_TIME_RULE,
    readability_rule,
)

from ..output_language import OUTPUT_LANGUAGE_RULE
from .system_v2 import GUARDRAILS, MESSAGE_LANGUAGE_RULE, _MESSAGE_INTRO, _PLAN_INTRO, _system_prompt
from .system_v2_1 import _RULES_V2_1  # noqa: F401 — the v2.1 rules, unchanged


SYSTEM_PROMPT_VERSION = 'v2.2'

# v2's next-step rule (« … two date options … »), replaced in v2.2.
_V2_NEXT_STEP_RULE = next(rule for rule in GUARDRAILS if rule.startswith('THE NEXT STEP IS A COMMITMENT'))

_COMMON = tuple(NEXT_STEP_RULE if rule is _V2_NEXT_STEP_RULE else rule for rule in _RULES_V2_1)

_PLAN_RULES = (*_COMMON, OPENING_TIME_RULE, readability_rule(PREP_CALL_LINE_MAX_WORDS))
_MESSAGE_RULES = (*_COMMON, MESSAGE_NEXT_EXCHANGE_RULE)

SYSTEM_PROMPT = _system_prompt(_PLAN_INTRO, OUTPUT_LANGUAGE_RULE, _PLAN_RULES)
MESSAGE_SYSTEM_PROMPT = _system_prompt(_MESSAGE_INTRO, MESSAGE_LANGUAGE_RULE, _MESSAGE_RULES)
