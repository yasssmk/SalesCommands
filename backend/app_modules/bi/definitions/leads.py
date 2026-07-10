# app_modules/bi/definitions/leads.py
"""
Leads KPI definitions.

KPI 6 — Leads. There is no Lead entity in app_modules; our product definition
is: generating leads = creating decision cycles and activities. So "leads
generated in a period" = (decision cycles created) + (activities created) in
that period, scoped by role (owner + C6).

Design — two ATOMIC KPIs, not one composite source:
  leads_dc_created         (count of DecisionCycle created in period)
  leads_activities_created (count of Activity created in period)
The total is their sum, composed by the consumer. A single composite source
(UNION of DecisionCycle + Activity) is deliberately avoided: the foundation's
apply_role_scope resolves ownership fields against ONE model's _meta, so a
two-model source would break per-model scoping. Two atomic KPIs keep each one
correctly scoped / cached / invalidated; summing two scalars is trivial.
"""

from django.db.models import Count

from app_modules.activities.models import Activity
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape
from app_modules.decision_cycles.models import DecisionCycle


# KPI 6a — decision cycles created in the period.
leads_dc_created = KPIDefinition(
    key='leads_dc_created',
    label='Leads — decision cycles created',
    source=lambda: DecisionCycle.objects.all(),
    aggregation=Count('id'),
    scope_module='decision_cycles',
    period_field='created_at',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('decision_cycles',),
    invalidation_sources=('decision_cycles.DecisionCycle',),
)


# KPI 6b — activities created in the period.
leads_activities_created = KPIDefinition(
    key='leads_activities_created',
    label='Leads — activities created',
    source=lambda: Activity.objects.all(),
    aggregation=Count('id'),
    scope_module='activities',
    period_field='created_at',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('activities',),
    invalidation_sources=('module_activities.Activity',),
)


KPIS = [
    leads_dc_created,
    leads_activities_created,
]
