# app_modules/signals/services/signal_manager.py
"""
SignalManager — signal lifecycle operations.

Centralises all state-mutating operations on signals:
  create     — route source → initial status, delegate save to model
  validate   — PENDING → VALIDATED
  reject     — PENDING → REJECTED (+ optional reason in metadata)
  merge      — source → MERGED, target confirmation_count += source's
  supersede  — old → is_superseded=True, create replacement signal
  edit       — patch value, snapshot original_value on first LLM edit

All methods raise StandardizedValidationError on guard violations.
All write paths use model.save(user=user, client_id=...) so that
ModuleBaseModel audit fields (created_by, updated_by) are kept consistent.
"""

from django.db import transaction
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

from ..constants import SignalStatus, SignalSource
from ..models import QualificationSignal, TechStackSignal


# =============================================================================
# ERROR MESSAGES — signals-specific (no dedicated SignalErrorMessages yet)
# =============================================================================

_ERR_NOT_PENDING     = "Only PENDING signals can be {action}."
_ERR_NOT_ALLOWED     = "Cannot {action} a signal with status {status}."
_ERR_DIFF_TYPE       = "Cannot merge signals of different types."
_ERR_DIFF_FIELD      = "Cannot merge signals with different field_name."
_ERR_TARGET_STATUS   = "Target signal must be VALIDATED before merging."
_ERR_SELF_MERGE      = "Cannot merge a signal into itself."
_ERR_ALREADY_MERGED  = "Source signal is already MERGED."
_ERR_NO_TARGET       = "target_signal_id is required for merge."
_ERR_NO_NEW_DATA     = "new_data is required for supersede."


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
        Create a new signal (QualificationSignal or TechStackSignal).

        Routing rules (enforced here, not in serializer):
          - source=MANUAL      → status will be forced to VALIDATED by model.save()
          - source=LLM_*       → status starts PENDING (model default)
          - confidence          → forced to None when source=MANUAL (model.save())

        Args:
            data:      Validated dict from the create serializer.
                       Must include 'signal_type' key ('qualification' | 'tech_stack')
                       which is consumed here and not passed to the model.
            user:      Request user (for audit trail).
            client_id: Tenant ID (injected by the view's perform_create).

        Returns:
            Saved signal instance.

        Raises:
            StandardizedValidationError on any guard violation.
        """
        signal_type = data.pop('signal_type')

        model_map = {
            'qualification': QualificationSignal,
            'tech_stack':    TechStackSignal,
        }
        model_class = model_map.get(signal_type)
        if not model_class:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='signal_type')
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
            signal: Signal instance (QualificationSignal or TechStackSignal).
            user:   Rep performing the validation.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is not PENDING.
        """
        if signal.status != SignalStatus.PENDING:
            raise StandardizedValidationError(
                _ERR_NOT_PENDING.format(action='validated')
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
            signal: Signal instance.
            user:   Rep performing the rejection.
            reason: Optional free-text rejection reason.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is not PENDING.
        """
        if signal.status != SignalStatus.PENDING:
            raise StandardizedValidationError(
                _ERR_NOT_PENDING.format(action='rejected')
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
    # MERGE
    # =========================================================================

    @classmethod
    @transaction.atomic
    def merge(cls, source_signal, target_signal, user) -> object:
        """
        Merge source_signal into target_signal.

        Guards:
          - source != target (no self-merge)
          - same concrete model type
          - same field_name
          - target must be VALIDATED
          - source must not already be MERGED

        Effects:
          - source → status=MERGED, merged_into=target
          - target → confirmation_count += source.confirmation_count
          - target → last_confirmed_at = now()
          - target → metadata['merge_history'] appended

        Args:
            source_signal: Signal to absorb (will become MERGED).
            target_signal: Surviving signal.
            user:          User performing the merge.

        Returns:
            Updated target_signal instance.

        Raises:
            StandardizedValidationError on any guard violation.
        """
        # --- guards -----------------------------------------------------------
        if source_signal.pk == target_signal.pk:
            raise StandardizedValidationError(_ERR_SELF_MERGE)

        if source_signal.__class__ != target_signal.__class__:
            raise StandardizedValidationError(_ERR_DIFF_TYPE)

        if source_signal.field_name != target_signal.field_name:
            raise StandardizedValidationError(_ERR_DIFF_FIELD)

        if source_signal.status == SignalStatus.MERGED:
            raise StandardizedValidationError(_ERR_ALREADY_MERGED)

        if target_signal.status != SignalStatus.VALIDATED:
            raise StandardizedValidationError(_ERR_TARGET_STATUS)

        # --- target: increment confirmation -----------------------------------
        target_signal.confirmation_count += source_signal.confirmation_count
        target_signal.last_confirmed_at   = timezone.now()

        # --- target: append merge history in metadata -------------------------
        if not target_signal.metadata:
            target_signal.metadata = {}
        target_signal.metadata.setdefault('merge_history', []).append({
            'merged_signal_id':    str(source_signal.id),
            'field_name':          source_signal.field_name,
            'merged_by':           str(user.id) if user else None,
            'timestamp':           timezone.now().isoformat(),
            'confirmations_added': source_signal.confirmation_count,
        })

        # --- source: mark as merged -------------------------------------------
        source_signal.status      = SignalStatus.MERGED
        source_signal.merged_into = target_signal

        # --- persist ----------------------------------------------------------
        target_signal.save(user=user)
        source_signal.save(user=user)

        return target_signal

    # =========================================================================
    # SUPERSEDE
    # =========================================================================

    @classmethod
    @transaction.atomic
    def supersede(cls, old_signal, new_data: dict, user) -> object:
        """
        Replace old_signal with a new signal carrying new_data.

        Steps:
          1. Mark old_signal as superseded (is_superseded=True).
          2. Create the new signal via cls.create() so that source routing
             (MANUAL → VALIDATED, LLM → PENDING) is enforced consistently.
          3. Point old_signal.superseded_by → new signal.

        new_data must include 'signal_type' (same as old_signal) and all
        fields required by the create path.

        Args:
            old_signal: Signal instance to supersede.
            new_data:   Dict for the replacement signal (same shape as create).
            user:       User performing the operation.

        Returns:
            New signal instance.

        Raises:
            StandardizedValidationError if new_data is missing or invalid.
        """
        if not new_data:
            raise StandardizedValidationError(_ERR_NO_NEW_DATA)

        client_id = old_signal.client_id

        # Create replacement first — if it fails we don't mutate old_signal
        new_signal = cls.create(data=new_data, user=user, client_id=client_id)

        # Mark old as superseded
        old_signal.is_superseded  = True
        old_signal.superseded_by  = new_signal
        old_signal.save(user=user)

        return new_signal

    # =========================================================================
    # EDIT
    # =========================================================================

    @classmethod
    def edit(cls, signal, new_value, user) -> object:
        """
        Edit the value of an existing signal.

        Guards:
          - REJECTED and MERGED signals cannot be edited.

        First-edit snapshot rule:
          - If source == LLM_EXTRACTED and original_value is still None,
            snapshot the current value into original_value and flip
            source → LLM_MODIFIED before saving.

        Args:
            signal:    Signal instance to edit.
            new_value: New value (any JSON-serialisable type).
            user:      User performing the edit.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError if signal is REJECTED or MERGED.
        """
        if signal.status in (SignalStatus.REJECTED, SignalStatus.MERGED):
            raise StandardizedValidationError(
                _ERR_NOT_ALLOWED.format(
                    action='edited',
                    status=signal.get_status_display(),
                )
            )

        # Snapshot original value on the first edit of an LLM-extracted signal
        if (
            signal.source == SignalSource.LLM_EXTRACTED
            and signal.original_value is None
        ):
            signal.original_value = signal.value
            signal.source         = SignalSource.LLM_MODIFIED

        signal.value            = new_value
        signal.last_modified_by = user
        signal.last_modified_at = timezone.now()
        signal.save(user=user)
        return signal