# app_modules/bi/definitions/campaigns.py
"""
Campaign KPI definitions.

KPI 2 — Campaign progress + objectives. A single KPI (parameterized by
campaign_id) that returns, for one campaign:
- value = campaign advancement = CampaignAccount completion rate where a
  WORKED-then-stopped account counts as DONE: (COMPLETED + STOPPED) / total.
  STOPPED is a terminal OUTCOME (the target was contacted, then no-response /
  opt-out), not a cancellation — so it belongs in the numerator, and the
  denominator stays the raw total. The Home's "N accounts to go" = total - done
  = the non-final accounts. This makes progress the exact complement of
  campaign_coverage (progress% = 100% - coverage% at the account level);
- meta.objectives = per objective_type: {target, current, progress_pct}, where
  current reuses CampaignAnalyticsService.calculate_objective_values (the same
  service metric logic as get_current_value, grouped by data source — MODULE
  objectives, not legacy).

It is one KPI, not two: same subject (a campaign), same scope, same
cache/invalidation, computed in one bounded pass.

Custom compute (ratio + parameterized), so it uses the compute_fn escape hatch
and obeys the two rules: it scopes the CAMPAIGN via apply_role_scope (owner +
executor via OWNERSHIP_MAP assigned_to_user='executor', so another user's
campaign is not visible), and it is query-bounded: campaign fetch + accounts
aggregate + objectives load + one query per distinct objective data source
present (<= 4), independent of the number of objectives.
"""

from django.db.models import Count, Q

from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignStatus,
    FINAL_ACCOUNT_STATES,
    FINAL_CONTACT_STATES,
)
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_account import CampaignAccount
from app_modules.campaigns.models.campaign_contact import CampaignContact
from app_modules.campaigns.models.campaign_objective import CampaignObjective
from app_modules.bi.definitions.aggregates import (
    managed_team_ids as _managed_team_ids,
    pct as _pct,
    person_labels as _person_labels,
    team_labels as _team_labels,
)
from permissions.owner_scope import get_team_member_ids
from permissions.scope_filter import apply_role_scope


# The STOPPED-as-done predicate (TD-86). SHARED by campaign_progress (per
# campaign) and the team/owner aggregates so the rep Home and the manager Home
# can never show contradictory % on the same campaigns: a WORKED-then-stopped
# account counts as done, denominator = raw total. Do NOT redeclare this
# elsewhere — like TODO_STATUSES / todo_window_q, one predicate, many consumers.
CAMPAIGN_DONE_Q = Q(status__in=FINAL_ACCOUNT_STATES)


