# apps/account/serializers/contact_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.serializers import ContactDetailsSerializer
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin, SignalAwareSerializerMixin
from ..models import Contact, InfluenceLevel

class ContactSerializer(ContactDetailsSerializer, AccountLinkedSerializerMixin,
                       HistoricalTrackingSerializerMixin, SignalAwareSerializerMixin, 
                       ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Contact model with qualification fields and signal awareness.
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
    
    influence_levels = serializers.SerializerMethodField(read_only=True)
    
    # Read-only fields
    account = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    
    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'email', 'phone',
            'job_title', 'department', 'influence_level', 'influence_levels',
            'account', 'account_id', 'address_line1', 'address_line2',
            'city', 'postal_code', 'state', 'country', 'website', 'linkedin',
            'created_at', 'updated_at', 'client_id', 'historical_data',
            'signal_metadata', 
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'client_id', 'historical_data', 'full_name',
            'signal_metadata'
        ]
    
    def get_full_name(self, obj):
        """Get the contact's full name"""
        return f"{obj.first_name} {obj.last_name}"
    
    def get_account(self, obj):
        """Return minimal account information"""
        return {
            'id': obj.account.id,
            'company_name': obj.account.company_name
        } if obj.account else None
    
    def get_influence_levels(self, obj):
        """Get available influence levels"""
        return [{'value': choice[0], 'label': choice[1]} for choice in InfluenceLevel.choices]
    
    def get_has_qualification_data(self, obj):
        """Check if contact has any qualification data"""
        qualification_fields = ['objectives', 'pain_points', 'criteria']
        return any(bool(getattr(obj, field)) for field in qualification_fields)
    
    def get_pending_changes_count(self, obj):
        """Get count of pending signals for this contact"""
        if hasattr(obj, 'get_pending_signals_count'):
            return obj.get_pending_signals_count()
        return 0
    
    def validate(self, data):
        """Validate contact data"""
        data = super().validate(data)
        
        # Client scoping validation for account
        client_id = self._get_client_id_from_context()
        
        account = data.get('account')
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
        # Validate influence level
        influence_level = data.get('influence_level')
        if influence_level and influence_level not in [choice[0] for choice in InfluenceLevel.choices]:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Influence Level")
            )
        
        return data