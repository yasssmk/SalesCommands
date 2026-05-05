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
  - related_techstack : compact list of tools the pain points to

Validation rules surfaced from the model (PainSignal.clean):
  1. source_activity is required

The previous "source_contact required" rule was retired during the
standardisation refactor — the field was removed from BaseSignal.
Contacts are now derived from source_activity.contacts and exposed
via the standardised `source_context` block (read-only).

The source_activity rule is enforced at both the model level and the
serializer level. The model's clean() is invoked through full_clean()
inside SignalManager.create(); the serializer's validate() raises
StandardizedValidationError early so the response shape is consistent
with other DRF validation errors.
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

    def get_related_techstack(self, obj):
        """
        Compact catalog payload for the cross-reference FK.

        Mirror of TechStackSignal serializers' get_tech_catalog_entry —
        keeps the frontend from issuing a separate /tech-catalog/<id>/
        fetch just to render the tool name on a Pain card.

        Returns None when the FK is not set (the textual
        related_techstack_mention is exposed as a separate field).
        """
        entry = obj.related_techstack
        if not entry:
            return None
        return {
            'id':                    str(entry.id),
            'company_name':          entry.company_name,
            'product_name':          entry.product_name,
            'is_competitor':         entry.is_competitor,
            'is_integration_target': entry.is_integration_target,
        }


# =============================================================================
# LIST
# =============================================================================

class PainSignalListSerializer(_PainDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for PainSignal list endpoints.

    Exposes the canonical axes, the narrative content (summary only —
    not notes, which belong to the detail view), nested impacts in
    read-only form, and the optional cross-reference to a TechStack
    catalog entry.

    corroboration_count is excluded here for performance — Detail only.

    Cross-reference exposure (Sprint TechStack):
      - related_techstack          : compact catalog payload or None
      - related_techstack_mention  : free-text mention or empty string

    Both fields are emitted unconditionally — the UI hides them when
    what != 'TECH', but the API stays neutral. See PainSignal model
    docstring for the rationale.
    """

    # Canonical axes
    what_display      = serializers.SerializerMethodField()
    dimension_display = serializers.SerializerMethodField()

    # Cross-reference — compact catalog payload (read)
    related_techstack = serializers.SerializerMethodField()

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
            # Cross-reference — TechStack
            'related_techstack',
            'related_techstack_mention',
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
    Adds notes on top of the list payload, plus nested impacts and
    the optional TechStack cross-reference.
    """

    what_display      = serializers.SerializerMethodField()
    dimension_display = serializers.SerializerMethodField()

    # Cross-reference — compact catalog payload (read)
    related_techstack = serializers.SerializerMethodField()

    impacts = PainImpactReadSerializer(many=True, read_only=True)

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PainSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'what', 'what_display',
            'dimension', 'dimension_display',
            'summary',
            'notes',
            # Cross-reference — TechStack
            'related_techstack',
            'related_techstack_mention',
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
      - source_activity (required — every pain must have a conversational
                         origin; see Sprint 1.6 model docstring)

    Optional fields (Sprint TechStack):
      - related_techstack          — FK to TechCatalog, written as UUID
      - related_techstack_mention  — free-text tool mention

    Removed during the standardisation refactor:
      - "source_contact required" rule. The field was retired from
         BaseSignal — contacts associated with the source conversation
         are now derived from source_activity.contacts at read time
         and exposed via the standardised `source_context` block.

    The two cross-reference fields are independent and not mutually
    exclusive at the API level. The frontend is responsible for hiding
    them when what != 'TECH' — the backend stays permissive.

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
            # Cross-reference — TechStack
            'related_techstack',
            'related_techstack_mention',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'what':      {'required': True},
            'dimension': {'required': True},
            'summary':   {'required': True},
            'notes':     {'required': False, 'allow_blank': True},
            'related_techstack':         {'required': False, 'allow_null': True},
            'related_techstack_mention': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce Pain-specific contextual rules, then delegate to base.

        Rule (re-surfaced from PainSignal.clean()):
          1. source_activity always required — every Pain must be tied
             to a real conversation (stricter than BaseSignal, where
             activity is optional).

        Removed during the standardisation refactor:
          - "source_contact always required" rule. The field was
             retired from BaseSignal; contacts are derived from
             source_activity.contacts at read time.

        Cross-reference fields (related_techstack / related_techstack_mention)
        carry no model-level constraint — see PainSignal model docstring
        for the rationale of permissive backend behaviour.
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
      - what, dimension, summary, notes
      - related_techstack, related_techstack_mention  (Sprint TechStack)

    Changing `what` or `dimension` is allowed — the model's save() recomputes
    canonical_key automatically. A pain can therefore be re-classified
    across clusters via a simple PATCH (e.g. the rep realizes it's actually
    DATA × QUALITY, not OPS × QUALITY).

    canonical_key itself is NOT writable: it is derived, not authored.
    Cluster metadata is recomputed on read from the current canonical_key.

    Cross-reference fields support progressive enrichment:
      - PATCH related_techstack_mention='Salesforce' first
      - Later PATCH related_techstack=<uuid> when the catalog has been
        populated
      - The UI may then drop the mention textually, but the backend
        accepts both being set simultaneously without error.

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
            # Cross-reference — TechStack
            'related_techstack',
            'related_techstack_mention',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'what':      {'required': False},
            'dimension': {'required': False},
            'summary':   {'required': False},
            'notes':     {'required': False, 'allow_blank': True},
            'related_techstack':         {'required': False, 'allow_null': True},
            'related_techstack_mention': {'required': False, 'allow_blank': True},
        }