from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts.models import Account
# from apps.accounts_app.org_units.models import AccountOrganizationUnit

class TranscriptAnalysisSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer for transcript analysis requests.
    Includes validation and client scope checking.
    """
    transcript = serializers.CharField(required=True)
    model = serializers.CharField(required=False, default='gpt-4o-mini')
    analysis_type = serializers.ChoiceField(
        choices=['full', 'tech_stack_only', 'contacts_only', 'account_only'],
        required=False,
        default='full'
    )
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        required=True 
    )
    

    def validate_transcript(self, value):
        """Validate transcript content"""
        if not value.strip():
            raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field='transcript'))
        if len(value.strip()) < 100:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_DATA.format(detail="Message too short to be analyzed")) 
        return value.strip()

    def validate_model(self, value):
        """Validate model selection"""
        allowed_models = ['gpt-4o-mini', 'gpt-4o']  # Add other allowed models
        if value not in allowed_models:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field='model'))
        return value
    
    def validate(self, data):
        """Ensure either account is provided and validate relationships"""
        data = super().validate(data)
        
        # Double-check we have an account
        if 'account' not in data:
            raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field="Account"))

        return data