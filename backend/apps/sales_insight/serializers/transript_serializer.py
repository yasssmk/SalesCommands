from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit

class TranscriptAnalysisSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer for transcript analysis requests.
    Includes validation and client scope checking.
    """
    transcript = serializers.CharField(required=True)
    model = serializers.CharField(required=False, default='gpt-4o-mini')

    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        required=True 
    )
    
    org_unit = serializers.PrimaryKeyRelatedField(
        queryset=AccountOrganizationUnit.objects.all(),
        required=False,
        allow_null=True
    )
    org_unit_id = serializers.PrimaryKeyRelatedField(
        source='org_unit',
        queryset=AccountOrganizationUnit.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
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
        
        # Validate org_unit belongs to account if provided
        org_unit = data.get('org_unit')
        account = data.get('account')
        
        if org_unit and account and org_unit.account_id != account.id:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Organization unit must belong to the specified account"
                )
            )
            
        return data