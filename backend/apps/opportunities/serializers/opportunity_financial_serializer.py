# apps/opportunities/serializers/opportunity_financial_serializer.py

from rest_framework import serializers
from apps.opportunities.models import OpportunityLineItem, OpportunityFinancialSummary, Opportunity
from apps.products.models import Product, Pricing
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from .opportunity_serializer import OpportunitySerializer
from decimal import Decimal


class OpportunityLineItemSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for opportunity line items (products)"""
    
    # Read-only fields for display
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    pricing_type = serializers.CharField(source='pricing.pricing_type', read_only=True)
    pricing_term = serializers.CharField(source='pricing.pricing_term', read_only=True)
    unit_of_measure = serializers.CharField(source='pricing.unit_of_measure', read_only=True)
    revenue_type = serializers.SerializerMethodField(read_only=True)
    currency = serializers.CharField(source='pricing.currency', read_only=True)
    
    # Write fields that accept IDs
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    pricing_id = serializers.PrimaryKeyRelatedField(
        queryset=Pricing.objects.all(),
        source='pricing',
        write_only=True
    )
    
    class Meta:
        model = OpportunityLineItem
        fields = [
            'id',
            'opportunity',
            'product_id',
            'product_name',
            'pricing_id',
            'pricing_type',
            'pricing_term',
            'unit_of_measure',
            'revenue_type',
            'quantity',
            'custom_unit_price',
            'discount_percentage',
            'line_total',
            'currency',
            'notes',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'line_total',
            'created_at',
            'updated_at'
        ]
    
    def get_revenue_type(self, obj):
        """Get the revenue type (MRR, QRR, ARR, ONE_TIME)"""
        return obj.get_revenue_type()
    
    def validate_quantity(self, value):
        if value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                field="quantity"
                )
            )
        return value
    
    def validate_custom_unit_price(self, value):
        """✅ AMÉLIORATION: Validation custom_unit_price"""
        if value is not None and value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                field="custom_unit_price"
                )
            )
        return value
    
    def validate_discount_percentage(self, value):
        if value < 0 or value > 100:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                field="discount_percentage"
                )
            )
        return value
    
    def validate(self, data):
        """Validate line item data"""
        data = super().validate(data)
        
        # Validate client_id matches for all objects
        client_id = self._get_client_id_from_context()
        
        # Ensure product belongs to current client
        if 'product' in data:
            product = data['product']
            if str(product.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
        
        # Ensure pricing belongs to current client and matches product
        if 'pricing' in data and 'product' in data:
            pricing = data['pricing']
            product = data['product']
            
            if str(pricing.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                )
            
            if pricing.product_id != product.id:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                    detail="Pricing must belong to the selected product"
                    )
                )
        
        # Validate opportunity belongs to current client
        if 'opportunity' in data:
            opportunity = data['opportunity']
            if str(opportunity.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                )
        
        return data
    
    def create(self, validated_data):
        """Create line item and update opportunity financials"""
        # Create the line item
        line_item = super().create(validated_data)
    
        
        return line_item
    
    def update(self, instance, validated_data):
        """Update line item and recalculate financials"""
        # Update the line item
        line_item = super().update(instance, validated_data)
        
        return line_item


class OpportunityFinancialSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for opportunity financial summary"""
    
    forecast_category_display = serializers.CharField(source='get_forecast_category_display', read_only=True)
    
    class Meta:
        model = OpportunityFinancialSummary
        fields = [
            'id',
            'opportunity',
            'forecast_category',
            'forecast_category_display',
            'probability',
            'total_amount',
            'expected_revenue',
            'mrr_amount',
            'qrr_amount',
            'arr_amount',
            'one_time_amount',
            'asset_revenue',
            'service_revenue',
            'subscription_revenue',
            'usage_revenue',
            'primary_currency',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'total_amount',
            'expected_revenue',
            'mrr_amount',
            'qrr_amount',
            'arr_amount',
            'one_time_amount',
            'asset_revenue',
            'service_revenue',
            'subscription_revenue',
            'usage_revenue',
            'primary_currency',
            'created_at',
            'updated_at'
        ]

    def validate_probability(self, value):
        if value < 0 or value > 100:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                detail="Probability must be between 0 and 100"
                )
            )
        return value
    
    def validate_forecast_category(self, value):
        valid_categories = dict(OpportunityFinancialSummary.ForecastCategory.choices)
        if value not in valid_categories:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                detail=(f"Invalid forecast category. Must be one of: {', '.join(valid_categories.keys())}")
                )
            )
        return value
    
    def validate(self, data):
        """Validate financial summary data"""
        data = super().validate(data)
        
        return data
    
    def update(self, instance, validated_data):
        """Update financial summary"""
        # Update probability and forecast category
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Recalculate expected revenue
        if 'probability' in validated_data:
            instance.expected_revenue = (instance.total_amount * instance.probability) / 100
        
        instance.save()
        return instance


class OpportunityWithFinancialsSerializer(OpportunitySerializer):
    """
    Extended opportunity serializer that includes financial summary and line items
    """
    
    financial_summary = OpportunityFinancialSummarySerializer(read_only=True)
    line_items = OpportunityLineItemSerializer(many=True, read_only=True)
    
    # Additional calculated fields
    total_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, source='financial_summary.total_amount'
    )
    probability = serializers.IntegerField(
        read_only=True, source='financial_summary.probability'
    )
    forecast_category = serializers.CharField(
        read_only=True, source='financial_summary.forecast_category'
    )
    
    class Meta(OpportunitySerializer.Meta):
        fields = OpportunitySerializer.Meta.fields + [
            'financial_summary',
            'line_items',
            'total_amount',
            'probability',
            'forecast_category'
        ]