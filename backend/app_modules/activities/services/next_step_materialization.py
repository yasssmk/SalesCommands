# app_modules/activities/services/next_step_materialization.py
"""
Next step materialisation — the SINGLE place where an Activity is created
from a NextStepSignal.

Both creation paths go through it:
  * POST /module-activities/                       (ActivityCreateSerializer)
  * POST /module-activities/create-with-entities/  (ActivityCreationService)

Contract (identical on both paths):
  1. resolve_pending_next_step — the signal must exist in the caller's
     tenant and be PENDING (one suggestion → one Activity), else 400.
  2. Defaults from the next step, applied ONLY where the create payload
     leaves the field empty (an explicit value always wins), BEFORE the
     callers' own checks (date required, step required with a cycle):
       * next_step_text_and_date_defaults — description ← suggested_topics;
         call_to_action ← objective + success criterion; date ←
         suggested_due_date, as scheduled_date for the types of
         SCHEDULED_DATE_ACTIVITY_TYPES, else as due_date (D6);
       * next_step_cycle_default — the next step's cycle (next_step_cycle:
         its own, else the cycle born from its campaign conversation; same
         account) when the payload sends none;
       * next_step_step_default — the proposed step when it belongs to the
         activity's cycle, else that cycle's CURRENT step (computed here,
         never stored on the signal).
     No contact is ever added by the server.
  3. next_step_activity_fields — the Activity carries the provenance FK.
  4. mark_next_step_materialised — the signal is validated, in the same
     transaction as the Activity creation (both callers are atomic).
"""

from django.core.exceptions import ValidationError as DjangoValidationError

from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import (
    NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR,
    NEXT_STEP_SUCCESS_CRITERION_LABEL,
    SCHEDULED_DATE_ACTIVITY_TYPES,
)


def resolve_pending_next_step(next_step_signal_id, client_id):
    """
    The PENDING NextStepSignal `next_step_signal_id` of tenant `client_id`,
    or None when no id is given.

    Raises:
        StandardizedValidationError — unknown / other-tenant signal, or a
        signal that is not PENDING.
    """
    if not next_step_signal_id:
        return None

    from app_modules.signals.constants import SignalStatus
    from app_modules.signals.models import NextStepSignal

    try:
        signal = NextStepSignal.objects.get(
            id=next_step_signal_id,
            client_id=client_id,
        )
    except (NextStepSignal.DoesNotExist, DjangoValidationError, ValueError):
        raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    if signal.status != SignalStatus.PENDING:
        raise StandardizedValidationError(
            CoreErrorMessages.INVALID_FIELD.format(
                field='next_step_signal must be in PENDING status'
            )
        )
    return signal


# =============================================================================
# DEFAULTS FROM THE NEXT STEP (only where the payload is empty)
# =============================================================================

def next_step_objective(signal):
    """call_to_action composed from the next step: the objective, then the
    success criterion under its label ('' when the signal has neither)."""
    parts = []
    if signal.suggested_objective:
        parts.append(signal.suggested_objective)
    if signal.suggested_success_criterion:
        parts.append(
            NEXT_STEP_SUCCESS_CRITERION_LABEL + signal.suggested_success_criterion
        )
    return NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR.join(parts)


def next_step_text_and_date_defaults(signal, fields):
    """
    The description / call_to_action / date values the next step brings,
    for the keys `fields` (Activity field names: activity_type, description,
    call_to_action, scheduled_date, due_date) leaves empty.
    """
    defaults = {}
    if not fields.get('description') and signal.suggested_topics:
        defaults['description'] = signal.suggested_topics
    objective = next_step_objective(signal)
    if not fields.get('call_to_action') and objective:
        defaults['call_to_action'] = objective
    if (
        signal.suggested_due_date
        and not fields.get('scheduled_date')
        and not fields.get('due_date')
    ):
        date_field = (
            'scheduled_date'
            if fields.get('activity_type') in SCHEDULED_DATE_ACTIVITY_TYPES
            else 'due_date'
        )
        defaults[date_field] = signal.suggested_due_date
    return defaults


def next_steps_enabled(activity):
    """
    Sprint Next steps 5.14b -- whether `activity` can have next steps: it is
    in a decision cycle, or it is a campaign activity whose outcome is
    successful (SUCCESSFUL_OUTCOMES -- PO: the goal of a campaign is to
    create decision cycles). The ONE predicate: the extraction guard
    (activity_extraction_view) reads it; the front mirrors it
    (utils/nextStepsBand hasSuggestedNextSteps).
    """
    from app_modules.campaigns.constants import SUCCESSFUL_OUTCOMES

    if activity.decision_cycle_id is not None:
        return True
    return activity.campaign_id is not None and activity.outcome in SUCCESSFUL_OUTCOMES


def next_step_cycle(signal):
    """The decision cycle of a next step: its own, else (a next step of a
    campaign activity, 5.14b) the cycle born from its conversation
    (born_decision_cycle, read at call time) -- None while none is born."""
    from .activity_sequence_service import born_decision_cycle

    if signal.decision_cycle is not None:
        return signal.decision_cycle
    if signal.source_activity is None:
        return None
    return born_decision_cycle(signal.source_activity)


def next_step_cycle_default(signal, account):
    """The next step's decision cycle (next_step_cycle) when it belongs to
    `account`, else None."""
    cycle = next_step_cycle(signal)
    if cycle is not None and cycle.account_id == account.id:
        return cycle
    return None


def decision_steps_state(cycle):
    """
    The steps of `cycle` by order, as [(step, derived status, is_current)]:
    the status derived from the step's activities (StepStatusDerivationService)
    and the CURRENT mark — the first step whose derived status is not
    VALIDATED, the shared definition of DecisionStep.is_current
    (CycleAggregationService._compute_progress). [] without steps.
    """
    from app_modules.decision_cycles.constants import DecisionStepStatus
    from app_modules.decision_cycles.models import DecisionStep
    from app_modules.decision_cycles.services import (
        CycleAggregationService,
        StepStatusDerivationService,
    )

    steps = sorted(
        DecisionStep.objects.filter(cycle=cycle).prefetch_related('activities'),
        key=lambda s: s.order,
    )
    if not steps:
        return []
    derived = StepStatusDerivationService().derive_bulk(steps)
    current_order = CycleAggregationService._compute_progress(
        steps, derived
    ).get('current_step_order')
    return [
        (s, derived.get(s.id, {}).get('status', DecisionStepStatus.NOT_STARTED),
         s.order == current_order)
        for s in steps
    ]


def current_decision_step(cycle):
    """
    The CURRENT step of `cycle` (decision_steps_state). None when the cycle
    has no steps or all are validated.
    """
    return next((s for s, _status, current in decision_steps_state(cycle) if current), None)


def next_step_step_default(signal, cycle):
    """The step proposed by the next step when it belongs to `cycle`, else
    the current step of `cycle` (computed, never stored on the signal)."""
    proposed = signal.suggested_decision_step
    if proposed is not None and proposed.cycle_id == cycle.id:
        return proposed
    return current_decision_step(cycle)


# =============================================================================
# PROVENANCE + VALIDATION
# =============================================================================

def next_step_activity_fields(signal):
    """The provenance FK the Activity carries (Activity.next_step_signal)."""
    return {'next_step_signal': signal}


def mark_next_step_materialised(signal, user):
    """Validate the signal its Activity was just created from."""
    from app_modules.signals.services.signal_manager import SignalManager
    SignalManager.validate(signal, user=user)
