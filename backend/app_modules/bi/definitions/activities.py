# app_modules/bi/definitions/activities.py
"""
Activity KPI definitions.

KPI 1 — Todo / my activities: the rep's open activities (status PLANNED or
ON_HOLD), bucketed by due-ness (overdue / today / upcoming / no_date) on the
effective date = COALESCE(due_date, scheduled_date).

Two membership paths into the todo, UNIONed and deduplicated by activity id
(Palier 3c — closes the "accept an invitation -> it enters my todo" loop):

  1. OWNER + C6 — activities scoped by the shared role primitive
     (apply_role_scope('activities')): owner + account-owner inheritance.
     This path widens with the scope (mine / team / client).

  2. INVITED & ACCEPTED — activities where the REQUESTING user is an invitee
     AND has an ACCEPTED E2 invitation notification for that activity
     (Notification: category=ACTIVITY_INVITATION, recipient=me,
     related_object_id=activity, response_status=ACCEPTED). This path is
     INTRINSICALLY personal (accepting is an individual act), so it is ALWAYS
     anchored on the requesting user and does NOT widen with the scope
     (Option A). PENDING / DECLINED invitations are excluded — the product
     rule of the loop.

Because the standard pipeline applies a SINGLE apply_role_scope to the whole
source, it cannot express "owner OR (invited AND accepted)" (the invited rows
would be filtered out by the owner scope). So this KPI uses the compute_fn
escape hatch: the owner path is role-scoped, the invited path is self-anchored,
and the two id-sets are UNIONed. Bucketing and the BREAKDOWN shape are
unchanged. The compute stays query-bounded (the invited path is an EXISTS
sub-query, not an N+1).
"""

from django.db.models import Case, CharField, Count, Exists, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.bi.compute import _apply_period
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import KPIResult, OutputShape
from app_modules.notifications.models import (
    Notification, NotificationCategory, NotificationResponseStatus,
)
from permissions.scope_filter import apply_role_scope


# Todo due-buckets (breakdown dimension values).
class TodoBucket:
    OVERDUE = 'overdue'
    TODAY = 'today'
    UPCOMING = 'upcoming'
    NO_DATE = 'no_date'


# Open statuses that make an activity a "todo".
TODO_STATUSES = (ActivityStatus.PLANNED, ActivityStatus.ON_HOLD)

# Period field for the (optional) due-date window.
_TODO_PERIOD_FIELD = 'due_date'


def todo_activities_source():
    """Base todo population, annotated with the due bucket.

    Shared, UNSCOPED base for BOTH membership paths (owner+C6, invited+accepted).
    `today` is resolved at call time; within the 30s cache TTL the buckets are
    stable, and a fresh compute re-resolves it across the boundary.
    """
    today = timezone.now().date()
    effective_date = Coalesce('due_date', 'scheduled_date')
    return (
        Activity.objects
        .filter(status__in=TODO_STATUSES)
        .annotate(_effective_date=effective_date)
        .annotate(due_bucket=Case(
            When(_effective_date__lt=today, then=Value(TodoBucket.OVERDUE)),
            When(_effective_date=today, then=Value(TodoBucket.TODAY)),
            When(_effective_date__gt=today, then=Value(TodoBucket.UPCOMING)),
            default=Value(TodoBucket.NO_DATE),
            output_field=CharField(),
        ))
    )


def _accepted_invitation_exists(auth_ctx):
    """EXISTS sub-query: an ACCEPTED E2 invitation for the requesting user that
    references the activity (correlated on Activity.pk). Tenant-filtered on the
    notification side too."""
    return Exists(
        Notification.objects.filter(
            recipient_id=auth_ctx.user_id,
            client_id=auth_ctx.client_id,
            category=NotificationCategory.ACTIVITY_INVITATION,
            response_status=NotificationResponseStatus.ACCEPTED,
            related_object_id=OuterRef('pk'),
        )
    )


