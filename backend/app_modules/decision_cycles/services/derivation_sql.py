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
    Count,
    Exists,
    F,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus

from ..constants import CycleOutcome, DecisionStepStatus

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


# =============================================================================
# CYCLE-LEVEL ANNOTATIONS
# =============================================================================
# SQL translation of CycleAggregationService._derive_status_bulk (effective
# cycle status) and _compute_progress (current step + validated/total counts).
# Every cycle-level predicate is an ISOLATED correlated subquery over the
# cycle's DecisionSteps; each step subquery reuses the 1a step-status Case
# (annotate_step_derived_status), so the cycle status is the exact aggregate of
# the 1a step statuses — no re-derivation, no divergence. Nested correlated
# subqueries keep the outer query one-row-per-cycle: a Count over a deep
# cycle->step->activity join would multiply rows and skew every count together.
# Join choice is unchanged from 1a (decision_step FK) — see the module docstring.
# =============================================================================

# Public alias names for the cycle annotations (also the attributes the service
# reads when consuming the annotation).
CYCLE_STATUS_ALIAS = '_cycle_effective_status'
CURRENT_STEP_NAME_ALIAS = '_current_step_name'
CURRENT_STEP_ORDER_ALIAS = '_current_step_order'
CURRENT_STEP_STAGE_ALIAS = '_current_step_stage'
VALIDATED_STEPS_COUNT_ALIAS = '_validated_steps_count'
TOTAL_STEPS_COUNT_ALIAS = '_total_steps_count'
STALLED_STEPS_COUNT_ALIAS = '_stalled_steps_count'

# Cycle statuses as CycleAggregationService names them (kept in sync here).
_CYCLE_WON = 'WON'
_CYCLE_LOST = 'LOST'
_CYCLE_ON_HOLD = 'ON_HOLD'
_CYCLE_NOT_STARTED = 'NOT_STARTED'
_CYCLE_OVERDUE = 'OVERDUE'
_CYCLE_STALLED = 'STALLED'
_CYCLE_IN_PROGRESS = 'IN_PROGRESS'


def _cycle_step_subquery(today):
    """A DecisionStep queryset correlated to the OUTER DecisionCycle, carrying
    the 1a `_derived_status`. Each per-step OuterRef('pk')/OuterRef('cycle_id')
    resolves to this step row (the immediate parent), while cycle_id=OuterRef
    ('pk') binds the set to the outer cycle."""
    from ..models import DecisionStep

    return annotate_step_derived_status(
        DecisionStep.objects.filter(cycle_id=OuterRef('pk')), today
    )


def _isolated_step_count(step_qs):
    """Coalesced count of a correlated step subquery, grouped so it returns a
    single scalar (0 when empty). Never a Count over a deep join."""
    return Coalesce(
        Subquery(
            step_qs.order_by().values('cycle_id').annotate(c=Count('pk')).values('c')[:1],
            output_field=IntegerField(),
        ),
        Value(0),
        output_field=IntegerField(),
    )


def _cycle_effective_status_case(today):
    """
    Case for the effective cycle status. Outcome first (stored), then the state
    derived from the step statuses — mirroring _derive_status_bulk priority
    exactly: outcome (WON / LOST+NOT_QUALIFIED / ON_HOLD) → no steps NOT_STARTED
    → any OVERDUE → any STALLED → any IN_PROGRESS/VALIDATED → NOT_STARTED (the
    remaining case is "all steps NOT_STARTED", the only reachable default).
    """
    from ..models import DecisionStep

    steps = _cycle_step_subquery(today)
    has_steps = Exists(DecisionStep.objects.filter(cycle_id=OuterRef('pk')))
    any_overdue = Exists(steps.filter(**{DERIVED_STATUS_ALIAS: DecisionStepStatus.OVERDUE}))
    any_stalled = Exists(steps.filter(**{DERIVED_STATUS_ALIAS: DecisionStepStatus.STALLED}))
    any_active = Exists(
        steps.filter(**{
            f'{DERIVED_STATUS_ALIAS}__in': [
                DecisionStepStatus.IN_PROGRESS,
                DecisionStepStatus.VALIDATED,
            ],
        })
    )

    return Case(
        # 1 — explicit stored outcome overrides everything (NOT_QUALIFIED → LOST).
        When(Q(outcome=CycleOutcome.WON), then=Value(_CYCLE_WON)),
        When(Q(outcome__in=[CycleOutcome.LOST, CycleOutcome.NOT_QUALIFIED]),
             then=Value(_CYCLE_LOST)),
        When(Q(outcome=CycleOutcome.ON_HOLD), then=Value(_CYCLE_ON_HOLD)),
        # 2 — no steps → NOT_STARTED.
        When(~has_steps, then=Value(_CYCLE_NOT_STARTED)),
        # 3 — any OVERDUE step → OVERDUE.
        When(any_overdue, then=Value(_CYCLE_OVERDUE)),
        # 4 — any STALLED step → STALLED (before IN_PROGRESS, as in the Python).
        When(any_stalled, then=Value(_CYCLE_STALLED)),
        # 5 — any IN_PROGRESS or VALIDATED step → IN_PROGRESS.
        When(any_active, then=Value(_CYCLE_IN_PROGRESS)),
        # 6 — remaining reachable state is "all steps NOT_STARTED".
        default=Value(_CYCLE_NOT_STARTED),
        output_field=CharField(),
    )


def annotate_cycle_state(queryset, today=None):
    """
    Annotate a DecisionCycle queryset with the effective status, the current
    step (name / stage / order) and the validated / total / stalled step
    counts — the SQL translation of CycleAggregationService.get_bulk_summaries.

    The current step is the first non-VALIDATED step by `order` (matching
    _compute_progress); its name/stage/order come from three isolated
    correlated subqueries over the same ordered, filtered step set.

    `today` defaults to the current date; pass an explicit date for
    deterministic tests.
    """
    from ..models import DecisionStep

    if today is None:
        today = timezone.now().date()

    steps = _cycle_step_subquery(today)

    # Current step = first step (by order) whose derived status is not VALIDATED.
    current = steps.exclude(
        **{DERIVED_STATUS_ALIAS: DecisionStepStatus.VALIDATED}
    ).order_by('order')

    validated_steps = steps.filter(**{DERIVED_STATUS_ALIAS: DecisionStepStatus.VALIDATED})
    stalled_steps = steps.filter(**{DERIVED_STATUS_ALIAS: DecisionStepStatus.STALLED})
    all_steps = DecisionStep.objects.filter(cycle_id=OuterRef('pk'))

    return queryset.annotate(
        **{
            CYCLE_STATUS_ALIAS: _cycle_effective_status_case(today),
            CURRENT_STEP_NAME_ALIAS: Subquery(
                current.values('name')[:1], output_field=CharField()
            ),
            CURRENT_STEP_ORDER_ALIAS: Subquery(
                current.values('order')[:1], output_field=IntegerField()
            ),
            CURRENT_STEP_STAGE_ALIAS: Subquery(
                current.values('stage')[:1], output_field=CharField()
            ),
            VALIDATED_STEPS_COUNT_ALIAS: _isolated_step_count(validated_steps),
            TOTAL_STEPS_COUNT_ALIAS: _isolated_step_count(all_steps),
            STALLED_STEPS_COUNT_ALIAS: _isolated_step_count(stalled_steps),
        }
    )
