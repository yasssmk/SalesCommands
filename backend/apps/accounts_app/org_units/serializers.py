from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import AccountOrganizationUnit
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin

class OrganizationUnitSummarySerializer(serializers.ModelSerializer):
    """Serializer for nested organization unit representations"""
    class Meta:
        model = AccountOrganizationUnit
        fields = ['id', 'organization_name', 'unit_type', 'estimated_employee_count']
        read_only_fields = fields

class AccountOrganizationUnitSerializer(AccountLinkedSerializerMixin, 
                                      ClientScopeManager.SerializerMixin, 
                                      serializers.ModelSerializer):
    # Write-only fields
    organization_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Organization name')  
        }
    )

    unit_type = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Unit Type'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Unit Type'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Unit Type')
        }
    )

    parent_unit_id = serializers.IntegerField(
        source='parent_organization_unit_id',
        required=False,
        allow_null=True,
        write_only=True
    )

    # Read-only fields
    parent_organization_unit = OrganizationUnitSummarySerializer(read_only=True)
    child_organization_units = OrganizationUnitSummarySerializer(many=True, read_only=True)

    class Meta:
        model = AccountOrganizationUnit
        fields = [
            'id', 'organization_name', 'unit_type', 
            'parent_organization_unit', 'parent_unit_id',
            'child_organization_units', 'estimated_employee_count',
            'metadata', 'org_insights', 'account', 'created_at', 
            'updated_at', 'client_id'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']

    def validate(self, data):
        """Complete validation of AccountOrganizationUnit data."""
        try:
            # First validate account through the mixin
            data = super().validate(data)

            if self.partial:
                fields_to_validate = set(self.initial_data.keys())
                
                if 'unit_type' in fields_to_validate:
                    self.validate_unit_type(data.get('unit_type'))
                
                if 'metadata' in fields_to_validate:
                    self.validate_metadata(data.get('metadata'))
            else:
                # For full updates (PUT/POST), validate everything
                if 'unit_type' not in data:
                    raise serializers.ValidationError({
                        'unit_type': CoreErrorMessages.REQUIRED_FIELD.format(field='Unit Type')
                    })
                    
                self.validate_unit_type(data['unit_type'])
                if 'metadata' in data:
                    self.validate_metadata(data.get('metadata'))

            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            # Organization name standardization
            if 'organization_name' in data:
                data['organization_name'] = data['organization_name'].upper()
            elif not self.partial:
                raise serializers.ValidationError({
                    'organization_name': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization Name')
                })

            # Validate unique constraint within account scope
            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['account', 'organization_name'],
                model_class=AccountOrganizationUnit,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='organization name within this account'
                )
            )

            # Parent organization validation
            if 'parent_organization_unit_id' in data:
                parent_id = data.get('parent_organization_unit_id')
                if parent_id is not None:
                    self._validate_parent_organization(parent_id, client_id, instance)

            # Validate estimated_employee_count if provided
            if 'estimated_employee_count' in data:
                count = data['estimated_employee_count']
                if count is not None and count < 0:
                    raise serializers.ValidationError({
                        'estimated_employee_count': AccountErrorMessages.EMPLOYEE_COUNT
                    })

            return data

        except serializers.ValidationError as e:
            error_msg = self._extract_error_message(e)
            raise serializers.ValidationError(error_msg)

    def validate_unit_type(self, value):
        """Validate unit type field"""
        if not value:
            raise serializers.ValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Unit Type")
            )
        if value not in [choice[0] for choice in AccountOrganizationUnit.UnitType.choices]:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Unit Type")
            )
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a valid JSON object"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail="Metadata must be a valid JSON object")
            )
        return value