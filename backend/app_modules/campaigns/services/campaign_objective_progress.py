# app_modules/campaigns/services/campaign_objective_progress.py
"""
Batch progress for each campaign's PRIMARY objective (list / card payload).

The per-campaign calculation is CampaignAnalyticsService._calculate_objective_value
— the single source of truth the DETAIL serializer uses. Calling it once per
campaign while rendering a LIST page would be an N+1. This module computes the
SAME values for a whole page in a BOUNDED number of queries: the page's primary
objectives are grouped by objective_type and each type runs ONE aggregate grouped
by campaign, so the query count is bounded by the number of distinct objective
types on the page (<= 6) — never by the number of campaigns.

The grouped predicates mirror _calculate_objective_value branch for branch
(source_campaign for the DecisionCycle metrics, Activity.campaign for MEETINGS /
CONTACTS_REACHED, the CampaignAccount pivot for NEW_LOGOS). A parity test
(tests/campaigns/test_campaign_list_objective_progress.py) locks each grouped
result to the per-campaign calculation so the two paths can never drift.
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q, Sum

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle

from ..models import (
    CampaignAccount,
    CampaignAccountStatus,
    CampaignObjective,
    ObjectiveType,
)


def progress_percentage(current_value, target_value):
    """current/target as a 0-100 percentage, capped at 100.

    Identical rule to CampaignAnalyticsService.get_objectives_progress
    (round(.., 1) then min(.., 100.0)); 0.0 when the target is missing/<= 0.
    """
    if not target_value or float(target_value) <= 0:
        return 0.0
    return min(round((float(current_value) / float(target_value)) * 100, 1), 100.0)


def _grouped(queryset, group_field, aggregate):
    """{group_value: aggregate} for queryset.values(group_field).annotate(v=aggregate)."""
    return {
        row[group_field]: row['v']
        for row in queryset.values(group_field).annotate(v=aggregate)
    }


def _meetings_by_campaign(campaign_ids):
    """{campaign_id: meeting_count} under the SAME three-branch union as
    CampaignAnalyticsService._count_meetings: a completed MEETING counts for a
    campaign when its cycle's ``source_campaign`` is that campaign, OR its
    ``Activity.campaign`` is that campaign, OR its ``source_activity.campaign``
    is that campaign.

    ONE query fetches the page's completed meetings with the three attribution
    keys; the union tally is done in Python (a meeting attributing to a campaign
    through several keys counts once for that campaign; a meeting bridging two
    different campaigns counts once for each). ``decision_cycle`` and
    ``source_activity`` are to-one, so the joins never fan out. Query count stays
    bounded (one query for the whole page).
    """
    ids = set(campaign_ids)
    rows = (
        Activity.objects
        .filter(
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
        )
        .filter(
            Q(campaign_id__in=ids)
            | Q(decision_cycle__source_campaign_id__in=ids)
            | Q(source_activity__campaign_id__in=ids)
        )
        .values_list(
            'campaign_id',
            'decision_cycle__source_campaign_id',
            'source_activity__campaign_id',
        )
    )
    counts = defaultdict(int)
    for campaign_id, cycle_campaign_id, source_campaign_id in rows:
        keys = set()
        if campaign_id in ids:
            keys.add(campaign_id)
        if cycle_campaign_id in ids:
            keys.add(cycle_campaign_id)
        if source_campaign_id in ids:
            keys.add(source_campaign_id)
        for key in keys:
            counts[key] += 1
    return dict(counts)


def _values_for_type(objective_type, campaign_ids, client_id):
    """{campaign_id: current_value} for one objective_type in ONE grouped query.

    The predicates MIRROR CampaignAnalyticsService._calculate_objective_value.
    """
    if objective_type == ObjectiveType.DECISION_CYCLES:
        qs = DecisionCycle.objects.filter(source_campaign_id__in=campaign_ids)
        return _grouped(qs, 'source_campaign', Count('id'))

    if objective_type == ObjectiveType.PIPELINE_VALUE:
        qs = DecisionCycle.objects.filter(
            source_campaign_id__in=campaign_ids, outcome__isnull=True,
        )
        return _grouped(qs, 'source_campaign', Sum('estimated_value'))

    if objective_type == ObjectiveType.REVENUE_WON:
        qs = DecisionCycle.objects.filter(
            source_campaign_id__in=campaign_ids, outcome=CycleOutcome.WON,
        )
        return _grouped(qs, 'source_campaign', Sum('estimated_value'))

    if objective_type == ObjectiveType.MEETINGS:
        return _meetings_by_campaign(campaign_ids)

    if objective_type == ObjectiveType.CONTACTS_REACHED:
        qs = Activity.objects.filter(
            campaign_id__in=campaign_ids, status=ActivityStatus.COMPLETED,
        )
        return _grouped(qs, 'campaign', Count('contacts', distinct=True))

    if objective_type == ObjectiveType.NEW_LOGOS:
        qs = CampaignAccount.objects.filter(
            campaign_id__in=campaign_ids,
            status=CampaignAccountStatus.COMPLETED,
            account__type='CLIENT',
        )
        return _grouped(qs, 'campaign', Count('id'))

    return {}


def compute_primary_objective_progress_batch(campaigns, client_id):
    """{campaign_id: {'current_value': float, 'progress_percentage': float}}.

    One grouped query per distinct objective_type present on the page (<= 6),
    plus one query to load the page's primary objectives — never one query per
    campaign. Campaigns with no primary objective are simply absent from the map.
    """
    campaign_ids = [c.id for c in campaigns]
    if not campaign_ids:
        return {}

    # ONE query: the page's primary objectives.
    primaries = {
        obj.campaign_id: obj
        for obj in CampaignObjective.objects.filter(
            campaign_id__in=campaign_ids, is_primary=True, client_id=client_id,
        )
    }
    if not primaries:
        return {}

    ids_by_type = defaultdict(list)
    for campaign_id, obj in primaries.items():
        ids_by_type[obj.objective_type].append(campaign_id)

    # One grouped aggregate per objective_type -> {campaign_id: current_value}.
    current_by_campaign = {}
    for objective_type, ids in ids_by_type.items():
        current_by_campaign.update(_values_for_type(objective_type, ids, client_id))

    result = {}
    for campaign_id, obj in primaries.items():
        current = float(current_by_campaign.get(campaign_id, 0) or 0)
        result[campaign_id] = {
            'current_value': current,
            'progress_percentage': progress_percentage(current, obj.target_value),
        }
    return result
