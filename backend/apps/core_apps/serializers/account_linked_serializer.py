
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError, AuthenticationFailed, StandardizedPermissionDenied
from apps.accounts_app.accounts.models import Account

class AccountLinkedSerializerMixin:
    """
    Mixin for serializers of models that inherit from AccountLinkedModel.
    Provides account validation and standardized error messages.
    """
    
    def get_account(self, obj):
        """Return minimal account information"""
        return {
            'id': obj.account.id,
            'company_name': obj.account.company_name
        } if obj.account else None
    
    def validate_account(self, value):
        """Validate account exists and belongs to the current client"""
        if not value:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account")
            )
            
        try:
            # Get client_id from context (set by view)
            client_id = self.context.get('client_id')
            if not client_id:
                raise AuthenticationFailed(CoreErrorMessages.CLIENT_ID_REQUIRED)

            # Verify account belongs to client
            if str(value.client_id) != str(client_id):
                raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
            
            return value

        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def validate(self, data):
        """Ensure account is provided"""
        if not self.partial and 'account' not in data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Account")
            )
        return super().validate(data)

    class Meta:
        fields = ['account']
        read_only_fields = ['client_id']