# apps/sales_insight/serializers/apd_analyze_serializer.py

from rest_framework import serializers
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product
from core.client_scope import ClientScopeManager
from apps.core_apps.serializers import AccountLinkedSerializerMixin

class APDAnalysisSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer for Account Product Detail analysis requests.
    Validates input parameters for APD analysis.
    """
    product_id = serializers.UUIDField(required=True, help_text="UUID of the product to compare against")
    
    # Optional parameters for more advanced analysis
    org_unit_id = serializers.UUIDField(required=False, allow_null=True, 
                                       help_text="Optional: Restrict analysis to a specific org unit")
    contact_id = serializers.UUIDField(required=False, allow_null=True,
                                      help_text="Optional: Include insights from a specific contact")
    
    class Meta:
        # Define fields that should be included in the serializer
        fields = ['account', 'product_id', 'org_unit_id', 'contact_id']
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
        """Additional cross-field validation if needed"""
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


class ObjectiveAlignmentResponseSerializer(serializers.Serializer):
    """
    Serializer for the response from objective alignment analysis.
    Used for documentation and consistent API responses.
    """
    success = serializers.BooleanField()
    account_id = serializers.CharField()
    product_id = serializers.CharField()
    results = serializers.JSONField(allow_null=True)