def _todo_compute(definition, auth_ctx, scope, period, params):
    """Todo = (owner + C6, role-scoped) UNION (invited & ACCEPTED, personal),
    deduplicated by activity id, bucketed by due-ness."""
    base = todo_activities_source().filter(client_id=auth_ctx.client_id)  # tenant filter

    # Path 1 — owner + C6 via the shared primitive (mine / team / client + C6).
    owner = apply_role_scope(
        base, module=definition.scope_module, scope=scope, auth_ctx=auth_ctx
    )

    # Path 2 — invited & ACCEPTED, ALWAYS the requesting user (Option A): an
    # accepted invitation is personal and does not widen with the scope.
    invited = base.filter(invited_users=auth_ctx.user_id).filter(
        _accepted_invitation_exists(auth_ctx)
    )

    # UNION deduplicated by id: one row per activity even if owned AND invited.
    final = base.filter(
        Q(pk__in=owner.values('pk')) | Q(pk__in=invited.values('pk'))
    )
    final = _apply_period(final, _TODO_PERIOD_FIELD, period)

    rows = final.values('due_bucket').annotate(_value=Count('id'))
    value = {row['due_bucket']: row['_value'] for row in rows}

    return KPIResult(
        key=definition.key,
        shape=OutputShape.BREAKDOWN,
        value=value,
        scope=scope,
        period_start=period.start if period else None,
        period_end=period.end if period else None,
        meta={'scope_module': definition.scope_module},
    )


# KPI 1 — Todo / my activities, by due bucket (owner+C6 UNION invited-accepted).
# compute_fn (not standard) because the two membership paths need different
# scoping — the standard single apply_role_scope cannot host the union.
# Depends on Notification too: accepting/declining an invitation changes
# membership, so a Notification write must bust this KPI's cache.
todo_my_activities = KPIDefinition(
    key='todo_my_activities',
    label='Todo — my activities by due bucket',
    scope_module='activities',
    period_field=_TODO_PERIOD_FIELD,
    output_shape=OutputShape.BREAKDOWN,
    dimension='due_bucket',
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('activities', 'notifications'),
    invalidation_sources=(
        'module_activities.Activity',
        'module_notifications.Notification',
    ),
    compute_fn=_todo_compute,
)


def _owner_labels(owner_ids):
    """Resolve activity-owner ids to display names in ONE query.

    Receives ONLY the ids present in the (already scope-filtered) breakdown, so
    it never widens visibility beyond what the scope already returned. Mirrors
    User.get_full_name(), falling back to the email when no name is set.
    """
    from end_users.models import User

    labels = {}
    for u in User.objects.filter(id__in=owner_ids).values(
        'id', 'first_name', 'last_name', 'email'
    ):
        full = f"{(u['first_name'] or '').strip()} {(u['last_name'] or '').strip()}".strip()
        labels[u['id']] = full or u['email']
    return labels


# Team todo, BY OWNER — the manager view's "were today's tasks done, WITH
# NAMES". OPEN activities (PLANNED / ON_HOLD) grouped by owner (the responsible
# person). This is ONE standard-pipeline BREAKDOWN declaration: the per-person
# capability the manager view needs falls straight out of the registry via
# dimension='owner' — no bespoke compute. Manager scopes only; owner ids are
# resolved to names server-side via dimension_labels so the client never
# resolves N ids (and never sees any name outside the scoped breakdown).
todo_team_by_owner = KPIDefinition(
    key='todo_team_by_owner',
    label='Todo — team open activities by owner',
    scope_module='activities',
    source=lambda: Activity.objects.filter(status__in=TODO_STATUSES),
    aggregation=Count('id'),
    period_field=_TODO_PERIOD_FIELD,
    output_shape=OutputShape.BREAKDOWN,
    dimension='owner',
    allowed_scopes=('team', 'client'),
    dimension_labels=_owner_labels,
    cache_tags=('activities',),
    invalidation_sources=('module_activities.Activity',),
)


KPIS = [
    todo_my_activities,
    todo_team_by_owner,
]
