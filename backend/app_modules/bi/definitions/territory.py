# app_modules/bi/definitions/territory.py
"""
Territory KPI definitions.

KPI 4 — Territory coverage %: of the accounts in a territory, how many were
"touched with a response" (an Activity carrying an outcome) during the period,
over the total accounts in the territory.

This is the documented EXCEPTION to the standard aggregate-a-scoped-queryset
pipeline: it is a RATIO, parameterized by a territory, over a dynamically
JSON-filtered account set (a different WHERE per territory — not a single
GROUP BY). It uses the foundation's compute_fn escape hatch, but obeys the two
non-negotiable rules:
  1. it scopes via permissions.scope_filter.apply_role_scope (on Territory —
     owner scope, so another owner's territory is not visible), NEVER a
     homemade scope filter;
  2. it is query-bounded: territory fetch + denominator count + numerator count
     (+1 for default-fiscal resolution when period is None). No per-account N+1.

Denominator uses AccountFilterService (the territory's filter_definition),
NOT the accounts-count endpoint (a placeholder that returns 0).
"""

from app_modules.accounts.models import CompanyAccount
from app_modules.accounts.services.filter_service import AccountFilterService
from app_modules.bi.periods import current_fiscal_year_period
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.territories.models import Territory
from permissions.scope_filter import apply_role_scope


def _territory_coverage(definition, auth_ctx, scope, period, params):
    territory_id = params.get('territory_id')
    if not territory_id:
        raise ValueError(
            f"KPI '{definition.key}' requires params['territory_id']"
        )
    client_id = auth_ctx.client_id

    # RULE 1 — scope on the TERRITORY via the shared primitive. If the
    # territory is not in the caller's scope, it is not visible -> no coverage.
    territories = (
        Territory.objects.filter(client_id=client_id).select_related('owner')
    )
    territories = apply_role_scope(
        territories, module='territories', scope=scope, auth_ctx=auth_ctx
    )
    territory = territories.filter(id=territory_id).first()          # query 1
    if territory is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'territory_id': str(territory_id),
                  'reason': 'out_of_scope_or_missing'},
        )

    # Default period = the tenant's current fiscal year.
    resolved = period or current_fiscal_year_period(client_id)      # query (only if period is None)

    # Denominator — accounts in the territory (dynamic filter, evaluated ONCE).
    # Start tenant-scoped so isolation holds regardless of the filter definition.
    base = CompanyAccount.objects.filter(client_id=client_id)
    accounts = AccountFilterService.apply_filters(
        base, territory.filter_definition or {},
        client_id=client_id, user=territory.owner,
    )
    denominator = accounts.count()                                  # query 2

    # Numerator — accounts touched with a response (Activity.outcome set) in the
    # period. One query (JOIN + COUNT DISTINCT), no per-account loop.
    touched = accounts.filter(activities__outcome__isnull=False)
    if resolved and resolved.start is not None:
        touched = touched.filter(activities__scheduled_date__gte=resolved.start)
    if resolved and resolved.end is not None:
        touched = touched.filter(activities__scheduled_date__lte=resolved.end)
    numerator = touched.distinct().count()                          # query 3

    coverage = round(100.0 * numerator / denominator, 1) if denominator else 0.0
    return KPIResult(
        key=definition.key, shape=OutputShape.SCALAR, value=coverage, scope=scope,
        period_start=resolved.start if resolved else None,
        period_end=resolved.end if resolved else None,
        meta={'numerator': numerator, 'denominator': denominator,
              'territory_id': str(territory_id)},
    )


# KPI 4 — territory coverage % (custom compute; parameterized by territory_id).
territory_coverage = KPIDefinition(
    key='territory_coverage',
    label='Territory coverage %',
    scope_module='territories',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('territories', 'accounts', 'activities'),
    invalidation_sources=(
        'module_territories.Territory',
        'module_accounts.CompanyAccount',
        'module_activities.Activity',
    ),
    compute_fn=_territory_coverage,
)


KPIS = [
    territory_coverage,
]
