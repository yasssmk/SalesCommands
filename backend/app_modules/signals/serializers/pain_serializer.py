# app_modules/signals/serializers/pain_serializer.py
"""
Serializers for PainSignal.

Pain = the diagnosis (qualitative, narrative). Metrics, impacted parties,
and human consequences all live on PainImpact (see pain_impact_serializer).

Stack:
  PainSignalListSerializer   — lightweight list view + nested impacts (read)
  PainSignalDetailSerializer — full detail + corroboration_count + impacts
  PainSignalCreateSerializer — write path: strict source_activity requirement
  PainSignalUpdateSerializer — restricted PATCH, allows canonical changes

Impacts are exposed read-only here. Creating, updating, or deleting an
impact happens through dedicated /module-signals/pain-impacts/ endpoints.
This keeps the write surface small and avoids nested-write complexity
(transactions, partial-failure semantics, idempotency).
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
from .pain_impact_serializer import PainImpactReadSerializer


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


# =============================================================================
# LIST
# =============================================================================

class PainSignalListSerializer(_PainDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for PainSignal list endpoints.

    Exposes the canonical axes, the narrative content (summary only —
    not notes, which belong to the detail view), and nested impacts in
    read-only form so the UI can render a pain card with its evidence
    at-a-glance.

    corroboration_count is excluded here for performance — available in
    Detail only.
    """

    # Canonical axes
    what_display      = serializers.SerializerMethodField()
    dimension_display = serializers.SerializerMethodField()

    # Read-only nested impacts — via the reverse relation 'impacts'
    # on PainSignal (declared by the FK related_name on PainImpact).
    impacts = PainImpactReadSerializer(many=True, read_only=True)

    class Meta(BaseSignalListSerializer.Meta):
        model = PainSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            # Canonical axes (form canonical_key)
            'what', 'what_display',
            'dimension', 'dimension_display',
            # Narrative
            'summary',
            # Nested impacts (read-only)
            'impacts',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class PainSignalDetailSerializer(_PainDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for PainSignal retrieve endpoints.

    Inherits corroboration_count from BaseSignalDetailSerializer.
    Adds notes on top of the list payload, plus nested impacts.
    """

    what_display      = serializers.SerializerMethodField()
    dimension_display = serializers.SerializerMethodField()

    impacts = PainImpactReadSerializer(many=True, read_only=True)

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PainSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'summary',
            'notes',
            'impacts',
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
      - source_contact  (always required)
      - source_activity (required — every pain must have a conversational
                         origin; see Sprint 1.6 model docstring)

    Impacts are NOT accepted here. To attach evidence to a pain, use the
    dedicated POST /module-signals/pain-impacts/ endpoint with pain_signal
    set to the created pain's UUID.
    """

    signal_type = serializers.HiddenField(default='pain')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'what',
            'dimension',
            'summary',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'what':      {'required': True},
            'dimension': {'required': True},
            'summary':   {'required': True},
            'notes':     {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce Pain-specific contextual rules, then delegate to base.

        Rules:
          1. source_contact always required.
          2. source_activity always required — every Pain must be tied
             to a real conversation (stricter than BaseSignal, where
             activity is optional).
        """
        # Rule 1 — source_contact
        if not attrs.get('source_contact'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_CONTACT_REQUIRED
            )

        # Rule 2 — source_activity (strict for Pain)
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        # Delegate to base for cross-account source_contact check + client_id
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class PainSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for PainSignal.

    Allowed beyond base fields: what, dimension, summary, notes.

    Changing `what` or `dimension` is allowed — the model's save() recomputes
    canonical_key automatically. A pain can therefore be re-classified
    across clusters via a simple PATCH (e.g. the rep realizes it's actually
    DATA × QUALITY, not OPS × QUALITY).

    canonical_key itself is NOT writable: it is derived, not authored.
    Cluster metadata is recomputed on read from the current canonical_key.

    Impacts cannot be mutated via this endpoint. Use the dedicated
    /module-signals/pain-impacts/{id}/ endpoint for impact CRUD.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'what',
            'dimension',
            'summary',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'what':      {'required': False},
            'dimension': {'required': False},
            'summary':   {'required': False},
            'notes':     {'required': False, 'allow_blank': True},
        }