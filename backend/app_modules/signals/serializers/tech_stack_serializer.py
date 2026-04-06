# app_modules/signals/serializers/tech_stack_serializer.py
"""
Concrete serializers for TechStackSignal.

Inherits shared logic from base_serializer and adds tech_name,
which is the only field specific to TechStackSignal beyond BaseSignal.

tech_name is:
  - Exposed (read) on list and detail views.
  - Accepted (write) on create — optional, free text.
  - Not modifiable via PATCH (tool identity should not change after creation;
    create a new signal instead).
"""

from rest_framework import serializers

from ..models import TechStackSignal
from .base_serializer import (
    BaseSignalListSerializer,
    BaseSignalDetailSerializer,
    BaseSignalCreateSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# LIST
# =============================================================================

class TechStackSignalListSerializer(BaseSignalListSerializer):
    """
    Lightweight serializer for TechStackSignal list endpoints.

    Adds tech_name to the standard list fields.
    """

    class Meta(BaseSignalListSerializer.Meta):
        model  = TechStackSignal
        fields = BaseSignalListSerializer.Meta.fields + ['tech_name']


# =============================================================================
# DETAIL
# =============================================================================

class TechStackSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for TechStackSignal retrieve endpoints.

    Adds tech_name after the full base detail fields.
    """

    class Meta(BaseSignalDetailSerializer.Meta):
        model  = TechStackSignal
        fields = BaseSignalDetailSerializer.Meta.fields + ['tech_name']


# =============================================================================
# CREATE
# =============================================================================

class TechStackSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Create serializer for TechStackSignal.

    Fixes signal_type to 'tech_stack' via HiddenField.
    Adds tech_name as an optional write field — free text capturing the tool
    name as mentioned in the transcript.
    """

    signal_type = serializers.HiddenField(default='tech_stack')

    tech_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text='Name of the tool as mentioned in the transcript.',
    )

    class Meta(BaseSignalCreateSerializer.Meta):
        model  = TechStackSignal
        fields = BaseSignalCreateSerializer.Meta.fields + ['tech_name']


# =============================================================================
# UPDATE
# =============================================================================

class TechStackSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for TechStackSignal.

    tech_name is intentionally excluded from PATCH — tool identity is set
    at creation and should not drift. If the tool name is wrong, supersede
    the signal via the supersede/ action.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model  = TechStackSignal
        fields = BaseSignalUpdateSerializer.Meta.fields