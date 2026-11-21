# app_modules/ai_pipelines/prompts/deal_health/diagnostic_v2_1.py
"""
Request layer v2.1 of the deal-health diagnostic — sprint « Deal health v2 »,
step 7 (PO decision of 18/11): the TONE of a strategic report.

Same task, same reference grid and the SAME strict schema as v2
(prompts/deal_health/diagnostic_v2.py — reused, not copied). Two field rules
are rewritten and examples are added:
  * strategic_conclusion — a strategic action plan: each action says WHO,
    WHAT and TO OBTAIN WHAT, with an indicative deadline only when the
    evidence gives one; no script, no wording to say (the Game Plan's role);
  * top_arguments — DATA for the stakeholder profiles and the Game Plan:
    which need and which value to put forward, for whom (benefit /
    advantage / feature behind it); never a task of the rep;
  * TONE_EXAMPLES — what a good action and a good argument look like (no
    figure, no name, no guard-rail phrase: tests/ai_pipelines/
    test_deal_health_eval_checks.py).
"""

import json

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_BANT_STATUSES,
    DEAL_HEALTH_DIMENSION_STATUSES,
    DEAL_HEALTH_MISSING_INFO_LEVELS,
    DEAL_HEALTH_TOP_ARGUMENTS_MAX,
)
from app_modules.decision_cycles.constants import ConvictionState

from .diagnostic_v2 import (  # noqa: F401 — the v2 schema and grid, unchanged
    DEAL_HEALTH_DIMENSION_KEYS,
    DEAL_HEALTH_RESPONSE_SCHEMA,
    _ESTIMABLE_STEPS,
    _GRID,
)


__all__ = [
    'DIAGNOSTIC_PROMPT_VERSION',
    'DEAL_HEALTH_DIMENSION_KEYS',
    'DEAL_HEALTH_RESPONSE_SCHEMA',
    'TONE_EXAMPLES',
    'TONE_EXAMPLE_ARGUMENTS',
    'build_diagnostic_request',
]

DIAGNOSTIC_PROMPT_VERSION = 'v2.1'


# =============================================================================
# EXAMPLES — the expected tone (generic: no figure, no name)
# =============================================================================

TONE_EXAMPLE_ACTIONS = (
    "The rep meets the finance lead to learn when budgets are reallocated, "
    "to get the project on that list.",
    "The champion takes the security questionnaire to the IT team, to have "
    "the integration approved before the pilot.",
    "The rep and the operations lead agree on the success criteria of the "
    "pilot, to turn the evaluation into a clear yes or no.",
)

TONE_EXAMPLE_ARGUMENTS = [
    {
        'target': 'The finance lead',
        'arguments': [{
            'need': 'Predictable operating costs',
            'value': 'Planner time freed for higher-value work',
            'benefit': 'Lower cost per delivery',
            'advantage': 'Plans adjusted automatically when orders change',
            'feature': 'Automatic route re-planning',
        }],
    },
]

TONE_EXAMPLES = '\n'.join([
    'EXAMPLES — the expected tone (illustrations: never copy them, use the evidence).',
    'Good actions of strategic_conclusion (who, what, to obtain what):',
    *[f'  - {action}' for action in TONE_EXAMPLE_ACTIONS],
    'Not an action of the plan: a sentence to say to the customer, or a '
    'generic "keep qualifying".',
    'A good top_arguments entry (data: the need and the value, for whom):',
    '  ' + json.dumps(TONE_EXAMPLE_ARGUMENTS, ensure_ascii=False),
    'Not an argument: a to-do of the rep ("Build a business case", '
    '"Schedule a demo") — that belongs to the action plan.',
])


# =============================================================================
# REQUEST TEXT
# =============================================================================

_FIELD_RULES = f"""\
FIELD RULES:

1. KEEP the original fields exactly: global_reading (2-4 sentences),
   dimensions (EXACTLY these 7 keys, in this order: {', '.join(DEAL_HEALTH_DIMENSION_KEYS)};
   status one of {', '.join(DEAL_HEALTH_DIMENSION_STATUSES)}), discovery_gaps,
   levers, themes, evidence_scope (note: "Based on captured evidence.").

2. summary: a very readable summary of the deal for a busy manager — what
   is won, what blocks, what comes next.

3. The three axes, each with a status (same values as the dimensions) and
   an assessment:
   - needs_and_urgency: is there a need, is it recognised, is it urgent, its
     impacts; cost_of_inaction ("Unknown" when not in the evidence).
   - credibility: does the customer believe we are able to deliver?
   - fit_and_value: the requirements; does the customer think we meet them,
     do we really meet them; value - cost versus the competitors
     (competitive_position).

4. buying_process: the customer's buying process as known (steps,
   timeline); "Unknown" when not in the evidence.

5. bant: budget, authority, need, timeline — each {{status:
   {' | '.join(DEAL_HEALTH_BANT_STATUSES)}, reason}}.

6. strategic_conclusion: the ACTION PLAN, at the strategic level, fitted to
   the situation and to the BANT reasons. Each action says WHO acts (the
   rep, our team, or a stakeholder ref), WHAT they do, and TO OBTAIN WHAT
   (the result that moves the deal); add an indicative deadline only when
   the evidence gives one. No script and no wording to say — the Game Plan
   prepares the conversation. Decide: e.g. no budget this year -> find out
   when and by whom budgets are reallocated, then get in front of that
   person before then; deal too small -> close the decision cycle and call
   back later; budget but no timeline -> create urgency.

7. levers_to_invest: the levers worth investing in to move the deal.

8. objectives: deal = what is sold, to whom (from the products when known,
   else "Unknown"); next_activity = the objectives of the next activity.

9. missing_info: what is not yet known, each with its level
   ({' | '.join(DEAL_HEALTH_MISSING_INFO_LEVELS)}), why it matters and the
   question to ask — guided by the grid.

10. estimated_step: the step the deal is REALLY at (one of
    {', '.join(_ESTIMABLE_STEPS)}) and the reason. It may differ from the
    declared step; you never change the declared step.

11. top_arguments: DATA for the stakeholder profiles and the Game Plan —
    per stakeholder ref (or per department), at most
    {DEAL_HEALTH_TOP_ARGUMENTS_MAX} arguments: the need to put forward and
    the value it brings to that person, with the benefit / advantage /
    feature behind it, adapted to the step. An argument is never a task of
    the rep (preparing a business case, scheduling a demo): actions belong
    to strategic_conclusion. Only capabilities present in the evidence.

12. stakeholders: one entry per stakeholder ref of the input you can say
    something about — conviction_state ({', '.join(ConvictionState.values)}),
    convincing_metrics, frustrations, conviction_strategy,
    communication_style, communication_language (BCP-47, "" when unknown).
    "" for any field the evidence does not support. Use the refs of the
    input exactly; never a last name.

13. Every text field in ENGLISH. A figure, a reference or a capability
    absent from the evidence is "Unknown" or an entry of missing_info.
"""


def build_diagnostic_request(pack):
    """Render the request layer: the task, the declared step, the grid, the
    field rules and the tone examples (the schema itself is sent as
    Structured Outputs)."""
    step = (pack.get('cycle') or {}).get('current_step')
    declared = step.get('stage') if step else 'none'
    return '\n'.join([
        "TASK: Produce a deal-health diagnostic for this deal, as its sales "
        "manager and coach who wants to win it.",
        f"Declared step: {declared}",
        '',
        _GRID,
        _FIELD_RULES,
        TONE_EXAMPLES,
        '',
        "Return ONLY the JSON object of the response schema.",
    ])
