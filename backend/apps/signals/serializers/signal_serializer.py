# apps/signals/serializers/signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from ..models import Signal
import re

class SignalSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Signal model with simplified validation and client scoping.
    """
    
    category_label = serializers.SerializerMethodField(read_only=True)
    status_label = serializers.SerializerMethodField(read_only=True)
    entity_type_label = serializers.SerializerMethodField(read_only=True)
    
    source_contact_summary = serializers.SerializerMethodField(read_only=True)
    source_department_summary = serializers.SerializerMethodField(read_only=True)
    
    confirmation_count = serializers.IntegerField(read_only=True)
    last_confirmed_at = serializers.DateTimeField(read_only=True)
    merged_from_signals_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Signal
        fields = [
            'id', 
            'account', 
            'category', 'category_label',
            'entity_type', 'entity_type_label',
            'field_name', 'value',
            'status', 'status_label',
            'source',
            'source_contact', 'source_contact_summary',
            'source_department', 'source_department_summary',
            'confirmation_count',
            'last_confirmed_at',
            'merged_into',
            'merged_from_signals_count',
            'metadata',
            'created_at', 'updated_at', 
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'id', 'confirmation_count', 'last_confirmed_at',
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'category_label', 'status_label', 'entity_type_label',
            'source_contact_summary', 'source_department_summary',
            'merged_from_signals_count'
        ]

    def get_category_label(self, obj):
        return obj.get_category_display()
    
    def get_status_label(self, obj):
        return obj.get_status_display()
    
    def get_entity_type_label(self, obj):
        return obj.get_entity_type_display()
    
    def get_source_contact_summary(self, obj):
        if obj.source_contact:
            return {
                'id': obj.source_contact.id,
                'name': f"{getattr(obj.source_contact, 'first_name', '')} {getattr(obj.source_contact, 'last_name', '')}".strip(),
                'role': getattr(obj.source_contact, 'job_title', None)
            }
        return None
    
    def get_source_department_summary(self, obj):
        if obj.source_department:
            return {
                'id': obj.source_department.id,
                'name': obj.source_department.name,
                'display_name': obj.source_department.get_name_display()
            }
        return None
    
    def get_merged_from_signals_count(self, obj):
        """Count signals that have been merged into this one"""
        if not obj.pk:
            return 0
        return obj.merged_from_signals.count() if hasattr(obj, 'merged_from_signals') else 0
    
    def validate(self, data):
        """Enhanced validation for signal data"""
        data = super().validate(data)
        
        # Validate field_name and category match
        field_name = data.get('field_name')
        category = data.get('category')
        value = data.get('value')
        
        # 1. Category and field name validation
        if field_name and category:
            if field_name in Signal.FIELD_CATEGORIES:
                expected_category = Signal.FIELD_CATEGORIES[field_name]
                if category != expected_category:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            'detail': f"Field '{field_name}' should be in category '{expected_category}', not '{category}'"
                        }
                    })
        
        # 2. Value format validation based on field type
        if field_name and value is not None:
            # Fields that should be lists
            list_fields = [
                Signal.Field.OBJECTIVES,
                Signal.Field.MOTIVATIONS,
                Signal.Field.METRICS,
                Signal.Field.PAIN_POINTS,
                Signal.Field.IMPLICATIONS,
                Signal.Field.PROS,
                Signal.Field.CONS,
                Signal.Field.ANNUAL_COSTS
            ]
            
            if field_name in list_fields and not isinstance(value, list):
                if isinstance(value, str):
                    data['value'] = [value]
                # If it's neither a list nor a string, reject it
                elif not isinstance(value, list):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            'detail': f"Field '{field_name}' requires a list or string value, got {type(value).__name__}"
                        }
                    })
            
            # Numeric fields
            numeric_fields = [
                Signal.Field.COMPANY_SIZE,
                Signal.Field.ANNUAL_REVENUE,
            ]
            
            if field_name in numeric_fields:
                try:
                    # If it's a string, try to convert to float
                    if isinstance(value, str):
                        float(value)
                    # If it's not numeric, raise error
                    elif not isinstance(value, (int, float)):
                        raise ValueError()
                except ValueError:
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            'detail': f"Field '{field_name}' requires a numeric value"
                        }
                    })
            
            # Date fields
            date_fields = [Signal.Field.RENEWAL_DATE]
            if field_name in date_fields:
                try:
                    if isinstance(value, str):
                        # Simple validation for YYYY-MM-DD format
                        if not re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                            raise ValueError()
                except (ValueError, TypeError):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            'detail': f"Field '{field_name}' requires a date in YYYY-MM-DD format"
                        }
                    })
                    
            # Year field
            if field_name == Signal.Field.START_YEAR_OF_USAGE:
                try:
                    year = int(value)
                    current_year = timezone.now().year
                    if year < 1900 or year > current_year + 1:
                        raise StandardizedValidationError({
                            CoreErrorMessages.INVALID_DATA: {
                                'detail': f"Year must be between 1900 and {current_year + 1}"
                            }
                        })
                except (ValueError, TypeError):
                    raise StandardizedValidationError({
                        CoreErrorMessages.INVALID_DATA: {
                            'detail': f"Field '{field_name}' requires a valid year"
                        }
                    })
        
        # 3. Entity relationship validation
        account = data.get('account')
        if not account and self.instance:
            account = self.instance.account
        
        if not account:
            raise StandardizedValidationError({
                CoreErrorMessages.REQUIRED_FIELD: "Account is required"
            })
        
        # Validate source_contact belongs to account if provided
        source_contact = data.get('source_contact')
        if source_contact and source_contact.account.id != account.id:
            raise StandardizedValidationError({
                CoreErrorMessages.INVALID_FIELD: "Source contact must belong to the specified account"
            })
            
        # 4. Client scope validation for related entities
        client_id = self._get_client_id_from_context()
        
        if source_contact and str(source_contact.client_id) != str(client_id):
            raise StandardizedValidationError({
                CoreErrorMessages.CLIENT_MISMATCH: "Source contact does not belong to your client"
            })
        
        source_department = data.get('source_department')
        if source_department and str(source_department.client_id) != str(client_id):
            raise StandardizedValidationError({
                CoreErrorMessages.CLIENT_MISMATCH: "Source department does not belong to your client"
            })
        
        # 5. Status transitions validation (for updates)
        if self.instance and 'status' in data:
            old_status = self.instance.status
            new_status = data['status']
            
            # Prevent changing from MERGED status
            if old_status == Signal.Status.MERGED and new_status != Signal.Status.MERGED:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_OPERATION: "Cannot change status of a merged signal"
                })
        
        # 6. Default values for new signals
        if not self.instance:
            # Set default source if not provided
            if 'source' not in data:
                data['source'] = 'manual_entry'
                
            # Auto-set status for manual entries
            if data.get('source') == 'manual_entry':
                data['status'] = Signal.Status.APPROVED
        
        return data

    def create(self, validated_data):
        """
        Override create to properly handle user and client_id parameters
        """
        # Extract special parameters
        user = validated_data.pop('user', None) if 'user' in validated_data else None
        client_id = validated_data.pop('client_id', None) if 'client_id' in validated_data else None
        
        # Make sure we have a client_id
        if not client_id:
            client_id = self._get_client_id_from_context()  # Get from serializer context
        
        if not client_id:
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
        
        # Set client_id in validated_data so it gets passed to __init__
        validated_data['client_id'] = client_id
        
        # Create instance and save
        instance = Signal(**validated_data)
        
        # Apply any manual field assignments if needed
        if user:
            instance.created_by = user
            instance.updated_by = user
        
        # Save with user parameter
        instance.save(user=user)
        
        return instance


class SignalBulkSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for bulk signal operations
    """
    
    class Meta:
        model = Signal
        fields = [
            'account', 'category', 'entity_type', 'field_name', 'value',
            'status', 'source', 'source_contact', 'source_department',
            'metadata', 'client_id'
        ]
    
    def validate(self, data):
        """Minimal validation for bulk operations"""
        # Auto-approve manual entries
        if data.get('source') == 'manual_entry':
            data['status'] = Signal.Status.APPROVED
            
        return data