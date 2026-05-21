# app_modules/signals/services/signal_manager.py
"""
SignalManager — signal lifecycle operations.

Centralises all state-mutating operations on signals:
  create   — route signal_type → model, propagate activity context,
             delegate save
  validate — PENDING → VALIDATED
  reject   — PENDING → REJECTED (+ optional reason in metadata)
  edit     — patch fields, snapshot original_value on first LLM edit

Supported signal types (routed by SignalManager.create):
  pain       → PainSignal
  objective  → ObjectiveSignal
  impact     → ImpactSignal
  tech_stack → TechStackSignal

All methods raise StandardizedValidationError on guard violations.
All write paths use model.save(user=user, client_id=...) so that
ModuleBaseModel audit fields (created_by, updated_by) are always enforced.

Activity-context propagation
----------------------------
At create time, when a `source_activity` is provided, the manager
auto-fills `decision_cycle`, `campaign`, and (for future signal types)
`decision_step` from the activity's own FKs — unless the caller passed
explicit values, which always win. Concrete signal types that
shadow-override these inherited fields to None on the model
(TechStackSignal sets all three) are skipped by class-level
hasattr checks. This guarantees that signals captured from an Activity
context inherit the deal-level metadata required for cluster scoping
without forcing every UI surface to remember the propagation rules.
"""

import logging

from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus, SignalSource
from ..models import PainSignal, ObjectiveSignal, ImpactSignal, TechStackSignal


