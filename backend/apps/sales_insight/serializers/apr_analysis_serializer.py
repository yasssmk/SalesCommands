# apps/sales_insight/serializers/apr_analysis_serializer.py

from rest_framework import serializers
from apps.accounts.models import Account, Contact  # Updated import
from apps.products.models import Product
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin

class APRAnalysisSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer for Account Product Relationship analysis requests.
    Validates input parameters for comprehensive APR analysis.
    """
    product_id = serializers.UUIDField(required=True, help_text="UUID of the product to compare against")
    
    # Optional parameters for targeted analysis - remove org_unit_id
    contact_id = serializers.UUIDField(required=False, allow_null=True,
                                      help_text="Optional: Include insights from a specific contact")
    
    # Analysis focus options
    include_objectives = serializers.BooleanField(default=True, help_text="Include objectives analysis")
    include_pain_points = serializers.BooleanField(default=True, help_text="Include pain points analysis")
    include_economic_impact = serializers.BooleanField(default=True, help_text="Include economic impact analysis")

    class Meta:
        # Define fields that should be included in the serializer
        fields = ['account', 'product_id', 'contact_id', 
                  'include_objectives', 'include_pain_points', 'include_economic_impact']
        read_only_fields = ['client_id']
    
    def validate_product_id(self, value):
        """Validate product exists and user has access"""
        try:
            product = Product.objects.get(id=value)
            # Client ID validation would typically happen in the view
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")
    
    def validate(self, data):
        """Additional cross-field validation"""
        data = super().validate(data)
        
        # Ensure at least one analysis type is enabled
        if not any([
            data.get('include_objectives', True),
            data.get('include_pain_points', True),
            data.get('include_economic_impact', True)
        ]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="At least one analysis type must be enabled"
                )
            )
            
        # Validate contact belongs to account if provided
        contact_id = data.get('contact_id')
        account = data.get('account')
        
        if contact_id and account:
            try:
                contact = Contact.objects.get(id=contact_id)
                if contact.account_id != account.id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Contact must belong to the specified account"
                        )
                    )
            except Contact.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND.format(entity="Contact")
                )
        
        return data
    
    def create(self, validated_data):
        """
        This is just a placeholder since we're not actually creating a model instance.
        We're just using the serializer for validation.
        """
        return validated_data
    
    def update(self, instance, validated_data):
        """
        This is just a placeholder since we're not actually updating a model instance.
        We're just using the serializer for validation.
        """
        return validated_data
    
class APRAlignmentResponseSerializer(serializers.Serializer):
    """
    Serializer for the comprehensive APR alignment analysis response.
    Used for documentation and consistent API responses.
    """
    success = serializers.BooleanField()
    account_id = serializers.CharField()
    entity_type = serializers.CharField()
    entity_id = serializers.CharField()
    product_id = serializers.CharField()
    entity_name = serializers.CharField()
    product_name = serializers.CharField()
    coverage_stats = serializers.DictField()
    apr_updated = serializers.BooleanField()
    apr_id = serializers.CharField()
    apr_created = serializers.BooleanField()
    analysis_results = serializers.JSONField(allow_null=True)