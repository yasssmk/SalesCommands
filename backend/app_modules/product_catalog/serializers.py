# app_modules/product_catalog/serializers.py
"""
Serializers for the ProductCatalog module.

Four serializers mirroring the TechCatalog pattern:
    * ProductCatalogListSerializer   — lightweight list view
    * ProductCatalogSerializer       — full read view
    * ProductCatalogCreateSerializer — write path for POST
    * ProductCatalogUpdateSerializer — restricted write path for PATCH
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from app_modules.product_catalog.models import ProductCatalog


# =============================================================================
# LIST SERIALIZER (lightweight)
# =============================================================================

class ProductCatalogListSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):

    class Meta:
        model = ProductCatalog
        fields = [
            'id',
            'name',
            'description',
            'value_proposition',
            'default_unit_price',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL SERIALIZER (full read view)
# =============================================================================

class ProductCatalogSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):

    class Meta:
        model = ProductCatalog
        fields = [
            'id',
            'client_id',
            'name',
            'description',
            'value_proposition',
            'default_unit_price',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE SERIALIZER
# =============================================================================

class ProductCatalogCreateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):

    class Meta:
        model = ProductCatalog
        fields = [
            'name',
            'description',
            'value_proposition',
            'default_unit_price',
        ]
        # Bypass DRF auto-generated UniqueTogetherValidator from the
        # composite constraint (client_id, name).
        validators = []
        extra_kwargs = {
            'name': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Product name'
                    ),
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Product name'
                    ),
                },
            },
            'description': {'required': False},
            'value_proposition': {'required': False},
            'default_unit_price': {
                'required': False,
                'allow_null': True,
            },
        }

    def validate(self, attrs):
        name = (attrs.get('name') or '').strip()
        if not name:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Product name')
            )
        attrs['name'] = name

        client_id = self._get_client_id_from_context()
        attrs['client_id'] = client_id

        self.validate_client_scoped_uniqueness(
            data=attrs,
            unique_fields=['name'],
            model_class=ProductCatalog,
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='product name'
            ),
        )

        return attrs

    def create(self, validated_data):
        user = self.context.get('request').user if self.context.get('request') else None
        instance = ProductCatalog(**validated_data)
        instance.save(user=user)
        return instance


# =============================================================================
# UPDATE SERIALIZER
# =============================================================================

class ProductCatalogUpdateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):

    class Meta:
        model = ProductCatalog
        fields = [
            'name',
            'description',
            'value_proposition',
            'default_unit_price',
        ]
        # Bypass DRF auto-generated UniqueTogetherValidator.
        validators = []
        extra_kwargs = {
            'name': {
                'required': False,
                'allow_blank': False,
                'error_messages': {
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Product name'
                    ),
                },
            },
            'description': {'required': False},
            'value_proposition': {'required': False},
            'default_unit_price': {
                'required': False,
                'allow_null': True,
            },
        }

    def validate(self, attrs):
        if 'name' in attrs and attrs['name'] is not None:
            attrs['name'] = attrs['name'].strip()
            if not attrs['name']:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Product name'
                    )
                )

        name_changing = 'name' in attrs
        if name_changing and self.instance:
            uniqueness_data = {
                'name': attrs.get('name', self.instance.name),
            }
            self.validate_client_scoped_uniqueness(
                data=uniqueness_data,
                unique_fields=['name'],
                model_class=ProductCatalog,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='product name'
                ),
            )

        return attrs

    def update(self, instance, validated_data):
        user = self.context.get('request').user if self.context.get('request') else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(user=user)
        return instance
