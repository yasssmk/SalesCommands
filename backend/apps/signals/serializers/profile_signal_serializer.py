# apps/signals/serializers/profile_signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .base_signal_serializer import BaseSignalSerializer
from ..models.profile_signal_model import ProfileSignal


class ProfileSignalSerializer(BaseSignalSerializer):
    """
    Serializer for company profile signals with field-specific validation.
    """
    field_name_label = serializers.SerializerMethodField(read_only=True)
    
    class Meta(BaseSignalSerializer.Meta):
        model = ProfileSignal
        fields = BaseSignalSerializer.Meta.fields + ['field_name', 'field_name_label']
        read_only_fields = BaseSignalSerializer.Meta.read_only_fields + ['field_name_label']
    
    def get_field_name_label(self, obj):
        """Get human-readable field name"""
        return obj.get_field_name_display()
    
    def validate_value(self, value):
        """Process and validate the value based on expected format"""
        # Try to convert strings to numeric values where appropriate
        if isinstance(value, str) and value.strip():
            # Remove currency symbols and formatting characters
            cleaned_value = value.replace('$', '').replace(',', '')
            try:
                # Try to convert to numeric value
                return float(cleaned_value)
            except ValueError:
                # If not convertible, keep as string
                pass
        
        return value
    
    def validate(self, data):
        """Validate profile-specific fields"""
        data = super().validate(data)
        
        # Ensure field_name is provided
        if 'field_name' not in data:
            raise StandardizedValidationError({
                'field_name': CoreErrorMessages.REQUIRED_FIELD
            })
            
        # Validate field_name is one of the valid choices
        field_name = data['field_name']
        valid_choices = [choice[0] for choice in ProfileSignal.Field.choices]
        if field_name not in valid_choices:
            raise StandardizedValidationError({
                'field_name': f"Invalid field name. Must be one of: {', '.join(valid_choices)}"
            })
        
        # Field-specific validation for value
        if 'value' in data and field_name in [ProfileSignal.Field.COMPANY_SIZE, ProfileSignal.Field.ANNUAL_REVENUE]:
            value = data['value']
            
            # If the value is neither numeric nor a string, raise an error
            if not isinstance(value, (int, float, str)):
                raise StandardizedValidationError({
                    'value': f"{ProfileSignal.Field(field_name).label} should be a numeric value or string"
                })
        
        return data