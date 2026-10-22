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
  2. next_step_activity_fields — the Activity carries the FK to the signal
     (provenance) and, when the payload sets no objective, the signal's
     suggested_objective as call_to_action. An explicit objective wins.
  3. mark_next_step_materialised — the signal is validated, in the same
     transaction as the Activity creation (both callers are atomic).
"""

from django.core.exceptions import ValidationError as DjangoValidationError

from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError


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


def next_step_activity_fields(signal, call_to_action=None):
    """
    The Activity fields that come from `signal`: the provenance FK and the
    objective (`call_to_action`, the payload's value when it sets one, else
    the signal's suggested_objective; unchanged when neither is set).
    """
    return {
        'next_step_signal': signal,
        'call_to_action':   (
            call_to_action or signal.suggested_objective or call_to_action
        ),
    }


def mark_next_step_materialised(signal, user):
    """Validate the signal its Activity was just created from."""
    from app_modules.signals.services.signal_manager import SignalManager
    SignalManager.validate(signal, user=user)
