from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import AccountOrganizationUnit
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages, ValidationErrorMessages
# from sales_insight.serializers import SalesInsightSerializer

class OrganizationUnitSummarySerializer(serializers.ModelSerializer):
    """Serializer for nested organization unit representations"""
    class Meta:
        model = AccountOrganizationUnit
        fields = ['id', 'organization_name', 'unit_type', 'estimated_employee_count']
        read_only_fields = fields

class AccountOrganizationUnitSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    # Write-only fields
    parent_unit_id = serializers.IntegerField(
        source='parent_organization_unit_id',
        required=False,
        allow_null=True,
        write_only=True
    )

    # Read-only fields
    parent_organization_unit = OrganizationUnitSummarySerializer(read_only=True)
    child_organization_units = OrganizationUnitSummarySerializer(many=True, read_only=True)
    # org_insights = SalesInsightSerializer(read_only=True)

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
    
    def validate_unit_type(self, value):
        """Validate unit type field"""
        if value not in [choice[0] for choice in AccountOrganizationUnit.UnitType.choices]:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Unit Type")
            )
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a valid JSON object"""
        if value is not None and not isinstance(value, dict):
            raise CoreErrorMessages.INVALID_DATA.format(detail="Metadata must be a valid JSON object")
        return value
    
    def validate(self, data):
        """Complete validation of AccountOrganizationUnit data."""
        try:
            if self.partial:
                # For PATCH requests, only validate fields that were sent
                fields_to_validate = set(self.initial_data.keys())
                
                if 'unit_type' in fields_to_validate:
                    self.validate_unit_type(data.get('unit_type'))
                
                if 'metadata' in fields_to_validate:
                    self.validate_metadata(data.get('metadata'))
            else:
                # For full updates (PUT/POST), validate everything
                if 'unit_type' in data:
                    self.validate_unit_type(data['unit_type'])
                if 'metadata' in data:
                    self.validate_metadata(data.get('metadata'))

            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            # Organization name standardization
            if 'organization_name' in data:
                data['organization_name'] = data['organization_name'].upper()

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
                    raise AccountErrorMessages.EMPLOYEE_COUNT

            return data

        except serializers.ValidationError as e:
            error_msg = self._extract_error_message(e)
            raise serializers.ValidationError(error_msg)

    def _validate_parent_organization(self, parent_id, client_id, instance):
        """Validate parent organization unit relationships."""
        try:
            parent = AccountOrganizationUnit.objects.get(id=parent_id)

            # Verify same client scope
            if str(parent.client_id) != str(client_id):
                raise AccountErrorMessages.INVALID_PARENT

            # Verify same account scope
            if instance and parent.account_id != instance.account_id:
                raise AccountErrorMessages.INVALID_PARENT_ORG

            # Check for self-reference
            if instance and str(parent.id) == str(instance.id):
                raise AccountErrorMessages.SELF_PARENT

            # Check for circular references
            current = parent
            path = {str(current.id)}
            while current.parent_organization_unit:
                current = current.parent_organization_unit
                if str(current.id) in path or (instance and str(current.id) == str(instance.id)):
                    raise AccountErrorMessages.CIRCULAR_HIERARCHY
                path.add(str(current.id))

        except AccountOrganizationUnit.DoesNotExist:
            raise AccountErrorMessages.PARENT_NOT_FOUND
    
    def create(self, validated_data):
        """Override create to handle nested relationships"""
        # Ensure account is provided
        if 'account' not in validated_data:
            raise CoreErrorMessages.REQUIRED_FIELD.format(field='Account')
            

        # Create the organization unit
        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        """Override update to handle nested relationships"""
        # Prevent changing the account
        if 'account' in validated_data and validated_data['account'] != instance.account:
            raise AccountErrorMessages.CHANGE_ACCOUNT_ORG

        return super().update(instance, validated_data)