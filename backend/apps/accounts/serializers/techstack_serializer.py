# apps/account/serializers/techstack_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin
from apps.accounts.models import TechStack
from core.exceptions import StandardizedValidationError

class TechStackSerializer(AccountLinkedSerializerMixin, 
                          ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TechStack model with related data.
    """
    evaluation_data = serializers.SerializerMethodField(read_only=True)
    evaluation_by_department = serializers.SerializerMethodField(read_only=True)
    purpose = serializers.SerializerMethodField(read_only=True)
    pros_and_cons = serializers.SerializerMethodField(read_only=True)
    costs = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TechStack
        fields = [
            'id',
            'account',
            'tech_name',
            'notes',
            'evaluation_data',
            'evaluation_by_department',
            'purpose',
            'pros_and_cons',
            'costs',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 
            'historical_data',
            'evaluation_data', 
            'evaluation_by_department',
            'purpose',
            'pros_and_cons',
            'costs',
            'created_at', 
            'updated_at'
        ]


    def get_evaluation_data(self, obj):
        """Get tech stack evaluation data from signals."""
        # Only include evaluation data if specifically requested or if this is a detail view
        
        department = self.context.get('department', None)
        source_contact = self.context.get('source_contact', None)
        min_confirmations = self.context.get('min_confirmations', None)
        
        # Use the model method to get evaluation data
        return obj.get_evaluation_data(
            department=department,
            source_contact=source_contact,
            min_confirmations=min_confirmations,
        )
        
    def get_evaluation_by_department(self, obj):
        """Get tech stack evaluation data organized by department."""
        # Only include if explicitly requested
        # Use model method to get evaluation data by department
        return obj.get_evaluation_by_department()
    
    def get_purpose(self, obj):
        """Get the purpose of this tech stack."""
        # Only include in detail view or if specifically requested
            
        return obj.get_purpose()
    
    def get_pros_and_cons(self, obj):
        """Get pros and cons for this tech stack."""
        # Only include in detail view or if specifically requested
            
        return obj.get_pros_and_cons()
    
    def get_costs(self, obj):
        """Get cost information for this tech stack."""
        # Only include in detail view or if specifically requested
            
        return obj.get_costs()

    def validate(self, data):
        """Validate tech stack data"""
        data = super().validate(data)
        
        # Ensure account belongs to the client
        client_id = self._get_client_id_from_context()
        account = data.get('account')
        
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Ensure tech_name and account combination is unique
        self.validate_client_scoped_uniqueness(
            data=data,
            unique_fields=['account', 'tech_name'],
            model_class=TechStack,
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='account and tech name'
            )
        )
        
        return data