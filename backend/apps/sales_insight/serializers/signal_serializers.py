from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.accounts_app.contacts.models import Contact
from apps.accounts_app.account_product_detail.models import AccountProductDetail
from apps.products.models import Product
from models import Signal

class SignalSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Signal model with proper validation and client scoping.
    """
    # Write-only fields
    org_unit_id = serializers.PrimaryKeyRelatedField(
        source='org_unit',
        queryset=AccountOrganizationUnit.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    contact_id = serializers.PrimaryKeyRelatedField(
        source='contact',
        queryset=Contact.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    account_product_detail_id = serializers.PrimaryKeyRelatedField(
        source='account_product_detail',
        queryset=AccountProductDetail.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    product_alignment_ids = serializers.PrimaryKeyRelatedField(
        source='product_alignment',
        queryset=Product.objects.all(),
        required=False,
        many=True,
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
    confidence_label = serializers.SerializerMethodField()
    urgency_label = serializers.SerializerMethodField()
    entity_type_label = serializers.SerializerMethodField()
    
    account_summary = serializers.SerializerMethodField()
    org_unit_summary = serializers.SerializerMethodField()
    contact_summary = serializers.SerializerMethodField()
    account_product_detail_summary = serializers.SerializerMethodField()
    product_alignment_summary = serializers.SerializerMethodField()
    approved_by_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Signal
        fields = [
            'id', 
            'account', 'account_summary',
            'category', 'category_label',
            'entity_type', 'entity_type_label',
            'field_name', 'value',
            'confidence', 'confidence_label',
            'potential_value',
            'urgency', 'urgency_label',
            'status', 'status_label',
            'source',
            'revisit_date', 'applied_date',
            'org_unit', 'org_unit_id', 'org_unit_summary',
            'contact', 'contact_id', 'contact_summary',
            'account_product_detail', 'account_product_detail_id', 'account_product_detail_summary',
            'product_alignment', 'product_alignment_ids', 'product_alignment_summary',
            'approved_by', 'approved_by_summary', 'approved_at',
            'parent_signal', 'parent_signal_id',
            'created_at', 'updated_at', 'client_id'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'client_id',
            'category_label', 'status_label', 'confidence_label', 'urgency_label', 'entity_type_label',
            'account_summary', 'org_unit_summary', 'contact_summary', 'account_product_detail_summary',
            'product_alignment_summary', 'approved_by_summary', 'applied_date'
        ]
    
    def get_category_label(self, obj):
        return obj.get_category_display()
    
    def get_status_label(self, obj):
        return obj.get_status_display()
    
    def get_confidence_label(self, obj):
        return obj.get_confidence_display()
    
    def get_urgency_label(self, obj):
        return obj.get_urgency_display()
    
    def get_entity_type_label(self, obj):
        return obj.get_entity_type_display()
    
    def get_account_summary(self, obj):
        if obj.account:
            return {
                'id': obj.account.id,
                'company_name': obj.account.company_name
            }
        return None
    
    def get_org_unit_summary(self, obj):
        if obj.org_unit:
            return {
                'id': obj.org_unit.id,
                'organization_name': obj.org_unit.organization_name,
                'unit_type': obj.org_unit.unit_type
            }
        return None
    
    def get_contact_summary(self, obj):
        if obj.contact:
            return {
                'id': obj.contact.id,
                'name': f"{getattr(obj.contact, 'first_name', '')} {getattr(obj.contact, 'last_name', '')}".strip(),
                'role': getattr(obj.contact, 'job_title', None)
            }
        return None
    
    def get_account_product_detail_summary(self, obj):
        if obj.account_product_detail:
            apd = obj.account_product_detail
            return {
                'id': apd.id,
                'product_name': apd.product.product_name if apd.product else None,
                'estimated_units': apd.estimated_units,
                'potential_revenue': str(apd.potential_revenue)
            }
        return None
    
    def get_product_alignment_summary(self, obj):
        return [
            {'id': product.id, 'product_name': product.product_name}
            for product in obj.product_alignment.all()
        ]
    
    def get_approved_by_summary(self, obj):
        if obj.approved_by:
            return {
                'id': obj.approved_by.id,
                'name': f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
            }
        return None
    
    def validate(self, data):
        """Custom validation for signal data"""
        data = super().validate(data)
        
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
        
        # Validate org_unit belongs to account
        org_unit = data.get('org_unit')
        if org_unit and org_unit.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Organization unit must belong to the specified account'
                )
            )
            
        # Validate contact belongs to account
        contact = data.get('contact')
        if contact and contact.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Contact must belong to the specified account'
                )
            )
            
        # Validate account_product_detail belongs to account
        apd = data.get('account_product_detail')
        if apd and apd.account.id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='Account product detail must belong to the specified account'
                )
            )
            
        # Validate product alignment client scope
        if 'product_alignment' in data:
            for product in data['product_alignment']:
                if str(product.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate entity_type matches provided entities
        entity_type = data.get('entity_type')
        if entity_type:
            if entity_type == Signal.EntityType.ORG_UNIT and not org_unit:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Organization unit is required for ORG_UNIT entity type'
                    )
                )
                
            if entity_type == Signal.EntityType.CONTACT and not contact:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Contact is required for CONTACT entity type'
                    )
                )
                
            if entity_type == Signal.EntityType.ACCOUNT_PRODUCT and not apd:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Account product detail is required for ACCOUNT_PRODUCT entity type'
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
        choices=['approve', 'reject', 'apply'],
        required=True
    )
    
    signal_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1
    )
    
    def validate_signal_ids(self, value):
        """Validate signal IDs exist"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Signal IDs")
            )
        return value