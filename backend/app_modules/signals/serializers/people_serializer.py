# app_modules/signals/serializers/people_serializer.py
"""
Serializers for PeopleSignal.

Stack:
  PeopleSignalListSerializer   — lightweight list view
  PeopleSignalDetailSerializer — full detail with corroboration_count
  PeopleSignalCreateSerializer — write path, signal_type hidden
  PeopleSignalUpdateSerializer — restricted PATCH
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import PeopleRole, InfluenceLevel
from ..models import PeopleSignal
from .base_serializer import (
    BaseSignalListSerializer,
    BaseSignalDetailSerializer,
    BaseSignalCreateSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# LIST
# =============================================================================

class PeopleSignalListSerializer(BaseSignalListSerializer):
    """
    Lightweight serializer for PeopleSignal list endpoints.

    Adds stakeholder-specific fields: role, influence_level,
    target_contact, target_department, notes.
    corroboration_count is excluded for performance — detail only.
    """

    role_display           = serializers.SerializerMethodField()
    influence_level_display = serializers.SerializerMethodField()
    target_contact         = serializers.SerializerMethodField()
    target_department      = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = PeopleSignal
        fields = BaseSignalListSerializer.Meta.fields + [
            'role', 'role_display',
            'influence_level', 'influence_level_display',
            'target_contact', 'target_department',
            'notes',
        ]
        read_only_fields = fields

    def get_role_display(self, obj):
        return obj.get_role_display()

    def get_influence_level_display(self, obj):
        return obj.get_influence_level_display() if obj.influence_level else None

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

class PeopleSignalDetailSerializer(BaseSignalDetailSerializer):
    """
    Full detail serializer for PeopleSignal retrieve endpoints.

    Inherits corroboration_count from BaseSignalDetailSerializer.
    All stakeholder fields included.
    """

    role_display            = serializers.SerializerMethodField()
    influence_level_display = serializers.SerializerMethodField()
    target_contact          = serializers.SerializerMethodField()
    target_department       = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PeopleSignal
        fields = BaseSignalDetailSerializer.Meta.fields + [
            'role', 'role_display',
            'influence_level', 'influence_level_display',
            'target_contact', 'target_department',
            'notes',
        ]
        read_only_fields = fields

    def get_role_display(self, obj):
        return obj.get_role_display()

    def get_influence_level_display(self, obj):
        return obj.get_influence_level_display() if obj.influence_level else None

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

class PeopleSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for PeopleSignal creation.

    signal_type is fixed to 'people' via HiddenField.
    source_contact and source_activity remain optional — no enforcement
    added for PeopleSignal.

    FK write fields (target_contact, target_department) accept UUIDs
    resolved via PrimaryKeyRelatedField.
    """

    signal_type = serializers.HiddenField(default='people')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = PeopleSignal
        fields = BaseSignalCreateSerializer.Meta.fields + [
            'target_contact',
            'target_department',
            'role',
            'influence_level',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalCreateSerializer.Meta.extra_kwargs,
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'role':              {'required': True},
            'influence_level':   {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """Delegate to base validation — no extra enforcement for PeopleSignal."""
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class PeopleSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for PeopleSignal.

    Allowed fields beyond base: role, influence_level,
    target_contact, target_department, notes.
    canonical_key is NOT writable — auto-computed in save().
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = PeopleSignal
        fields = BaseSignalUpdateSerializer.Meta.fields + [
            'role',
            'influence_level',
            'target_contact',
            'target_department',
            'notes',
        ]
        extra_kwargs = {
            **BaseSignalUpdateSerializer.Meta.extra_kwargs,
            'role':              {'required': False},
            'influence_level':   {'required': False, 'allow_null': True},
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }