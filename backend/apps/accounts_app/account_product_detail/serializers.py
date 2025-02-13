from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.accounts_app.org_units.serializers import AccountOrganizationUnitSerializer
from apps.products.models import Product, Pricing
from apps.products.serializers import ProductSerializer, PricingSerializer
from .models import AccountProductDetail

class AccountProductDetailSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for AccountProductDetail with nested relations and calculated fields.
    """
    # Nested serializers for related fields
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source='product',
        queryset=Product.objects.all(),
        write_only=True
    )
    
    selected_pricing = PricingSerializer(read_only=True)
    selected_pricing_id = serializers.PrimaryKeyRelatedField(
        source='selected_pricing',
        queryset=Pricing.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    
    target_org_units = AccountOrganizationUnitSerializer(many=True, read_only=True)
    target_org_unit_ids = serializers.PrimaryKeyRelatedField(
        source='target_org_units',
        queryset='accounts_app.AccountOrganizationUnit.objects.all()',
        write_only=True,
        many=True,
        required=False
    )

    # Calculated fields
    potential_revenue_formatted = serializers.SerializerMethodField()
    revenue_label = serializers.SerializerMethodField()
    
    class Meta:
        model = AccountProductDetail
        fields = [
            'id',
            'product',
            'product_id',
            'selected_pricing',
            'selected_pricing_id',
            'target_org_units',
            'target_org_unit_ids',
            'estimated_units',
            'potential_revenue',
            'potential_revenue_formatted',
            'revenue_type',
            'revenue_label',
            'ai_relevance_score',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 
            'potential_revenue',
            'revenue_type',
            'created_at',
            'updated_at'
        ]

    def get_potential_revenue_formatted(self, obj):
        """Format potential revenue with currency symbol."""
        if obj.selected_pricing:
            return f"{obj.selected_pricing.currency} {obj.potential_revenue:,.2f}"
        return None

    def get_revenue_label(self, obj):
        """Get human-readable revenue type label."""
        return obj.get_revenue_type_display()

    def validate(self, data):
        """
        Custom validation for the serializer.
        Ensures proper client scoping and business rules.
        """
        data = super().validate(data)
        
        # Get the current client_id
        client_id = self._get_client_id_from_context()
        
        # Validate client scoping for product
        product = data.get('product')
        if product and str(product.client_id) != str(client_id):
            raise StandardizedValidationError(
                CoreErrorMessages.CLIENT_MISMATCH
            )
        
        # Validate selected pricing belongs to product
        pricing = data.get('selected_pricing')
        if pricing:
            if not product:
                product = self.instance.product if self.instance else None
                
            if not product or pricing.product_id != product.id:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Selected pricing must belong to the selected product"
                    )
                )
            
            # Validate client scoping for pricing
            if str(pricing.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
        
        # Validate org units belong to account
        org_units = data.get('target_org_units', [])
        if org_units:
            account = self.context.get('account')
            if not account:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field="Account context is required for org unit validation"
                    )
                )
            
            invalid_units = [
                unit for unit in org_units 
                if unit.account_id != account.id
            ]
            
            if invalid_units:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Target org units must belong to the account"
                    )
                )
        
        return data

    def create(self, validated_data):
        """Create with proper client_id handling."""
        client_id = self._get_client_id_from_context()
        account = self.context.get('account')
        
        if not account:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="Account context is required"
                )
            )
        
        # Extract m2m fields
        target_org_units = validated_data.pop('target_org_units', [])
        
        # Create the instance
        instance = super().create({
            **validated_data,
            'client_id': client_id,
            'account': account
        })
        
        # Set m2m relations
        if target_org_units:
            instance.target_org_units.set(target_org_units)
        
        return instance

    def update(self, instance, validated_data):
        """Update with proper client_id validation."""
        # Extract m2m fields
        target_org_units = validated_data.pop('target_org_units', None)
        
        # Update the instance
        instance = super().update(instance, validated_data)
        
        # Update m2m relations if provided
        if target_org_units is not None:
            instance.target_org_units.set(target_org_units)
        
        return instance