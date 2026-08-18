# app_modules/bi/quota.py
"""
Module-facing quota current-value computation (app_modules data).

Replaces the legacy UserPerformanceService raw-SQL path for SalesQuota
attainment: given a quota, compute its current value from app_modules models
(DecisionCycle, Activity), scoped to the quota's OWNER and period.

target_type mapping:
- closed_won   -> Σ total_deal_value of WON cycles in the period (by outcome_date)          [flow]
- pipeline     -> Σ total_deal_value of OPEN cycles right now (outcome NULL)                [STOCK — no period]
- meetings     -> count(Activity type=MEETING, COMPLETED) in the period (by scheduled_date) [flow]
- opportunities-> count(DecisionCycle) created in the period (by created_at)                [flow]
- leads_accepted / conversion_rate -> None (no clean app_modules source — "not available")

Each supported type is a SINGLE aggregate query; unsupported types return None
without touching the DB. Value is computed for the quota's owner (quota.user);
ACCESS control (who may read the quota) is the KPI's apply_role_scope, separate
from this value computation.
"""

from __future__ import annotations

from typing import Optional

from django.db.models import Sum

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.services.deal_value_sql import (
    DEAL_VALUE_ALIAS,
    annotate_deal_value,
)

# target_types with a clean app_modules mapping.
SUPPORTED_TARGET_TYPES = frozenset({'closed_won', 'pipeline', 'meetings', 'opportunities'})


def compute_quota_current_value(quota) -> Optional[float]:
    """Current value of `quota` from app_modules data, or None if the quota's
    target_type has no clean app_modules source (leads_accepted, conversion_rate)."""
    target_type = quota.target_type
    if target_type not in SUPPORTED_TARGET_TYPES:
        return None

    client_id = quota.client_id
    user_id = quota.user_id
    start, end = quota.period_start, quota.period_end

    if target_type == 'pipeline':
        # STOCK: everything currently open for the user (no period filter — a
        # deal opened 8 months ago is still in the pipe today).
        agg = annotate_deal_value(
            DecisionCycle.objects.filter(
                client_id=client_id, owner_id=user_id, outcome__isnull=True,
            )
        ).aggregate(total=Sum(DEAL_VALUE_ALIAS))
        return float(agg['total'] or 0)

    if target_type == 'closed_won':
        qs = DecisionCycle.objects.filter(
            client_id=client_id, owner_id=user_id, outcome=CycleOutcome.WON,
        )
        # Selected by STATUS (outcome=WON above), then windowed on the cycle's
        # single close date — same pairing as the modern quota path, see
        # metrics.revenue_won.
        if start is not None:
            qs = qs.filter(outcome_date__gte=start)
        if end is not None:
            qs = qs.filter(outcome_date__lte=end)
        agg = annotate_deal_value(qs).aggregate(total=Sum(DEAL_VALUE_ALIAS))
        return float(agg['total'] or 0)

    if target_type == 'meetings':
        qs = Activity.objects.filter(
            client_id=client_id, owner_id=user_id,
            activity_type=ActivityType.MEETING, status=ActivityStatus.COMPLETED,
        )
        if start is not None:
            qs = qs.filter(scheduled_date__gte=start)
        if end is not None:
            qs = qs.filter(scheduled_date__lte=end)
        return float(qs.count())

    # opportunities -> count of decision cycles created in the period.
    qs = DecisionCycle.objects.filter(client_id=client_id, owner_id=user_id)
    if start is not None:
        qs = qs.filter(created_at__date__gte=start)
    if end is not None:
        qs = qs.filter(created_at__date__lte=end)
    return float(qs.count())
