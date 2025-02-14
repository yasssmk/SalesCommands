from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from .models import Pricing, Product
from apps.core_apps.serializers import StandardDepartmentSerializer
from apps.core_apps.models import StandardDepartment
from core.constants import CURRENCY
from core.exceptions import StandardizedValidationError

class PricingSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        error_messages={
            'does_not_exist': f"{CoreErrorMessages.OBJECT_NOT_FOUND}: Product not found",
            'incorrect_type': CoreErrorMessages.INVALID_FIELD.format(field='Product ID must be a number'),
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Product')
        }
    )

    pricing_type = serializers.ChoiceField(
        choices=Pricing.PricingType.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Pricing Type'),
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Pricing Type must be one of: {[choice[0] for choice in Pricing.PricingType.choices]}'
            )
        }
    )

    contract_payment_term = serializers.ChoiceField(
        choices=Pricing.ContractPaymentTerm.choices,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Contract Payment Term must be one of: {[choice[0] for choice in Pricing.ContractPaymentTerm.choices]}'
            )
        }
    )

    unit_of_measure = serializers.ChoiceField(
        choices=Pricing.UnitOfMeasure.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Unit of Measure'),
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Unit of Measure must be one of: {[choice[0] for choice in Pricing.UnitOfMeasure.choices]}'
            )
        }
    )

    units_per = serializers.IntegerField(
        min_value=1,
        error_messages={
            'min_value': CoreErrorMessages.INVALID_FIELD.format(field='Units Per must be at least 1'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Units Per must be a valid number')
        }
    )

    unit_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Unit Price'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Unit Price must be a valid number'),
            'max_digits': CoreErrorMessages.INVALID_FIELD.format(field='Unit Price cannot exceed 10 digits'),
            'max_decimal_places': CoreErrorMessages.INVALID_FIELD.format(field='Unit Price cannot exceed 2 decimal places')
        }
    )

    base_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Base Price'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Base Price must be a valid number'),
            'max_digits': CoreErrorMessages.INVALID_FIELD.format(field='Base Price cannot exceed 10 digits'),
            'max_decimal_places': CoreErrorMessages.INVALID_FIELD.format(field='Base Price cannot exceed 2 decimal places')
        }
    )

    pricing_term = serializers.ChoiceField(
        choices=Pricing.PricingTerms.choices,
        allow_null=True,
        required=False,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Billing Term must be one of: {[choice[0] for choice in Pricing.PricingTerms.choices]}'
            )
        }
    )

    currency = serializers.ChoiceField(
        choices=CURRENCY,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(
                field=f'Currency must be one of: {[choice[0] for choice in CURRENCY]}'
            )
        }
    )

    formula = serializers.CharField(
        required=False,
        allow_blank=True
    )

    class Meta:
        model = Pricing
        fields = [
            'id', 'product', 'pricing_type', 'unit_of_measure',
            'units_per', 'unit_price', 'base_price', 'pricing_term', 'contract_payment_term',
            'currency', 'formula', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']

    def validate_product(self, product):
        """Validate product belongs to current client"""
        if not product:
            raise serializers.ValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Product')
            )

        client_id = self._get_client_id_from_context()
        
        if str(product.client_id) != str(client_id):
            raise serializers.ValidationError(
                CoreErrorMessages.PERMISSION_DENIED
            )
            
        return product

    def validate_unit_price(self, value):
        """Validate unit price is non-negative"""
        if value < 0:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Unit Price must be non-negative')
            )
        return value

    def validate_base_price(self, value):
        """Validate base price is non-negative"""
        if value < 0:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Base Price must be non-negative')
            )
        return value

    def validate(self, data):
        """Complete validation of Pricing data"""
        data = super().validate(data)

        # For partial updates, we should use existing values for missing fields
        if self.instance:
            product = data.get('product', self.instance.product)
            pricing_type = data.get('pricing_type', self.instance.pricing_type)
        else:
            product = data.get('product')
            pricing_type = data.get('pricing_type')

        # Validate unique constraint for product and pricing type combination
        if 'product' in data or 'pricing_type' in data:
            self.validate_client_scoped_uniqueness(
                data={'product': product.id, 'pricing_type': pricing_type},
                unique_fields=['product', 'pricing_type'],
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='Product and pricing type combination'
                )
            )

        return data

class PricingSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Simplified Pricing serializer for nested representations"""
    
    class Meta:
        model = Pricing
        fields = [
            'id', 'pricing_type', 'contract_payment_term',
            'unit_of_measure', 'units_per', 'unit_price', 
            'base_price', 'pricing_term', 'currency'
        ]
        read_only_fields = fields
    
class ProductSummarySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Simplified Product serializer for nested representations"""
    
    class Meta:
        model = Product
        fields = ['id', 'product_name', 'product_type', 'description']
        read_only_fields = fields

class ProductSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Main serializer for Product model with full relationships"""
    
    # Related fields
    pricing_models = PricingSerializer(many=True, read_only=True)
    target_categories = StandardDepartmentSerializer(many=True, read_only=True)

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
    
    # Custom fields for better validation messages
    product_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name'),
            'null': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name')
        }
    )

    description = serializers.CharField(
        required=False, 
        allow_blank=True,
        allow_null=True
    )

    value_proposition = serializers.JSONField(
        required=False,
        allow_null=True
    )

    potential_cons = serializers.JSONField(
        required=False,
        allow_null=True
    )

    competitors = serializers.JSONField(
        required=False,
        allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'description',
            'target_categories', 'target_category_ids', 
            'value_proposition', 'potential_cons', 
            'competitors', 'pricing_models',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        """Complete validation of Product data"""
        try:
            data = super().validate(data)
            
            # Handle empty description
            if 'description' in data:
                description = data.get('description')
                if not description or description.strip() == '':
                    data['description'] = None
            
            # Handle JSON fields with default structures
            default_structures = {
                'value_proposition': {'key_benefits': [], 'target_audience': []},
                'potential_cons': {'limitations': [], 'risks': []},
                'competitors': {'direct': [], 'indirect': []}
            }

            # Always set default structures for empty/missing JSON fields
            for field, default_structure in default_structures.items():
                # Convert empty strings, None, or missing values to default structure
                value = data.get(field)
                if not value or value == '' or value == {}:
                    data[field] = default_structure

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