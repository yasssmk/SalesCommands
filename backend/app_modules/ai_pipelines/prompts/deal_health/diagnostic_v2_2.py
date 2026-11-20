# app_modules/ai_pipelines/prompts/deal_health/diagnostic_v2_2.py
"""
Request layer v2.2 of the deal-health diagnostic — sprint « Deal health v2 »,
step 7b (after the first real evaluation): v2.1 (the tone of a strategic
report, kept as is) + two corrections, the schema unchanged:
  * the grid's LEVELS clarified — a company constraint (security policy,
    data hosting, compliance, a mandatory security review) is BUSINESS; a
    department's evaluation criteria (the integration requirements of the
    tool, the IT team's criteria) are DEPARTMENT;
  * the summary follows « What is won / What blocks / What comes next », in
    short sentences, the tone of a manager who wants to win the deal.

v2.1, for the record (its own docstring):

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

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_BANT_STATUSES,
    DEAL_HEALTH_DIMENSION_STATUSES,
    DEAL_HEALTH_MISSING_INFO_LEVELS,
    DEAL_HEALTH_TOP_ARGUMENTS_MAX,
)
from app_modules.decision_cycles.constants import ConvictionState

from .diagnostic_v2 import (  # noqa: F401 — the v2 schema, unchanged
    DEAL_HEALTH_DIMENSION_KEYS,
    DEAL_HEALTH_RESPONSE_SCHEMA,
    _ESTIMABLE_STEPS,
)
from .diagnostic_v2_1 import (  # noqa: F401 — the v2.1 tone examples, unchanged
    TONE_EXAMPLE_ACTIONS,
    TONE_EXAMPLE_ARGUMENTS,
    TONE_EXAMPLES,
)


__all__ = [
    'DIAGNOSTIC_PROMPT_VERSION',
    'DEAL_HEALTH_DIMENSION_KEYS',
    'DEAL_HEALTH_RESPONSE_SCHEMA',
    'TONE_EXAMPLES',
    'TONE_EXAMPLE_ARGUMENTS',
    'build_diagnostic_request',
]

DIAGNOSTIC_PROMPT_VERSION = 'v2.2'


# =============================================================================
# REFERENCE GRID — v2's, the LEVELS clarified (7b)
# =============================================================================

_GRID = """\
REFERENCE GRID — a GUIDE, not a rigid plan. Information missing from an
EARLIER step stays a priority whatever the current step. The information of
a step should be collected during the step BEFORE.

LEVELS — BUSINESS = the company: its strategic stakes, budget, timeline and
  every company constraint (a security policy, data hosting, compliance, a
  mandatory security review). DEPARTMENT = a department: its pains,
  quantified impacts, current tools and its evaluation criteria (decision
  criteria, the integration requirements of the tool, the IT team's
  criteria). CONTACT = a person: their role in the decision, conviction and
  objections.

QUALIFICATION — goal: understand the need (product, units) and the buying
  process; exit: BANT validated, otherwise a next step adapted to the reason.
  BUSINESS: strategic stakes, budget, timeline. DEPARTMENT: pains, quantified
  impacts, current tools. CONTACT: role in the decision, final
  decision-maker, possible champion.
TECHNICAL_FIT — goal: prove we meet the requirements; exit: the customer
  confirms we meet their criteria. BUSINESS: the company constraints —
  security policy, data hosting, compliance, a mandatory security review.
  DEPARTMENT: the evaluation criteria — decision criteria, the integration
  requirements of the tool, the IT team's criteria, current tools. CONTACT:
  who evaluates (IT, key users) and their criteria.
SOLUTION_VALIDATION — covers "solution fit" (being the best offer:
  value - cost > 0, better than competitors) THEN "validation" (verbal
  agreement on our offer); say which one is reached. BUSINESS: expected
  value, competitors evaluated. DEPARTMENT: quantified gains, switching
  costs (time, complexity). CONTACT: remaining objections, conviction of
  each decision-maker, champion.
BUSINESS_CASE — goal: get the decision through the customer's internal
  process; exit: verbal agreement of those who place the order. BUSINESS:
  decision and signature process (legal, procurement, finance), timeline.
  DEPARTMENT: procurement and legal requirements. CONTACT: final
  decision-maker, signatories, champion carrying the case.
CLOSING — goal: sign; exit: contract signed. BUSINESS: contract terms,
  signature date. DEPARTMENT: last procurement requirements. CONTACT:
  signatories, last blockers.
BANT across levels: budget and timeline = BUSINESS, need = DEPARTMENT,
authority = CONTACT.
"""


# =============================================================================
# REQUEST TEXT
# =============================================================================

_FIELD_RULES = f"""\
FIELD RULES:

1. KEEP the original fields exactly: global_reading (2-4 sentences),
   dimensions (EXACTLY these 7 keys, in this order: {', '.join(DEAL_HEALTH_DIMENSION_KEYS)};
   status one of {', '.join(DEAL_HEALTH_DIMENSION_STATUSES)}), discovery_gaps,
   levers, themes, evidence_scope (note: "Based on captured evidence.").

2. summary: three parts, in this order and with these labels —
   "What is won: …", "What blocks: …", "What comes next: …" — written in
   short sentences, the tone of a manager who wants to win the deal.

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
   ({' | '.join(DEAL_HEALTH_MISSING_INFO_LEVELS)} — the LEVELS of the grid: a
   company constraint is BUSINESS, a department's evaluation criteria are
   DEPARTMENT), why it matters and the question to ask — guided by the grid.

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
