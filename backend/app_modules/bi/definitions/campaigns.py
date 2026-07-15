# app_modules/bi/definitions/campaigns.py
"""
Campaign KPI definitions.

KPI 2 — Campaign progress + objectives. A single KPI (parameterized by
campaign_id) that returns, for one campaign:
- value = campaign advancement = CampaignAccount completion rate (COMPLETED /
  total), matching the existing dashboard's completion_rate;
- meta.objectives = per objective_type: {target, current, progress_pct}, where
  current reuses CampaignObjective.get_current_value() (the existing service
  metric logic — MODULE objectives, not legacy).

It is one KPI, not two: same subject (a campaign), same scope, same
cache/invalidation, computed in one bounded pass.

Custom compute (ratio + parameterized), so it uses the compute_fn escape hatch
and obeys the two rules: it scopes the CAMPAIGN via apply_role_scope (owner +
executor via OWNERSHIP_MAP assigned_to_user='executor', so another user's
campaign is not visible), and it is query-bounded: campaign fetch + accounts
aggregate + objectives load + one query per objective (K <= 6 per campaign).
"""

from django.db.models import Count, Q

from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    FINAL_ACCOUNT_STATES,
    FINAL_CONTACT_STATES,
)
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_account import CampaignAccount
from app_modules.campaigns.models.campaign_contact import CampaignContact
from app_modules.campaigns.models.campaign_objective import CampaignObjective
from permissions.scope_filter import apply_role_scope


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
    agg = CampaignAccount.objects.filter(campaign=campaign).aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status=CampaignAccountStatus.COMPLETED)),
    )                                                              # query 2
    total = agg['total'] or 0
    completed = agg['completed'] or 0
    completion_rate = round((completed / total) * 100, 1) if total else 0.0

    # Objective advancement — current/target per objective_type. campaign is
    # prefetched so get_current_value() is one query per objective.
    objectives = list(
        CampaignObjective.objects.filter(campaign=campaign).select_related('campaign')
    )                                                              # query 3
    objective_rows = []
    for obj in objectives:
        current = float(obj.get_current_value() or 0)              # 1 query / objective
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
            'accounts_total': total,
            'accounts_completed': completed,
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


KPIS = [
    campaign_progress,
    campaign_coverage,
]
