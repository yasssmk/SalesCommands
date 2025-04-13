# apps/signals/serializers/signal_summary_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from ..models.qualification_signal_model import QualificationSignal
from ..models.tech_stack_signal_model import TechStackSignal
from ..models.profile_signal_model import ProfileSignal


class SignalSummarySerializer(serializers.Serializer):
    """
    A simplified summary serializer for signals that works with any signal type.
    Provides key information without all the details of the full serializers.
    """
    id = serializers.UUIDField(read_only=True)
    category = serializers.SerializerMethodField(read_only=True)
    field_name = serializers.CharField(read_only=True)
    field_name_label = serializers.SerializerMethodField(read_only=True)
    value = serializers.JSONField(read_only=True)
    
    # Source information
    source = serializers.CharField(read_only=True)
    source_contact_summary = serializers.SerializerMethodField(read_only=True)
    source_department_summary = serializers.SerializerMethodField(read_only=True)
    
    # Tracking information
    confirmation_count = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_label = serializers.SerializerMethodField(read_only=True)
    
    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)
    
    def get_category(self, obj):
        """Get the signal category based on its class"""
        if isinstance(obj, QualificationSignal):
            return "QUALIFICATION"
        elif isinstance(obj, TechStackSignal):
            return "TECH_STACK"
        elif isinstance(obj, ProfileSignal):
            return "PROFILE"
        return "UNKNOWN"
    
    def get_field_name_label(self, obj):
        """Get human-readable field name"""
        if hasattr(obj, 'get_field_name_display'):
            return obj.get_field_name_display()
        return obj.field_name
    
    def get_status_label(self, obj):
        """Get human-readable status"""
        if hasattr(obj, 'get_status_display'):
            return obj.get_status_display()
        return obj.status
    
    def get_source_contact_summary(self, obj):
        """Get simplified contact information"""
        if hasattr(obj, 'source_contact') and obj.source_contact:
            return {
                'id': obj.source_contact.id,
                'name': f"{getattr(obj.source_contact, 'first_name', '')} {getattr(obj.source_contact, 'last_name', '')}".strip(),
                'role': getattr(obj.source_contact, 'job_title', None)
            }
        return None
    
    def get_source_department_summary(self, obj):
        """Get simplified department information"""
        if hasattr(obj, 'source_department') and obj.source_department:
            return {
                'id': obj.source_department.id,
                'name': getattr(obj.source_department, 'name', ''),
                'display_name': getattr(obj.source_department, 'get_name_display', lambda: '')()
            }
        return None
    
    class Meta:
        fields = [
            'id', 'category', 'field_name', 'field_name_label', 'value',
            'source', 'source_contact_summary', 'source_department_summary',
            'confirmation_count', 'status', 'status_label',
            'created_at', 'approved_at'
        ]