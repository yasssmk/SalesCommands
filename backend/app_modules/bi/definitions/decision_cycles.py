# app_modules/bi/definitions/decision_cycles.py
"""
Decision-cycle KPI definitions.

KPI 5 — DC counters (non-monetary): number of decision cycles grouped by
outcome, where NULL outcome = an OPEN cycle. Scoped by the decision_cycles
role scope (owner + C6 account-owner inheritance). Purely a count of cycles;
step stage/status counters are intentionally out of scope here — those depend
on the derived-status fix owned by KPI 9.
"""

from django.db.models import Count

from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape
from app_modules.decision_cycles.models import DecisionCycle


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


KPIS = [
    dc_cycles_by_outcome,
]
