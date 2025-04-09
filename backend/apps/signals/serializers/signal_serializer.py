# apps/signals/serializers/signal_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts.models import Account, Contact, AccountProductRelationship
from apps.products.models import Product
from ..models import Signal

class SignalSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Signal model with proper validation and client scoping.
    """
    
    source_contact_id = serializers.PrimaryKeyRelatedField(
        source='source_contact',
        queryset=Contact.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    account_product_relationship_id = serializers.PrimaryKeyRelatedField(
        source='account_product_relationship',
        queryset=AccountProductRelationship.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    product_alignment_id = serializers.PrimaryKeyRelatedField(
        source='product_alignment',
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    parent_signal_id = serializers.PrimaryKeyRelatedField(
        source='parent_signal',
        queryset=Signal.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    # Read-only display fields
    category_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    entity_type_label = serializers.SerializerMethodField()
    
    account_summary = serializers.SerializerMethodField()
    source_contact_summary = serializers.SerializerMethodField()
    source_department_summary = serializers.SerializerMethodField()
    account_product_relationship_summary = serializers.SerializerMethodField()
    product_alignment_summary = serializers.SerializerMethodField()
    approved_by_summary = serializers.SerializerMethodField()

    entity_validation_status = serializers.SerializerMethodField(read_only=True)

    effective_status = serializers.SerializerMethodField(read_only=True)
    confirmation_count = serializers.IntegerField(read_only=True)
    last_confirmed_at = serializers.DateTimeField(read_only=True)
    merged_from_signals_count = serializers.SerializerMethodField(read_only=True)
    merged_into_signal = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Signal
        fields = [
            'id', 
            'account', 'account_summary',
            'category', 'category_label',
            'entity_type', 'entity_type_label',
            'field_name', 'value',
            'status', 'status_label',
            'source',
            'revisit_date', 'applied_date',
            'source_contact', 'source_contact_id', 'source_contact_summary',
            'source_department', 'source_department_summary',
            'account_product_relationship', 'account_product_relationship_id', 'account_product_relationship_summary',
            'product_alignment', 'product_alignment_id', 'product_alignment_summary',
            'approved_by', 'approved_by_summary', 'approved_at',
            'parent_signal', 'parent_signal_id',
            'metadata', 
            'entity_validation_status',
            'confirmation_count',
            'last_confirmed_at',
            'effective_status',
            'merged_from_signals_count',
            'merged_into_signal',
            'created_at', 'updated_at', 'client_id'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'client_id',
            'category_label', 'status_label', 'entity_type_label',
            'account_summary', 
            'source_contact_summary', 'source_department_summary',
            'account_product_relationship_summary',
            'product_alignment_summary', 'approved_by_summary', 'applied_date',
            'entity_validation_status','confirmation_count',
            'last_confirmed_at',
            'effective_status',
            'merged_from_signals_count',
            'merged_into_signal',
        ]

    def get_effective_status(self, obj):
        """Get the effective status with expiration calculation"""
        return obj.get_effective_status()
    
    def get_merged_from_signals_count(self, obj):
        """Count signals that have been merged into this one"""
        return obj.merged_from_signals.count() if hasattr(obj, 'merged_from_signals') else 0
    
    def get_merged_into_signal(self, obj):
        """Get summary of the signal this one was merged into"""
        if obj.merged_into:
            return {
                'id': obj.merged_into.id,
                'category': obj.merged_into.get_category_display(),
                'field_name': obj.merged_into.field_name,
                'status': obj.merged_into.status
            }
        return None
    
    def get_category_label(self, obj):
        return obj.get_category_display()
    
    def get_status_label(self, obj):
        return obj.get_status_display()
    
    def get_entity_type_label(self, obj):
        return obj.get_entity_type_display()
    
    def get_account_summary(self, obj):
        if obj.account:
            return {
                'id': obj.account.id,
                'company_name': obj.account.company_name
            }
        return None
    
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
    
    def get_account_product_relationship_summary(self, obj):
        if obj.account_product_relationship:
            apr = obj.account_product_relationship
            return {
                'id': apr.id,
                'product_name': apr.product.product_name if apr.product else None,
                'estimated_units': apr.estimated_units,
                'potential_revenue': str(apr.potential_revenue)
            }
        return None
    
    def get_product_alignment_summary(self, obj):
        if obj.product_alignment:
            return {
                'id': obj.product_alignment.id,
                'product_name': obj.product_alignment.product_name
            }
        return None
    
    def get_approved_by_summary(self, obj):
        if obj.approved_by:
            return {
                'id': obj.approved_by.id,
                'name': f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
            }
        return None
    
    def get_entity_validation_status(self, obj):
        """Returns validation status for the associated entity"""
        result = {
            'account_valid': True,
            'source_contact_valid': obj.source_contact is not None,
            'source_department_valid': obj.source_department is not None,
            'apr_valid': obj.account_product_relationship is not None if obj.entity_type == Signal.EntityType.ACCOUNT_PRODUCT else True
        }
        
        # Check if any entity needs validation
        result['needs_validation'] = not all([
            result['account_valid'],
            result['source_contact_valid'],
            result['source_department_valid'],
            result['apr_valid']
        ])
        
        return result
    
    def validate(self, data):
        """Custom validation for signal data"""
        data = super().validate(data)
        
        # Validate field_name and category match
        field_name = data.get('field_name')
        category = data.get('category')
        value = data.get('value')
        
        if field_name and category:
            # Use the static validation method
            is_valid, error_message = Signal.validate_signal_data(field_name, value, category)
            
            if not is_valid:
                raise StandardizedValidationError({
                    CoreErrorMessages.INVALID_DATA: {'detail': error_message}
                })
        
        # Get client_id from context
        client_id = self._get_client_id_from_context()
        
        # Validate entity references match the account
        account = data.get('account')
        if not account and self.instance:
            account = self.instance.account
            
        if not account:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
            )
        
        # Validate source_contact belongs to account if provided
        source_contact = data.get('source_contact')
        if source_contact and source_contact.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Source contact must belong to the specified account'
                )
            )
            
        # Update field name
        apr = data.get('account_product_relationship')
        if apr and apr.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Account product relationship must belong to the specified account'
                )
            )
            
        # Validate product alignment client scope
        product_alignment = data.get('product_alignment')
        if product_alignment and str(product_alignment.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate entity_type matches provided entities
        entity_type = data.get('entity_type')
        if entity_type:                
            if entity_type == Signal.EntityType.ACCOUNT_PRODUCT and not apr:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Account product relationship is required for ACCOUNT_PRODUCT entity type'
                    )
                )
        
        # Validate parent signal belongs to same account
        parent_signal = data.get('parent_signal')
        if parent_signal and parent_signal.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Parent signal must belong to the same account'
                )
            )
            
        # Prevent circular parent references
        if parent_signal and self.instance and parent_signal.id == self.instance.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Signal cannot be its own parent'
                )
            )
                
        return data

class SignalBulkActionSerializer(serializers.Serializer):
    """
    Serializer for bulk actions on signals.
    """
    action = serializers.ChoiceField(
        choices=['approve', 'reject', 'apply', 'merge'],
        required=True
    )
    
    signal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1
    )
    
    reason = serializers.CharField(required=False, allow_blank=True)
    
    # For merge actions
    target_signal_id = serializers.IntegerField(required=False)
    
    # For entity assignments during bulk approval
    source_contact_id = serializers.IntegerField(required=False)
    source_department_id = serializers.IntegerField(required=False)
    
    def validate_signal_ids(self, value):
        """Validate signal IDs exist"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Signal IDs")
            )
        return value
    
    def validate(self, data):
        """Validate action-specific requirements"""
        action = data.get('action')
        
        # Validate merge action has target_signal_id
        if action == 'merge' and 'target_signal_id' not in data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="target_signal_id for merge action")
            )
            
        return data