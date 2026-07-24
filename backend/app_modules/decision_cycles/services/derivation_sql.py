# app_modules/decision_cycles/services/derivation_sql.py
"""
SQL translation of StepStatusDerivationService._compute_status.

Single source of truth for a DecisionStep's derived status, expressed as ORM
annotations so a list queryset can carry the status without per-row Python or
extra queries. The Python service consumes this annotation when it is present
on a step (StepStatusDerivationService.derive / derive_bulk) and keeps its own
_compute_status as the parity oracle — see tests/decision_cycles/
test_derivation_parity.py, which asserts the annotation and the Python agree on
every branch.

No stored column, no TTL, no write: the status changes with the passage of
time (OVERDUE), so it is derived on read (never persisted).

JOIN CHOICE (deliberate — do not "fix" to decision_cycle_id):
    An Activity carries TWO foreign keys: decision_cycle (related_name
    'activities') and decision_step (related_name 'activities') —
    activities/models.py:196,206. Nothing at the DB level guarantees
    activity.decision_cycle_id == activity.decision_step.cycle_id. The
    application enforces it at write time (activities/serializers.py: the create
    and update validators fetch DecisionStep with cycle=<decision_cycle>, so a
    step must belong to the provided cycle), but no CHECK constraint backs it.

    These annotations reach activities through the decision_step FK
    (decision_step_id for the per-step predicates, decision_step__cycle_id for
    the cross-cycle aggregates). That is the SAME join the BULK path uses:
    StepStatusDerivationService.derive_bulk reads step.activities and groups by
    step.cycle_id (_has_planned_in_cycle_bulk / _is_last_completed_step_bulk).
    The list / timeline / KPI consumers this annotation is built to replace all
    go through the bulk path, so mirroring its join keeps behaviour identical.
    (The single-instance DB helpers correlate by decision_cycle_id instead; if
    the two FKs ever diverge for a real row the two paths already disagree
    today — a data question to settle on the real dataset, not one to paper over
    with a different join here.)

Priority order mirrors _compute_status (step_status_derivation_service.py:189)
exactly. The empty-step guard is evaluated FIRST — before OVERDUE — because the
Python returns NOT_STARTED for a step with no activities even when its
expected_end is in the past.
"""

