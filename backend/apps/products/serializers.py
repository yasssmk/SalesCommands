from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from .models import BillingCycle, Pricing, Product
from apps.core_apps.serializers import StandardDepartmentSerializer

class BillingCycleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    
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
    """Serializer for the Pricing model with multiple billing cycles"""
    
    available_cycles = BillingCycleSerializer(many=True, read_only=True)
    cycle_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Pricing
        fields = [
            'id', 'pricing_type', 'base_price', 'currency',
            'available_cycles', 'cycle_ids', 'product'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']
    
    def validate(self, data):
        """Validate pricing data"""
        data = super().validate(data)

        # Validate that subscription pricing has at least one billing cycle
        if data.get('pricing_type') == Pricing.PricingType.SUBSCRIPTION:
            cycle_ids = data.get('cycle_ids', [])
            if not cycle_ids and not (self.instance and self.instance.available_cycles.exists()):
                raise serializers.ValidationError({
                    'cycle_ids': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='At least one billing cycle for subscription pricing'
                    )
                })
            
            # Validate that all cycle_ids exist and belong to the same client
            if cycle_ids:
                cycles_count = BillingCycle.objects.filter(
                    id__in=cycle_ids,
                    client_id=self._get_client_id_from_context()
                ).count()
                
                if cycles_count != len(cycle_ids):
                    raise serializers.ValidationError({
                        'cycle_ids': CoreErrorMessages.INVALID_FIELD.format(
                            field='cycle_ids'
                        )
                    })
        
        # Validate base price
        if data.get('base_price', 0) < 0:
            raise serializers.ValidationError({
                'base_price': CoreErrorMessages.INVALID_FIELD.format(
                    field='base_price'
                )
            })
        
        return data

    def create(self, validated_data):
        """Handle creation with billing cycles"""
        cycle_ids = validated_data.pop('cycle_ids', [])
        instance = super().create(validated_data)
        
        if cycle_ids:
            instance.available_cycles.set(cycle_ids)
        
        return instance

    def update(self, instance, validated_data):
        """Handle updates with billing cycles"""
        cycle_ids = validated_data.pop('cycle_ids', None)
        instance = super().update(instance, validated_data)
        
        if cycle_ids is not None:
            instance.available_cycles.set(cycle_ids)
        
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
    target_category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
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
            'invalid_choice': CoreErrorMessages.INVALID_CHOICE.format(
                field='Product Type',
                choices=', '.join([choice[1] for choice in Product.ProductType.choices])
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