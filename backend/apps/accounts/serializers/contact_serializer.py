# apps/account/serializers/contact_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.serializers import ContactDetailsSerializer
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.models import StandardDepartment
from apps.core_apps.serializers import AccountLinkedSerializerMixin, StandardDepartmentSerializer

from ..models import Contact, InfluenceLevel

class ContactSerializer(ContactDetailsSerializer, AccountLinkedSerializerMixin,
                       ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Contact model with qualification fields and signal awareness.
    """
    
    influence_levels = serializers.SerializerMethodField(read_only=True)

    
    # Read-only fields
    full_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField(read_only=True)

    # Standard department fields
    standard_department = StandardDepartmentSerializer(read_only=True)
    standard_department_id = serializers.PrimaryKeyRelatedField(
        queryset=StandardDepartment.objects.all(),
        source='standard_department',
        required=False,
        allow_null=True,
        write_only=True
    )
    
    
    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'email', 'phone_number',
            'email_is_valid', 'phone_is_valid', 'opted_out',
            'job_title', 'department_name', 'standard_department', 'standard_department_id',
            'influence_level', 'influence_levels',
            'account', 'account_id',
            'linkedin', 'has_buying_authority', 'notes',
            'created_at', 'updated_at', 'client_id'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'client_id', 'historical_data', 'full_name',
            'department_name'
        ]
    
    def get_full_name(self, obj):
        """Get the contact's full name"""
        return f"{obj.first_name} {obj.last_name}"
    
    def get_department_name(self, obj):
        """Get department name from standard_department"""
        return obj.standard_department.get_name_display() if obj.standard_department else None
    
    def get_account(self, obj):
        """Return minimal account information"""
        return {
            'id': obj.account.id,
            'company_name': obj.account.company_name
        } if obj.account else None
    
    def get_influence_levels(self, obj):
        """Get available influence levels"""
        return [{'value': choice[0], 'label': choice[1]} for choice in InfluenceLevel.choices]
    
    
    def validate(self, data):
        """Validate contact data"""
        data = super().validate(data)
        
        # Client scoping validation for account
        client_id = self._get_client_id_from_context()
        
        account = data.get('account')
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['account', 'email'],
                model_class=Contact,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='Account and Email'
                )
            )
            
        # Validate influence level
        influence_level = data.get('influence_level')
        if influence_level and influence_level not in [choice[0] for choice in InfluenceLevel.choices]:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Influence Level")
            )
        
        return data
    