logger = logging.getLogger(__name__)


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

    # Fields auto-propagated from source_activity at create time when not
    # explicitly provided. The list is intentionally inclusive — concrete
    # models that shadow-override a field to None (e.g. TechStackSignal
    # for decision_cycle / campaign) are detected at runtime and skipped.
    # decision_step is included for forward-compatibility: no current
    # signal type carries it, but adding one later requires no change here.
    _ACTIVITY_PROPAGATED_FIELDS = ('decision_cycle', 'campaign', 'decision_step')

    @classmethod
    def create(cls, data: dict, user, client_id) -> object:
        """
        Create a new signal of the appropriate concrete type.

         Routing (signal_type key consumed here, not passed to the model):
          'pain'       → PainSignal
          'objective'  → ObjectiveSignal
          'impact'     → ImpactSignal
          'tech_stack' → TechStackSignal

        Activity-context propagation:
          When `data['source_activity']` is set, fields listed in
          _ACTIVITY_PROPAGATED_FIELDS are auto-filled from the activity
          when not already provided in `data`. See
          _propagate_activity_context() for the full algorithm.

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
            'pain':       PainSignal,
            'objective':  ObjectiveSignal,
            'impact':     ImpactSignal,
            'tech_stack': TechStackSignal,
        }
        model_class = model_map.get(signal_type)
        if not model_class:
            raise StandardizedValidationError(
                SignalErrorMessages.INVALID_SIGNAL_TYPE.format(
                    signal_type=signal_type
                )
            )

        # Auto-fill deal-level context from source_activity when applicable.
        # Mutates `data` in place — non-destructive (only fills None / missing keys).
        cls._propagate_activity_context(model_class, data)

        signal = model_class(**data)
        signal.save(user=user, client_id=client_id)
        return signal

    # -------------------------------------------------------------------------
    # CREATE — helpers
    # -------------------------------------------------------------------------

    @classmethod
    def _propagate_activity_context(cls, model_class, data: dict) -> None:
        """
        Auto-fill deal-level FKs from `data['source_activity']` when the
        caller didn't pass them explicitly.

        Fields covered: decision_cycle, campaign, decision_step
        (see _ACTIVITY_PROPAGATED_FIELDS).

        Algorithm (per field):
          1. If source_activity is None / missing in data → no-op (early return).
          2. If the concrete model shadow-overrides the field to None at the
             class level (TechStackSignal sets decision_cycle, campaign,
             decision_step to None) → skip silently. Detected via class-level
             getattr to avoid triggering Django descriptor refresh on a
             non-existent column (same pattern as BaseSignal.save() rule 2).
          3. If `data[field]` is already set to a non-None value → skip
             (caller value wins; propagation is non-destructive).
          4. Otherwise: copy `getattr(source_activity, field, None)` into data.
             A None on the activity propagates as None — no field violation
             is introduced because all three propagated fields are nullable
             on every signal model that exposes them.

        Args:
            model_class: Concrete signal model class (PeopleSignal, PainSignal,
                         ObjectiveSignal, TechStackSignal).
            data:        Mutable validated_data dict from the create serializer.
                         Mutated in place.

        Returns:
            None. Side effect: `data` may have new keys filled in.
        """
        source_activity = data.get('source_activity')
        if source_activity is None:
            return

        for field in cls._ACTIVITY_PROPAGATED_FIELDS:
            # Class-level check — None means the concrete model has
            # shadow-overridden the field (no DB column). Reading via the
            # class avoids the descriptor machinery that an instance access
            # would trigger.
            if getattr(model_class, field, None) is None:
                continue

            # Caller provided an explicit value (including a non-null FK):
            # respect it. We test `is not None` rather than truthiness so a
            # caller intentionally passing None to override the propagation
            # would still trigger the fill — which is consistent with
            # "caller didn't really commit to a value". If a caller wants
            # to force null, they should not include the key at all and
            # then no propagation happens because source_activity itself
            # may be null too. In practice the wizard sends None for
            # missing values, which is exactly what we want to fill in.
            if data.get(field) is not None:
                continue

            propagated_value = getattr(source_activity, field, None)
            if propagated_value is not None:
                data[field] = propagated_value
                logger.debug(
                    'SignalManager: propagated %s=%s from activity %s to %s',
                    field,
                    getattr(propagated_value, 'pk', propagated_value),
                    source_activity.pk,
                    model_class.__name__,
                )

    # =========================================================================
    # VALIDATE
    # =========================================================================

    @classmethod
    def validate(cls, signal, user) -> object:
        """
        Validate (approve) a PENDING signal.

        Guards (raised before any mutation):
          1. Signal must be in status=PENDING.
          2. TechStackSignal must have tech_catalog_entry set. PENDING
             LLM-extracted TechStack signals may legitimately exist
             with tech_catalog_entry=None — the LLM could not match
             the mentioned tool to the tenant catalog at extraction
             time (see TechStackSignal.clean() rule 1 and the LLM-
             PENDING exception). Promotion to VALIDATED requires the
             catalog anchor because canonical_key is derived from it
             and cluster aggregation cannot work without it. The rep
             must attach (or create) a catalog entry before validating.

        Sets status → VALIDATED, records validated_by and validated_at.

        Args:
            signal: Any concrete signal instance.
            user:   Rep performing the validation.

        Returns:
            Updated signal instance.

        Raises:
            StandardizedValidationError when any guard fails.
        """
        if signal.status != SignalStatus.PENDING:
            raise StandardizedValidationError(
                SignalErrorMessages.NOT_PENDING_VALIDATED
            )

        # TechStack-specific guard — cannot validate without the catalog FK.
        # The model only allows the FK to be null on PENDING LLM-extracted
        # signals (see TechStackSignal.clean() rule 1). Validation forces
        # the rep to attach the anchor before promoting the signal.
        if (
            isinstance(signal, TechStackSignal)
            and signal.tech_catalog_entry_id is None
        ):
            raise StandardizedValidationError(
                SignalErrorMessages.TECHSTACK_CATALOG_ENTRY_REQUIRED
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

        Audit trail:
          ModuleBaseModel.save(user=user) updates `updated_by` and
          `updated_at` automatically. The previous explicit
          `last_modified_by` / `last_modified_at` setters were removed
          during the standardisation refactor — the fields were retired
          from BaseSignal because they duplicated the inherited
          `updated_*` audit pair from ModuleBaseModel. The save() call
          below is now the single audit source of truth for "who
          touched this signal last and when".

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

        signal.save(user=user)
        return signal