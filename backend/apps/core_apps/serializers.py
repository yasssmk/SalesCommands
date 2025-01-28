from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from apps.accounts_app.accounts.models import Account

class AccountLinkedSerializerMixin:
    """
    Mixin for serializers of models that inherit from AccountLinkedModel.
    Provides account validation and standardized error messages.
    """
    # account = serializers.CharField(
    #     error_messages={
    #         'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Account'),
    #         'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Account')  
    #     }
    # )

    def validate_account(self, value):
        """Validate account exists and belongs to the current client"""
        if not value:
            raise serializers.ValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
            )
            
        try:
            # Get client_id from context (set by view)
            client_id = self.context.get('client_id')
            if not client_id:
                raise serializers.ValidationError(
                    CoreErrorMessages.CLIENT_ID_REQUIRED
                )

            # Verify account belongs to client
            if str(value.client_id) != str(client_id):
                raise serializers.ValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )

            return value

        except Account.DoesNotExist:
            raise serializers.ValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )

    def validate(self, data):
        """Ensure account is provided"""
        if not self.partial and 'account' not in data:
            raise serializers.ValidationError({
                'account': CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
            })
        return super().validate(data)

    class Meta:
        fields = ['account']
        read_only_fields = ['client_id']