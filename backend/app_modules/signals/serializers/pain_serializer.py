# app_modules/signals/serializers/pain_serializer.py
"""
Serializers for PainSignal.

Stack:
  PainSignalListSerializer   — lightweight list view
  PainSignalDetailSerializer — full detail with corroboration_count
  PainSignalCreateSerializer — write path, enforces source_contact + source_activity
  PainSignalUpdateSerializer — restricted PATCH
"""

from rest_framework import serializers

from core.error_messages import CoreErrorMessages, SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import PainCategory, PainLevel
from ..models import PainSignal
from .base_serializer import (
    BaseSignalListSerializer,
    BaseSignalDetailSerializer,
    BaseSignalCreateSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# LIST
# =============================================================================

class PainSignalListSerializer(BaseSignalListSerializer):
    """
    Lightweight serializer for PainSignal list endpoints.

    Adds pain-specific fields: summary, category, pain_level,
    impacted_department, business_cost.
    corroboration_count excluded for performance — detail only.
    """

    category_display   = serializers.SerializerMethodField()
    pain_level_display = serializers.SerializerMethodField()
    impacted_department = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = PainSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            'summary',
            'category', 'category_display',
            'pain_level', 'pain_level_display',
            'impacted_department',
            'business_cost',
        ]
        read_only_fields = fields

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_pain_level_display(self, obj):
        return obj.get_pain_level_display()

    def get_impacted_department(self, obj):
        d = obj.impacted_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# DETAIL
# =============================================================================

class PainSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for PainSignal retrieve endpoints.

    Inherits corroboration_count from BaseSignalDetailSerializer.
    Adds impact_summary and notes on top of list fields.
    """

    category_display    = serializers.SerializerMethodField()
    pain_level_display  = serializers.SerializerMethodField()
    impacted_department = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PainSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'summary',
            'category', 'category_display',
            'pain_level', 'pain_level_display',
            'impacted_department',
            'business_cost',
            'impact_summary',
            'notes',
        ]
        read_only_fields = fields

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_pain_level_display(self, obj):
        return obj.get_pain_level_display()

    def get_impacted_department(self, obj):
        d = obj.impacted_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# CREATE
# =============================================================================

class PainSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for PainSignal creation.

    signal_type is fixed to 'pain' via HiddenField.
    source_contact and source_activity are required — enforced in validate().
    """

    signal_type = serializers.HiddenField(default='pain')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'summary',
            'category',
            'pain_level',
            'business_cost',
            'impacted_department',
            'impact_summary',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'summary':            {'required': True},
            'category':           {'required': True},
            'pain_level':         {'required': True},
            'business_cost':      {'required': False, 'allow_blank': True},
            'impacted_department': {'required': False, 'allow_null': True},
            'impact_summary':     {'required': False, 'allow_blank': True},
            'notes':              {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce required context fields before base validation.

        source_contact and source_activity are required for PainSignal —
        a pain point must always be anchored to a known contact and activity.
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

class PainSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for PainSignal.

    Allowed fields beyond base: summary, category, pain_level,
    business_cost, impacted_department, impact_summary, notes.
    canonical_key is writable — reps can assign the grouping slug manually.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = PainSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'summary',
            'category',
            'pain_level',
            'business_cost',
            'impacted_department',
            'impact_summary',
            'notes',
            'canonical_key',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'summary':            {'required': False},
            'category':           {'required': False},
            'pain_level':         {'required': False},
            'business_cost':      {'required': False, 'allow_blank': True},
            'impacted_department': {'required': False, 'allow_null': True},
            'impact_summary':     {'required': False, 'allow_blank': True},
            'notes':              {'required': False, 'allow_blank': True},
            'canonical_key':      {'required': False, 'allow_null': True,
                                   'allow_blank': True},
        }