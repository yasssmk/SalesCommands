# app_modules/ai_pipelines/prompts/output_language.py
"""
THE output-language rule of the strategic prompts — written once, read by:
  * the deal-health diagnostic v2.1 (prompts/deal_health/system_v2_1.py,
    its rule 10 — moved here byte for byte, sprint 2 Game Plan G10);
  * the Game Plan v2 (prompts/prep_call/system_v2.py — PO: « the same
    output-language rule as the deal health v2 »).

The text carries no rule number: each prompt puts its own in front of it.
The continuation lines are indented for a two-digit number ("10. ").
"""

OUTPUT_LANGUAGE_RULE = """\
LANGUAGE: Write every text field in ENGLISH, whatever the language of
    the evidence. A stakeholder's communication_language is the language
    they use (a BCP-47 tag such as "fr" or "en-US"), "" when unknown."""
