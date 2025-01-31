from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError, AuthenticationFailed, StandardizedPermissionDenied
from apps.accounts_app.accounts.models import Account

class AccountLinkedSerializerMixin:
    """
    Mixin for serializers of models that inherit from AccountLinkedModel.
    Provides account validation and standardized error messages.
    """
 
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


from .models import StandardDepartment

class StandardDepartmentSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for StandardDepartment model.
    Used for internal taxonomy and mapping purposes only.
    """
    
    # Add display name for the choice field
    name_display = serializers.SerializerMethodField()
    
    class Meta:
        model = StandardDepartment
        fields = ['id', 'name', 'name_display']
        read_only_fields = fields  # Make all fields read-only

    def get_name_display(self, obj):
        """
        Get the display name for the department choice
        """
        return obj.get_name_display()

    def create(self, validated_data):
        """
        Prevent creation through API
        """
        raise StandardizedValidationError(
            "Standard departments cannot be created through the API"
        )

    def update(self, instance, validated_data):
        """
        Prevent updates through API
        """
        raise StandardizedValidationError(
            "Standard departments cannot be modified through the API"
        )