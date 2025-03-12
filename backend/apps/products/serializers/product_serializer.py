from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from ..models import Product
from apps.core_apps.serializers import StandardDepartmentSerializer
from apps.core_apps.models import StandardDepartment
from core.exceptions import StandardizedValidationError
from .pricing_serializer import PricingSerializer


class ProductSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Simplified Product serializer for nested representations"""
    
    class Meta:
        model = Product
        fields = ['id', 'product_name', 'product_type', 'description', 'key_features', 'key_benefits']
        read_only_fields = fields

class ProductSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Main serializer for Product model with full relationships"""
    
    # Related fields
    pricing_models = PricingSerializer(many=True, read_only=True)
    target_categories = StandardDepartmentSerializer(many=True, read_only=True)
    competitors = serializers.SerializerMethodField()

    target_category_ids = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=StandardDepartment.objects.all()
        ),
        write_only=True,
        required=False,
        allow_empty=True, 
        default=list,
        error_messages={
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Target categories ID')
        }
    )
    
    # New fields
    key_features = serializers.JSONField(
        required=False,
        allow_null=True,
        default=list
    )
    
    key_benefits = serializers.JSONField(
        required=False,
        allow_null=True,
        default=list
    )
    
    typical_implementation_time = serializers.IntegerField(
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'description',
            'target_categories', 'target_category_ids', 
            'key_features', 'key_benefits',
            'competitors', 'typical_implementation_time',
            'pricing_models', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_competitors(self, obj):
        """Return list of competitors for this product"""
        from .competitor_serializer import CompetitorSummarySerializer
        
        competitors = obj.competitor_list.all()
        return CompetitorSummarySerializer(competitors, many=True, context=self.context).data

    def validate(self, data):
        """Complete validation of Product data"""
        try:
            data = super().validate(data)
            
            # Handle empty description
            if 'description' in data:
                description = data.get('description')
                if not description or description.strip() == '':
                    data['description'] = None
            
            # Ensure key_features and key_benefits are always lists
            for field in ['key_features', 'key_benefits']:
                if field in data:
                    value = data.get(field)
                    if value is None or value == '' or not isinstance(value, list):
                        data[field] = []

            # Validate unique product name within client scope
            if 'product_name' in data:
                self.validate_client_scoped_uniqueness(
                    data=data,
                    unique_fields=['product_name'],
                    error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                        fields='product name'
                    )
                )

            return data
       
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
        

    def create(self, validated_data):
        target_category_ids = validated_data.pop('target_category_ids', [])
        product = super().create(validated_data)
        
        if target_category_ids:
            product.target_categories.set(target_category_ids)
        return product

    def update(self, instance, validated_data):
        target_category_ids = validated_data.pop('target_category_ids', None)
        product = super().update(instance, validated_data)
        
        if target_category_ids is not None:
            product.target_categories.set(target_category_ids)
        return product