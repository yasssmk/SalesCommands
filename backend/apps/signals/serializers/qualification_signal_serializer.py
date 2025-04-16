# apps/signals/serializers/qualification_signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .base_signal_serializer import BaseSignalSerializer
from ..models.qualification_signal_model import QualificationSignal


class QualificationSignalSerializer(BaseSignalSerializer):
    """
    Serializer for qualification signals with field-specific validation.
    """
    field_name_label = serializers.SerializerMethodField(read_only=True)
    
    class Meta(BaseSignalSerializer.Meta):
        model = QualificationSignal
        fields = BaseSignalSerializer.Meta.fields + ['field_name', 'field_name_label']
        read_only_fields = BaseSignalSerializer.Meta.read_only_fields + ['field_name_label']
    
    def get_field_name_label(self, obj):
        """Get human-readable field name"""
        return obj.get_field_name_display()
    
    def validate(self, data):
        """Validate field-specific requirements"""
        data = super().validate(data)
        
        # Ensure field_name is provided
        if 'field_name' not in data:
            raise StandardizedValidationError({
                CoreErrorMessages.REQUIRED_FIELD.format(field='field_name')
            })
        
        # Validate field_name is one of the valid choices
        field_name = data['field_name']
        valid_choices = [choice[0] for choice in QualificationSignal.Field.choices]
        if field_name not in valid_choices:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD,
                detail= f"Invalid field name. Must be one of: {', '.join(valid_choices)}"
            )
        
        # For manual entries, require source_contact
        is_manual_entry = data.get('source') == 'manual_entry'
        if is_manual_entry and 'source_contact' not in data:
            raise StandardizedValidationError({
                'source_contact': "Source contact is required for qualification signals"
            })
        
        return data
    
    def to_representation(self, instance):
        """Add approval requirements information for pending signals"""
        representation = super().to_representation(instance)
        
        # For pending signals, add information about what's required for approval
        if instance.status == QualificationSignal.Status.PENDING:
            requires_approval = {
                'requires_source_contact': instance.source_contact is None
            }
            representation['approval_requirements'] = requires_approval
        
        return representation