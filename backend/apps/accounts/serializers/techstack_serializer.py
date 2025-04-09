# apps/account/serializers/techstack_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin
from apps.accounts.models import TechStack
from core.exceptions import StandardizedValidationError

class TechStackSerializer(AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin, 
                          ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TechStack model with related data.
    """
    evaluation_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TechStack
        fields = [
            'id',
            'account',
            'tech_name',
            'notes',
            'historical_data',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'historical_data','evaluation_data', 'created_at', 'updated_at']

    def get_evaluation_data(self, obj):
        """Get tech stack evaluation data from signals."""
        # Check if include_signal_info is in context
        include_signal_info = self.context.get('include_signal_info', False)
        department = self.context.get('department', None)
        
        return obj.get_tech_evaluation_data(
            include_signal_info=include_signal_info,
            department=department
        )

    def validate(self, data):
        """Validate tech stack data"""
        data = super().validate(data)
        
        # Ensure account belongs to the client
        client_id = self._get_client_id_from_context()
        account = data.get('account')
        
        if account and str(account.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['account', 'tech_name'],
                model_class=TechStack,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='account and tech Name'
                )
            )

        
        return data