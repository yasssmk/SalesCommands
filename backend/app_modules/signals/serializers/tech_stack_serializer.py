# app_modules/signals/serializers/tech_stack_serializer.py
"""
Serializers for TechStackSignal.

Stack:
  TechStackSignalListSerializer   — lightweight list view
  TechStackSignalDetailSerializer — full detail with corroboration_count
  TechStackSignalCreateSerializer — write path, enforces source_contact + source_activity
  TechStackSignalUpdateSerializer — restricted PATCH
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import TechCategory, Satisfaction
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

    Adds tech-specific fields: tech_name, category, satisfaction,
    renewal_date.
    corroboration_count excluded for performance — detail only.
    """

    category_display     = serializers.SerializerMethodField()
    satisfaction_display = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = TechStackSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            'tech_name',
            'category', 'category_display',
            'satisfaction', 'satisfaction_display',
            'renewal_date',
        ]
        read_only_fields = fields

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def get_satisfaction_display(self, obj):
        return obj.get_satisfaction_display() if obj.satisfaction else None


# =============================================================================
# DETAIL
# =============================================================================

class TechStackSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for TechStackSignal retrieve endpoints.

    Inherits corroboration_count from BaseSignalDetailSerializer.
    Adds usage, limitations, workarounds, integrations on top of list fields.
    """

    category_display     = serializers.SerializerMethodField()
    satisfaction_display = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = TechStackSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'tech_name',
            'category', 'category_display',
            'satisfaction', 'satisfaction_display',
            'renewal_date',
            'usage',
            'limitations',
            'workarounds',
            'integrations',
        ]
        read_only_fields = fields

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def get_satisfaction_display(self, obj):
        return obj.get_satisfaction_display() if obj.satisfaction else None


# =============================================================================
# CREATE
# =============================================================================

class TechStackSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for TechStackSignal creation.

    signal_type is fixed to 'tech_stack' via HiddenField.
    source_contact and source_activity are required — enforced in validate().
    canonical_key is auto-computed in save() from tech_name — not writable.
    """

    signal_type = serializers.HiddenField(default='tech_stack')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = TechStackSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'tech_name',
            'category',
            'usage',
            'satisfaction',
            'limitations',
            'workarounds',
            'integrations',
            'renewal_date',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'tech_name':    {'required': False, 'allow_blank': True},
            'category':     {'required': False, 'allow_null': True},
            'usage':        {'required': False, 'allow_blank': True},
            'satisfaction': {'required': False, 'allow_null': True},
            'limitations':  {'required': False, 'allow_blank': True},
            'workarounds':  {'required': False, 'allow_blank': True},
            'integrations': {'required': False, 'allow_blank': True},
            'renewal_date': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        """
        Enforce required context fields before base validation.

        source_contact and source_activity are required for TechStackSignal —
        a tech stack observation must always be anchored to a known contact
        and activity.
        """
        if not attrs.get('source_contact'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_CONTACT_REQUIRED
            )

        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class TechStackSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for TechStackSignal.

    Allowed fields beyond base: tech_name, category, usage, satisfaction,
    limitations, workarounds, integrations, renewal_date.
    canonical_key is NOT writable — auto-computed in save() from tech_name.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = TechStackSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'tech_name',
            'category',
            'usage',
            'satisfaction',
            'limitations',
            'workarounds',
            'integrations',
            'renewal_date',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'tech_name':    {'required': False, 'allow_blank': True},
            'category':     {'required': False, 'allow_null': True},
            'usage':        {'required': False, 'allow_blank': True},
            'satisfaction': {'required': False, 'allow_null': True},
            'limitations':  {'required': False, 'allow_blank': True},
            'workarounds':  {'required': False, 'allow_blank': True},
            'integrations': {'required': False, 'allow_blank': True},
            'renewal_date': {'required': False, 'allow_null': True},
        }