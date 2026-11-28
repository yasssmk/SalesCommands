# app_modules/ai_pipelines/prompts/prep_call/system_v2_3.py
"""
System prompt v2.3 of the Game Plan — sprint 2 Game Plan, G13g (PO decision
of 28/11 on the rhetoric).

ethos / pathos / logos are not forbidden: they are INTERNAL. v2.3 makes the
frame explicit in the prompt as a REASONING tool — for each participant and
each section, the right lever (ethos = credibility from the input's proof;
pathos, measured = what the client expressed; logos = the input's facts and
figures), BAC, the rhetorical pivots to adapt, the adjustments to the deal,
one dominant lever per section — so the plan is well thought and lands: the
right line, at the right moment, to the right person. The OUTPUT stays plain
sales language, said as is in the meeting (PLAIN_LANGUAGE_RULE).

Every v2.2 rule stays (the « closer », sober closing; lines of at most
PREP_CALL_LINE_MAX_WORDS words; nothing invented; no invented slot). The
schema does not change. v2.2 is kept, unchanged (system_v2_2.py).
"""

from app_modules.ai_pipelines.services.prep_call.rhetoric_guide import (
    PLAIN_LANGUAGE_RULE,
    RHETORIC_ADJUSTMENTS,
    RHETORIC_LEVERS,
    RHETORIC_MIX,
    RHETORIC_PIVOTS,
)

from ..output_language import OUTPUT_LANGUAGE_RULE
from .system_v2 import MESSAGE_LANGUAGE_RULE, _MESSAGE_INTRO, _PLAN_INTRO, _bullets, _system_prompt
from .system_v2_2 import _MESSAGE_RULES, _PLAN_RULES


SYSTEM_PROMPT_VERSION = 'v2.3'

REASONING_FRAME = f"""\
HOW YOU THINK EACH SECTION — an INTERNAL frame: use it to reason, never write it.
For each participant and each section, choose the right lever — the right
line, at the right moment, for the right person:
{_bullets(RHETORIC_LEVERS)}

Rhetorical pivots — adapt them, never follow them to the letter:
{_bullets(RHETORIC_PIVOTS)}

Adapt to the deal:
{_bullets(RHETORIC_ADJUSTMENTS)}

{RHETORIC_MIX}"""

SYSTEM_PROMPT = _system_prompt(
    _PLAN_INTRO, OUTPUT_LANGUAGE_RULE, (*_PLAN_RULES, PLAIN_LANGUAGE_RULE), REASONING_FRAME,
)
MESSAGE_SYSTEM_PROMPT = _system_prompt(
    _MESSAGE_INTRO, MESSAGE_LANGUAGE_RULE, (*_MESSAGE_RULES, PLAIN_LANGUAGE_RULE), REASONING_FRAME,
)
