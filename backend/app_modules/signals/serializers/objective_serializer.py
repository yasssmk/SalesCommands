# app_modules/signals/serializers/objective_serializer.py
"""
Serializers for ObjectiveSignal.

Stack:
  ObjectiveSignalListSerializer   — lightweight list view
  ObjectiveSignalDetailSerializer — full detail with corroboration_count
  ObjectiveSignalCreateSerializer — write path, enforces source_contact + source_activity
  ObjectiveSignalUpdateSerializer — restricted PATCH
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import GoalLevel
from ..models import ObjectiveSignal
from .base_serializer import (
    BaseSignalListSerializer,
    BaseSignalDetailSerializer,
    BaseSignalCreateSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# LIST
# =============================================================================

class ObjectiveSignalListSerializer(BaseSignalListSerializer):
    """
    Lightweight serializer for ObjectiveSignal list endpoints.

    Adds goal-specific fields: summary, goal_level,
    target_contact, target_department.
    corroboration_count excluded for performance — detail only.
    """

    goal_level_display = serializers.SerializerMethodField()
    target_contact     = serializers.SerializerMethodField()
    target_department  = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = ObjectiveSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            'summary',
            'goal_level', 'goal_level_display',
            'target_contact',
            'target_department',
        ]
        read_only_fields = fields

    def get_goal_level_display(self, obj):
        return obj.get_goal_level_display()

    def get_target_contact(self, obj):
        c = obj.target_contact
        if not c:
            return None
        return {
            'id':         str(c.id),
            'first_name': c.first_name,
            'last_name':  c.last_name,
            'job_title':  getattr(c, 'job_title', None),
        }

    def get_target_department(self, obj):
        d = obj.target_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# DETAIL
# =============================================================================

class ObjectiveSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for ObjectiveSignal retrieve endpoints.

    Inherits corroboration_count from BaseSignalDetailSerializer.
    Adds success_criteria, measurement_method, notes on top of list fields.
    """

    goal_level_display = serializers.SerializerMethodField()
    target_contact     = serializers.SerializerMethodField()
    target_department  = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = ObjectiveSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'summary',
            'goal_level', 'goal_level_display',
            'target_contact',
            'target_department',
            'success_criteria',
            'measurement_method',
            'notes',
        ]
        read_only_fields = fields

    def get_goal_level_display(self, obj):
        return obj.get_goal_level_display()

    def get_target_contact(self, obj):
        c = obj.target_contact
        if not c:
            return None
        return {
            'id':         str(c.id),
            'first_name': c.first_name,
            'last_name':  c.last_name,
            'job_title':  getattr(c, 'job_title', None),
        }

    def get_target_department(self, obj):
        d = obj.target_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# CREATE
# =============================================================================

class ObjectiveSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for ObjectiveSignal creation.

    signal_type is fixed to 'objective' via HiddenField.
    source_contact and source_activity are required — enforced in validate().
    """

    signal_type = serializers.HiddenField(default='objective')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = ObjectiveSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'summary',
            'goal_level',
            'success_criteria',
            'measurement_method',
            'target_contact',
            'target_department',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'summary':            {'required': True},
            'goal_level':         {'required': True},
            'success_criteria':   {'required': False, 'allow_blank': True},
            'measurement_method': {'required': False, 'allow_blank': True},
            'target_contact':     {'required': False, 'allow_null': True},
            'target_department':  {'required': False, 'allow_null': True},
            'notes':              {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce required context fields before base validation.

        source_contact and source_activity are required for ObjectiveSignal —
        an objective must always be anchored to a known contact and activity.
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

class ObjectiveSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for ObjectiveSignal.

    Allowed fields beyond base: summary, goal_level, success_criteria,
    measurement_method, target_contact, target_department, notes.
    canonical_key is writable — reps can assign the grouping slug manually.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = ObjectiveSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'summary',
            'goal_level',
            'success_criteria',
            'measurement_method',
            'target_contact',
            'target_department',
            'notes',
            'canonical_key',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'summary':            {'required': False},
            'goal_level':         {'required': False},
            'success_criteria':   {'required': False, 'allow_blank': True},
            'measurement_method': {'required': False, 'allow_blank': True},
            'target_contact':     {'required': False, 'allow_null': True},
            'target_department':  {'required': False, 'allow_null': True},
            'notes':              {'required': False, 'allow_blank': True},
            'canonical_key':      {'required': False, 'allow_null': True,
                                   'allow_blank': True},
        }