from django.db.models import (
    Case,
    CharField,
    Exists,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus

from ..constants import DecisionStepStatus

# Alias names used for the internal boolean/scalar annotations. Underscored so
# they never clash with a model field or a serializer output key.
_HAS_ACTIVITY = '_dsql_has_activity'
_HAS_PLANNED = '_dsql_has_planned'
_HAS_COMPLETED = '_dsql_has_completed'
_HAS_PLANNED_OVERDUE = '_dsql_has_planned_overdue'
_PLANNED_IN_CYCLE = '_dsql_planned_in_cycle'
_MAX_COMPLETED_ORDER = '_dsql_max_completed_order'

DERIVED_STATUS_ALIAS = '_derived_status'


def _support_annotations(today):
    """
    Build the dict of internal Exists/Subquery annotations the status Case
    depends on. All correlate on the OUTER DecisionStep via the decision_step
    FK (see module docstring). CANCELLED activities are excluded everywhere,
    exactly like the Python service.
    """
    from app_modules.activities.models import Activity

    # Non-cancelled activities of THIS step.
    step_acts = Activity.objects.filter(
        decision_step_id=OuterRef('pk'),
    ).exclude(status=ActivityStatus.CANCELLED)

    # A PLANNED activity of this step that is past its scheduled_date or due_date.
    planned_overdue = step_acts.filter(status=ActivityStatus.PLANNED).filter(
        Q(scheduled_date__lt=today) | Q(due_date__lt=today)
    )

    # Any PLANNED activity anywhere in the SAME cycle (cross-step aggregate —
    # mirror _has_planned_in_cycle_bulk). PLANNED is never CANCELLED.
    planned_in_cycle = Activity.objects.filter(
        decision_step__cycle_id=OuterRef('cycle_id'),
        status=ActivityStatus.PLANNED,
    )

    # Highest step order among steps of the cycle that have >=1 COMPLETED
    # activity (mirror _is_last_completed_step_bulk). Isolated correlated
    # subquery, grouped by cycle so it returns a single scalar; never a Count
    # over a deep join.
    max_completed_order = (
        Activity.objects.filter(
            decision_step__cycle_id=OuterRef('cycle_id'),
            status=ActivityStatus.COMPLETED,
        )
        .order_by()
        .values('decision_step__cycle_id')
        .annotate(m=Max('decision_step__order'))
        .values('m')[:1]
    )

    return {
        _HAS_ACTIVITY: Exists(step_acts),
        _HAS_PLANNED: Exists(step_acts.filter(status=ActivityStatus.PLANNED)),
        _HAS_COMPLETED: Exists(step_acts.filter(status=ActivityStatus.COMPLETED)),
        _HAS_PLANNED_OVERDUE: Exists(planned_overdue),
        _PLANNED_IN_CYCLE: Exists(planned_in_cycle),
        _MAX_COMPLETED_ORDER: Subquery(max_completed_order),
    }


def _status_case(today):
    """
    The Case expression that yields the derived status string, referencing the
    boolean/scalar annotations added by _support_annotations. Reproduces the
    exact branch priority of _compute_status.
    """
    # "DONE in this step" — all activities completed, none planned here
    # (VALIDATED / STALLED family). Checked BEFORE overdue so a completed step
    # never flips to OVERDUE.
    done = Q(**{_HAS_COMPLETED: True}) & Q(**{_HAS_PLANNED: False})
    # This step is the last completed step of the cycle (highest order among
    # steps with a completed activity). NULL max (no completed anywhere) never
    # equals `order`, matching the Python False.
    is_last_completed = Q(order=F(_MAX_COMPLETED_ORDER))

    return Case(
        # 0 — no activities → NOT_STARTED. FIRST, so a past expected_end on an
        # empty step does not read as OVERDUE (Python returns here early).
        When(Q(**{_HAS_ACTIVITY: False}), then=Value(DecisionStepStatus.NOT_STARTED)),
        # 1a — done + a PLANNED activity elsewhere in the cycle → VALIDATED.
        When(done & Q(**{_PLANNED_IN_CYCLE: True}),
             then=Value(DecisionStepStatus.VALIDATED)),
        # 1b — done + no PLANNED in cycle + last completed step → STALLED.
        When(done & Q(**{_PLANNED_IN_CYCLE: False}) & is_last_completed,
             then=Value(DecisionStepStatus.STALLED)),
        # 1c — done + no PLANNED in cycle + not last completed → VALIDATED.
        When(done, then=Value(DecisionStepStatus.VALIDATED)),
        # 2 — overdue: step deadline passed OR a PLANNED activity past due.
        When(Q(expected_end__lt=today) | Q(**{_HAS_PLANNED_OVERDUE: True}),
             then=Value(DecisionStepStatus.OVERDUE)),
        # 3 — has PLANNED work → IN_PROGRESS.
        When(Q(**{_HAS_PLANNED: True}), then=Value(DecisionStepStatus.IN_PROGRESS)),
        # 4 — fallback → NOT_STARTED.
        default=Value(DecisionStepStatus.NOT_STARTED),
        output_field=CharField(),
    )


def annotate_step_derived_status(queryset, today=None, alias=DERIVED_STATUS_ALIAS):
    """
    Annotate `alias` (default '_derived_status') on a DecisionStep queryset with
    the SQL-derived step status — the single source of truth translated from
    StepStatusDerivationService._compute_status.

    `today` defaults to the current date; pass an explicit date for
    deterministic tests. The support annotations are added first (a Case cannot
    reference annotations declared in the same .annotate() call).
    """
    if today is None:
        today = timezone.now().date()

    return queryset.annotate(**_support_annotations(today)).annotate(
        **{alias: _status_case(today)}
    )
