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

from datetime import timedelta

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


# Todo windows (forward-looking + overdue) for the Rep todo table filters.
# ROLLING windows (not calendar): today ⊂ next_7_days ⊂ next_4_weeks; overdue is
# the past. Rolling so the horizon never degenerates at a calendar boundary (on
# the 29th "this month" would show almost nothing) — there is always a useful
# look-ahead.
class TodoWindow:
    OVERDUE = 'overdue'
    TODAY = 'today'
    NEXT_7_DAYS = 'next_7_days'
    NEXT_4_WEEKS = 'next_4_weeks'


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


def build_todo_population(auth_ctx, scope):
    """THE single definition of "my todo": the open activities the requesting
    user must act on. Owner + C6 (role-scoped via apply_role_scope) UNION
    invited-&-ACCEPTED (always personal), deduplicated by id, carrying the
    ``_effective_date = COALESCE(due_date, scheduled_date)`` and ``due_bucket``
    annotations from todo_activities_source().

    Both the count KPIs (_todo_compute, _todo_windows_compute) AND the /bi/todo/
    list endpoint read THIS queryset, so a window's counter and its rows are the
    SAME population BY CONSTRUCTION — never a "5 shown above 4 rows" divergence.
    Tenant + role scope are applied here, exactly as the viewsets do.
    """
    base = todo_activities_source().filter(client_id=auth_ctx.client_id)  # tenant filter

    # Path 1 — owner + C6 via the shared primitive (mine / team / client + C6).
    owner = apply_role_scope(
        base, module='activities', scope=scope, auth_ctx=auth_ctx
    )

    # Path 2 — invited & ACCEPTED, ALWAYS the requesting user (Option A): an
    # accepted invitation is personal and does not widen with the scope.
    invited = base.filter(invited_users=auth_ctx.user_id).filter(
        _accepted_invitation_exists(auth_ctx)
    )

    # UNION deduplicated by id: one row per activity even if owned AND invited.
    return base.filter(
        Q(pk__in=owner.values('pk')) | Q(pk__in=invited.values('pk'))
    )


def build_team_todo_population(auth_ctx, scope):
    """THE manager view's team todo ROWS: the open activities (TODO_STATUSES) a
    manager is responsible for, role-scoped via apply_role_scope, carrying the
    ``_effective_date = COALESCE(due_date, scheduled_date)`` annotation for
    sorting and serialisation.

    This is the ROW counterpart of the ``todo_team_by_owner`` COUNT KPI: both
    read ``todo_activities_source()`` (SAME ``TODO_STATUSES`` constant) and apply
    the SAME ``apply_role_scope(module='activities', scope=...)`` over the SAME
    tenant filter — so a person's row count here equals their bucket in that KPI
    BY CONSTRUCTION, never a "shown above ≠ rows" divergence.

    Unlike ``build_todo_population`` it does NOT union the personal
    invited-&-accepted path: the manager table is a view of the TEAM's OWNED
    work, not the manager's personal inbox, so an activity the manager was merely
    invited to (even accepted) never appears here.
    """
    base = todo_activities_source().filter(client_id=auth_ctx.client_id)  # tenant filter
    return apply_role_scope(
        base, module='activities', scope=scope, auth_ctx=auth_ctx
    )


def todo_window_q(window, today):
    """The predicate defining a todo window on ``_effective_date``. SINGLE source
    of the window boundaries, used by BOTH the window counts and the /bi/todo/
    list so "today count" and "today rows" are identical. Windows are
    forward-looking and nested (today ⊂ next_7_days ⊂ next_4_weeks); overdue is
    the past. Windows are ROLLING (relative to today), so the horizon never
    collapses at a calendar boundary. An unknown/None window returns an empty Q
    (the whole population)."""
    if window == TodoWindow.OVERDUE:
        return Q(_effective_date__lt=today)
    if window == TodoWindow.TODAY:
        return Q(_effective_date=today)
    if window == TodoWindow.NEXT_7_DAYS:
        return Q(_effective_date__gte=today, _effective_date__lte=today + timedelta(days=7))
    if window == TodoWindow.NEXT_4_WEEKS:
        return Q(_effective_date__gte=today, _effective_date__lte=today + timedelta(days=28))
    return Q()


