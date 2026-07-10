# app_modules/bi/definitions/activities.py
"""
Activity KPI definitions.

KPI 1 — Todo / my activities: the rep's open activities (status PLANNED or
ON_HOLD), bucketed by due-ness (overdue / today / upcoming / no_date) on the
effective date = COALESCE(due_date, scheduled_date). Scoped by the activities
role scope (owner + C6 account-owner inheritance), so a rep sees their own
open work plus open work on accounts they own.

The due bucket is a COMPUTED dimension, not a raw column, so it is annotated in
source() (a zero-arg callable) — the compute layer then does the usual
.values('due_bucket').annotate(Count). No change to the foundation.
"""

from django.db.models import Case, CharField, Count, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape


# Todo due-buckets (breakdown dimension values).
class TodoBucket:
    OVERDUE = 'overdue'
    TODAY = 'today'
    UPCOMING = 'upcoming'
    NO_DATE = 'no_date'


# Open statuses that make an activity a "todo".
TODO_STATUSES = (ActivityStatus.PLANNED, ActivityStatus.ON_HOLD)


def todo_activities_source():
    """Base todo population, annotated with the due bucket.

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
    # ---------------------------------------------------------------------
    # EXTENSION POINT — "accepted invitations" (C2 / Palier 3), OFF for now.
    # Once invitation ACCEPT/DECLINE exists (Notification.response_status or an
    # Activity-invitation through-model), the todo must also include activities
    # where the requesting user is an ACCEPTED invitee (invited_users=user,
    # response=ACCEPTED). That is a source/scope UNION added here; it does NOT
    # change the bucketing or the shape. Deliberately not wired this sprint.
    # ---------------------------------------------------------------------


# KPI 1 — Todo / my activities, by due bucket.
todo_my_activities = KPIDefinition(
    key='todo_my_activities',
    label='Todo — my activities by due bucket',
    source=todo_activities_source,
    aggregation=Count('id'),
    scope_module='activities',
    period_field='due_date',
    output_shape=OutputShape.BREAKDOWN,
    dimension='due_bucket',
    allowed_scopes=('mine', 'team', 'client'),
    cache_tags=('activities',),
    invalidation_sources=('module_activities.Activity',),
)


KPIS = [
    todo_my_activities,
]
