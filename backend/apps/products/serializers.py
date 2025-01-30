from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from .models import BillingCycle, Pricing, Product
from apps.core_apps.serializers import StandardDepartmentSerializer
from django.db import transaction
from core.constants import CURRENCY


class BillingCycleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    
    name = serializers.CharField(
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='The name of the cycling type'),
            'incorrect_type': CoreErrorMessages.INVALID_FIELD.format(field='cycle type name is too long')

        }
    )
    cycle_type = serializers.ChoiceField(
        choices=BillingCycle.CycleType.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Cycling Type'),
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail=f'Cycling Type must be one of: {[choice[0] for choice in BillingCycle.CycleType.choices]}'
            )
        }
    )
    class Meta:
        model = BillingCycle
        fields = ['id', 'name', 'cycle_type', 'multiplier']
        read_only_fields = ['created_at', 'updated_at', 'client_id']

    def validate(self, data):
        """Complete validation of BillingCycle data"""
        data = super().validate(data)

        # Validate multiplier
        if not (0 < data.get('multiplier', 1) <= 1):
            raise serializers.ValidationError({
                'multiplier': CoreErrorMessages.INVALID_FIELD.format(
                    field="Multiplier must be between 0 and 1"
                )
            })

        # Validate unique name within client scope
        self.validate_client_scoped_uniqueness(
            data=data,
            unique_fields=['name'],
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='billing cycle name'
            )
        )

        return data

class PricingSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    available_cycles = BillingCycleSerializer(many=True, read_only=True)
    
    cycle_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True,
        allow_empty=True,
        error_messages={
            'does_not_exist': f"{CoreErrorMessages.OBJECT_NOT_FOUND}: Billing cycles with IDs not found",
            'incorrect_type': CoreErrorMessages.INVALID_FIELD.format(field='cycle ID must be a number')
        }
    )
    # Define product as PrimaryKeyRelatedField
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        error_messages={
            'does_not_exist': f"{CoreErrorMessages.OBJECT_NOT_FOUND}: Product IDs not found",
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
    
    currency = serializers.CharField(
        max_length=10,
        error_messages={
            'invalid_choice': CoreErrorMessages.INVALID_FIELD.format(field='Invalid currency')
        }
    )

    class Meta:
        model = Pricing
        fields = [
            'id', 'pricing_type', 'base_price', 'currency',
            'available_cycles', 'cycle_ids', 'product'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']
    
    def validate_currency(self, value):
        """Validate country field"""
        if self.partial and (value is None or value == ''):
            return value
            
        valid_currency= [choice[0] for choice in CURRENCY]
        if value not in valid_currency:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Currency")
            )
        return value

    def validate(self, data):
        """Validate pricing data"""
        data = super().validate(data)

        # For partial updates, we should use existing values for missing fields
        if self.instance:
            product = data.get('product', self.instance.product)
            pricing_type = data.get('pricing_type', self.instance.pricing_type)
        else:
            product = data.get('product')
            pricing_type = data.get('pricing_type')

        # Only validate uniqueness if either product or pricing_type is being updated
        if 'product' in data or 'pricing_type' in data:
            self.validate_client_scoped_uniqueness(
                data={'product_id': product.id, 'pricing_type': pricing_type},
                unique_fields=['product_id', 'pricing_type'],
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='Product and pricing type'
                )
            )

        cycle_ids = data.get('cycle_ids', [])

        # Handle pricing type and cycles validation
        if pricing_type == Pricing.PricingType.ONE_TIME:
            if cycle_ids:
                raise serializers.ValidationError({
                    'cycle_ids': CoreErrorMessages.INVALID_FIELD.format(
                        field='Billing cycles are not allowed for one-time pricing'
                    )
                })
            data['cycle_ids'] = []
                
        elif pricing_type == Pricing.PricingType.SUBSCRIPTION:
            if not cycle_ids and not (self.instance and self.instance.available_cycles.exists()):
                raise serializers.ValidationError({
                    'cycle_ids': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='At least one billing cycle is required for subscription pricing'
                    )
                })
                
            if cycle_ids:
                available_cycles = BillingCycle.objects.select_for_update().filter(
                    id__in=cycle_ids,
                    client_id=self._get_client_id_from_context()
                )
                    
                if available_cycles.count() == 0:
                    raise serializers.ValidationError({
                        'cycle_ids': f"{CoreErrorMessages.OBJECT_NOT_FOUND}: cycles IDs not found",
                    })
                    
                found_cycle_ids = set(available_cycles.values_list('id', flat=True))
                missing_ids = set(cycle_ids) - found_cycle_ids
                if missing_ids:
                    raise serializers.ValidationError({
                        'cycle_ids': f"{CoreErrorMessages.OBJECT_NOT_FOUND}: Billing cycles with IDs {list(missing_ids)} not found"
                    })

                self.context['validated_cycles'] = available_cycles

        # Validate base price
        if 'base_price' in data and data.get('base_price', 0) < 0:
            raise serializers.ValidationError({
                'base_price': CoreErrorMessages.INVALID_FIELD.format(
                    field='base_price must be greater than 0'
                )
            })

        return data

    def create(self, validated_data):
        """Create pricing with proper cycle handling"""
        cycle_ids = validated_data.pop('cycle_ids', [])
        
        # Create the pricing instance
        instance = super().create(validated_data)
        
        # Add cycles if any
        if cycle_ids and 'validated_cycles' in self.context:
            instance.available_cycles.set(self.context['validated_cycles'])
        
        return instance

    def update(self, instance, validated_data):
        """Update pricing with proper cycle handling"""
        cycle_ids = validated_data.pop('cycle_ids', None)
        
        # Update the pricing instance
        instance = super().update(instance, validated_data)
        
        # Update cycles if provided
        if cycle_ids is not None:
            if validated_data.get('pricing_type') == Pricing.PricingType.ONE_TIME:
                instance.available_cycles.clear()
            elif 'validated_cycles' in self.context:
                instance.available_cycles.set(self.context['validated_cycles'])
        
        return instance
    
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
    target_category = StandardDepartmentSerializer(read_only=True)

    target_category_id = serializers.IntegerField(
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
    
    product_type = serializers.ChoiceField(
        choices=Product.ProductType.choices,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Product Type'),
            'invalid_choice': CoreErrorMessages.INVALID_DATA.format(
                detail='Product Type is not a valid choice',
                # choices=', '.join([choice[1] for choice in Product.ProductType.choices])
            )
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
                for field in ['product_name', 'product_type']:
                    if field not in data:
                        raise serializers.ValidationError({
                            field: CoreErrorMessages.REQUIRED_FIELD.format(field=field)
                        })
                
                # Validate all JSON fields for complete creation/update
                for field in ['value_proposition', 'potential_cons', 'competitors']:
                    if field in data:
                        self._validate_json_field(data.get(field), field)

            # Validate unique product name within client scope
            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['product_name'],
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='product name within this client'
                )
            )

            return data
            
        except serializers.ValidationError as e:
            raise serializers.ValidationError(self._extract_error_message(e))

    def _validate_json_field(self, value, field_name):
        """Validate JSON fields structure"""
        if value is not None:
            if not isinstance(value, dict):
                raise serializers.ValidationError({
                    field_name: CoreErrorMessages.INVALID_DATA.format(
                        detail=f"{field_name} must be a valid JSON object"
                    )
                })
                
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
            raise serializers.ValidationError({
                field_name: CoreErrorMessages.INVALID_DATA.format(
                    detail=f"Missing required keys in {field_name}: {', '.join(missing_keys)}"
                )
            })