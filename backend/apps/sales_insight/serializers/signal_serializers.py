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
from ..models import Signal

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
    org_unit_summary = serializers.SerializerMethodField()
    contact_summary = serializers.SerializerMethodField()
    account_product_detail_summary = serializers.SerializerMethodField()
    product_alignment_summary = serializers.SerializerMethodField()
    approved_by_summary = serializers.SerializerMethodField()

    org_unit_validation = serializers.SerializerMethodField(read_only=True)
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
            'org_unit', 'org_unit_id', 'org_unit_summary',
            'contact', 'contact_id', 'contact_summary',
            'account_product_detail', 'account_product_detail_id', 'account_product_detail_summary',
            'product_alignment', 'product_alignment_id', 'product_alignment_summary',
            'approved_by', 'approved_by_summary', 'approved_at',
            'parent_signal', 'parent_signal_id',
            'metadata', 'org_unit_validation', 'entity_validation_status',
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
            'account_summary', 'org_unit_summary', 'contact_summary', 'account_product_detail_summary',
            'product_alignment_summary', 'approved_by_summary', 'applied_date',
            'org_unit_validation', 'entity_validation_status','confirmation_count',
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
    
    def get_org_unit_validation(self, obj):
        """Returns org unit validation info if needed"""
        if obj.entity_type == Signal.EntityType.ORG_UNIT and obj.metadata:
            if obj.metadata.get('needs_validation'):
                # Get similar units
                similar_units = []
                if obj.metadata.get('similar_unit_ids'):
                    unit_ids = obj.metadata.get('similar_unit_ids')
                    units = AccountOrganizationUnit.objects.filter(id__in=unit_ids)
                    similar_units = [
                        {
                            'id': unit.id,
                            'organization_name': unit.organization_name,
                            'unit_type': unit.unit_type,
                            'standard_department': unit.standard_department.name if unit.standard_department else None
                        }
                        for unit in units
                    ]
                
                # Get standard department
                std_dept = None
                if obj.metadata.get('matching_std_department_id'):
                    try:
                        from apps.core_apps.models import StandardDepartment
                        dept = StandardDepartment.objects.get(
                            id=obj.metadata.get('matching_std_department_id')
                        )
                        std_dept = {
                            'id': dept.id,
                            'name': dept.name,
                            'display_name': dept.get_name_display()
                        }
                    except:
                        pass
                
                return {
                    'needs_validation': True,
                    'proposed_name': obj.metadata.get('proposed_name'),
                    'proposed_unit_type': obj.metadata.get('proposed_unit_type'),
                    'matching_std_department': std_dept,
                    'similar_units': similar_units
                }
        
        return {'needs_validation': False}

    def get_entity_validation_status(self, obj):
        """Returns validation status for the associated entity"""
        result = {
            'account_valid': True,
            'org_unit_valid': obj.org_unit is not None if obj.entity_type == Signal.EntityType.ORG_UNIT else True,
            'contact_valid': obj.contact is not None if obj.entity_type == Signal.EntityType.CONTACT else True,
            'apd_valid': obj.account_product_detail is not None if obj.entity_type == Signal.EntityType.ACCOUNT_PRODUCT else True
        }
        
        # Check if any entity needs validation
        result['needs_validation'] = not all([
            result['account_valid'],
            result['org_unit_valid'],
            result['contact_valid'],
            result['apd_valid']
        ])
        
        return result
    
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
        product_alignment = data.get('product_alignment')
        if product_alignment and str(product_alignment.client_id) != str(client_id):
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
        child=serializers.IntegerField(),  # Changed from UUIDField to IntegerField
        required=True,
        min_length=1
    )
    
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate_signal_ids(self, value):
        """Validate signal IDs exist"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Signal IDs")
            )
        return value

