from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from ..models import Product, Competitor
from .product_serializer import ProductSummarySerializer


class CompetitorSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Summary serializer for Competitor model - used in nested contexts"""
    
    class Meta:
        model = Competitor
        fields = ['id', 'name', 'website']
        read_only_fields = fields

class CompetitorSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Main serializer for Competitor model"""
    
    products = ProductSummarySerializer(many=True, read_only=True)
    product_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=Product.objects.all()
        ),
        write_only=True,
        required=False,
        allow_empty=True,
        default=list
    )
    
    battle_cards = serializers.JSONField(
        required=False,
        allow_null=True,
        default=dict
    )
    
    class Meta:
        model = Competitor
        fields = [
            'id', 'name', 'description', 'website',
            'products', 'product_ids', 'battle_cards',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        data = super().validate(data)
        
        # Validate name uniqueness
        if 'name' in data:
            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['name'],
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='competitor name'
                )
            )
            
        # Ensure battle_cards is a dictionary
        if 'battle_cards' in data:
            value = data.get('battle_cards')
            if value is None or value == '' or not isinstance(value, dict):
                data['battle_cards'] = {}
                
        return data
    
    def create(self, validated_data):
        product_ids = validated_data.pop('product_ids', [])
        competitor = super().create(validated_data)
        
        if product_ids:
            competitor.products.set(product_ids)
        return competitor
    
    def update(self, instance, validated_data):
        product_ids = validated_data.pop('product_ids', None)
        competitor = super().update(instance, validated_data)
        
        if product_ids is not None:
            competitor.products.set(product_ids)
        return competitor