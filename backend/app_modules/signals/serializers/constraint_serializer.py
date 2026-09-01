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

  - ConstraintSignal is classified on `nature` (ConstraintNature). It is
    detached from the business what × dimension axes: `what` / `dimension`
    are legacy-nullable (still exposed read-only for historical rows, no
    longer authored on Create/Update) and canonical_key stays None.

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

from app_modules.core_modules.models import StandardDepartment

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

    def get_nature_display(self, obj):
        return obj.get_nature_display() if obj.nature else None

    def get_what_display(self, obj):
        return obj.get_what_display() if obj.what else None

    def get_dimension_display(self, obj):
        return obj.get_dimension_display() if obj.dimension else None

    def get_rigidity_display(self, obj):
        return obj.get_rigidity_display() if obj.rigidity else None

    def get_target_departments(self, obj):
        """
        Compact list of the departments this constraint concerns
        (multi-department). Returns a list of {id, name} payloads, one entry
        per linked StandardDepartment. Empty list when none are designated.

        N+1-safe: reads obj.target_departments.all(), which the ViewSet
        prefetches (prefetch_related('target_departments')); `.all()` (not a
        filtered queryset) hits the prefetched cache. Mirrors
        _TechStackDisplayMixin.get_usage_departments.
        """
        return [
            {
                'id':   str(d.id),
                'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
            }
            for d in obj.target_departments.all()
        ]


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

    Exposes the classification axis (nature), the narrative summary,
    rigidity, and target department (compact payload). Legacy what /
    dimension are exposed read-only for historical rows.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    nature_display      = serializers.SerializerMethodField()
    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    rigidity_display    = serializers.SerializerMethodField()
    target_departments  = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = ConstraintSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'nature', 'nature_display',
            'summary',
            'rigidity', 'rigidity_display',
            'target_departments',
            # Legacy axes — read-only, present for historical rows.
            'what', 'what_display',
            'dimension', 'dimension_display',
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

    nature_display      = serializers.SerializerMethodField()
    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    rigidity_display    = serializers.SerializerMethodField()
    target_departments  = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = ConstraintSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'nature', 'nature_display',
            'summary',
            'notes',
            'rigidity', 'rigidity_display',
            'target_departments',
            # Legacy axes — read-only, present for historical rows.
            'what', 'what_display',
            'dimension', 'dimension_display',
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
      - nature             — constraint taxonomy (ConstraintNature enum)
      - summary            — free-text description
      - rigidity           — FIRM or FLEXIBLE

    Optional:
      - target_department  — FK to StandardDepartment
      - notes              — additional context
      - source_quote, language_original, source, confidence,
        is_inferred, metadata (inherited)

    Not authored here (detached): what / dimension. They are legacy
    nullable columns kept for historical rows; the Create path no longer
    accepts them (constraints are classified on `nature`).

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Validation (re-surfaced from ConstraintSignal.clean()):
      1. source_activity always required.
    """

    signal_type = serializers.HiddenField(default='constraint')

    # WHO the constraint concerns — multi-department M2M, written as a list of
    # StandardDepartment ids. PrimaryKeyRelatedField(many=True) validates each
    # id and hands SignalManager.create a list of instances, applied via .set()
    # after the row is saved (M2M can't be set pre-save). Same write shape as
    # TechStackSignal.usage_departments. Optional — [] means no department.
    # Replaces the legacy single-FK target_department (no longer written).
    target_departments = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=StandardDepartment.objects.all(),
    )

    class Meta(BaseSignalCreateSerializer.Meta):
        model = ConstraintSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'nature',
            'summary',
            'rigidity',
            'target_departments',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'nature':            {'required': True},
            'summary':           {'required': True},
            'rigidity':          {'required': True},
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
      - nature             — constraint taxonomy may be reclassified
      - summary, notes
      - rigidity           — constraint firmness may be reclassified
      - target_department  — department may be corrected

    Not authored here (detached): what / dimension — legacy nullable
    columns, no longer writable.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    # Multi-department scope, writable via a list of StandardDepartment ids
    # (same shape as Create). Applied via .set() by SignalManager on update;
    # PATCH { target_departments: [] } clears the set. Replaces the legacy
    # single-FK target_department (no longer written).
    target_departments = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=StandardDepartment.objects.all(),
    )

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = ConstraintSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'nature',
            'summary',
            'rigidity',
            'target_departments',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'nature':            {'required': False},
            'summary':           {'required': False},
            'rigidity':          {'required': False},
            'notes':             {'required': False, 'allow_blank': True},
        }
