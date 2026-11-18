# app_modules/ai_pipelines/prompts/deal_health/diagnostic_v2.py
"""
Request layer v2 of the deal-health diagnostic — sprint « Deal health v2 »,
step 5: the task, the reference grid (step x level x information to obtain —
a GUIDE, not a rigid plan), the field rules, and the strict Structured
Outputs schema DEAL_HEALTH_RESPONSE_SCHEMA (the next_steps_v2.py pattern:
every field required, no other field).

The v2 keeps EVERY v1 key as is (amendment A5: DealHealthView and the
current prep call read them): global_reading, dimensions (the 7, in order),
discovery_gaps, levers, themes, evidence_scope.
"""

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_BANT_LETTERS,
    DEAL_HEALTH_BANT_STATUSES,
    DEAL_HEALTH_DIMENSION_STATUSES,
    DEAL_HEALTH_MISSING_INFO_LEVELS,
    DEAL_HEALTH_TOP_ARGUMENTS_MAX,
)
from app_modules.decision_cycles.constants import (
    PIPELINE_STEPS_ORDER,
    STAKEHOLDER_PROFILE_FIELDS,
    ConvictionState,
)


__all__ = [
    'DIAGNOSTIC_PROMPT_VERSION',
    'DEAL_HEALTH_DIMENSION_KEYS',
    'DEAL_HEALTH_RESPONSE_SCHEMA',
    'build_diagnostic_request',
]

DIAGNOSTIC_PROMPT_VERSION = 'v2'

# The 7 v1 dimensions, in their mandatory order (DealHealthWriter).
DEAL_HEALTH_DIMENSION_KEYS = (
    'problem_recognized', 'felt_pain', 'impact_understood', 'desired_gain',
    'urgency', 'willingness_to_act', 'solution_trust',
)

# The 5 steps a deal can be estimated at (the auto-created ones).
_ESTIMABLE_STEPS = [str(step) for step in PIPELINE_STEPS_ORDER]


# =============================================================================
# STRICT RESPONSE SCHEMA
# =============================================================================

_STR = {'type': 'string'}
_STRS = {'type': 'array', 'items': _STR}


def _obj(properties):
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': list(properties),
        'properties': properties,
    }


def _arr(item):
    return {'type': 'array', 'items': item}


_STATUS = {'type': 'string', 'enum': list(DEAL_HEALTH_DIMENSION_STATUSES)}

DEAL_HEALTH_RESPONSE_SCHEMA = {
    'name': 'deal_health_diagnostic_v2',
    'schema': _obj({
        # -- v1 keys, unchanged (A5) --
        'global_reading': _STR,
        'dimensions': _arr(_obj({
            'key': {'type': 'string', 'enum': list(DEAL_HEALTH_DIMENSION_KEYS)},
            'status': _STATUS,
            'evidence': _STR,
            'missing': _STR,
        })),
        'discovery_gaps': _arr(_obj({
            'kind': {'type': 'string', 'enum': ['qualification', 'procedural']},
            'dimension': _STR,
            'public_text': _STR,
            'suggested_questions': _STRS,
            'related_theme': _STR,
            'related_actor': _STR,
        })),
        'levers': _obj({
            'desires': _arr(_obj({'summary': _STR, 'theme': _STR})),
            'value': _arr(_obj({'summary': _STR, 'theme': _STR})),
            'cost': _arr(_obj({'summary': _STR, 'actor': _STR})),
            'constraints': _arr(_obj({
                'summary': _STR, 'rigidity': _STR, 'is_metric': {'type': 'boolean'},
            })),
        }),
        'themes': _arr(_obj({'label': _STR, 'summary': _STR})),
        'evidence_scope': _obj({
            'validated_signals_count': {'type': 'integer'}, 'note': _STR,
        }),
        # -- v2 --
        'summary': _STR,
        'needs_and_urgency': _obj({
            'status': _STATUS, 'assessment': _STR, 'cost_of_inaction': _STR,
        }),
        'credibility': _obj({'status': _STATUS, 'assessment': _STR}),
        'fit_and_value': _obj({
            'status': _STATUS, 'assessment': _STR,
            'requirements': _STRS, 'competitive_position': _STR,
        }),
        'buying_process': _obj({'assessment': _STR, 'steps': _STRS, 'timeline': _STR}),
        'bant': _obj({
            letter: _obj({
                'status': {'type': 'string', 'enum': list(DEAL_HEALTH_BANT_STATUSES)},
                'reason': _STR,
            })
            for letter in DEAL_HEALTH_BANT_LETTERS
        }),
        'strategic_conclusion': _STR,
        'levers_to_invest': _arr(_obj({'lever': _STR, 'why': _STR})),
        'objectives': _obj({'deal': _STR, 'next_activity': _STRS}),
        'missing_info': _arr(_obj({
            'level': {'type': 'string', 'enum': list(DEAL_HEALTH_MISSING_INFO_LEVELS)},
            'item': _STR,
            'why_it_matters': _STR,
            'suggested_question': _STR,
        })),
        'estimated_step': _obj({
            'step': {'type': 'string', 'enum': _ESTIMABLE_STEPS},
            'reason': _STR,
        }),
        'top_arguments': _arr(_obj({
            'target': _STR,
            'arguments': _arr(_obj({
                'need': _STR, 'value': _STR,
                'benefit': _STR, 'advantage': _STR, 'feature': _STR,
            })),
        })),
        'stakeholders': _arr(_obj({
            'ref': _STR,
            **{
                field: (
                    {'type': 'string', 'enum': list(ConvictionState.values)}
                    if field == 'conviction_state' else _STR
                )
                for field in STAKEHOLDER_PROFILE_FIELDS
            },
        })),
    }),
}


