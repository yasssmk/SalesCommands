# app_modules/ai_pipelines/prompts/transcript_signals/date_rules.py
"""
Prompt fragments on dates, shared by the transcript_signals request layers.

RELATIVE_DATE_RULE -- every relative date is resolved with the "Conversation
date" of the context layer (context.py, session block). Extracted verbatim
from techstack_v1.py (TechStack T4b) so the rendered techstack prompt is
unchanged; reused by objective_v1.py v2 for `target_date` (TD-279 C2).
"""

__all__ = ['RELATIVE_DATE_RULE']


RELATIVE_DATE_RULE = """Every relative date ("this year", "next year", "end of the year", "in June",
"for three years") is resolved with the "Conversation date" given in the
context. When the context says the conversation date is not provided, every
relative date is null."""
