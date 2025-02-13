from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.accounts_app.org_units.serializers import AccountOrganizationUnitSerializer
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts_app.accounts.models import Account
from apps.products.models import Product, Pricing
from apps.products.serializers import ProductSerializer, PricingSerializer
from .models import AccountProductDetail

class AccountProductDetailSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for AccountProductDetail with nested relations and calculated fields.
    """

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
        queryset=AccountOrganizationUnit.objects.all(),
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
            'account',
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
            'updated_at',
            'client_id'
        ]

    def validate(self, data):
            """Custom validation for the serializer."""
            data = super().validate(data)  # This includes AccountLinkedSerializerMixin validation
            
            # Additional product and pricing validations
            client_id = self._get_client_id_from_context()
            
            # Validate client scoping for product
            product = data.get('product')
            if product and str(product.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
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
                
                if str(pricing.client_id) != str(client_id):
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
            
            if 'target_org_units' in data:
                account = data.get('account') or self.instance.account
                org_units = data['target_org_units']
                invalid_units = [
                    unit for unit in org_units 
                    if unit.account_id != account.id
                ]
                if invalid_units:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Target organization units must belong to the account"
                        )
                    )
        
            return data

    def get_potential_revenue_formatted(self, obj):
        if obj.selected_pricing:
            return f"{obj.selected_pricing.currency} {obj.potential_revenue:,.2f}"
        return None

    def get_revenue_label(self, obj):
        return obj.get_revenue_type_display()
    
    def create(self, validated_data):
        """Optimized creation with proper relationship handling"""
        target_org_units = validated_data.pop('target_org_units', [])
        instance = super().create(validated_data)
        
        if target_org_units:
            instance.target_org_units.set(target_org_units)
            
        return instance

    def update(self, instance, validated_data):
        """Optimized update with proper relationship handling"""
        target_org_units = validated_data.pop('target_org_units', None)
        instance = super().update(instance, validated_data)
        
        if target_org_units is not None:
            instance.target_org_units.set(target_org_units)
            
        return instance