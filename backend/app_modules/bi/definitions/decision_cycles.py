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
C6 correctly — DealProduct has no owner), and the value is a DB-level Sum over
the reverse `deal_products` relation of the line roll-up
(quantity × Coalesce(unit_price, catalog default, 0) × (1 − discount%/100)) —
no Python loop, line_total property NOT used. estimated_value is a separate
manual field, not used here. The scope filters are to-one joins (owner,
account), and the aggregate is over a single to-many (deal_products), so there
is no double-counting across a cycle's multiple lines.
"""

from decimal import Decimal

from django.db.models import (
    Count, DecimalField, ExpressionWrapper, F, Sum, Value,
)
from django.db.models.functions import Coalesce

from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from permissions.scope_filter import apply_role_scope


# Per-line value, in SQL: quantity × price × (1 − discount%/100).
# price = unit_price override, else the catalog default_unit_price, else 0.
_LINE_VALUE = ExpressionWrapper(
    F('deal_products__quantity')
    * Coalesce(
        F('deal_products__unit_price'),
        F('deal_products__product_catalog_entry__default_unit_price'),
        Value(Decimal('0')),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    * (Value(Decimal('1')) - F('deal_products__discount_percent') / Value(Decimal('100'))),
    output_field=DecimalField(max_digits=24, decimal_places=4),
)

# Σ of the line values over a cycle's deal_products (0 when there are none).
_PRODUCT_ROLLUP = Coalesce(
    Sum(_LINE_VALUE),
    Value(Decimal('0')),
    output_field=DecimalField(max_digits=24, decimal_places=4),
)


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
def _cycle_state(definition, auth_ctx, scope, period, params):
    cycle_id = params.get('cycle_id')
    if not cycle_id:
        raise ValueError(f"KPI '{definition.key}' requires params['cycle_id']")
    client_id = auth_ctx.client_id

    from app_modules.decision_cycles.services.cycle_aggregation_service import (
        CycleAggregationService,
    )

    # RULE 1 — scope the cycle via the shared primitive (owner + C6).
    cycles = DecisionCycle.objects.filter(client_id=client_id)
    cycles = apply_role_scope(
        cycles, module='decision_cycles', scope=scope, auth_ctx=auth_ctx
    )
    # Prefetch steps + activities so the derived logic runs from cache.
    cycle = cycles.prefetch_related('steps__activities').filter(id=cycle_id).first()
    if cycle is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'cycle_id': str(cycle_id), 'reason': 'out_of_scope_or_missing'},
        )

    summary = CycleAggregationService().get_bulk_summaries([cycle]).get(cycle.id, {})
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


# KPI 9 — decision cycle state (custom compute; param cycle_id). No percentage.
dc_cycle_state = KPIDefinition(
    key='dc_cycle_state',
    label='Decision cycle state',
    scope_module='decision_cycles',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('decision_cycles', 'activities'),
    invalidation_sources=(
        'decision_cycles.DecisionCycle',
        'decision_cycles.DecisionStep',
        'module_activities.Activity',
    ),
    compute_fn=_cycle_state,
)


KPIS = [
    dc_cycles_by_outcome,
    dc_pipeline_value,
    dc_won_value,
    dc_cycle_state,
]
