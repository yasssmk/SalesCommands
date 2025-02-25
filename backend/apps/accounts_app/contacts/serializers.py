from rest_framework import serializers
from .models import Contact
from core.serializers import ContactDetailsSerializer
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from core.client_scope import ClientScopeManager
from sales_insight.serializers.qualification_serializers import QualificationFieldsSerializer
from core.exceptions import StandardizedValidationError, CoreErrorMessages

class ContactSerializer(ContactDetailsSerializer, AccountLinkedSerializerMixin, QualificationFieldsSerializer, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Contact model with qualification fields
    """
    # Write-only fields
    account_id = serializers.UUIDField(
        required=True,
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Account ID'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Account ID')
        }
    )
    
    organization_unit_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True
    )
    
    # Read-only fields
    account = serializers.SerializerMethodField()
    organization_unit = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    # Qualification indicators
    has_qualification_data = serializers.SerializerMethodField(read_only=True)
    pending_changes_count = serializers.SerializerMethodField(read_only=True)
    
    # Historical data is read-only
    historical_data = serializers.JSONField(required=False, allow_null=True, read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'email', 'phone',
            'job_title', 'influence_level', 'account', 'account_id',
            'organization_unit', 'organization_unit_id', 'address',
            'city', 'post_code', 'state', 'country', 'website', 'linkedin',
            'created_at', 'updated_at', 'client_id', 'historical_data',
            # Qualification fields
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 'current_tech_stack',
            'partners', 'projects', 'budget', 'new_budget_start_date',
            'has_qualification_data', 'pending_changes_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id', 'historical_data', 'full_name']
    
    def get_full_name(self, obj):
        """Get the contact's full name"""
        return f"{obj.first_name} {obj.last_name}"
    
    def get_account(self, obj):
        """Return minimal account information"""
        return {
            'id': obj.account.id,
            'company_name': obj.account.company_name
        } if obj.account else None
    
    def get_organization_unit(self, obj):
        """Return organization unit information"""
        if obj.organization_unit:
            return {
                'id': obj.organization_unit.id,
                'organization_name': obj.organization_unit.organization_name,
                'unit_type': obj.organization_unit.unit_type
            }
        return None
    