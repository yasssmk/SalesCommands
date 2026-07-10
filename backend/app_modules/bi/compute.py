# app_modules/bi/compute.py
"""
BI compute layer — runs a declared KPI, DB-level, no N+1.

`run(definition, auth_ctx, scope, period)` executes the pipeline:

    source()                              # base queryset (lazy)
      -> tenant filter (client_id)        # multi-tenant isolation
      -> apply_role_scope (1a callable)   # mine/team/client + C6, REUSED
      -> period filter (period_field)     # closed date window
      -> DB aggregation                   # .aggregate / .values().annotate()

Everything is pushed to the database: a SCALAR is one `.aggregate()`, a
BREAKDOWN is one `.values(dimension).annotate()`, a TIMESERIES is one
`.annotate(Trunc).values().annotate()`. There is NO Python-side loop over
rows and NO per-object query — only the (small) grouped result set is read to
shape the dict/list. Team scope may add a bounded number of lookups for the
team-member expansion (see apply_role_scope); every other scope is a single
aggregate query.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.db.models import QuerySet
from django.db.models.functions import TruncMonth

from permissions.scope_filter import apply_role_scope

from .registry import KPIDefinition
from .types import KPIResult, OutputShape, Period

logger = logging.getLogger(__name__)


def _apply_tenant_filter(queryset: QuerySet, client_id) -> QuerySet:
    """Filter to the tenant. Supports both the app_modules `client_id` UUID
    field and the end_users `client_account` FK — same rule as
    ScopedQuerysetMixin.get_object / ClientScopeManager."""
    if not client_id:
        return queryset

    model = queryset.model

    def has_field(name: str) -> bool:
        try:
            model._meta.get_field(name)
            return True
        except Exception:
            return False

    if has_field('client_id'):
        return queryset.filter(client_id=client_id)
    if has_field('client_account'):
        return queryset.filter(client_account_id=client_id)

    logger.warning(
        "bi_compute_no_tenant_field",
        extra={'model': model.__name__, 'event': 'bi_compute'},
    )
    return queryset


def _apply_period(queryset: QuerySet, period_field: str, period: Optional[Period]) -> QuerySet:
    """Filter to the closed date window on `period_field`. No-op when period is
    None (default-period resolution against the tenant's fiscal config is wired
    when real KPIs are added).

    For a DateTimeField period field (e.g. created_at) the bounds are applied at
    DATE granularity (`__date`), so an end bound of `end` includes the whole day
    — a plain `<= end` would drop everything on `end` after 00:00. DateField
    period fields (scheduled_date, outcome_date, due_date) compare directly.
    """
    if period is None:
        return queryset

    try:
        is_datetime = queryset.model._meta.get_field(period_field).get_internal_type() == 'DateTimeField'
    except Exception:
        is_datetime = False
    lookup = f'{period_field}__date' if is_datetime else period_field

    flt = {}
    if period.start is not None:
        flt[f'{lookup}__gte'] = period.start
    if period.end is not None:
        flt[f'{lookup}__lte'] = period.end
    return queryset.filter(**flt) if flt else queryset


def run(definition: KPIDefinition, auth_ctx, scope: str,
        period: Optional[Period] = None, params: Optional[dict] = None) -> KPIResult:
    """Compute a single KPI for (tenant, scope, period) and return a KPIResult.

    Args:
        definition: the registered KPIDefinition to run.
        auth_ctx: AuthContext (from get_auth_ctx) — provides client_id / user_id
            / team_id used for tenant + role scoping.
        scope: 'mine' | 'team' | 'client' — must be in definition.allowed_scopes.
        period: optional Period window; None = no period filtering.
        params: optional parameters (e.g. {'territory_id': ...}) forwarded to a
            custom compute_fn; ignored by the standard pipeline.

    Raises:
        ValueError: if `scope` is not allowed for this KPI.
    """
    if scope not in definition.allowed_scopes:
        raise ValueError(
            f"scope '{scope}' not allowed for KPI '{definition.key}' "
            f"(allowed: {definition.allowed_scopes})"
        )

    # Custom-compute escape hatch (ratios / parameterized KPIs). It must still
    # scope via apply_role_scope and stay query-bounded — enforced by tests.
    if definition.compute_fn is not None:
        return definition.compute_fn(definition, auth_ctx, scope, period, params or {})

    # --- standard pipeline ------------------------------------------------
    queryset = definition.source()
    queryset = _apply_tenant_filter(queryset, auth_ctx.client_id)
    queryset = apply_role_scope(
        queryset, module=definition.scope_module, scope=scope, auth_ctx=auth_ctx
    )
    queryset = _apply_period(queryset, definition.period_field, period)

    # --- DB-level aggregation by output shape -----------------------------
    shape = definition.output_shape

    if shape is OutputShape.SCALAR:
        # one .aggregate() -> single value
        value = queryset.aggregate(_value=definition.aggregation)['_value']

    elif shape is OutputShape.BREAKDOWN:
        # one GROUP BY dimension. Reading the grouped rows to build the dict is
        # O(#groups), a single query — not N+1.
        rows = queryset.values(definition.dimension).annotate(
            _value=definition.aggregation
        )
        value = {row[definition.dimension]: row['_value'] for row in rows}

    elif shape is OutputShape.TIMESERIES:
        # one GROUP BY truncated period. Month buckets by default; a per-KPI
        # granularity can become a KPIDefinition field when a timeseries KPI
        # needs finer/coarser buckets.
        rows = (
            queryset
            .annotate(_bucket=TruncMonth(definition.period_field))
            .values('_bucket')
            .annotate(_value=definition.aggregation)
            .order_by('_bucket')
        )
        value = [{'period': row['_bucket'], 'value': row['_value']} for row in rows]

    else:  # pragma: no cover - guarded by KPIDefinition validation
        raise ValueError(f"Unsupported output_shape: {shape!r}")

    return KPIResult(
        key=definition.key,
        shape=shape,
        value=value,
        scope=scope,
        period_start=period.start if period else None,
        period_end=period.end if period else None,
        meta={'scope_module': definition.scope_module},
    )
