# apps/account/serializers/buyingprocess_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin
from apps.accounts.serializers.contact_serializer import ContactSerializer
from apps.accounts.models.buyingProcess import BuyingProcessStep, BuyingProcessStepContact
from apps.accounts.models.contacts import Contact

class BuyingProcessStepContactSerializer(serializers.ModelSerializer):
    """Serializer for junction table between BuyingProcessStep and Contact"""
    contact = ContactSerializer(read_only=True)
    
    class Meta:
        model = BuyingProcessStepContact
        fields = ['id', 'contact', 'created_at']
        read_only_fields = ['id', 'created_at']

class BuyingProcessStepSerializer(AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin,
                                 ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for BuyingProcessStep with related contacts.
    """
    contacts = ContactSerializer(many=True, read_only=True)
    contact_ids = serializers.PrimaryKeyRelatedField(
        source='contacts',
        queryset=Contact.objects.all(),
        write_only=True,
        many=True,
        required=False
    )
    
    step_contacts = BuyingProcessStepContactSerializer(many=True, read_only=True)
    
    class Meta:
        model = BuyingProcessStep
        fields = [
            'id',
            'account',
            'step_index',
            'stakeholder',
            'department_name',
            'step_description',
            'step_goal',
            'influence_score',
            'criterias',
            'metrics',
            'average_time_in_days',
            'contacts',
            'contact_ids',
            'step_contacts',
            'historical_data',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'historical_data', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate buying process step data"""
        data = super().validate(data)
        
        # Ensure account belongs to the client
        client_id = self._get_client_id_from_context()
        account = data.get('account')
        
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate that contacts belong to the same account
        if 'contacts' in data:
            contacts = data['contacts']
            invalid_contacts = [
                contact for contact in contacts
                if contact.account_id != account.id
            ]
            
            if invalid_contacts:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Contacts must belong to the same account"
                    )
                )
        
        return data
    
    def create(self, validated_data):
        """Create buying process step with contacts"""
        contacts = validated_data.pop('contacts', [])
        
        instance = super().create(validated_data)
        
        if contacts:
            instance.contacts.set(contacts)
            
        return instance
    
    def update(self, instance, validated_data):
        """Update buying process step with contacts"""
        contacts = validated_data.pop('contacts', None)
        
        instance = super().update(instance, validated_data)
        
        if contacts is not None:
            instance.contacts.set(contacts)
            
        return instance