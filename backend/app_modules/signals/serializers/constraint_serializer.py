# app_modules/signals/serializers/constraint_serializer.py
"""
Serializers for ConstraintSignal.

Stack:
  ConstraintSignalListSerializer   — lightweight list view
  ConstraintSignalDetailSerializer — full detail (validated_*, requested_by,
                                      source_quote, metadata, original_value
                                      on top of the list payload)
  ConstraintSignalCreateSerializer — write path
  ConstraintSignalUpdateSerializer — restricted PATCH

Notes:
  - The model shadow-overrides `signal_category` to None on the
    concrete ConstraintSignal. Among the base serializer fields, only
    `signal_category` (and its `signal_category_display` companion)
    requires filtering — same pattern as PainSignalSerializer (for
    non-category types).

  - ConstraintSignal participates in the cluster model via canonical
    axes (what × dimension). canonical_key is auto-computed in save()
    as "constraint:<what>:<dimension>".

  - `target_department` (FK StandardDepartment) identifies the
    department that owns or enforces the constraint.

  - `rigidity` (FIRM / FLEXIBLE) distinguishes non-negotiable criteria
    from preferences.

  - source_activity is required at the model layer (ConstraintSignal.clean)
    and re-surfaced at the Create serializer for a clean API error
    payload, mirroring PainSignal.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import ConstraintSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — shared display-field logic
# =============================================================================

class _ConstraintDisplayMixin:
    """Shared SerializerMethodField implementations for Constraint serializers."""

    def get_what_display(self, obj):
        return obj.get_what_display() if obj.what else None

    def get_dimension_display(self, obj):
        return obj.get_dimension_display() if obj.dimension else None

    def get_rigidity_display(self, obj):
        return obj.get_rigidity_display() if obj.rigidity else None

    def get_target_department(self, obj):
        """Compact department payload. Returns None when the FK is not set."""
        dept = obj.target_department
        if not dept:
            return None
        return {
            'id':   str(dept.id),
            'name': dept.get_name_display(),
        }


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# ConstraintSignal shadow-overrides `signal_category` to None on the
# concrete model. Among the base serializer fields, only signal_category
# and its signal_category_display companion need to be stripped.

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})


def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without Constraint's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without Constraint's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class ConstraintSignalListSerializer(_ConstraintDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for ConstraintSignal list endpoints.

    Exposes the canonical axes (what × dimension), the narrative summary,
    rigidity, and target department (compact payload).

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    rigidity_display    = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = ConstraintSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'summary',
            'rigidity', 'rigidity_display',
            'target_department',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class ConstraintSignalDetailSerializer(_ConstraintDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for ConstraintSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    rigidity_display    = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = ConstraintSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'summary',
            'notes',
            'rigidity', 'rigidity_display',
            'target_department',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class ConstraintSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for ConstraintSignal creation.

    signal_type is fixed to 'constraint' via HiddenField (consumed by
    SignalManager.create()).

    Required:
      - account            (inherited)
      - source_activity    — every constraint must be tied to a conversation
      - what               — domain axis (SignalWhat enum)
      - dimension          — friction axis (SignalDimension enum)
      - summary            — free-text description
      - rigidity           — FIRM or FLEXIBLE

    Optional:
      - target_department  — FK to StandardDepartment
      - notes              — additional context
      - source_quote, language_original, source, confidence,
        is_inferred, metadata (inherited)

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Validation (re-surfaced from ConstraintSignal.clean()):
      1. source_activity always required.
    """

    signal_type = serializers.HiddenField(default='constraint')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = ConstraintSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'what',
            'dimension',
            'summary',
            'rigidity',
            'target_department',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'what':              {'required': True},
            'dimension':         {'required': True},
            'summary':           {'required': True},
            'rigidity':          {'required': True},
            'target_department': {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce Constraint-specific contextual rules, then delegate to base.

        Rule (re-surfaced from ConstraintSignal.clean()):
          1. source_activity always required.
        """
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class ConstraintSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for ConstraintSignal.

    Allowed beyond base fields (source_quote, metadata):
      - what, dimension    — canonical axes (canonical_key recomputed
                              by model.save())
      - summary, notes
      - rigidity           — constraint firmness may be reclassified
      - target_department  — department may be corrected

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = ConstraintSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'what',
            'dimension',
            'summary',
            'rigidity',
            'target_department',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'what':              {'required': False},
            'dimension':         {'required': False},
            'summary':           {'required': False},
            'rigidity':          {'required': False},
            'target_department': {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }
