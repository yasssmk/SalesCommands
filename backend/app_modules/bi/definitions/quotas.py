# app_modules/bi/definitions/quotas.py
"""
Quota KPI definitions.

KPI 8 — User quota attainment (must-have): result-so-far / fixed target, per
the manager-chosen target_type, over the quota's period. Reuses the existing
SalesQuota (no model change): target = quota.target_value; current = computed
on app_modules via bi.quota.compute_quota_current_value.

Custom compute (ratio + parameterized by quota_id) via compute_fn, obeying the
two rules:
- ACCESS is scoped with apply_role_scope on SalesQuota (owner scope: mine = own
  quota; team = a manager's team members' quotas). A quota is personal,
  sensitive data — a user must not see another user's quota.
- the VALUE is computed on quota.user's data (the quota owner), separate from
  access.
- query-bounded: quota fetch + one aggregate (unsupported target_type returns
  None without a query).
"""

from app_modules.bi.quota import compute_quota_current_value
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from permissions.scope_filter import apply_role_scope


def _quota_attainment(definition, auth_ctx, scope, period, params):
    quota_id = params.get('quota_id')
    if not quota_id:
        raise ValueError(f"KPI '{definition.key}' requires params['quota_id']")
    client_id = auth_ctx.client_id

    from end_users.models import SalesQuota

    # RULE 1 — ACCESS: scope the quota via the shared primitive (owner scope).
    quotas = SalesQuota.objects.filter(client_id=client_id)
    quotas = apply_role_scope(
        quotas, module='sales_quotas', scope=scope, auth_ctx=auth_ctx
    )
    quota = quotas.filter(id=quota_id).first()                     # query 1
    if quota is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'quota_id': str(quota_id), 'reason': 'out_of_scope_or_missing'},
        )

    target = float(quota.target_value or 0)
    current = compute_quota_current_value(quota)                   # query 2 (None w/o query if unsupported)

    if current is None:
        # leads_accepted / conversion_rate — no clean app_modules source.
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'quota_id': str(quota_id), 'target_type': quota.target_type,
                  'target': target, 'reason': 'metric_not_available'},
        )

    pct = round((current / target) * 100, 1) if target else 0.0
    return KPIResult(
        key=definition.key, shape=OutputShape.SCALAR, value=pct, scope=scope,
        period_start=quota.period_start, period_end=quota.period_end,
        meta={
            'quota_id': str(quota_id),
            'target_type': quota.target_type,
            'current': current,
            'target': target,
            'is_achieved': target > 0 and current >= target,
        },
    )


# KPI 8 — user quota attainment (custom compute; param quota_id).
quota_attainment = KPIDefinition(
    key='quota_attainment',
    label='User quota attainment',
    scope_module='sales_quotas',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    # Value derives from decision cycles + activities; the target lives on the
    # quota. Any of these writes should bust the cached attainment.
    cache_tags=('sales_quotas', 'decision_cycles', 'activities'),
    invalidation_sources=(
        'end_users.SalesQuota',
        'decision_cycles.DecisionCycle',
        'module_activities.Activity',
    ),
    compute_fn=_quota_attainment,
)


KPIS = [
    quota_attainment,
]
