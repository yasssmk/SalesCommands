from rest_framework import serializers
from core.error_messages import CoreErrorMessages
from core.client_scope import ClientScopeManager
from ..models import Pricing, Product
from core.constants import CURRENCY


class PricingSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        error_messages={
            'does_not_exist': f"{CoreErrorMessages.OBJECT_NOT_FOUND}",
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
    
    def create(self, validated_data):
        """
        Create Pricing instance, call full_clean(), then save.
        """
        instance = Pricing(**validated_data)
        instance.full_clean()  # This calls model-level clean()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """
        Update Pricing instance, call full_clean(), then save.
        For partial updates, override only fields in validated_data.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()  # This calls model-level clean()
        instance.save()
        return instance

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