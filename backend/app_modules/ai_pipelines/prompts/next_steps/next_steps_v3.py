# app_modules/ai_pipelines/prompts/next_steps/next_steps_v3.py
"""
Request layer for Next-Step signal extraction (v3).

v3 = v2 (next_steps_v2.py, measured by the PO run out/20261023-125420 and
kept unchanged) + ONE rule in its DATES paragraph, PERIOD_DATE_RULE (PO):
a PERIOD said for a deadline ("next week", "end of the month", "in January")
resolves to the LAST BUSINESS DAY of that period, from the Conversation date
-- the application of the locked PO rule "end of the year + meeting date ->
12/31"; `suggested_date_text` keeps the text as said.

The v3 text is BUILT from the v2 one -- the rule inserted right after the
"Never invent a date." line of DATES -- so the two can only differ by that
rule (tests/ai_pipelines/test_next_steps_prompt_v3.py). The response schema
is v2's, unchanged. The worked example (2031) comes from no test transcript.
"""

from . import next_steps_v2 as _v2


__all__ = [
    'NEXT_STEPS_PROMPT_VERSION',
    'NEXT_STEPS_RESPONSE_SCHEMA',
    'PERIOD_DATE_RULE',
    'build_next_steps_request',
]


NEXT_STEPS_PROMPT_VERSION = 'v3'

# Unchanged from v2.
NEXT_STEPS_RESPONSE_SCHEMA = _v2.NEXT_STEPS_RESPONSE_SCHEMA

PERIOD_DATE_RULE = '''A PERIOD said for a deadline ("next week", "end of the month", "in January")
resolves to the LAST BUSINESS DAY of that period, counted from the
"Conversation date". EXAMPLE, Conversation date 2031-03-05 (a Wednesday):
"next week" -> 2031-03-14 (Friday); "by the end of the month" -> 2031-03-31
(Monday); "in May" -> 2031-05-30 (Friday); "by the end of the year" ->
2031-12-31 (Wednesday). `suggested_date_text` keeps the period as said
("next week").
'''

# The v2 DATES line the rule follows.
_ANCHOR = 'null -- the rep picks a date at validation. Never invent a date.\n'
# Rendered in place of the transcript, so a transcript can never move the rule.
_SENTINEL = '\x00TRANSCRIPT\x00'


def _template():
    text = _v2.build_next_steps_request(_SENTINEL)
    if text.count(_ANCHOR) != 1:
        raise ImportError('next_steps v3: the v2 DATES anchor is not found exactly once.')
    return text.replace(_ANCHOR, _ANCHOR + PERIOD_DATE_RULE)


_TEMPLATE = _template()


def build_next_steps_request(transcript):
    """The v3 request layer: v2's, with PERIOD_DATE_RULE in DATES."""
    return _TEMPLATE.replace(_SENTINEL, transcript)
