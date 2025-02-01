from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import AccountOrganizationUnit
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from core.exceptions import StandardizedValidationError
from apps.core_apps.models import StandardDepartment

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

    standard_department_id = serializers.IntegerField(
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Standard department'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Standard department'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Standard department')
        })
    
    standard_department = serializers.CharField(
        source='standard_department.name',
        read_only=True
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
            'updated_at', 'client_id', 'standard_department',
            'standard_department_id'
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
                    raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field='Unit Type'))
                    
                    
                self.validate_unit_type(data['unit_type'])
                if 'metadata' in data:
                    self.validate_metadata(data.get('metadata'))

            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            # Organization name standardization
            if 'organization_name' in data:
                data['organization_name'] = data['organization_name'].upper()
            elif not self.partial:
                raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field='Organization Name'))
                
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
                    raise StandardizedValidationError(AccountErrorMessages.EMPLOYEE_COUNT)
            
            if 'standard_department_id' in data or not self.partial:
                try:
                    standard_department_id = data.get('standard_department_id')
                    if not standard_department_id:
                        raise StandardizedValidationError(
                            CoreErrorMessages.REQUIRED_FIELD.format(field='Standard department')
                        )
                    StandardDepartment.objects.get(id=standard_department_id)
                except StandardDepartment.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='Standard department')
                    )
                    
            return data

        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)

    def validate_unit_type(self, value):
        """Validate unit type field"""
        if not value:
            raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field="Unit Type"))
            
        if value not in [choice[0] for choice in AccountOrganizationUnit.UnitType.choices]:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Unit Type is not a valid option"))
        
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a valid JSON object"""
        if value is not None and not isinstance(value, dict):
            raise StandardizedValidationError(CoreErrorMessages.INVALID_DATA.format(detail="Metadata must be a valid JSON object"))
            
        return value
    
    def _validate_parent_organization(self, parent_id, client_id, instance):
        """
        Validate parent organization relationship to prevent circular dependencies
        and ensure proper hierarchy.
        
        Args:
            parent_id: ID of the proposed parent organization
            client_id: Current client ID for scoping
            instance: Current organization unit instance (if updating)
        
        Raises:
            StandardizedValidationError: If validation fails
        """
        try:
            parent = AccountOrganizationUnit.objects.get(
                id=parent_id,
                client_id=client_id
            )
            
            # Cannot set itself as parent
            if instance and instance.id == parent_id:
                raise StandardizedValidationError(
                    AccountErrorMessages.SELF_PARENT
                )
                
            # Check for circular reference
            current_parent = parent
            while current_parent:
                # If updating existing org unit, check if any parent in chain
                # references the current instance
                if instance and current_parent.parent_organization_unit_id == instance.id:
                    raise StandardizedValidationError(
                        AccountErrorMessages.CIRCULAR_HIERARCHY
                    )
                current_parent = current_parent.parent_organization_unit
                
            # Validate organizational hierarchy logic
            if instance and instance.unit_type == AccountOrganizationUnit.UnitType.DIVISION:
                if parent.unit_type != AccountOrganizationUnit.UnitType.DEPARTMENT:
                    raise StandardizedValidationError(
                        AccountErrorMessages.INVALID_PARENT_ORG.format(
                            detail="Division must have Department as parent"
                        )
                    )
            
            if instance and instance.unit_type == AccountOrganizationUnit.UnitType.TEAM:
                if parent.unit_type not in [
                    AccountOrganizationUnit.UnitType.DIVISION,
                    AccountOrganizationUnit.UnitType.DEPARTMENT
                ]:
                    raise StandardizedValidationError(
                        AccountErrorMessages.INVALID_PARENT_ORG.format(
                            detail="Team must have Division or Department as parent"
                        )
                    )
                    
        except AccountOrganizationUnit.DoesNotExist:
            raise StandardizedValidationError(
                AccountErrorMessages.INVALID_PARENT_ORG.format(
                    detail="Parent organization unit not found"
                )
            )