# app_modules/bi/definitions/aggregates.py
"""
Shared helpers for the manager "by team / by owner" AGGREGATE KPIs.

One home for the group percentage, the id->label resolution, and the managed
hierarchy so the campaign and territory aggregates surface the same buckets the
same way (same discipline as CAMPAIGN_DONE_Q / build_todo_population — one
definition, many consumers, never a copy).
"""

from permissions.owner_scope import get_all_descendant_team_ids


def pct(done, total):
    return round(100.0 * done / total, 1) if total else 0.0


def team_labels(ids):
    """id -> team name, one query (empty ids -> no query)."""
    from end_users.models import Team
    return {str(t['id']): t['name']
            for t in Team.objects.filter(id__in=ids).values('id', 'name')}


def person_labels(ids):
    """id -> "First Last" (falling back to email), one query."""
    from end_users.models import User
    labels = {}
    for u in User.objects.filter(id__in=ids).values('id', 'first_name', 'last_name', 'email'):
        full = f"{(u['first_name'] or '').strip()} {(u['last_name'] or '').strip()}".strip()
        labels[str(u['id'])] = full or u['email']
    return labels


def managed_team_ids(auth_ctx):
    """The manager's managed subtree team ids: teams he manages directly (+ his
    own team) and all descendants. The SAME set apply_role_scope('team') is built
    on; used to surface ONLY the manager's hierarchy (relevance)."""
    from end_users.models import Team
    roots = {str(t) for t in Team.objects.filter(
        client_account_id=auth_ctx.client_id, manager_id=auth_ctx.user_id
    ).values_list('id', flat=True)}
    if getattr(auth_ctx, 'team_id', None):
        roots.add(str(auth_ctx.team_id))
    return get_all_descendant_team_ids(roots, auth_ctx.client_id) if roots else set()
