# app_modules/signals/serializers/pain_serializer.py
"""
PainSignal serializers.

Implements the four standard variants on top of BaseSignal* serializers:
  - PainSignalListSerializer
  - PainSignalDetailSerializer
  - PainSignalCreateSerializer
  - PainSignalUpdateSerializer

Also exposes:
  - canonical axes    : what / dimension (drive canonical_key)
  - scope_level       : organisational scope at which the pain is felt
                        (BUSINESS / DEPARTMENT / PERSONAL) — defaults to
                        BUSINESS at the model layer if not provided
  - related_techstack_mention : free-text tool reference when the pain points
                        to a tool, as free text

Validation rules surfaced from the model (PainSignal.clean):
  1. source_activity is required

Contacts who participated in the source conversation are derived
from source_activity.contacts and exposed via the standardised
`source_context` block (read-only) on the base serializers.

The source_activity rule is enforced at both the model level and the
serializer level. The model's clean() is invoked through full_clean()
inside SignalManager.create(); the serializer's validate() raises
StandardizedValidationError early so the response shape is consistent
with other DRF validation errors.

Impact-level evidence (metrics, human consequences, quantified
proof) is captured by ImpactSignal — a separate first-class signal
type sharing the same (what, dimension) canonical axes as PainSignal.
A Pain cluster and an Impact cluster on the same (what × dimension)
can be cross-referenced at the cluster layer; the relationship is
not modelled as an FK on either side.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import PainSignal
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
# List and Detail expose the same display fields for the canonical axes.
# A small mixin keeps the two serializers aligned when the schema evolves.
# =============================================================================


class _PainDisplayMixin:
    """Shared SerializerMethodField implementations for Pain serializers."""

    def get_what_display(self, obj):
        return obj.get_what_display() if obj.what else None

    def get_dimension_display(self, obj):
        return obj.get_dimension_display() if obj.dimension else None

    def get_scope_level_display(self, obj):
        return obj.get_scope_level_display() if obj.scope_level else None

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

class PainSignalListSerializer(_PainDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for PainSignal list endpoints.

    Exposes the canonical axes (what × dimension), the scope axis, the
    narrative summary (notes live on the detail view), and the optional
    free-text cross-reference to a tool.

    Cross-reference exposure:
      - related_techstack_mention  : free-text mention or empty string

    Both fields are emitted unconditionally — the UI hides them when
    what != 'TECH', but the API stays neutral. See PainSignal model
    docstring for the rationale.
    """

    # Canonical axes
    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()

    # Scope axis
    scope_level_display = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    # Cross-reference — free-text tool mention

    class Meta(BaseSignalListSerializer.Meta):
        model = PainSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            # Canonical axes (form canonical_key)
            'what', 'what_display',
            'dimension', 'dimension_display',
            # Scope
            'scope_level', 'scope_level_display',
            'target_department',
            # Narrative
            'summary',
            # Cross-reference — TechStack
            'related_techstack_mention',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class PainSignalDetailSerializer(_PainDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for PainSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer. Adds
    scope_level, notes, and the optional TechStack cross-reference on
    top of the list payload.
    """

    what_display        = serializers.SerializerMethodField()
    dimension_display   = serializers.SerializerMethodField()
    scope_level_display = serializers.SerializerMethodField()
    target_department   = serializers.SerializerMethodField()

    # Cross-reference — free-text tool mention

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PainSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'scope_level', 'scope_level_display',
            'target_department',
            'summary',
            'notes',
            # Cross-reference — TechStack
            'related_techstack_mention',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class PainSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for PainSignal creation.

    signal_type is fixed to 'pain' via HiddenField.

    Required fields:
      - what
      - dimension
      - summary
      - source_activity (every pain must have a conversational origin)

    Optional fields:
      - scope_level                — defaults to BUSINESS at the model
                                      layer when omitted
      - notes                      — free-text additional context
      - related_techstack_mention  — free-text tool mention

    Contacts who participated in the source conversation are derived
    from source_activity.contacts and exposed read-only via the
    standardised `source_context` block — the signal itself does not
    carry a source_contact FK.

    The two cross-reference fields are independent and not mutually
    exclusive at the API level. The frontend is responsible for hiding
    them when what != 'TECH' — the backend stays permissive.

    Impact-level evidence (metrics, human consequences) is not
    accepted here. ImpactSignal is a separate first-class signal type;
    use POST /module-signals/impact/ to record an impact observation
    on the same (what, dimension) axes.
    """

    signal_type = serializers.HiddenField(default='pain')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'what',
            'dimension',
            'scope_level',
            'summary',
            'notes',
            # Cross-reference — TechStack
            'related_techstack_mention',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'what':        {'required': True},
            'dimension':   {'required': True},
            'scope_level': {'required': False},  # default BUSINESS at model
            'summary':     {'required': True},
            'notes':       {'required': False, 'allow_blank': True},
            'related_techstack_mention': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce Pain-specific contextual rules, then delegate to base.

        Rule (re-surfaced from PainSignal.clean()):
          1. source_activity always required — every Pain must be tied
             to a real conversation (stricter than BaseSignal, where
             activity is optional).

        The cross-reference field (related_techstack_mention)
        carry no model-level constraint — see PainSignal model docstring
        for the rationale of permissive backend behaviour.

        scope_level is not validated here: it has a model-level default
        (BUSINESS) that guarantees the column is never empty, even when
        the API omits the value entirely.
        """
        # Rule 1 — source_activity (strict for Pain)
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        # Delegate to base for client_id injection.
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class PainSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for PainSignal.

    Allowed beyond base fields:
      - what, dimension          — canonical axes (canonical_key recomputed
                                    by model.save())
      - scope_level              — scope axis (re-anchors the pain at a
                                    different organisational layer)
      - summary, notes
      - related_techstack_mention

    Changing `what` or `dimension` is allowed — the model's save() recomputes
    canonical_key automatically. A pain can therefore be re-classified
    across clusters via a simple PATCH (e.g. the rep realizes it's actually
    DATA × QUALITY, not OPS × QUALITY).

    canonical_key itself is NOT writable: it is derived, not authored.
    Cluster metadata is recomputed on read from the current canonical_key.

    `related_techstack_mention` is free text — a trace of the tool
    involved in the pain. Its structured FK companion was removed in S10
    along with the tech catalogue.

    Impact-level evidence (metrics, human consequences) is not mutated
    here. ImpactSignal is a separate first-class signal type with its
    own CRUD endpoints at /module-signals/impact/.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'what',
            'dimension',
            'scope_level',
            'summary',
            'notes',
            # Cross-reference — TechStack
            'related_techstack_mention',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'what':        {'required': False},
            'dimension':   {'required': False},
            'scope_level': {'required': False},
            'summary':     {'required': False},
            'notes':       {'required': False, 'allow_blank': True},
            'related_techstack_mention': {'required': False, 'allow_blank': True},
        }