from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class TranscriptAnalysisSerializer(ClientScopeManager.SerializerMixin):
    """
    Serializer for transcript analysis requests.
    Includes validation and client scope checking.
    """
    transcript = serializers.CharField(required=True)
    model = serializers.CharField(required=False, default='gpt-4o-mini')

    def validate_transcript(self, value):
        """Validate transcript content"""
        if not value.strip():
            raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field='transcript'))
        return value.strip()

    def validate_model(self, value):
        """Validate model selection"""
        allowed_models = ['gpt-4o-mini', 'gpt-4o']  # Add other allowed models
        if value not in allowed_models:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field='model'))
        return value