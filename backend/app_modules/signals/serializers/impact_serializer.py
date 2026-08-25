# app_modules/signals/serializers/impact_serializer.py
"""
ImpactSignal serializers.

Implements the four standard variants on top of BaseSignal* serializers:
  - ImpactSignalListSerializer
  - ImpactSignalDetailSerializer
  - ImpactSignalCreateSerializer
  - ImpactSignalUpdateSerializer

Also exposes:
  - canonical axes    : what / dimension (drive canonical_key)
  - scope_level       : organisational scope at which the impact is
                        measured (BUSINESS / DEPARTMENT / PERSONAL)
  - impact_type       : nature of the impact observation (FINANCIAL,
                        TIME, PRODUCTIVITY, REVENUE, RISK, CUSTOMER,
                        HUMAN, STRATEGIC, METRIC)
  - metric_text       : optional free-text quantification
  - human_impact      : optional HumanImpactType qualifier

Validation rules surfaced from the model (ImpactSignal.clean):
  1. source_activity is required

Contacts who participated in the source conversation are derived
from source_activity.contacts and exposed via the standardised
`source_context` block (read-only) on the base serializers.

The source_activity rule is enforced at both the model level and the
serializer level. The model's clean() is invoked through full_clean()
inside SignalManager.create(); the serializer's validate() raises
StandardizedValidationError early so the response shape is consistent
with other DRF validation errors.

Shadow-override of signal_category
----------------------------------
ImpactSignal shadow-overrides signal_category to None on the model
(see ImpactSignal class definition). The four serializers below
therefore filter the inherited `signal_category` / `signal_category_display`
fields out of their Meta.fields to avoid exposing a constantly-null
field. Same stance as TechStackSignal and ObjectiveSignal serializers.

Cross-field permissiveness
--------------------------
The data layer is intentionally permissive on (impact_type, human_impact,
metric_text) cross-field coherence — human_impact may be set on any
impact_type, metric_text may be set on any impact_type. Frontend UX
guidance may suggest defaults (human_impact primarily on
impact_type=HUMAN) but the API never enforces. Mirror of model
ImpactSignal.clean() stance.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import ImpactSignal
from .base_serializer import (
    BaseSignalListSerializer,
    BaseSignalDetailSerializer,
    BaseSignalCreateSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — shared display-field logic
# =============================================================================
#
# List and Detail expose the same display fields for the canonical axes,
# the scope axis, the impact_type axis, and the optional human_impact
# qualifier. A small mixin keeps the two serializers aligned when the
# schema evolves.
# =============================================================================


class _ImpactDisplayMixin:
    """Shared SerializerMethodField implementations for Impact serializers."""

    def get_what_display(self, obj):
        return obj.get_what_display() if obj.what else None

    def get_dimension_display(self, obj):
        return obj.get_dimension_display() if obj.dimension else None

    def get_scope_level_display(self, obj):
        return obj.get_scope_level_display() if obj.scope_level else None

    def get_impact_type_display(self, obj):
        return obj.get_impact_type_display() if obj.impact_type else None

    def get_human_impact_display(self, obj):
        return obj.get_human_impact_display() if obj.human_impact else None

    def get_target_department(self, obj):
        # Compact FK shape — mirrors _ObjectiveDisplayMixin.get_target_department.
        # Null when scope is BUSINESS (no department). id + human name.
        d = obj.target_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# LIST
# =============================================================================

class ImpactSignalListSerializer(_ImpactDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for ImpactSignal list endpoints.

    Exposes the canonical axes (what × dimension), the scope axis,
    the impact_type nature axis, the narrative summary, and the
    optional metric_text and human_impact fields.

    signal_category is shadow-overridden to None on the model and
    therefore filtered out of the inherited base fields.
    """

    # Canonical axes
    what_display         = serializers.SerializerMethodField()
    dimension_display    = serializers.SerializerMethodField()

    # Scope axis
    scope_level_display  = serializers.SerializerMethodField()
    target_department    = serializers.SerializerMethodField()

    # Impact nature axis
    impact_type_display  = serializers.SerializerMethodField()

    # Human qualifier (optional)
    human_impact_display = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = ImpactSignal
        # Strip signal_category and signal_category_display from the
        # inherited base fields — ImpactSignal shadow-overrides
        # signal_category to None at the model layer.
        fields = [
            f for f in BaseSignalListSerializer.Meta.fields
            if f not in ('signal_category', 'signal_category_display')
        ] + [
            # Canonical axes (form canonical_key)
            'what', 'what_display',
            'dimension', 'dimension_display',
            # Scope
            'scope_level', 'scope_level_display',
            'target_department',
            # Impact nature
            'impact_type', 'impact_type_display',
            # Narrative
            'summary',
            # Metric (optional)
            'metric_text',
            # Human dimension (optional)
            'human_impact', 'human_impact_display',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class ImpactSignalDetailSerializer(_ImpactDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for ImpactSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer. Adds
    the same Impact-specific fields as the List variant — ImpactSignal
    has no detail-only narrative beyond summary (no `notes` field).

    signal_category is shadow-overridden to None on the model and
    therefore filtered out of the inherited base fields.
    """

    # Canonical axes
    what_display         = serializers.SerializerMethodField()
    dimension_display    = serializers.SerializerMethodField()

    # Scope axis
    scope_level_display  = serializers.SerializerMethodField()
    target_department    = serializers.SerializerMethodField()

    # Impact nature axis
    impact_type_display  = serializers.SerializerMethodField()

    # Human qualifier (optional)
    human_impact_display = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = ImpactSignal
        fields = [
            f for f in BaseSignalDetailSerializer.Meta.fields
            if f not in ('signal_category', 'signal_category_display')
        ] + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'scope_level', 'scope_level_display',
            'target_department',
            'impact_type', 'impact_type_display',
            'summary',
            'metric_text',
            'human_impact', 'human_impact_display',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class ImpactSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for ImpactSignal creation.

    signal_type is fixed to 'impact' via HiddenField.

    Required fields:
      - what
      - dimension
      - scope_level
      - impact_type
      - summary
      - source_activity (every impact must have a conversational origin)

    Optional fields:
      - metric_text   — free-text quantification (e.g. "30k€/month",
                         "5h/week", "around 50 people")
      - human_impact  — HumanImpactType qualifier; typically paired
                         with impact_type=HUMAN but the API stays
                         permissive (any combination accepted)

    Contacts who participated in the source conversation are derived
    from source_activity.contacts and exposed read-only via the
    standardised `source_context` block — the signal itself does not
    carry a source_contact FK.

    signal_category is shadow-overridden to None on the model and
    therefore filtered out of the inherited base fields. The signal
    type IS the categorisation here (impact_type axis).
    """

    signal_type = serializers.HiddenField(default='impact')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = ImpactSignal
        # Strip signal_category from the inherited base fields —
        # shadow-overridden to None at the model layer.
        fields = [
            f for f in BaseSignalCreateSerializer.Meta.fields
            if f != 'signal_category'
        ] + [
            'what',
            'dimension',
            'scope_level',
            'impact_type',
            'summary',
            'metric_text',
            'human_impact',
        ]
        # Filter signal_category from the inherited extra_kwargs so
        # DRF does not try to apply rules to a non-existent field.
        extra_kwargs = {
            k: v
            for k, v in BaseSignalCreateSerializer.Meta.extra_kwargs.items()
            if k != 'signal_category'
        }
        extra_kwargs.update({
            'what':         {'required': True},
            'dimension':    {'required': True},
            'scope_level':  {'required': True},
            'impact_type':  {'required': True},
            'summary':      {'required': True},
            'metric_text':  {'required': False, 'allow_blank': True},
            'human_impact': {'required': False, 'allow_null': True},
        })

    def validate(self, attrs):
        """
        Enforce ImpactSignal-specific contextual rules, then delegate
        to base.

        Rule (re-surfaced from ImpactSignal.clean()):
          1. source_activity always required — every Impact must be
             tied to a real conversation (stricter than BaseSignal,
             where activity is optional).

        No cross-field rules on (impact_type, human_impact, metric_text):
          the model layer stays permissive on cross-field coherence —
          see ImpactSignal.clean() docstring for the rationale.
        """
        # Rule 1 — source_activity (strict for Impact)
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        # Delegate to base for client_id injection.
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class ImpactSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for ImpactSignal.

    Allowed beyond base fields:
      - what, dimension         — canonical axes (canonical_key
                                   recomputed by model.save())
      - scope_level             — scope axis (re-anchors the impact
                                   at a different organisational layer)
      - impact_type             — nature axis (re-classifies the
                                   impact's flavour)
      - summary
      - metric_text             — re-stating or refining the metric
                                   as new evidence emerges
      - human_impact            — set / unset / re-qualify the human
                                   dimension

    Changing `what` or `dimension` is allowed — the model's save()
    recomputes canonical_key automatically. An impact can therefore be
    re-classified across clusters via a simple PATCH (e.g. the rep
    realizes it is actually DATA × QUALITY, not OPS × QUALITY).

    canonical_key itself is NOT writable: it is derived, not authored.
    Cluster metadata is recomputed on read from the current canonical_key.

    signal_category is shadow-overridden to None on the model and
    therefore filtered out of the inherited base fields.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = ImpactSignal
        # Strip signal_category from the inherited base fields —
        # shadow-overridden to None at the model layer.
        fields = [
            f for f in BaseSignalUpdateSerializer.Meta.fields
            if f != 'signal_category'
        ] + [
            'what',
            'dimension',
            'scope_level',
            'impact_type',
            'summary',
            'metric_text',
            'human_impact',
        ]
        extra_kwargs = {
            k: v
            for k, v in BaseSignalUpdateSerializer.Meta.extra_kwargs.items()
            if k != 'signal_category'
        }
        extra_kwargs.update({
            'what':         {'required': False},
            'dimension':    {'required': False},
            'scope_level':  {'required': False},
            'impact_type':  {'required': False},
            'summary':      {'required': False},
            'metric_text':  {'required': False, 'allow_blank': True},
            'human_impact': {'required': False, 'allow_null': True},
        })