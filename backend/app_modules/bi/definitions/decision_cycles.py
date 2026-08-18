# app_modules/bi/definitions/decision_cycles.py
"""
Decision-cycle KPI definitions.

KPI 5 — DC counters (non-monetary): cycles grouped by outcome (NULL = open).

KPI 7 — DC monetary ($ pipeline / $ result): product roll-up value.
- dc_pipeline_value = Σ product value of OPEN cycles (outcome NULL) — a STOCK,
  so it is called with period=None (convention; the outcome filter + no period
  express "what is open now").
- dc_won_value = Σ product value of WON cycles in the period (by outcome_date)
  — a FLUX.
Both are STANDARD KPIs (a scalar Sum over a scoped DecisionCycle queryset):
source = DecisionCycle (so apply_role_scope('decision_cycles') scopes owner +
C6 correctly — DealProduct has no owner), and the value is the CANONICAL deal
value — `DEAL_VALUE_SUM`, imported from decision_cycles/services/deal_value_sql.py,
which is also what `DecisionCycle.total_deal_value` returns. The formula is
declared there and nowhere else; this module states no arithmetic of its own.
No Python loop, line_total property NOT used. estimated_value is a separate
manual field, not used here. The scope filters are to-one joins (owner,
account), and the aggregate is over a single to-many (deal_products), so there
is no double-counting across a cycle's multiple lines.
"""

from django.db.models import Count

from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.services.deal_value_sql import DEAL_VALUE_SUM
from permissions.scope_filter import apply_role_scope


# The roll-up is NOT redeclared here: KPI 7's money IS the canonical deal value
# (decision_cycles/services/deal_value_sql.py), so the formula lives in exactly
# one place and this module consumes it. Kept under the historical name so the
# KPI definitions below read unchanged.
_PRODUCT_ROLLUP = DEAL_VALUE_SUM


# KPI 5 — cycles by outcome (None = open).
dc_cycles_by_outcome = KPIDefinition(
    key='dc_cycles_by_outcome',
    label='Decision cycles by outcome',
    source=lambda: DecisionCycle.objects.all(),
    aggregation=Count('id'),
    scope_module='decision_cycles',
    period_field='created_at',           # bucket/filter by cycle creation
    output_shape=OutputShape.BREAKDOWN,
    dimension='outcome',                 # WON / LOST / ON_HOLD / NOT_QUALIFIED / None(open)
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('decision_cycles',),
    invalidation_sources=('decision_cycles.DecisionCycle',),
)


# KPI 7a — $ pipeline: product value of OPEN cycles (STOCK; call with period=None).
dc_pipeline_value = KPIDefinition(
    key='dc_pipeline_value',
    label='$ pipeline (open decision cycles)',
    source=lambda: DecisionCycle.objects.filter(outcome__isnull=True),
    aggregation=_PRODUCT_ROLLUP,
    scope_module='decision_cycles',
    period_field='created_at',           # STOCK — call with period=None (see module docstring)
    output_shape=OutputShape.SCALAR,
    unit='currency',                     # money — payload carries the tenant's currency
    allowed_scopes=('mine', 'team', 'client'),
    # STOCK metric: the API default must NOT window it. default_period='all'
    # makes the endpoint's "absent -> default_period" resolve to no period
    # filter (correct by construction), instead of the fiscal-year default that
    # would wrongly drop cycles created before this fiscal year.
    default_period='all',
    cache_tags=('decision_cycles',),
    invalidation_sources=(
        'decision_cycles.DecisionCycle',
        'decision_cycles.DealProduct',
    ),
)


# KPI 7b — $ result: product value of WON cycles in the period (FLUX by outcome_date).
dc_won_value = KPIDefinition(
    key='dc_won_value',
    label='$ result (won decision cycles in period)',
    source=lambda: DecisionCycle.objects.filter(outcome=CycleOutcome.WON),
    aggregation=_PRODUCT_ROLLUP,
    scope_module='decision_cycles',
    period_field='outcome_date',         # FLUX — call with the period
    output_shape=OutputShape.SCALAR,
    unit='currency',                     # money — payload carries the tenant's currency
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('decision_cycles',),
    invalidation_sources=(
        'decision_cycles.DecisionCycle',
        'decision_cycles.DealProduct',
    ),
)


# KPI 9 — Decision-cycle STATE (not a %): current stage + derived status
# (STALLED visible) + next action + secondary "X/N stages validated".
# Reuses the REPAIRED derived logic (CycleAggregationService.get_bulk_summaries
# over prefetched steps+activities → StepStatusDerivationService.derive_bulk);
# no new progression logic, no percentage.
def _scoped_cycles(auth_ctx, scope):
    """The role-scoped DecisionCycle queryset (owner + C6), with steps+activities
    prefetched so the derived state runs from cache. Shared by the single and the
    bulk cycle-state paths so their scoping can never drift."""
    cycles = DecisionCycle.objects.filter(client_id=auth_ctx.client_id)
    cycles = apply_role_scope(
        cycles, module='decision_cycles', scope=scope, auth_ctx=auth_ctx
    )
    return cycles.prefetch_related('steps__activities')


