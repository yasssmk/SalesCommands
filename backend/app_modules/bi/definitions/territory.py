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

from django.db.models import Sum
from django.utils import timezone

from app_modules.bi.definitions.aggregates import managed_team_ids, pct, team_labels
from app_modules.bi.periods import current_fiscal_year_period
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.territories.models import Territory
from app_modules.territories.services.coverage import compute_territory_coverage_counts
from app_modules.territories.services.snapshot import (
    period_key_for,
    refresh_stale_snapshots,
)
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

    # Denominator + numerator via the SHARED core (queries 2 & 3) — the same
    # counts the manager-aggregate snapshot will materialise, so the live KPI
    # and the snapshot can never encode two different coverage definitions.
    numerator, denominator = compute_territory_coverage_counts(
        territory, client_id, resolved,
    )

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


# ============================================================================
# KPI 4b — TEAM territory coverage AGGREGATE (the manager Home)
#
# The manager Home can't fire one territory_coverage per territory (200
# territories -> 200 requests, and the live cache is nuked by every activity
# write). Territories have NO stored membership (each filter_definition is a
# different dynamic WHERE), so — unlike campaigns — the aggregate can't be a
# single GROUP BY over a through-table. Instead each territory's coverage counts
# are MATERIALISED on the row (the snapshot, refreshed lazily at read with a 2h
# TTL) and this KPI GROUPs BY owner__team over those columns.
#
# ONE bucket per territory: a Territory has only `owner` (no executor), so there
# is no fan-out and — crucially — no inter-team sharing. The GLOBAL is therefore
# the plain sum of the team rows (global.total == sum of per-group totals),
# UNLIKE the campaign aggregate where a shared campaign counts once and global <
# sum. So there is deliberately NO "counts once" note on this block.
#
# An account matching TWO territories is counted in BOTH (in each territory's
# numerator/denominator), so it contributes twice to the team sum. This is the
# SAME behaviour as today's per-territory territory_coverage (each ratio counts
# it independently) — a documented non-regression, not a bug introduced here.
#
# CACHE: ('territories',) only, never 'accounts'/'activities'. The 2h staleness
# lives in the snapshot columns (computed_at), decoupled from tag invalidation —
# account/activity churn is absorbed by the snapshot, not by re-running the
# expensive per-territory counts. (Note: the 'territories' tag is itself bumped
# by account/activity writes via the LIVE territory_coverage's broad
# invalidation_sources, so this aggregate's 30s result cache is short-lived — but
# its recompute is cheap: an empty refresh SELECT + one GROUP BY. The real cache
# is the columns + the TTL, exactly as intended.)
# ============================================================================


def _territory_progress_by_team(definition, auth_ctx, scope, period, params):
    client_id = auth_ctx.client_id

    # RULE 1 — scope the TERRITORIES via the shared primitive (owner scope). Not
    # in scope -> not in the aggregate.
    territories = Territory.objects.filter(client_id=client_id)
    territories = apply_role_scope(
        territories, module='territories', scope=scope, auth_ctx=auth_ctx
    )

    # Period = the caller's, else the tenant's current fiscal year. The snapshot
    # is per-period; a snapshot computed for another period is stale (period_key
    # mismatch) and gets refreshed below, never summed as-is.
    resolved = period or current_fiscal_year_period(client_id)
    period_key = period_key_for(resolved)

    # Lazily refresh stale snapshots on THIS scoped set (bounded by the budget),
    # then GROUP BY the materialised columns. When all snapshots are fresh the
    # refresh is a single empty SELECT, so the aggregate cost is constant in the
    # number of territories.
    refresh_stale_snapshots(
        territories, client_id=client_id, period=resolved, now=timezone.now()
    )

    # Only surface the manager's managed hierarchy (team scope); client -> all.
    keep = managed_team_ids(auth_ctx) if scope == 'team' else None

    grouped = (
        territories
        .filter(coverage_period_key=period_key, owner__team__isnull=False)
        .values('owner__team')
        .annotate(num=Sum('coverage_numerator'), den=Sum('coverage_denominator'))
    )                                                              # ONE query

    buckets = {}
    g_num = g_den = 0
    for r in grouped:
        tid = str(r['owner__team'])
        if keep is not None and tid not in keep:
            continue
        num, den = r['num'] or 0, r['den'] or 0
        buckets[tid] = {'total': den, 'done': num}
        g_num += num
        g_den += den  # one owner per territory -> global == sum of team rows

    return KPIResult(
        key=definition.key, shape=OutputShape.BREAKDOWN,
        value={tid: pct(b['done'], b['total']) for tid, b in buckets.items()},
        scope=scope,
        period_start=resolved.start if resolved else None,
        period_end=resolved.end if resolved else None,
        meta={
            'dimension': 'team',
            'labels': team_labels(list(buckets.keys())),
            'per_group': {tid: {'total': b['total'], 'done': b['done'],
                                'progress_pct': pct(b['done'], b['total'])}
                          for tid, b in buckets.items()},
            # global == sum of the team rows (no inter-team sharing).
            'global': {'total': g_den, 'done': g_num,
                       'progress_pct': pct(g_num, g_den)},
        },
    )


# KPI 4b — territory coverage aggregated BY TEAM (the manager Home).
territory_progress_by_team = KPIDefinition(
    key='territory_progress_by_team',
    label='Territory coverage by team',
    scope_module='territories',
    output_shape=OutputShape.BREAKDOWN,
    dimension='team',
    allowed_scopes=('team', 'client'),
    cache_tags=('territories',),   # NO accounts/activities — see module note above
    invalidation_sources=(
        'module_territories.Territory',
    ),
    compute_fn=_territory_progress_by_team,
)


KPIS = [
    territory_coverage,
    territory_progress_by_team,
]
