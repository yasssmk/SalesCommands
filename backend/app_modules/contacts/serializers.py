# app_modules/contacts/serializers.py
"""
Serializers for Contact module.

Follows the same patterns as CompanyAccountSerializer for consistency.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.serializers import ContactDetailsSerializer
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, ContactErrorMessages
from core.exceptions import StandardizedValidationError
from ..core_modules.models import StandardDepartment
from ..core_modules.serializers import StandardDepartmentSerializer
from app_modules.accounts.models import CompanyAccount
from .models import Contact, InfluenceLevel


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class ContactAccountSerializer(serializers.ModelSerializer):
    """Minimal account serializer for contact responses."""
    class Meta:
        model = CompanyAccount
        fields = ['id', 'company_name']
        read_only_fields = fields


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class ContactListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for contact lists (performance optimized).
    
    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    # Computed fields
    full_name = serializers.SerializerMethodField(read_only=True)
    
    # Relations as simple objects
    account = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    
    # Display fields
    influence_level_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            # Identity
            'id', 'first_name', 'last_name', 'full_name',
            
            # Contact info
            'email', 'phone_number', 'job_title', 'linkedin',
            
            # Location
            'city',
            
            # Department
            'department_name',
            
            # Qualification
            'influence_level', 'influence_level_display', 'has_buying_authority',
            
            # Account relation
            'account',
            
            # Status
            'opted_out', 'email_is_valid', 'phone_is_valid',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        """Get contact's full name."""
        return f"{obj.first_name} {obj.last_name}"
    
    def get_account(self, obj):
        """Return account as minimal object."""
        if obj.account:
            return {
                'id': str(obj.account_id),
                'company_name': obj.account.company_name,
            }
        return None
    
    def get_department_name(self, obj):
        """Get department display name."""
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None
    
    def get_influence_level_display(self, obj):
        """Get display name for influence level."""
        return obj.get_influence_level_display() if obj.influence_level else None


# ============================================================================
# MAIN SERIALIZER (Full details)
# ============================================================================

class ContactSerializer(ContactDetailsSerializer, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Full serializer for Contact with all business logic.
    """
    
    # Required fields with error messages
    first_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='First Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='First Name'),
        }
    )
    
    last_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Last Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Last Name'),
        }
    )
    
    # Account field (write)
    account_id = serializers.UUIDField(
        write_only=True,
        error_messages={
            'required': ContactErrorMessages.ACCOUNT_REQUIRED,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Account ID'),
        }
    )
    
    # Account field (read)
    account = ContactAccountSerializer(read_only=True)
    
    # Standard department fields
    standard_department = StandardDepartmentSerializer(read_only=True)
    standard_department_id = serializers.PrimaryKeyRelatedField(
        queryset=StandardDepartment.objects.all(),
        source='standard_department',
        required=False,
        allow_null=True,
        write_only=True
    )
    
    # Read-only computed fields
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    influence_level_display = serializers.SerializerMethodField(read_only=True)
    influence_levels = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            # Identity
            'id', 'first_name', 'last_name', 'full_name',
            
            # Contact details (from ContactDetailsMixin)
            'email', 'phone_number', 'linkedin',
            'address', 'city', 'state', 'post_code', 'country',
            'email_is_valid', 'phone_is_valid',
            
            # Job info
            'job_title', 'department', 'standard_department', 'standard_department_id',
            'department_name',
            
            # Qualification
            'influence_level', 'influence_level_display', 'influence_levels',
            'has_buying_authority',
            
            # Account
            'account', 'account_id',
            
            # Communication
            'opted_out',
            
            # Notes
            'notes',
            
            # Audit
            'client_id', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'id', 'full_name', 'department_name', 'influence_level_display',
            'influence_levels', 'client_id', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def get_full_name(self, obj):
        """Get contact's full name."""
        return f"{obj.first_name} {obj.last_name}"
    
    def get_department_name(self, obj):
        """Get department display name."""
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None
    
    def get_influence_level_display(self, obj):
        """Get display name for influence level."""
        return obj.get_influence_level_display() if obj.influence_level else None
    
    def get_influence_levels(self, obj):
        """Get available influence levels for dropdown."""
        return [
            {'value': choice[0], 'label': choice[1]} 
            for choice in InfluenceLevel.choices
        ]
    
    def validate_account_id(self, value):
        """Validate account exists and belongs to current client."""
        client_id = self._get_client_id_from_context()
        
        try:
            account = CompanyAccount.objects.get(id=value)
            if str(account.client_id) != str(client_id):
                raise StandardizedValidationError(ContactErrorMessages.INVALID_ACCOUNT)
            return value
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(ContactErrorMessages.INVALID_ACCOUNT)
    
    def validate(self, data):
        """Validate contact data."""
        data = super().validate(data)
        client_id = self._get_client_id_from_context()
        
        # Check for duplicate email within same account
        email = data.get('email')
        account_id = data.get('account_id')
        
        if email and account_id:
            existing = Contact.objects.filter(
                client_id=client_id,
                account_id=account_id,
                email=email
            )
            
            # Exclude current instance on update
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise StandardizedValidationError(ContactErrorMessages.DUPLICATE_EMAIL)
        
        return data
    
    def create(self, validated_data):
        """Create contact with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Extract account_id and get account
        account_id = validated_data.pop('account_id')
        account = CompanyAccount.objects.get(id=account_id)
        validated_data['account'] = account
        
        # Default standard_department to "General Management" if not provided
        if 'standard_department' not in validated_data or validated_data.get('standard_department') is None:
            default_dept = StandardDepartment.objects.filter(name='General Management').first()
            if default_dept:
                validated_data['standard_department'] = default_dept
        
        # Create instance
        instance = Contact(**validated_data)
        
        # Set client_id from account (multi-tenant isolation)
        instance.client_id = account.client_id
        
        instance.save(user=user)
        
        return instance
    
    def update(self, instance, validated_data):
        """Update contact with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Handle account_id if provided
        if 'account_id' in validated_data:
            account_id = validated_data.pop('account_id')
            validated_data['account'] = CompanyAccount.objects.get(id=account_id)
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        return instance


# ============================================================================
# CREATE SERIALIZER (Simplified for creation)
# ============================================================================

class ContactCreateSerializer(ContactSerializer):
    """
    Serializer optimized for contact creation.
    Inherits validation from ContactSerializer.
    """
    
    class Meta(ContactSerializer.Meta):
        fields = [
            # Required
            'first_name', 'last_name', 'account_id',
            
            # Contact details
            'email', 'phone_number', 'linkedin',
            
            # Job info
            'job_title', 'standard_department_id',
            
            # Qualification
            'influence_level', 'has_buying_authority',
            
            # Notes
            'notes',
        ]