def _campaign_progress(definition, auth_ctx, scope, period, params):
    campaign_id = params.get('campaign_id')
    if not campaign_id:
        raise ValueError(f"KPI '{definition.key}' requires params['campaign_id']")
    client_id = auth_ctx.client_id

    # RULE 1 — scope the CAMPAIGN (owner + executor + created_by) via the
    # shared primitive. Not in scope -> not visible.
    campaigns = Campaign.objects.filter(client_id=client_id)
    campaigns = apply_role_scope(
        campaigns, module='campaigns', scope=scope, auth_ctx=auth_ctx
    )
    campaign = campaigns.filter(id=campaign_id).first()             # query 1
    if campaign is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'campaign_id': str(campaign_id),
                  'reason': 'out_of_scope_or_missing'},
        )

    # Campaign advancement — CampaignAccount completion (one grouped aggregate).
    # `done` uses the SHARED CAMPAIGN_DONE_Q so this per-campaign KPI and the
    # team/owner aggregates agree by construction; completed/stopped are broken
    # out only for the meta decomposition.
    agg = CampaignAccount.objects.filter(campaign=campaign).aggregate(
        total=Count('id'),
        done=Count('id', filter=CAMPAIGN_DONE_Q),
        completed=Count('id', filter=Q(status=CampaignAccountStatus.COMPLETED)),
        stopped=Count('id', filter=Q(status=CampaignAccountStatus.STOPPED)),
    )                                                              # query 2
    total = agg['total'] or 0
    completed_only = agg['completed'] or 0
    stopped = agg['stopped'] or 0
    # STOPPED counts as DONE. A stopped target was WORKED — contacted, then
    # no-response / opt-out — the result is "stopped": a terminal OUTCOME, not a
    # cancellation. Excluding it would say "it never existed" and erase real
    # effort. So "done" = both final states (COMPLETED + STOPPED) and the
    # denominator stays the raw total. "Remaining" = total - done = the
    # NON-final accounts (PENDING + IN_PROGRESS) — never a stopped one.
    #
    # This makes campaign_progress the exact complement of campaign_coverage at
    # the account level: progress% = done/total = final/total, coverage% =
    # active/total = non-final/total, and final + non-final = total, so
    # progress% = 100% - coverage%. Same classification of a STOPPED account
    # (resolved / no-longer-to-do) on both sides.
    done = agg['done'] or 0  # == completed_only + stopped, from the shared predicate
    completion_rate = round((done / total) * 100, 1) if total else 0.0

    # Objective advancement — current/target per objective_type. Values are
    # computed in one grouped pass (one query per distinct data source present,
    # not one per objective), identical to CampaignObjective.get_current_value().
    # Deferred import: the service imports the bi metrics package, so importing
    # it at module load would risk a cycle through bi.
    from app_modules.campaigns.services.campaign_analytics_service import (
        CampaignAnalyticsService,
    )

    objectives = list(
        CampaignObjective.objects.filter(campaign=campaign)
    )                                                              # query 3
    objective_values = CampaignAnalyticsService(
        client_id=client_id
    ).calculate_objective_values(campaign, objectives)             # bounded: 1 query / source
    objective_rows = []
    for obj in objectives:
        current = float(objective_values.get(obj.id, 0) or 0)
        target = float(obj.target_value or 0)
        pct = round((current / target) * 100, 1) if target else 0.0
        objective_rows.append({
            'objective_type': obj.objective_type,
            'target': target,
            'current': current,
            'progress_pct': pct,
            'is_primary': obj.is_primary,
        })

    return KPIResult(
        key=definition.key, shape=OutputShape.SCALAR, value=completion_rate, scope=scope,
        meta={
            'campaign_id': str(campaign_id),
            'status': campaign.status,
            'accounts_total': total,                    # raw total (denominator)
            'accounts_completed': done,                 # DONE = COMPLETED + STOPPED (front reads this)
            'accounts_completed_only': completed_only,  # strictly COMPLETED (decomposition)
            'accounts_stopped': stopped,                # STOPPED counted as done (worked -> terminal)
            'objectives': objective_rows,
        },
    )


# KPI 2 — campaign progress + objectives (custom compute; param campaign_id).
campaign_progress = KPIDefinition(
    key='campaign_progress',
    label='Campaign progress + objectives',
    scope_module='campaigns',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    # Objective current values derive from activities and decision cycles, whose
    # writes bump 'activities' / 'decision_cycles' via their existing receivers;
    # campaign-structure writes bump 'campaigns' via the BI receiver below.
    cache_tags=('campaigns', 'activities', 'decision_cycles'),
    invalidation_sources=(
        'module_campaigns.Campaign',
        'module_campaigns.CampaignAccount',
        'module_campaigns.CampaignObjective',
    ),
    compute_fn=_campaign_progress,
)


