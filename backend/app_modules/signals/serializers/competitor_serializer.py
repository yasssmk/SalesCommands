# app_modules/signals/serializers/competitor_serializer.py
"""
Serializers for CompetitorSignal.

Stack (cloned on constraint_serializer.py, but simpler — CompetitorSignal
has no nature / rigidity / target_department / scope / what × dimension):
  CompetitorSignalListSerializer   — lightweight list view
  CompetitorSignalDetailSerializer — full detail (validated_*, requested_by,
                                      source_quote, metadata, original_value
                                      on top of the list payload)
  CompetitorSignalCreateSerializer — write path
  CompetitorSignalUpdateSerializer — restricted PATCH

Notes:
  - The model shadow-overrides `signal_category` to None on the concrete
    CompetitorSignal. Among the base serializer fields, only
    `signal_category` (and its `signal_category_display` companion) needs
    filtering — same pattern as ConstraintSignalSerializer.
  - CompetitorSignal is identified by `competitor_name` (raw) + the derived
    `competitor_name_normalized` grouping key; canonical_key stays None.
  - source_activity is required at the model layer (CompetitorSignal.clean)
    and re-surfaced at the Create serializer for a clean API error payload,
    mirroring ConstraintSignal.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import CompetitorSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# CompetitorSignal shadow-overrides `signal_category` to None on the concrete
# model. Among the base serializer fields, only signal_category and its
# signal_category_display companion need to be stripped (mirror of Constraint).

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})


def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without Competitor's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without Competitor's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class CompetitorSignalListSerializer(BaseSignalListSerializer):
    """
    Lightweight serializer for CompetitorSignal list endpoints.

    Exposes the competitor identity (competitor_name) and the narrative
    summary. signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    class Meta(BaseSignalListSerializer.Meta):
        model = CompetitorSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'competitor_name',
            'summary',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class CompetitorSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for CompetitorSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer.

    signal_category / signal_category_display are stripped from inherited
    fields (model shadow-overrides signal_category to None).
    """

    class Meta(BaseSignalDetailSerializer.Meta):
        model = CompetitorSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'competitor_name',
            'summary',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class CompetitorSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for CompetitorSignal creation.

    signal_type is fixed to 'competitor' via HiddenField (consumed by
    SignalManager.create()).

    Required:
      - account            (inherited)
      - source_activity    — every competitor must be tied to a conversation
      - competitor_name    — the competing tool / vendor
      - summary            — one-sentence description

    Optional (inherited):
      - source_quote, language_original, source, confidence, is_inferred, metadata

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Validation (re-surfaced from CompetitorSignal.clean()):
      1. source_activity always required.
    """

    signal_type = serializers.HiddenField(default='competitor')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = CompetitorSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'competitor_name',
            'summary',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'competitor_name': {'required': True},
            'summary':         {'required': True},
        }

    def validate(self, attrs):
        """
        Enforce Competitor-specific contextual rules, then delegate to base.

        Rule (re-surfaced from CompetitorSignal.clean()):
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

class CompetitorSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for CompetitorSignal.

    Allowed beyond base fields (source_quote, metadata):
      - competitor_name    — the competitor may be corrected
      - summary

    signal_category / signal_category_display are stripped from inherited
    fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = CompetitorSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'competitor_name',
            'summary',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'competitor_name': {'required': False},
            'summary':         {'required': False},
        }
