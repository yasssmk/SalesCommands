# app_modules/signals/serializers/objective_serializer.py
"""
Serializers for ObjectiveSignal.

Stack:
  ObjectiveSignalListSerializer   — lightweight list view
  ObjectiveSignalDetailSerializer — full detail (validated_*, requested_by,
                                    source_quote, metadata, original_value
                                    on top of the list payload)
  ObjectiveSignalCreateSerializer — write path, enforces scope-conditional
                                    target requirements
  ObjectiveSignalUpdateSerializer — restricted PATCH, canonical axes
                                    rewritable (canonical_key recomputed
                                    by model.save())

Notes:
  - `goal_level`, `measurement_method`, `signal_category` are gone.
    `scope_level` is the scope axis (shared ScopeLevel enum).
    `what` × `dimension` are the canonical axes (shared with Pain).
  - `signal_category` is shadow-overridden to None on the model, so it
    is neither stored nor exposed on ObjectiveSignal. Inherited base
    serializer lists that include `signal_category` / `signal_category_display`
    are filtered out by the Meta.fields overrides below.
  - Scope-conditional rules (mirror of model.clean()):
      PERSONAL   → target_contact required, target_department forbidden
      DEPARTMENT → target_department required, target_contact forbidden
      BUSINESS   → neither target_contact nor target_department
    Enforced in Create (strict) and Update (merged-state on partial
    payloads — same pattern as ImpactSignal).
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import ScopeLevel
from ..models import ObjectiveSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — shared display-field logic
# =============================================================================
#
# List and Detail expose the same display fields for the canonical axes
# and scope. A small mixin keeps the two serializers aligned when the
# schema evolves.
# =============================================================================


class _ObjectiveDisplayMixin:
    """Shared SerializerMethodField implementations for Objective serializers."""

    def get_what_display(self, obj):
        return obj.get_what_display() if obj.what else None

    def get_dimension_display(self, obj):
        return obj.get_dimension_display() if obj.dimension else None

    def get_scope_level_display(self, obj):
        return obj.get_scope_level_display() if obj.scope_level else None

    def get_target_contact(self, obj):
        c = obj.target_contact
        if not c:
            return None
        return {
            'id':         str(c.id),
            'first_name': c.first_name,
            'last_name':  c.last_name,
            'job_title':  getattr(c, 'job_title', None),
        }

    def get_target_department(self, obj):
        d = obj.target_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# SCOPE VALIDATION HELPER
# =============================================================================

def _validate_scope_consistency(scope_level, target_contact, target_department):
    """
    Enforce scope-conditional target requirements.

    Mirror of ObjectiveSignal.clean() — called by Create (strict) and
    Update (merged-state). Raises StandardizedValidationError on the
    first offending field for a clean API error payload.

    Args:
        scope_level:        Resolved scope value (ScopeLevel or None).
        target_contact:     Resolved target_contact (Contact or None).
        target_department:  Resolved target_department (StandardDepartment or None).

    Rules:
      PERSONAL   → target_contact required, target_department forbidden
      DEPARTMENT → target_department required, target_contact forbidden
      BUSINESS   → neither allowed
    """
    if scope_level == ScopeLevel.PERSONAL:
        if not target_contact:
            raise StandardizedValidationError({
                'target_contact': SignalErrorMessages.OBJECTIVE_PERSONAL_REQUIRES_CONTACT,
            })
        if target_department:
            raise StandardizedValidationError({
                'target_department': SignalErrorMessages.OBJECTIVE_PERSONAL_NO_DEPT,
            })

    elif scope_level == ScopeLevel.DEPARTMENT:
        if not target_department:
            raise StandardizedValidationError({
                'target_department': SignalErrorMessages.OBJECTIVE_DEPT_REQUIRES_DEPT,
            })
        if target_contact:
            raise StandardizedValidationError({
                'target_contact': SignalErrorMessages.OBJECTIVE_DEPT_NO_CONTACT,
            })

    elif scope_level == ScopeLevel.BUSINESS:
        if target_contact:
            raise StandardizedValidationError({
                'target_contact': SignalErrorMessages.OBJECTIVE_BUSINESS_NO_CONTACT,
            })
        if target_department:
            raise StandardizedValidationError({
                'target_department': SignalErrorMessages.OBJECTIVE_BUSINESS_NO_DEPT,
            })


# =============================================================================
# LIST
# =============================================================================

class ObjectiveSignalListSerializer(_ObjectiveDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for ObjectiveSignal list endpoints.

    Exposes the canonical axes (what × dimension), the scope axis, the
    narrative summary, the target (contact or department — exactly one
    will be non-null per scope_level), and the target_date.

    signal_category is dropped from the base fields because the model
    shadow-overrides it to None for Objective.

    Note (history):
      Earlier versions noted that corroboration_count was excluded
      here for performance and only emitted by the Detail variant.
      CorroborationService was deprecated during the standardisation
      refactor and the field was removed from the Detail variant too;
      the cluster service's confirmation_count is the replacement
      metric.
    """

    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    scope_level_display = serializers.SerializerMethodField()
    target_contact      = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = ObjectiveSignal

        # Drop signal_category / signal_category_display from the inherited
        # field list — the model shadows them to None. All other base list
        # fields are kept as-is.
        _base_fields = [
            f for f in BaseSignalListSerializer.Meta.fields
            if f not in ('signal_category', 'signal_category_display')
        ]

        fields = _base_fields + [
            # Canonical axes
            'what',        'what_display',
            'dimension',   'dimension_display',
            # Scope
            'scope_level', 'scope_level_display',
            # Narrative
            'summary',
            # Target (conditional on scope_level)
            'target_contact',
            'target_department',
            # Timeline
            'target_date',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class ObjectiveSignalDetailSerializer(_ObjectiveDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for ObjectiveSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer. Adds
    success_criteria + notes on top of the list payload.

    signal_category is dropped from the base fields (shadow override on
    the model).

    Note (history):
      Earlier versions inherited a `corroboration_count` field from
      BaseSignalDetailSerializer. CorroborationService was deprecated
      during the standardisation refactor and the field was removed
      from the base detail serializer; the cluster service's
      confirmation_count is the replacement metric.
    """

    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    scope_level_display = serializers.SerializerMethodField()
    target_contact      = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = ObjectiveSignal

        _base_fields = [
            f for f in BaseSignalDetailSerializer.Meta.fields
            if f not in ('signal_category', 'signal_category_display')
        ]

        fields = _base_fields + [
            # Canonical axes
            'what',        'what_display',
            'dimension',   'dimension_display',
            # Scope
            'scope_level', 'scope_level_display',
            # Narrative
            'summary',
            'success_criteria',
            'notes',
            # Target (conditional)
            'target_contact',
            'target_department',
            # Timeline
            'target_date',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class ObjectiveSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for ObjectiveSignal creation.

    signal_type is fixed to 'objective' via HiddenField.

    Required fields:
      - what
      - dimension
      - scope_level
      - summary

    Optional fields:
      - success_criteria, notes
      - target_date
      - target_contact, target_department (constrained by scope_level)
      - source_activity (optional for MVP — see model docstring)

    Scope-conditional rules (mirror of ObjectiveSignal.clean()):
      - PERSONAL   → target_contact required, target_department forbidden
      - DEPARTMENT → target_department required, target_contact forbidden
      - BUSINESS   → neither target_contact nor target_department

    signal_category is dropped from the base fields (shadow override on
    the model).

    Source contacts:
      Contacts associated with the source conversation are derived
      from source_activity.contacts at read time and exposed via the
      standardised `source_context` block. The signal does not carry
      a writable source_contact / source_department — both fields
      were retired from BaseSignal during the standardisation
      refactor. target_contact and target_department remain (they
      describe the OWNER of the objective, not its source) and are
      governed by the scope-conditional rules above.
    """

    signal_type = serializers.HiddenField(default='objective')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = ObjectiveSignal

        # Drop signal_category from the inherited writable fields —
        # the model has no such column.
        _base_fields = [
            f for f in BaseSignalCreateSerializer.Meta.fields
            if f != 'signal_category'
        ]

        fields = _base_fields + [
            # Canonical axes
            'what',
            'dimension',
            # Scope
            'scope_level',
            # Narrative
            'summary',
            'success_criteria',
            'notes',
            # Target (conditional)
            'target_contact',
            'target_department',
            # Timeline
            'target_date',
        ]

        # Strip signal_category from extra_kwargs too — referencing a
        # non-declared field would raise a config error at class load.
        _base_extra_kwargs = {
            k: v for k, v in BaseSignalCreateSerializer.Meta.extra_kwargs.items()
            if k != 'signal_category'
        }

        extra_kwargs = {
            **_base_extra_kwargs,
            'what':              {'required': True},
            'dimension':         {'required': True},
            'scope_level':       {'required': True},
            'summary':           {'required': True},
            'success_criteria':  {'required': False, 'allow_blank': True},
            'notes':             {'required': False, 'allow_blank': True},
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'target_date':       {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        """
        Enforce scope-conditional target rules, then delegate to base.

        `target_contact` and `target_department` default to None when
        absent from the payload — the helper handles both "missing" and
        "explicit null" the same way, which matches the model-level
        clean() semantics.
        """
        _validate_scope_consistency(
            scope_level=attrs.get('scope_level'),
            target_contact=attrs.get('target_contact'),
            target_department=attrs.get('target_department'),
        )

        # Delegate to base for cross-account source_contact check + client_id
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class ObjectiveSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for ObjectiveSignal.

    Allowed beyond base fields:
      - what, dimension     (canonical axes — canonical_key recomputed by
                             model.save())
      - scope_level         (triggers scope-conditional merged-state check)
      - summary, success_criteria, notes
      - target_contact, target_department
      - target_date

    Merged-state scope validation:
      When the payload changes `scope_level`, `target_contact`, or
      `target_department`, we merge the partial payload with the
      current instance state and run the same scope-consistency check
      as Create. This is the pattern used by ImpactSignal.update().

      Example — switching a BUSINESS objective to PERSONAL:
        PATCH { scope_level: 'PERSONAL' }          → rejected
                                                      (missing target_contact)
        PATCH { scope_level: 'PERSONAL',
                target_contact: <uuid> }           → accepted

    canonical_key itself is NOT writable — it is derived from
    what × dimension by model.save().

    signal_category is dropped (shadow override on the model).
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = ObjectiveSignal

        # Drop signal_category from the inherited writable fields.
        _base_fields = [
            f for f in BaseSignalUpdateSerializer.Meta.fields
            if f != 'signal_category'
        ]

        fields = _base_fields + [
            # Canonical axes
            'what',
            'dimension',
            # Scope
            'scope_level',
            # Narrative
            'summary',
            'success_criteria',
            'notes',
            # Target (conditional)
            'target_contact',
            'target_department',
            # Timeline
            'target_date',
        ]

        _base_extra_kwargs = {
            k: v for k, v in BaseSignalUpdateSerializer.Meta.extra_kwargs.items()
            if k != 'signal_category'
        }

        extra_kwargs = {
            **_base_extra_kwargs,
            'what':              {'required': False},
            'dimension':         {'required': False},
            'scope_level':       {'required': False},
            'summary':           {'required': False},
            'success_criteria':  {'required': False, 'allow_blank': True},
            'notes':             {'required': False, 'allow_blank': True},
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'target_date':       {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        """
        Merged-state scope consistency check on partial payload.

        Only runs when at least one of scope_level / target_contact /
        target_department is touched — otherwise the instance is
        already in a valid state and nothing to re-check.
        """
        instance = self.instance

        touched_scope_fields = any(
            field in attrs
            for field in ('scope_level', 'target_contact', 'target_department')
        )

        if touched_scope_fields and instance is not None:
            # Merge: for fields NOT in attrs, fall back to the instance
            # current value. For fields IN attrs, use the new value —
            # including explicit None (the caller is clearing the field).
            merged_scope = (
                attrs['scope_level']
                if 'scope_level' in attrs
                else instance.scope_level
            )
            merged_target_contact = (
                attrs['target_contact']
                if 'target_contact' in attrs
                else instance.target_contact
            )
            merged_target_department = (
                attrs['target_department']
                if 'target_department' in attrs
                else instance.target_department
            )

            _validate_scope_consistency(
                scope_level=merged_scope,
                target_contact=merged_target_contact,
                target_department=merged_target_department,
            )

        return super().validate(attrs)