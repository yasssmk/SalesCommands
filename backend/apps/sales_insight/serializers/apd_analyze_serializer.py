# apps/sales_insight/serializers/apd_analyze_serializer.py

from rest_framework import serializers
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product
from core.client_scope import ClientScopeManager
from apps.core_apps.serializers import AccountLinkedSerializerMixin

class APDAnalysisSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer for Account Product Detail analysis requests.
    Validates input parameters for comprehensive APD analysis.
    """
    product_id = serializers.UUIDField(required=True, help_text="UUID of the product to compare against")
    
    # Optional parameters for targeted analysis
    org_unit_id = serializers.UUIDField(required=False, allow_null=True, 
                                       help_text="Optional: Restrict analysis to a specific org unit")
    contact_id = serializers.UUIDField(required=False, allow_null=True,
                                      help_text="Optional: Include insights from a specific contact")
    
    # Analysis focus options
    include_objectives = serializers.BooleanField(default=True, help_text="Include objectives analysis")
    include_pain_points = serializers.BooleanField(default=True, help_text="Include pain points analysis")
    include_economic_impact = serializers.BooleanField(default=True, help_text="Include economic impact analysis")
    
    class Meta:
        # Define fields that should be included in the serializer
        fields = ['account', 'product_id', 'org_unit_id', 'contact_id', 
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
        # Ensure at least one analysis type is enabled
        if not any([
            data.get('include_objectives', True),
            data.get('include_pain_points', True),
            data.get('include_economic_impact', True)
        ]):
            raise serializers.ValidationError(
                "At least one analysis type must be enabled (objectives, pain points, or economic impact)"
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


class APDAlignmentResponseSerializer(serializers.Serializer):
    """
    Serializer for the comprehensive APD alignment analysis response.
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
    results = serializers.JSONField(allow_null=True)