# app_modules/ai_pipelines/prompts/deal_health/diagnostic_v1.py
"""
Request layer for the deal-health diagnostic pipeline (v1).

Renders the validated signals grouped by type as evidence, then
specifies the output JSON schema and emission rules.
"""

import json

__all__ = ['DIAGNOSTIC_PROMPT_VERSION', 'build_diagnostic_request']

DIAGNOSTIC_PROMPT_VERSION = 'v1'


# -- Output schema documentation (embedded in the prompt) --
_OUTPUT_SCHEMA = """\
OUTPUT SCHEMA — return EXACTLY this JSON structure:

{
  "global_reading": "<strategic reading of deal maturity, evidence-based, 2-4 sentences>",
  "dimensions": [
    {"key": "problem_recognized", "status": "<S>", "evidence": "<supporting quotes or signals, or empty string>", "missing": "<what is not yet captured, or empty string>"},
    {"key": "felt_pain", "status": "<S>", "evidence": "<...>", "missing": "<...>"},
    {"key": "impact_understood", "status": "<S>", "evidence": "<...>", "missing": "<...>"},
    {"key": "desired_gain", "status": "<S>", "evidence": "<...>", "missing": "<...>"},
    {"key": "urgency", "status": "<S>", "evidence": "<...>", "missing": "<...>"},
    {"key": "willingness_to_act", "status": "<S>", "evidence": "<...>", "missing": "<...>"},
    {"key": "solution_trust", "status": "<S>", "evidence": "<...>", "missing": "<...>"}
  ],
  "discovery_gaps": [
    {
      "kind": "qualification | procedural",
      "dimension": "<dimension key or general area>",
      "public_text": "<neutral description of what is not yet captured>",
      "suggested_questions": ["<question 1>", "<question 2>"],
      "related_theme": "<optional: canonical_key or theme label>",
      "related_actor": "<optional: department or role>"
    }
  ],
  "levers": {
    "desires": [{"summary": "<...>", "theme": "<optional canonical_key>"}],
    "value": [{"summary": "<...>", "theme": "<optional canonical_key>"}],
    "cost": [{"summary": "<...>", "actor": "<optional contact/department>"}],
    "constraints": [{"summary": "<...>", "rigidity": "<optional: FIRM or FLEXIBLE>", "is_metric": <optional boolean>}]
  },
  "themes": [{"label": "<thematic label>", "summary": "<short interpretive reading>"}],
  "evidence_scope": {"validated_signals_count": <int>, "note": "Based on captured evidence."}
}

STATUS values (S): "confirmed", "suggested", "unclear", "missing_evidence", "contradictory"
  - "confirmed": explicit proof in source quotes
  - "suggested": indirect evidence pointing in this direction
  - "unclear": evidence exists but is ambiguous or insufficient
  - "missing_evidence": no evidence captured — NOT "weak" or "absent"
  - "contradictory": conflicting evidence found

DIMENSIONS must appear in EXACTLY this order with EXACTLY these 7 keys.
"""

_EMISSION_RULES = """\
EMISSION RULES:

1. DIMENSIONS: Assess each of the 7 dimensions based solely on the
   signals and source quotes provided. If no signal or quote relates
   to a dimension, status MUST be "missing_evidence".

2. DISCOVERY GAPS: Generate gaps for dimensions with status
   "missing_evidence" or "unclear". Two kinds:
   - "qualification": a business topic not yet explored (pain depth,
     urgency proof, impact quantification).
   - "procedural": a process or governance aspect not yet clarified
     (validation steps, decision timeline, approval authority).
   Tone: neutral. Describe what is not captured, never blame anyone.

3. LEVERS: Derive from signal types:
   - desires <- Objective signals (what they want to achieve)
   - value <- Pain signals + Impact signals (the problem and its proof)
   - cost <- Blocker signals (resistances, objections, human friction)
   - constraints <- Constraint signals (decision criteria, rules, metrics)
   Prioritize by strength of evidence. Include only levers backed by
   at least one validated signal.

4. THEMES: Provide a SHORT interpretive reading per thematic cluster
   (not an exhaustive listing). Themes synthesize across signal types.

5. EVIDENCE SCOPE: Set validated_signals_count to the actual count of
   signals provided. The note is always "Based on captured evidence."

6. Return ONLY the JSON object. No prose, no fences, no commentary.
"""


def build_diagnostic_request(pack):
    """
    Render the request layer: signals as evidence + output schema.

    Args:
        pack: dict returned by DealHealthEvidenceBuilder.build().

    Returns:
        str: the request prompt for the LLM.
    """
    sections = ["TASK: Produce a deal-health diagnostic for this deal.\n"]

    # -- Signals grouped by type --
    signals = pack.get('signals', {})
    total_count = 0

    for signal_type, signal_list in signals.items():
        if not signal_list:
            continue
        total_count += len(signal_list)
        sections.append(f"--- {signal_type.upper()} SIGNALS ({len(signal_list)}) ---")
        for sig in signal_list:
            sections.append(_format_signal(signal_type, sig))
        sections.append('')

    if total_count == 0:
        sections.append(
            "NO VALIDATED SIGNALS PROVIDED.\n"
            "Set all dimension statuses to \"missing_evidence\" and generate "
            "discovery gaps for all 7 dimensions.\n"
        )

    sections.append(_OUTPUT_SCHEMA)
    sections.append(_EMISSION_RULES)

    return '\n'.join(sections)


def _format_signal(signal_type, sig):
    """Format a single signal dict for prompt rendering."""
    lines = []

    summary = sig.get('summary', '')
    quote = sig.get('source_quote', '')

    lines.append(f"  [{sig.get('canonical_key') or signal_type}]")
    if summary:
        lines.append(f"    Summary: {summary}")
    if quote:
        lines.append(f"    Source quote: \"{quote}\"")

    dept = sig.get('target_department')
    if dept:
        lines.append(f"    Department: {dept}")

    scope = sig.get('scope_level')
    if scope:
        lines.append(f"    Scope: {scope}")

    # Type-specific fields
    if signal_type == 'techstack':
        catalog = sig.get('catalog_name')
        if catalog:
            lines.append(f"    Tool: {catalog}")
        if sig.get('is_competitor'):
            lines.append("    Competitor: yes")
        if sig.get('on_deal'):
            lines.append("    Evaluated on this deal: yes")

    if signal_type == 'blocker':
        actor = sig.get('contact_name')
        if actor:
            lines.append(f"    Actor: {actor}")

    if signal_type == 'constraint':
        rigidity = sig.get('rigidity')
        if rigidity:
            lines.append(f"    Rigidity: {rigidity}")

    if signal_type == 'people':
        role = sig.get('role')
        influence = sig.get('influence')
        if role:
            lines.append(f"    Role: {role}")
        if influence:
            lines.append(f"    Influence: {influence}")

    return '\n'.join(lines)