def _todo_compute(definition, auth_ctx, scope, period, params):
    """Todo counts by due-bucket. Reads the shared build_todo_population so it
    stays iso with the /bi/todo/ list."""
    final = _apply_period(
        build_todo_population(auth_ctx, scope), _TODO_PERIOD_FIELD, period
    )

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


def _windows_over(pop, today):
    """The 4 window counts over a todo population, in ONE query via conditional
    aggregation. SHARED by the rep (build_todo_population) and manager
    (build_team_todo_population) window KPIs so the tile counts always use the
    exact same window predicates as the /bi/todo/ list — parity by construction,
    whichever population the caller passes."""
    agg = pop.aggregate(
        overdue=Count('id', filter=todo_window_q(TodoWindow.OVERDUE, today)),
        today=Count('id', filter=todo_window_q(TodoWindow.TODAY, today)),
        next_7_days=Count('id', filter=todo_window_q(TodoWindow.NEXT_7_DAYS, today)),
        next_4_weeks=Count('id', filter=todo_window_q(TodoWindow.NEXT_4_WEEKS, today)),
    )
    return {
        TodoWindow.OVERDUE: agg['overdue'] or 0,
        TodoWindow.TODAY: agg['today'] or 0,
        TodoWindow.NEXT_7_DAYS: agg['next_7_days'] or 0,
        TodoWindow.NEXT_4_WEEKS: agg['next_4_weeks'] or 0,
    }


def _todo_windows_compute(definition, auth_ctx, scope, period, params):
    """Counts of the REP todo population per FORWARD window (+ overdue). Same
    population (build_todo_population: owner+C6 UNION invited-accepted) and same
    window predicates as the /bi/todo/ list → counters and rows match."""
    value = _windows_over(build_todo_population(auth_ctx, scope), timezone.now().date())
    return KPIResult(
        key=definition.key,
        shape=OutputShape.BREAKDOWN,
        value=value,
        scope=scope,
        meta={'scope_module': definition.scope_module},
    )


def _team_todo_windows_compute(definition, auth_ctx, scope, period, params):
    """Counts of the MANAGER team todo population per window. Reads
    build_team_todo_population — the SAME source as /bi/todo/team/ (role-scoped,
    NO personal invited-accepted union) — so the manager's tiles and the team
    table match by construction. Reusing todo_my_windows at scope='team' would
    read build_todo_population instead and fold the manager's OWN accepted
    invitations into the tiles, breaking that parity."""
    value = _windows_over(build_team_todo_population(auth_ctx, scope), timezone.now().date())
    return KPIResult(
        key=definition.key,
        shape=OutputShape.BREAKDOWN,
        value=value,
        scope=scope,
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


# Todo BY WINDOW — the Rep todo table's tiles (overdue / today / this week /
# this month). Counts from build_todo_population + todo_window_q, i.e. the SAME
# population and SAME window predicates the /bi/todo/ list uses → each tile's
# count equals its window's row count by construction.
todo_my_windows = KPIDefinition(
    key='todo_my_windows',
    label='Todo — my activities by window (overdue / today / this week / this month)',
    scope_module='activities',
    period_field=_TODO_PERIOD_FIELD,
    output_shape=OutputShape.BREAKDOWN,
    dimension='window',
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('activities', 'notifications'),
    invalidation_sources=(
        'module_activities.Activity',
        'module_notifications.Notification',
    ),
    compute_fn=_todo_windows_compute,
)


# Team todo BY WINDOW — the Manager Home's tiles (same 4 windows as the rep).
# Reads build_team_todo_population (the /bi/todo/team/ source), so each tile's
# count equals that window's team-table row count by construction. NO
# 'notifications' tag: the team population has no invited-accepted union, so an
# invitation accept/decline does not change it (mirrors todo_team_by_owner).
todo_team_windows = KPIDefinition(
    key='todo_team_windows',
    label='Todo — team open activities by window (overdue / today / this week / this month)',
    scope_module='activities',
    period_field=_TODO_PERIOD_FIELD,
    output_shape=OutputShape.BREAKDOWN,
    dimension='window',
    allowed_scopes=('team', 'client'),
    cache_tags=('activities',),
    invalidation_sources=('module_activities.Activity',),
    compute_fn=_team_todo_windows_compute,
)


KPIS = [
    todo_my_activities,
    todo_team_by_owner,
    todo_my_windows,
    todo_team_windows,
]
