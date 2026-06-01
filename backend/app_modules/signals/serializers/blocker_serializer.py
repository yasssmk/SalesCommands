# app_modules/signals/serializers/blocker_serializer.py
"""
Serializers for BlockerSignal.

Stack:
  BlockerSignalListSerializer   — lightweight list view
  BlockerSignalDetailSerializer — full detail (validated_*, requested_by,
                                  source_quote, metadata, original_value
                                  on top of the list payload)
  BlockerSignalCreateSerializer — write path
  BlockerSignalUpdateSerializer — restricted PATCH

Notes:
  - The model shadow-overrides `signal_category` to None on the
    concrete BlockerSignal. Among the base serializer fields, only
    `signal_category` (and its `signal_category_display` companion)
    requires filtering — same pattern as TechStackSignalSerializer.

  - BlockerSignal does not carry canonical axes (no `what` / `dimension`)
    and does not participate in cluster aggregation. The inherited
    `canonical_key` field stays in the base fields for shape
    consistency but is always None on a BlockerSignal — see
    BlockerSignal.save().

  - `contact` (FK Contact) is the blocker-specific attribution surface;
    contacts who participated in the conversation remain accessible
    read-only through the standardised `source_context` block produced
    by SignalSourceSerializer.

  - source_activity is required at the model layer (BlockerSignal.clean)
    and re-surfaced at the Create serializer for a clean API error
    payload, mirroring PainSignal.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import BlockerSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — display + compact contact
# =============================================================================

class _BlockerDisplayMixin:
    """Shared SerializerMethodField implementations for Blocker serializers."""

    def get_contact(self, obj):
        """
        Compact contact payload — keeps the frontend from issuing a
        separate /contacts/<id>/ fetch just to render the attribution
        on a blocker card. Returns None when the FK is not set.
        """
        contact = obj.contact
        if not contact:
            return None
        return {
            'id':         str(contact.id),
            'first_name': contact.first_name,
            'last_name':  contact.last_name,
            'job_title':  getattr(contact, 'job_title', None),
        }


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# BlockerSignal shadow-overrides `signal_category` to None on the
# concrete model. Among the base serializer fields, only signal_category
# and its signal_category_display companion need to be stripped — they
# are declared at the top level of BaseSignalListSerializer /
# BaseSignalDetailSerializer / BaseSignalCreateSerializer /
# BaseSignalUpdateSerializer. We strip them here once and reuse the
# resulting filtered lists in every Meta below — keeps the four
# serializers in sync. Same pattern as TechStackSignalSerializer.

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})


def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without Blocker's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without Blocker's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class BlockerSignalListSerializer(_BlockerDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for BlockerSignal list endpoints.

    Exposes the free-text `summary`, the optional blocker-specific
    `contact` attribution (compact payload), and the standardised
    `source_context` block inherited from the base.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    contact = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = BlockerSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'summary',
            'contact',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class BlockerSignalDetailSerializer(_BlockerDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for BlockerSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    contact = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = BlockerSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'summary',
            'contact',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class BlockerSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for BlockerSignal creation.

    signal_type is fixed to 'blocker' via HiddenField (consumed by
    SignalManager.create() — same identifier across all layers).

    Required:
      - account            (inherited)
      - source_activity    — every blocker must be tied to a conversation
      - summary            — free-text description of the blocker

    Optional:
      - contact            — FK to Contact who raised the blocker
      - source_quote, language_original, source, confidence,
        is_inferred, metadata (inherited)

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    source_activity rule is enforced at both the model level
    (BlockerSignal.clean) and the serializer level for a consistent
    API error payload — mirror of PainSignal.
    """

    signal_type = serializers.HiddenField(default='blocker')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = BlockerSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'summary',
            'contact',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'summary': {'required': True},
            'contact': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        """
        Enforce Blocker-specific contextual rules, then delegate to base.

        Rule (re-surfaced from BlockerSignal.clean()):
          1. source_activity always required — every blocker must be tied
             to a real conversation.
        """
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class BlockerSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for BlockerSignal.

    Allowed beyond base fields (source_quote, metadata):
      - summary  — free-text narrative may be refined post-extraction
      - contact  — attribution may be amended (e.g. corrected from null
                   to a specific contact once the rep recalls who raised
                   the blocker)

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = BlockerSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'summary',
            'contact',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'summary': {'required': False},
            'contact': {'required': False, 'allow_null': True},
        }
