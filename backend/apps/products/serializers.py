from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from .models import Pricing, Product
from apps.core_apps.serializers import StandardDepartmentSerializer
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

    billing_term = serializers.ChoiceField(
        choices=Pricing.BillingTerms.choices,
        allow_null=True,
        required=False,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Billing Term must be one of: {[choice[0] for choice in Pricing.BillingTerms.choices]}'
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
            'units_per', 'unit_price', 'base_price', 'billing_term', 'contract_payment_term',
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
            'base_price', 'billing_term', 'currency'
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
    target_categoryies = StandardDepartmentSerializer(many=True, read_only=True)

    target_category_id = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Target department'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Target department'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Target department')
        })
    
    # Custom fields for better validation messages
    product_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name'),
            'null': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Name')
        }
    )

    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'product_type', 'description',
            'target_category', 'target_category_id', 'value_proposition',
            'potential_cons', 'competitors', 'pricing_models',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        """Complete validation of Product data"""
        try:
            data = super().validate(data)
            
            if self.partial:
                fields_to_validate = set(self.initial_data.keys())
                
                # Validate JSON fields if provided in partial update
                if 'value_proposition' in fields_to_validate:
                    self._validate_json_field(data.get('value_proposition'), 'value_proposition')
                if 'potential_cons' in fields_to_validate:
                    self._validate_json_field(data.get('potential_cons'), 'potential_cons')
                if 'competitors' in fields_to_validate:
                    self._validate_json_field(data.get('competitors'), 'competitors')
            else:
                # Validate required fields for complete creation/update
                for field in ['product_name']:
                    if field not in data:
                        raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field=field))
                        
                
                # Validate all JSON fields for complete creation/update
                for field in ['value_proposition', 'potential_cons', 'competitors']:
                    if field in data:
                        self._validate_json_field(data.get(field), field)

            # Validate unique product name within client scope
            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['product_name'],
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='product name'
                )
            )

            return data
            
        except serializers.ValidationError as e:
            raise serializers.ValidationError(self._extract_error_message(e))

    def _validate_json_field(self, value, field_name):
        """Validate JSON fields structure"""
        if value is not None:
            if not isinstance(value, dict):
                raise StandardizedValidationError(CoreErrorMessages.INVALID_DATA.format(
                        detail=f"{field_name} must be a valid JSON object"
                    ))
                
                
            # Validate specific structure based on field
            if field_name == 'value_proposition':
                required_keys = ['key_benefits', 'target_audience']
                self._validate_json_structure(value, required_keys, field_name)
            elif field_name == 'potential_cons':
                required_keys = ['limitations', 'risks']
                self._validate_json_structure(value, required_keys, field_name)
            elif field_name == 'competitors':
                required_keys = ['direct', 'indirect']
                self._validate_json_structure(value, required_keys, field_name)
        
        return value

    def _validate_json_structure(self, value, required_keys, field_name):
        """Validate required keys in JSON structure"""
        missing_keys = [key for key in required_keys if key not in value]
        if missing_keys:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_DATA.format(
                    detail=f"Missing required keys in {field_name}: {', '.join(missing_keys)}"
                ))
    
    def create(self, validated_data):
        target_category_ids = validated_data.pop('target_category_ids', [])
        product = super().create(validated_data)

        if target_category_ids:
            from apps.core_apps.models import StandardDepartment
            categories = StandardDepartment.objects.filter(
                id__in=target_category_ids,
                client_id=self._get_client_id_from_context()  
            )
            product.target_categories.set(categories)
        return product

    def update(self, instance, validated_data):
        target_category_ids = validated_data.pop('target_category_ids', None)
        product = super().update(instance, validated_data)

        if target_category_ids is not None:
            from apps.core_apps.models import StandardDepartment
            categories = StandardDepartment.objects.filter(
                id__in=target_category_ids,
                client_id=self._get_client_id_from_context()
            )
            product.target_categories.set(categories)
        return product