# =============================================================================
# REQUEST TEXT
# =============================================================================

_GRID = """\
REFERENCE GRID — a GUIDE, not a rigid plan. Information missing from an
EARLIER step stays a priority whatever the current step. The information of
a step should be collected during the step BEFORE.

QUALIFICATION — goal: understand the need (product, units) and the buying
  process; exit: BANT validated, otherwise a next step adapted to the reason.
  BUSINESS: strategic stakes, budget, timeline. DEPARTMENT: pains, quantified
  impacts, current tools. CONTACT: role in the decision, final
  decision-maker, possible champion.
TECHNICAL_FIT — goal: prove we meet the requirements; exit: the customer
  confirms we meet their criteria. BUSINESS: security, compliance,
  integration constraints. DEPARTMENT: decision criteria, requirements,
  current tools. CONTACT: who evaluates (IT, key users) and their criteria.
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

_FIELD_RULES = f"""\
FIELD RULES:

1. KEEP the original fields exactly: global_reading (2-4 sentences),
   dimensions (EXACTLY these 7 keys, in this order: {', '.join(DEAL_HEALTH_DIMENSION_KEYS)};
   status one of {', '.join(DEAL_HEALTH_DIMENSION_STATUSES)}), discovery_gaps,
   levers, themes, evidence_scope (note: "Based on captured evidence.").

2. summary: a very readable summary of the deal for a busy manager.

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

6. strategic_conclusion: an action plan in TEXT whose next steps fit the
   situation and the BANT reasons. You decide. Examples:
   - no budget this year -> find out when and by whom budgets are
     reallocated, then get a meeting with that person before then;
   - deal too small -> close the decision cycle and call back later;
   - budget but no timeline -> create urgency.

7. levers_to_invest: the levers worth investing in to move the deal.

8. objectives: deal = what is sold, to whom (from the products when known,
   else "Unknown"); next_activity = the objectives of the next activity.

9. missing_info: what is not yet known, each with its level
   ({' | '.join(DEAL_HEALTH_MISSING_INFO_LEVELS)}), why it matters and the
   question to ask — guided by the grid.

10. estimated_step: the step the deal is REALLY at (one of
    {', '.join(_ESTIMABLE_STEPS)}) and the reason. It may differ from the
    declared step; you never change the declared step.

11. top_arguments: per stakeholder ref (or per department), at most
    {DEAL_HEALTH_TOP_ARGUMENTS_MAX} arguments, each the need, the value, and
    the benefit / advantage / feature behind it — adapted to the step and to
    the person. Never invent a product capability.

12. stakeholders: one entry per stakeholder ref of the input you can say
    something about — conviction_state ({', '.join(ConvictionState.values)}),
    convincing_metrics, frustrations, conviction_strategy,
    communication_style, communication_language (BCP-47, "" when unknown).
    "" for any field the evidence does not support. Use the refs of the
    input exactly; never a last name.

13. Every text field in ENGLISH. Never invent a reference, a figure or a
    product capability: write "Unknown" or add it to missing_info.
"""


def build_diagnostic_request(pack):
    """Render the request layer: the task, the declared step, the grid and the
    field rules (the schema itself is sent as Structured Outputs)."""
    step = (pack.get('cycle') or {}).get('current_step')
    declared = step.get('stage') if step else 'none'
    return '\n'.join([
        "TASK: Produce a deal-health diagnostic for this deal, as its sales "
        "manager and coach.",
        f"Declared step: {declared}",
        '',
        _GRID,
        _FIELD_RULES,
        "Return ONLY the JSON object of the response schema.",
    ])