def _build_cycle_state_result(definition, scope, cycle_id, cycle, summary):
    """Turn one cycle + its get_bulk_summaries entry into the KPIResult. Shared by
    _cycle_state (single) and _cycle_state_bulk so both return byte-identical
    results. ``cycle`` is None when the id is out of scope / not found."""
    if cycle is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'cycle_id': str(cycle_id), 'reason': 'out_of_scope_or_missing'},
        )

    cycle_status = summary.get('cycle_status', 'NOT_STARTED')
    progress = summary.get('progress', {})
    validated = progress.get('validated_steps', 0)
    total = progress.get('total_steps', 0)
    current_order = progress.get('current_step_order')
    current_name = progress.get('current_step_name')

    current_stage = None
    if current_order is not None:
        current_step = next(
            (s for s in cycle.steps.all() if s.order == current_order), None
        )
        current_stage = current_step.stage if current_step else None

    # Next action — the motivation lever, esp. when STALLED (act to unblock).
    if cycle_status == 'STALLED':
        next_action = 'Act: close the deal or define the next step'
    elif cycle_status == 'OVERDUE':
        next_action = 'Overdue — act on the current step now'
    elif current_name:
        next_action = f'Advance: {current_name}'
    else:
        next_action = None

    return KPIResult(
        key=definition.key, shape=OutputShape.SCALAR, value=cycle_status, scope=scope,
        meta={
            'cycle_id': str(cycle_id),
            'cycle_status': cycle_status,        # derived — STALLED is visible
            'current_stage': current_stage,
            'current_step_name': current_name,
            'current_step_order': current_order,
            'next_action': next_action,
            'validated_steps': validated,        # the "X"
            'total_steps': total,                # the "N" (X/N stages validated)
        },
    )


def _cycle_state(definition, auth_ctx, scope, period, params):
    cycle_id = params.get('cycle_id')
    if not cycle_id:
        raise ValueError(f"KPI '{definition.key}' requires params['cycle_id']")

    from app_modules.decision_cycles.services.cycle_aggregation_service import (
        CycleAggregationService,
    )

    cycle = _scoped_cycles(auth_ctx, scope).filter(id=cycle_id).first()
    summary = (
        CycleAggregationService().get_bulk_summaries([cycle]).get(cycle.id, {})
        if cycle is not None else {}
    )
    return _build_cycle_state_result(definition, scope, cycle_id, cycle, summary)


def _cycle_state_bulk(definition, auth_ctx, scope, period, params_list):
    """Batch path: compute the state of every requested cycle in ONE shared
    query set (filter id__in + steps/activities prefetch = 3 queries total,
    instead of 3 per cycle), then get_bulk_summaries over the whole set (0
    queries). Returns a list aligned to params_list, each item a KPIResult — or,
    for a spec missing cycle_id, a ValueError so the view renders that spec's
    own 400 (strict parity with the per-spec path)."""
    from app_modules.decision_cycles.services.cycle_aggregation_service import (
        CycleAggregationService,
    )

    valid_ids = [str(p['cycle_id']) for p in params_list if p.get('cycle_id')]
    cycles = list(_scoped_cycles(auth_ctx, scope).filter(id__in=valid_ids))
    by_id = {str(c.id): c for c in cycles}
    summaries = CycleAggregationService().get_bulk_summaries(cycles)

    results = []
    for p in params_list:
        cycle_id = p.get('cycle_id')
        if not cycle_id:
            # Same message + error class as the per-spec path -> identical 400.
            results.append(ValueError(f"KPI '{definition.key}' requires params['cycle_id']"))
            continue
        cycle = by_id.get(str(cycle_id))
        summary = summaries.get(cycle.id, {}) if cycle is not None else {}
        results.append(_build_cycle_state_result(definition, scope, cycle_id, cycle, summary))
    return results


# KPI 9 — decision cycle state (custom compute; param cycle_id). No percentage.
dc_cycle_state = KPIDefinition(
    key='dc_cycle_state',
    label='Decision cycle state',
    scope_module='decision_cycles',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    # STATE metric: the derived status ignores any period window, so the API
    # default must NOT resolve to the fiscal year (which would fetch the tenant's
    # ClientAccount per spec for nothing). 'all' -> no period, same as the STOCK
    # KPIs above (dc_pipeline_value).
    default_period='all',
    cache_tags=('decision_cycles', 'activities'),
    invalidation_sources=(
        'decision_cycles.DecisionCycle',
        'decision_cycles.DecisionStep',
        'module_activities.Activity',
    ),
    compute_fn=_cycle_state,
    bulk_compute_fn=_cycle_state_bulk,
)


KPIS = [
    dc_cycles_by_outcome,
    dc_pipeline_value,
    dc_won_value,
    dc_cycle_state,
]
