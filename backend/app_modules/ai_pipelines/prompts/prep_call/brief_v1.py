# app_modules/ai_pipelines/prompts/prep_call/brief_v1.py
"""
Request layer for the prep-call tactical brief pipeline (v1).

Specifies the brief generation task, discovery gaps from the maturity
snapshot, and the strict output JSON schema.
"""

import json

__all__ = ['BRIEF_PROMPT_VERSION', 'build_brief_request']

BRIEF_PROMPT_VERSION = 'v1'


_OUTPUT_SCHEMA = """\
OUTPUT SCHEMA — return EXACTLY this JSON structure:

{
  "context": "<string: 3-4 sentences situating the call — who, what stage, key stakes>",
  "objectives": [
    {
      "rank": "primary | secondary",
      "summary": "<string: what to achieve>",
      "nature": "ETHOS | VALUE | OBJECTION | CONVICTION",
      "success_criteria": "<string: how the AE knows this objective is met>"
    }
  ],
  "rhetoric": {
    "register": "<string: incarnated register description — NEVER name the register>",
    "key_argument": "<string: the single strongest argument anchored in evidence>",
    "tangible_reformulation": "<string: make a real number tangible, e.g. '10h/week = one month/year lost to consolidation'>",
    "proof": "<string: concrete proof element from captured evidence>"
  },
  "gaps": [
    {
      "topic": "<string: what is not yet known>",
      "strategy": "DIRECT | ELICITATION",
      "question": "<string: the exact question the AE should ask>"
    }
  ],
  "next_step": {
    "what": "<string: the concrete action to secure during the call>",
    "with_whom": "<string: who should be in the next meeting>",
    "when": "<string: during the call / propose two date options>"
  }
}

FIELD RULES:

1. objectives: 1 primary + 0-2 secondary. Nature values:
   - ETHOS: build trust or rapport with the stakeholder.
   - VALUE: demonstrate business value or ROI.
   - OBJECTION: address a known resistance or blocker.
   - CONVICTION: deepen problem awareness or urgency.

2. rhetoric.register: Describe the TONE and APPROACH to use.
   NEVER use terms like "logos", "pathos", "epideictic",
   "deliberative", "demonstrative", or any classical rhetoric label.
   Instead, describe concretely: "lead with hard numbers and causal
   chains" or "contrast the current frustration with the relief after
   adoption".

3. rhetoric.tangible_reformulation: MUST anchor on a real number or
   fact from the evidence. If no number is available, anchor on a
   concrete operational fact.

4. gaps: Generate from dimensions with status "missing_evidence" or
   "unclear" in the maturity snapshot. Strategy:
   - DIRECT: ask openly when the stakeholder is likely to answer.
   - ELICITATION: probe indirectly when the topic is sensitive.

5. next_step: MUST be a concrete, datable commitment. Never "I'll get
   back to you". Always: which meeting, with whom, two date options.

6. Return ONLY the JSON object. No prose, no fences, no commentary.
"""

_EMISSION_RULES = """\
EMISSION RULES:

1. Every recommendation in objectives and rhetoric MUST be traceable
   to at least one signal or fact from the input pack. If you cannot
   anchor a recommendation, convert it into a gap question instead.

2. Gaps MUST cover all maturity dimensions with status
   "missing_evidence" or "unclear". Each gap question must be specific
   enough for the AE to ask verbatim.

3. The brief must be usable as a standalone pre-call cheat sheet.
   No references to external documents or prior conversations that
   are not in the input pack.

4. Prioritize objectives by impact: what will move the deal forward
   the most given the current brief mode and maturity state.

5. Keep the total brief concise: the AE should be able to read it
   in under 2 minutes.
"""


def build_brief_request(input_pack, brief_mode):
    """
    Render the request layer: brief generation task + output schema.

    Args:
        input_pack: dict returned by PrepInputPackAssembler.build().
        brief_mode: str — one of DISCOVERY, CONVICTION, PROOF, DECISION.

    Returns:
        str: the request prompt for the LLM.
    """
    sections = [
        f"TASK: Produce a tactical pre-call brief in {brief_mode} mode.\n"
    ]

    # -- Discovery gaps from maturity snapshot --
    discovery_gaps = input_pack.get('discovery_gaps', [])
    if discovery_gaps:
        sections.append(
            f"MATURITY GAPS TO ADDRESS ({len(discovery_gaps)} dimensions "
            f"with weak or missing evidence):"
        )
        for dim in discovery_gaps:
            if isinstance(dim, dict):
                key = dim.get('key', dim.get('dimension', 'unknown'))
                status = dim.get('status', '')
                sections.append(f"  - {key}: {status}")
        sections.append('')

    # -- Evidence summary counts --
    scope = input_pack.get('evidence_scope', {})
    sections.append(
        f"EVIDENCE AVAILABLE: "
        f"{scope.get('validated_signals_count', 0)} validated signals, "
        f"{scope.get('transcripts_count', 0)} transcripts analyzed."
    )

    sections.append('')
    sections.append(_OUTPUT_SCHEMA)
    sections.append(_EMISSION_RULES)

    return '\n'.join(sections)
