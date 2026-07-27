# app_modules/quotas/services/progress.py
"""
Quota progress — current value and attainment ratio of a personal objective.

This service CONSUMES the canonical formulas in app_modules/bi/metrics (sub-step
1); it never re-implements a calculation. It lives in the quotas module (not in
bi) because quotas depends on bi/metrics — the reverse would be circular.

Perimeter rule (PO decision) — the base data a quota is measured over depends on
the TIER OF ITS OWNER, not on who is looking:
- individual owner -> the owner's own data (metric ``user=owner``);
- manager owner    -> the whole SUBTREE rooted at the owner's team node: the
  node's members plus every descendant team's members, recursively to the leaves
  (``Team`` is a self-FK hierarchy). The objective is the manager's, but its
  value is the team's real production — a manager on a high node measures
  everything under them, not just their direct members;
- admin owner      -> the whole tenant.
Tenant isolation is always applied first and never bypassed.

The attainment ratio is value / target and is NOT clamped: over-achievement
(ratio > 1) stays visible — that is the point of the sub-step 5 display.

Batch computation groups quotas that share the same (metric, perimeter, window,
campaign) so the metric runs once per group, never once per quota (no N+1).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.models import Activity
from app_modules.bi import metrics
from app_modules.bi.metrics import MetricKey
from app_modules.decision_cycles.models import DecisionCycle


# Per-metric wiring: the canonical function, its base model, and the field that
# reaches the OWNER's team from that base (for the manager perimeter). The owner
# path mirrors each metric's own ``user=`` filter: DC metrics own on ``owner``,
# MEETINGS on the activity's cycle owner, NEW_LOGOS on ``account_owner``.
_SPEC = {
    MetricKey.DECISION_CYCLES: (metrics.decision_cycles, DecisionCycle, 'owner__team_id'),
    MetricKey.LEADS: (metrics.leads, DecisionCycle, 'owner__team_id'),
    MetricKey.PIPELINE_VALUE: (metrics.pipeline_value, DecisionCycle, 'owner__team_id'),
    MetricKey.REVENUE_WON: (metrics.revenue_won, DecisionCycle, 'owner__team_id'),
    MetricKey.MEETINGS: (metrics.meetings, Activity, 'decision_step__cycle__owner__team_id'),
    MetricKey.NEW_LOGOS: (metrics.new_logos, CompanyAccount, 'account_owner__team_id'),
}


@dataclass(frozen=True)
class QuotaProgress:
    """Progress of one quota. ``ratio`` is value/target, NOT clamped."""
    current_value: float
    target_value: float
    ratio: Optional[float]        # None when target_value <= 0 (undefined)

    @property
    def is_over_achieved(self) -> bool:
        return self.ratio is not None and self.ratio > 1.0


def _owner_tier(owner) -> str:
    """The owner's tier ('admin' | 'manager' | 'individual'). A user with no
    role falls back to the narrowest perimeter ('individual')."""
    role = getattr(owner, 'role', None)
    return role.get_tier() if role is not None else 'individual'


def _perimeter_key(owner):
    """Identity of the perimeter this owner's quota is measured over, so two
    quotas with the same (metric, window, campaign) AND the same perimeter share
    a single metric call. Individual -> the owner; manager -> the team; admin ->
    the tenant."""
    tier = _owner_tier(owner)
    if tier == 'manager':
        return ('manager', owner.team_id)
    if tier == 'admin':
        return ('admin', owner.client_account_id)
    return ('individual', owner.id)


def team_subtree_ids(team_id, client_id):
    """All team ids in the subtree ROOTED at ``team_id`` — the node itself plus
    every descendant, at any depth.

    Team carries a plain self-FK hierarchy (``Team.parent_team``) with no tree
    library and no DB constraint forbidding a cycle, so the descent is done here:
    - ONE query loads the client's (id, parent_team_id) adjacency, then the
      traversal is in-memory — the query count is CONSTANT regardless of the
      tree's depth or size (a WITH RECURSIVE CTE would also be one query; this
      form keeps it portable and needs no raw SQL);
    - the traversal is iterative with a ``seen`` guard, so a cycle
      (A -> B -> A) terminates instead of recursing forever.

    Returns a set of team ids (the node included). Empty when ``team_id`` is None.
    """
    if team_id is None:
        return set()

    from end_users.models import Team

    children = defaultdict(list)
    for row in Team.objects.filter(client_account_id=client_id).values('id', 'parent_team_id'):
        if row['parent_team_id'] is not None:
            children[row['parent_team_id']].append(row['id'])

    seen = set()
    stack = [team_id]
    while stack:
        tid = stack.pop()
        if tid in seen:                 # cycle / already-visited guard
            continue
        seen.add(tid)
        stack.extend(children.get(tid, ()))
    return seen


def compute_metric_for_team_node(metric, team_id, client_id, *, period=None,
                                 source_campaign=None) -> float:
    """Current value of ``metric`` aggregated over the team subtree rooted at
    ``team_id`` (the node AND all its descendants), for an ARBITRARY node — not
    only the current manager's. Sub-step 5 reuses this to decompose a manager's
    aggregate by direct child node.

    The perimeter is expressed by bounding the base queryset to the subtree's
    owners (``<owner>__team_id__in``); the canonical function then runs its own
    isolated aggregate — no fan-out join. One query for the subtree ids + one for
    the metric, independent of the tree depth."""
    fn, model, team_field = _SPEC[metric]
    ids = team_subtree_ids(team_id, client_id)
    if not ids:
        return fn(model.objects.none(), period=period, source_campaign=source_campaign)
    base = model.objects.filter(client_id=client_id, **{f'{team_field}__in': ids})
    return fn(base, period=period, source_campaign=source_campaign)


def _compute_value(metric, owner, period, source_campaign) -> float:
    """Run the canonical metric for one (metric, owner-perimeter, window,
    campaign). One isolated metric call — the perimeter is expressed by bounding
    the base queryset (team) or via the metric's own ``user=`` filter
    (individual), never a fan-out join."""
    fn, model, team_field = _SPEC[metric]
    client_id = owner.client_account_id
    tier = _owner_tier(owner)

    if tier == 'individual':
        base = model.objects.filter(client_id=client_id)
        return fn(base, user=owner, period=period, source_campaign=source_campaign)

    if tier == 'manager':
        # The manager's aggregate is the REAL production of the WHOLE subtree
        # rooted at their team node — the node plus every descendant (regions,
        # countries, ...), recursively to the leaves. A manager on a high node
        # with no direct members still measures everything under them. A manager
        # with no team measures an empty aggregate.
        return compute_metric_for_team_node(
            metric, owner.team_id, client_id, period=period, source_campaign=source_campaign
        )

    # admin -> whole tenant.
    base = model.objects.filter(client_id=client_id)
    return fn(base, period=period, source_campaign=source_campaign)


def _ratio(value, target) -> Optional[float]:
    target = float(target or 0)
    if target <= 0:
        return None
    return float(value) / target


def compute_progress_batch(quotas) -> dict:
    """Progress for a list of quotas, keyed by quota id. Quotas sharing the same
    (metric, perimeter, window, campaign) trigger ONE metric call — the query
    count grows with the number of distinct groups, not with the number of
    quotas. Owners are loaded once (single query) to resolve tier/team without a
    per-quota role lookup."""
    quotas = list(quotas)
    if not quotas:
        return {}

    # One query: resolve every owner (tier + team) up front.
    from end_users.models import User
    owner_ids = {q.owner_id for q in quotas}
    owners = {
        u.id: u
        for u in User.objects.filter(id__in=owner_ids).select_related('role')
    }

    # Group by (metric, perimeter, window, campaign). The VALUE is shared across a
    # group; only target_value (hence ratio) varies per quota.
    groups = defaultdict(list)
    for q in quotas:
        owner = owners[q.owner_id]
        gkey = (
            q.metric,
            _perimeter_key(owner),
            (q.period_start, q.period_end),
            q.source_campaign_id,
        )
        groups[gkey].append((q, owner))

    results = {}
    for (metric, _pkey, period, _cid), items in groups.items():
        q0, owner0 = items[0]
        value = _compute_value(metric, owner0, period, q0.source_campaign)
        for q, _owner in items:
            results[q.id] = QuotaProgress(
                current_value=value,
                target_value=float(q.target_value),
                ratio=_ratio(value, q.target_value),
            )
    return results


def compute_progress(quota) -> QuotaProgress:
    """Progress for a single quota."""
    return compute_progress_batch([quota])[quota.id]