def _campaign_coverage(definition, auth_ctx, scope, period, params):
    """KPI 3 — campaign coverage = still-active targets / total targets.

    Primary level = CampaignContact (what the UI/TargetsTab calls a target);
    secondary level = CampaignAccount (consistent with the existing dashboard's
    account-level completion). "Active" = status NOT in the FINAL set.
    """
    campaign_id = params.get('campaign_id')
    if not campaign_id:
        raise ValueError(f"KPI '{definition.key}' requires params['campaign_id']")
    client_id = auth_ctx.client_id

    # RULE 1 — scope the CAMPAIGN (owner + executor) via the shared primitive.
    campaigns = Campaign.objects.filter(client_id=client_id)
    campaigns = apply_role_scope(
        campaigns, module='campaigns', scope=scope, auth_ctx=auth_ctx
    )
    campaign = campaigns.filter(id=campaign_id).first()             # query 1
    if campaign is None:
        return KPIResult(
            key=definition.key, shape=OutputShape.SCALAR, value=None, scope=scope,
            meta={'campaign_id': str(campaign_id),
                  'reason': 'out_of_scope_or_missing'},
        )

    # Contact level (primary) — one grouped aggregate.
    contacts = CampaignContact.objects.filter(
        campaign_account__campaign=campaign
    ).aggregate(
        total=Count('id'),
        active=Count('id', filter=~Q(status__in=FINAL_CONTACT_STATES)),
    )                                                              # query 2

    # Account level (secondary) — one grouped aggregate.
    accounts = CampaignAccount.objects.filter(campaign=campaign).aggregate(
        total=Count('id'),
        active=Count('id', filter=~Q(status__in=FINAL_ACCOUNT_STATES)),
    )                                                              # query 3

    def _cov(active, total):
        return round((active / total) * 100, 1) if total else 0.0

    c_total, c_active = contacts['total'] or 0, contacts['active'] or 0
    a_total, a_active = accounts['total'] or 0, accounts['active'] or 0

    return KPIResult(
        key=definition.key, shape=OutputShape.SCALAR,
        value=_cov(c_active, c_total),  # headline = contact-level coverage
        scope=scope,
        meta={
            'campaign_id': str(campaign_id),
            'contacts': {'total': c_total, 'active': c_active,
                         'coverage_pct': _cov(c_active, c_total)},
            'accounts': {'total': a_total, 'active': a_active,
                         'coverage_pct': _cov(a_active, a_total)},
        },
    )


# KPI 3 — campaign coverage (custom compute; param campaign_id).
campaign_coverage = KPIDefinition(
    key='campaign_coverage',
    label='Campaign coverage (active targets / total)',
    scope_module='campaigns',
    output_shape=OutputShape.SCALAR,
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('campaigns',),
    invalidation_sources=(
        'module_campaigns.Campaign',
        'module_campaigns.CampaignAccount',
        'module_campaigns.CampaignContact',
    ),
    compute_fn=_campaign_coverage,
)


# ============================================================================
# KPI 2b — TEAM / OWNER campaign progress AGGREGATE (the manager Home)
#
# The manager Home can't fire one campaign_progress per campaign (200 campaigns
# -> 200 requests). These two KPIs return the aggregate in ONE grouped query.
#
# THE SHAPE (one query, Python fan-out): group CampaignAccount by
# (campaign, owner_group, executor_group) — since owner/executor groups are
# functionally determined by the campaign, this is per-campaign — with total +
# done (CAMPAIGN_DONE_Q). Then fan each per-campaign row out to BOTH its owner
# group AND its executor group (set-deduped), because a campaign is the work of
# whoever executes it AND the result of whoever owns it. A campaign
# owner-external / executor-internal therefore appears in the EXECUTOR's bucket
# of THIS manager, and in the OWNER's bucket of the owner's manager: each
# hierarchy sees what concerns it, from its own point of view (the PO's rule).
#
# GLOBAL: summed from the per-campaign rows ONCE (a campaign in two managed
# buckets is counted once), so global total != sum of per-group totals when
# campaigns are shared — intended, do NOT "fix" it to match. Only campaigns that
# land in >=1 surfaced bucket count toward the global (a created_by-only campaign
# with external owner+executor is out of the manager's relevance).
#
# CACHE: ('campaigns',) only, NO 'activities'. These read ONLY
# CampaignAccount.status; every status change is a CampaignAccount write —
# INCLUDING the activity-completion cascade (complete a campaign activity ->
# contact final -> _check_account_completion -> campaign_account.mark_* ->
# CampaignAccount write). So the campaigns tag bumps correctly without the
# coarse activities tag (which campaign_progress needs only for its
# meta.objectives, not computed here).
# ============================================================================


