# app_modules/quotas/services/progress.py
"""
Quota progress — current value and attainment ratio of a personal objective.

This service CONSUMES the canonical formulas in app_modules/bi/metrics (sub-step
1); it never re-implements a calculation. It lives in the quotas module (not in
bi) because quotas depends on bi/metrics — the reverse would be circular.

Perimeter rule (PO decision) — the base data a quota is measured over depends on
the TIER OF ITS OWNER, not on who is looking:
- individual owner -> the owner's own data (metric ``user=owner``). "Own" is
  declared in bi/metrics/attribution_scope and is not one rule for all five:
  the metrics measuring a DEAL (pipeline, won, new logos) take the union owner
  OR creator OR account owner, so a deal handed from an SDR to an AE stays in
  BOTH their attainments; the metrics counting an ACT (decision cycles,
  meetings) take ``created_by``, because one person opens a deal and one person
  holds a meeting;
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
from app_modules.bi.metrics.attribution_scope import (
    account_scope_q_for_teams,
    creator_scope_q_for_teams,
    cycle_scope_q_for_teams,
)
from app_modules.decision_cycles.models import DecisionCycle


# Per-metric wiring: the canonical function, its base model, and the predicate
# that bounds that base to a TEAM SUBTREE (for the manager perimeter).
#
# The team predicate is the queryset-level twin of the metric's own ``user=``
# filter — the SAME rule with ``= user`` replaced by ``__team_id__in``, taken
# from bi/metrics/attribution_scope so the personal and manager readings cannot
# drift. It used to be a single field path per metric, which was only expressible
# while a metric belonged to exactly one owner field.
#
# Two rules, matching the two kinds of metric: the ones measuring a DEAL take the
# three-branch union, the ones counting an ACT take its creator.
_SPEC = {
    MetricKey.DECISION_CYCLES: (metrics.decision_cycles, DecisionCycle,
                                creator_scope_q_for_teams),
    MetricKey.PIPELINE_VALUE: (metrics.pipeline_value, DecisionCycle,
                               cycle_scope_q_for_teams),
    MetricKey.REVENUE_WON: (metrics.revenue_won, DecisionCycle,
                            cycle_scope_q_for_teams),
    MetricKey.MEETINGS: (metrics.meetings, Activity,
                         creator_scope_q_for_teams),
    MetricKey.NEW_LOGOS: (metrics.new_logos, CompanyAccount,
                          account_scope_q_for_teams),
}


@dataclass(frozen=True)
class QuotaProgress:
    """Progress of one quota. ``ratio`` is value/target, NOT clamped, so
    over-achievement stays visible.

    No ``is_over_achieved`` helper: the serializer emits ``current_value`` and
    ``progress_ratio`` only (quotas/serializers.py:35-36), and the UI decides
    what counts as over-achieved from the ratio
    (frontend GoalProgressRow.jsx:35). One rule, one place — the helper here was
    a second copy that nothing in production read.
    """
    current_value: float
    target_value: float
    ratio: Optional[float]        # None when target_value <= 0 (undefined)


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

    The perimeter is expressed by bounding the base queryset with the metric's
    team predicate (attribution_scope, the widened form of its own ``user=``
    rule); the canonical function then runs its own isolated aggregate — no
    fan-out join. One query for the subtree ids + one for the metric,
    independent of the tree depth.

    Rows are DEDUPED, not summed per member: a deal created by an SDR and owned
    by an AE who are both in the subtree is ONE row here, counted once, while it
    counts for each of the two reps individually. The team has one deal; the two
    reps each delivered it. See attribution_scope for why both are right."""
    fn, model, team_q = _SPEC[metric]
    ids = team_subtree_ids(team_id, client_id)
    if not ids:
        return fn(model.objects.none(), period=period, source_campaign=source_campaign)
    base = model.objects.filter(client_id=client_id).filter(team_q(ids))
    return fn(base, period=period, source_campaign=source_campaign)


def _compute_value(metric, owner, period, source_campaign) -> float:
    """Run the canonical metric for one (metric, owner-perimeter, window,
    campaign). One isolated metric call — the perimeter is expressed by bounding
    the base queryset (team) or via the metric's own ``user=`` filter
    (individual), never a fan-out join.

    A metric this dispatch does not know reports 0, it does not raise.
    ``Quota.metric`` is a plain CharField — ``choices`` is checked on write and
    never enforced by the database — so a row saved under a metric that has
    since been retired (LEADS) outlives the vocabulary. Raising here would take
    down the whole objectives list over one dead row instead of just that row.
    Nothing is deleted or rewritten: the stale row stays visible, at 0 against
    its original target, which is what makes it findable."""
    spec = _SPEC.get(metric)
    if spec is None:
        return 0.0
    fn, model, _team_q = spec
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
