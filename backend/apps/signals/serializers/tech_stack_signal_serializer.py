# apps/signals/serializers/tech_stack_signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from .base_signal_serializer import BaseSignalSerializer
from ..models.tech_stack_signal_model import TechStackSignal
import re
from django.utils import timezone


class TechStackSignalSerializer(BaseSignalSerializer):
    """
    Serializer for technology stack signals with field-specific validation.
    """
    field_name_label = serializers.SerializerMethodField(read_only=True)
    tech_stack_summary = serializers.SerializerMethodField(read_only=True)
    tech_name = serializers.CharField(write_only=True, required=False)
    pending_tech_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta(BaseSignalSerializer.Meta):
        model = TechStackSignal
        fields = BaseSignalSerializer.Meta.fields + [
            'field_name', 'field_name_label', 
            'tech_stack', 'tech_stack_summary',
            'tech_name', 'pending_tech_name'
        ]
        read_only_fields = BaseSignalSerializer.Meta.read_only_fields + [
            'field_name_label', 'tech_stack_summary', 'pending_tech_name'
        ]
    
    def get_field_name_label(self, obj):
        """Get human-readable field name"""
        return obj.get_field_name_display()
    
    def get_tech_stack_summary(self, obj):
        """Get simplified tech stack information"""
        if obj.tech_stack:
            return {
                'id': obj.tech_stack.id,
                'name': obj.tech_stack.tech_name,
                'category': getattr(obj.tech_stack, 'category', None)
            }
        return None
    
    def get_pending_tech_name(self, obj):
        """Get pending tech name from metadata if available"""
        if obj.metadata and 'pending_tech_name' in obj.metadata:
            return obj.metadata['pending_tech_name']
        return None
    
    def validate(self, data):
        """Validate tech stack specific fields"""
        data = super().validate(data)
        
        # Ensure field_name is provided
        if 'field_name' not in data:
            raise StandardizedValidationError({
                CoreErrorMessages.REQUIRED_FIELD.format(field='field_name')
            })
            
        # Validate field_name is one of the valid choices
        field_name = data['field_name']
        valid_choices = [choice[0] for choice in TechStackSignal.Field.choices]
        if field_name not in valid_choices:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD,
                detail= f"Invalid field name. Must be one of: {', '.join(valid_choices)}"
            )
        
        # Handle manual creation (tech_stack required) vs LLM-generated (tech_name accepted)
        is_manual_entry = data.get('source') == 'manual_entry'
        
        if is_manual_entry and 'tech_stack' not in data:
            raise StandardizedValidationError({
                CoreErrorMessages.REQUIRED_FIELD.format(field='tech_stack')
            })
            
        # For non-manual entry, accept either tech_stack or tech_name
        if not is_manual_entry and 'tech_stack' not in data:
            # If tech_name is provided, we'll store it in metadata during creation
            if 'tech_name' not in data:
                raise StandardizedValidationError({
                    'tech_stack': "Either tech_stack or tech_name is required"
                })
        
        # Ensure tech_stack belongs to the same account if provided
        if 'tech_stack' in data and data['tech_stack']:
            tech_stack = data['tech_stack']
            account = data.get('account')
            
            if account and hasattr(tech_stack, 'account_id') and tech_stack.account_id != account.id:
                raise StandardizedValidationError({
                    'tech_stack': "Tech stack must belong to the specified account"
                })
        
        # Field-specific validation for value
        if 'value' in data:
            value = data['value']
            
            # Validate date format for renewal_date
            if field_name == TechStackSignal.Field.RENEWAL_DATE and isinstance(value, str):
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                    raise StandardizedValidationError({
                        'value': "Renewal date must be in YYYY-MM-DD format"
                    })
            
            # Validate year for start_year_of_usage
            if field_name == TechStackSignal.Field.START_YEAR_OF_USAGE:
                try:
                    year = int(value)
                    current_year = timezone.now().year
                    if year < 1900 or year > current_year + 1:
                        raise StandardizedValidationError({
                            'value': f"Year must be between 1900 and {current_year + 1}"
                        })
                except (ValueError, TypeError):
                    raise StandardizedValidationError({
                        'value': "Start year must be a valid year"
                    })
        
        return data
        
    def to_representation(self, instance):
        """Add approval requirements information for pending signals"""
        representation = super().to_representation(instance)
        
        # For pending signals, add information about what's required for approval
        if instance.status == TechStackSignal.Status.PENDING:
            requires_approval = {
                'requires_tech_stack': instance.tech_stack is None
            }
            representation['approval_requirements'] = requires_approval
            
            # Include pending_tech_name if available
            if instance.get_pending_tech_name():
                representation['pending_tech_name'] = instance.get_pending_tech_name()
        
        return representation