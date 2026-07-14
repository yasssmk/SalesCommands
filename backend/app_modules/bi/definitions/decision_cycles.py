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
from app_modules.bi.types import OutputShape
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle


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


KPIS = [
    dc_cycles_by_outcome,
    dc_pipeline_value,
    dc_won_value,
]
