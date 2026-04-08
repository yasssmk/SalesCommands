# app_modules/signals/services/signal_manager.py
"""
SignalManager — signal lifecycle operations.

Centralises all state-mutating operations on signals:
  create   — route signal_type → model, delegate save
  validate — PENDING → VALIDATED
  reject   — PENDING → REJECTED (+ optional reason in metadata)
  edit     — patch fields, snapshot original_value on first LLM edit

All methods raise StandardizedValidationError on guard violations.
All write paths use model.save(user=user, client_id=...) so that
ModuleBaseModel audit fields (created_by, updated_by) are always enforced.
"""

from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus, SignalSource
from ..models import PeopleSignal, PainSignal, ObjectiveSignal, TechStackSignal


class SignalManager:
    """
    Stateless service class for signal lifecycle management.

    All public methods are classmethods — no instance needed.
    All writes go through model.save() so BaseSignal.save() business rules
    (MANUAL → VALIDATED, department auto-populate) are always enforced.
    """

    # =========================================================================
    # CREATE
    # =========================================================================

    @classmethod
    def create(cls, data: dict, user, client_id) -> object:
        """
        Create a new signal of the appropriate concrete type.

        Routing (signal_type key consumed here, not passed to the model):
          'people'     → PeopleSignal
          'pain'       → PainSignal
          'objective'  → ObjectiveSignal
          'tech_stack' → TechStackSignal

        Source routing is enforced by BaseSignal.save():
          MANUAL source      → status forced to VALIDATED, confidence = None
          LLM_EXTRACTED/etc. → status starts PENDING

        Args:
            data:      Validated dict from the create serializer.
                       Must include 'signal_type' key (consumed and popped here).
            user:      Request user (for audit trail).
            client_id: Tenant ID (injected by the view's perform_create).

        Returns:
            Saved signal instance.

        Raises:
            StandardizedValidationError if signal_type is invalid.
        """
        signal_type = data.pop('signal_type')

        model_map = {
            'people':     PeopleSignal,
            'pain':       PainSignal,
            'objective':  ObjectiveSignal,
            'tech_stack': TechStackSignal,
        }
        model_class = model_map.get(signal_type)
        if not model_class:
            raise StandardizedValidationError(
                SignalErrorMessages.INVALID_SIGNAL_TYPE.format(
                    signal_type=signal_type
                )
            )

        signal = model_class(**data)
        signal.save(user=user, client_id=client_id)
        return signal

    # =========================================================================
    # VALIDATE
    # =========================================================================

    @classmethod
    def validate(cls, signal, user) -> object:
        """
        Validate (approve) a PENDING signal.

        Sets status → VALIDATED, records validated_by and validated_at.

        Args:
            signal: Any concrete signal instance.
            user:   Rep performing the validation.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is not PENDING.
        """
        if signal.status != SignalStatus.PENDING:
            raise StandardizedValidationError(
                SignalErrorMessages.NOT_PENDING_VALIDATED
            )

        signal.status       = SignalStatus.VALIDATED
        signal.validated_by = user
        signal.validated_at = timezone.now()
        signal.save(user=user)
        return signal

    # =========================================================================
    # REJECT
    # =========================================================================

    @classmethod
    def reject(cls, signal, user, reason: str = None) -> object:
        """
        Reject a PENDING signal.

        Sets status → REJECTED.
        If reason provided, stores it in metadata['rejection_reason']
        alongside timestamp and rejecting user ID for audit.

        Args:
            signal: Any concrete signal instance.
            user:   Rep performing the rejection.
            reason: Optional free-text rejection reason.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is not PENDING.
        """
        if signal.status != SignalStatus.PENDING:
            raise StandardizedValidationError(
                SignalErrorMessages.NOT_PENDING_REJECTED
            )

        if reason:
            if not signal.metadata:
                signal.metadata = {}
            signal.metadata['rejection_reason'] = reason
            signal.metadata['rejected_at']      = timezone.now().isoformat()
            signal.metadata['rejected_by']      = str(user.id) if user else None

        signal.status = SignalStatus.REJECTED
        signal.save(user=user)
        return signal

    # =========================================================================
    # EDIT
    # =========================================================================

    @classmethod
    def edit(cls, signal, updates: dict, user) -> object:
        """
        Apply field updates to an existing signal.

        Guards:
          - REJECTED signals cannot be edited.

        First-edit snapshot rule:
          - If source == LLM_EXTRACTED and original_value is still None,
            snapshot source_quote into original_value and flip
            source → LLM_MODIFIED before saving.

        Args:
            signal:  Any concrete signal instance.
            updates: Dict of field_name → new_value pairs to apply.
            user:    User performing the edit.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is REJECTED.
        """
        if signal.status == SignalStatus.REJECTED:
            raise StandardizedValidationError(
                SignalErrorMessages.NOT_EDITABLE.format(
                    status=signal.get_status_display()
                )
            )

        # Snapshot original source_quote on first edit of an LLM-extracted signal
        if (
            signal.source == SignalSource.LLM_EXTRACTED
            and signal.original_value is None
        ):
            signal.original_value = signal.source_quote
            signal.source         = SignalSource.LLM_MODIFIED

        for field, value in updates.items():
            setattr(signal, field, value)

        signal.last_modified_by = user
        signal.last_modified_at = timezone.now()
        signal.save(user=user)
        return signal