def _grouped_campaign_progress(auth_ctx, scope, owner_path, executor_path, keep_ids):
    """ONE grouped query -> per-campaign rows carrying owner + executor group ids;
    fan out in Python to buckets (owner AND executor, set-deduped). Global is the
    sum of the rows that land in >=1 kept bucket, counted ONCE. keep_ids limits
    surfaced buckets to the manager's hierarchy (None -> keep all, client scope).
    Returns (buckets{id:{total,done}}, global_total, global_done)."""
    campaigns = Campaign.objects.filter(
        client_id=auth_ctx.client_id, status=CampaignStatus.ACTIVE
    )
    campaigns = apply_role_scope(
        campaigns, module='campaigns', scope=scope, auth_ctx=auth_ctx
    )
    rows = (
        CampaignAccount.objects
        .filter(client_id=auth_ctx.client_id, campaign__in=campaigns)
        .values('campaign', owner_path, executor_path)
        .annotate(total=Count('id'), done=Count('id', filter=CAMPAIGN_DONE_Q))
    )                                                              # ONE query

    buckets = {}
    g_total = g_done = 0
    for r in rows:
        total, done = r['total'], r['done']
        groups = {r[owner_path], r[executor_path]}
        groups.discard(None)
        kept = [str(g) for g in groups if keep_ids is None or str(g) in keep_ids]
        if not kept:
            continue  # not in the manager's hierarchy -> out of buckets AND global
        g_total += total
        g_done += done  # once per campaign that appears in >=1 kept bucket
        for gid in kept:
            b = buckets.setdefault(gid, {'total': 0, 'done': 0})
            b['total'] += total
            b['done'] += done
    return buckets, g_total, g_done


def _breakdown_result(definition, scope, dimension, buckets, g_total, g_done, labels):
    return KPIResult(
        key=definition.key, shape=OutputShape.BREAKDOWN,
        value={gid: _pct(b['done'], b['total']) for gid, b in buckets.items()},
        scope=scope,
        meta={
            'dimension': dimension,
            'labels': labels,
            'per_group': {gid: {'total': b['total'], 'done': b['done'],
                                'progress_pct': _pct(b['done'], b['total'])}
                          for gid, b in buckets.items()},
            # GLOBAL counts each campaign ONCE (see module note): with shared
            # campaigns, global total < sum of per-group totals. Intended.
            'global': {'total': g_total, 'done': g_done,
                       'progress_pct': _pct(g_done, g_total)},
        },
    )


def _campaign_progress_by_team(definition, auth_ctx, scope, period, params):
    keep = _managed_team_ids(auth_ctx) if scope == 'team' else None
    buckets, g_total, g_done = _grouped_campaign_progress(
        auth_ctx, scope, 'campaign__owner__team', 'campaign__executor__team', keep,
    )
    return _breakdown_result(
        definition, scope, 'team', buckets, g_total, g_done,
        _team_labels(list(buckets.keys())),
    )


def _campaign_progress_by_owner(definition, auth_ctx, scope, period, params):
    if scope == 'team':
        teams = _managed_team_ids(auth_ctx)
        keep = get_team_member_ids(teams, auth_ctx.client_id) if teams else set()
        keep.add(str(auth_ctx.user_id))  # the manager may own/execute campaigns too
    else:
        keep = None
    buckets, g_total, g_done = _grouped_campaign_progress(
        auth_ctx, scope, 'campaign__owner', 'campaign__executor', keep,
    )
    return _breakdown_result(
        definition, scope, 'owner', buckets, g_total, g_done,
        _person_labels(list(buckets.keys())),
    )


# KPI 2b — campaign progress aggregated BY TEAM (the manager Home's first level).
campaign_progress_by_team = KPIDefinition(
    key='campaign_progress_by_team',
    label='Campaign progress by team',
    scope_module='campaigns',
    output_shape=OutputShape.BREAKDOWN,
    dimension='team',
    allowed_scopes=('team', 'client'),
    cache_tags=('campaigns',),   # NO 'activities' — see module note above
    invalidation_sources=(
        'module_campaigns.Campaign',
        'module_campaigns.CampaignAccount',
    ),
    compute_fn=_campaign_progress_by_team,
)


# KPI 2c — campaign progress aggregated BY OWNER (the "who's behind" drill-down).
campaign_progress_by_owner = KPIDefinition(
    key='campaign_progress_by_owner',
    label='Campaign progress by owner',
    scope_module='campaigns',
    output_shape=OutputShape.BREAKDOWN,
    dimension='owner',
    allowed_scopes=('team', 'client'),
    cache_tags=('campaigns',),
    invalidation_sources=(
        'module_campaigns.Campaign',
        'module_campaigns.CampaignAccount',
    ),
    compute_fn=_campaign_progress_by_owner,
)


KPIS = [
    campaign_progress,
    campaign_coverage,
    campaign_progress_by_team,
    campaign_progress_by_owner,
]
