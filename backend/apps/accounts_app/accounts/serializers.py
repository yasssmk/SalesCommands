from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from end_users.models import User, Team
from .models import Account, AccountType, AccountClassification
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.serializers import  ContactDetailsSerializer
from core.exceptions import StandardizedValidationError


class AssignedTeamSerializer(serializers.ModelSerializer):
    """Serializer for the assigned team summary"""
    class Meta:
        model = Team
        fields = ['id', 'name', 'organization']
        read_only_fields = fields

class AccountManagerSerializer(serializers.ModelSerializer):
    """Serializer for the account manager summary"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role_name', 'team']
        read_only_fields = fields

class AccountSerializer(ContactDetailsSerializer, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    # Field for write operations

    company_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Company Name')
        }
    )
    
    parent_id = serializers.IntegerField(
        source='parent_company_id',
        required=False,
        allow_null=True,
        write_only=True
    )

    account_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True
    )

    team_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True
    )

    company_size = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    annual_revenue = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    historical_data = serializers.JSONField(
        required=False,
        allow_null=True
    )

    type = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    classification = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )
    
    # Fields for read operations
    parent_company = serializers.SerializerMethodField(read_only=True)
    direct_child_companies = serializers.SerializerMethodField(read_only=True)
    account_owner = AccountManagerSerializer(read_only=True)
    team_owner = AssignedTeamSerializer(read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'company_name', 'industry', 'address', 
            'city', 'post_code', 'state', 'country', 'website', 
            'type', 'phone_number', 'created_at', 'updated_at',
            'company_size', 'annual_revenue', 'classification',
            'parent_company', 'parent_id', 'direct_child_companies',
            'email', 'linkedin', 'account_owner', 'account_owner_id', 
            'team_owner', 'team_owner_id', 'client_id', 'historical_data'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']
    
    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': obj.parent_company.id,
                'company_name': obj.parent_company.company_name,
                'type': obj.parent_company.type,
                'classification': obj.parent_company.classification
            }
        return None
    
    def get_direct_child_companies(self, obj):
        return [{
            'id': child.id,
            'company_name': child.company_name,
            'type': child.type,
            'classification': child.classification
        } for child in obj.direct_child_companies.all()]
    

    def validate_type(self, value):
        """Validate type field"""
        if value is None or value == '':
            return value
        
        valid_types = [choice[0] for choice in AccountType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Type"))
        return value
        return value

    def validate_classification(self, value):
        """Validate classification field"""
        if value is None or value == '':
            return value
            
        valid_classifications = [choice[0] for choice in AccountClassification.choices]
        if value not in valid_classifications:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Classification"))
        return value

    def validate(self, data):
        """Complete validation of Account data."""
        try:
            if self.partial:
                # For PATCH requests, only validate fields that were sent
                fields_to_validate = set(self.initial_data.keys())
                
                # Only validate choice fields if they're being updated
                for field in ['type', 'classification']:
                    if field in fields_to_validate:
                        value = data.get(field)
                        if field == 'type':
                            self.validate_type(value)
                        else:
                            self.validate_classification(value)
                
                # For contact fields, only validate if they're being updated
                contact_fields = {'address', 'city', 'post_code', 'state', 'country', 
                                'phone_number', 'email', 'website', 'linkedin'}
                if contact_fields.intersection(fields_to_validate):
                    # Call parent class's validate_contact_details method
                    data = super(ContactDetailsSerializer, self).validate(data)
                    
            else:
                # For full updates (PUT/POST), validate everything
                data = super(ContactDetailsSerializer, self).validate(data)

                if "city" not in data:
                    raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field="City"))

            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            if 'company_name' in data:
                data['company_name'] = data['company_name'].upper()

            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['company_name', 'city', 'country'],
                model_class=Account,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='company name, city, and country'
                )
            )

            # Parent company validation if needed
            if 'parent_company_id' in data:
                parent_id = data.get('parent_company_id')
                if parent_id is not None:
                    self._validate_parent_company(parent_id, client_id, instance)

            # Team and account owner validation if needed
            if {'account_owner_id', 'team_owner_id'}.intersection(data.keys()):
                self._validate_account_owner_and_team(data, client_id)

            return data

        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)

    def _validate_parent_company(self, parent_id, client_id, instance):
        """Validate parent company relationships."""
        try:
            parent = Account.objects.get(id=parent_id)

            if str(parent.client_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)

            # Check for self-reference and circular references
            if instance and str(parent.id) == str(instance.id):
               raise StandardizedValidationError(AccountErrorMessages.SELF_PARENT)

            current = parent
            path = {str(current.id)}
            while current.parent_company:
                current = current.parent_company
                if str(current.id) in path or (instance and str(current.id) == str(instance.id)):
                    raise StandardizedValidationError(AccountErrorMessages.CIRCULAR_HIERARCHY)
                path.add(str(current.id))
        except Account.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)

    def _validate_account_owner_and_team(self, data, client_id):
        """Validate account owner and team owner relationships."""
        account_owner_id = data.get('account_owner_id')
        team_owner_id = data.get('team_owner_id')

        if account_owner_id is not None:
            try:
                account_owner = User.objects.get(id=account_owner_id)
                if not account_owner.is_active:
                    raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)

                if team_owner_id:
                    team = Team.objects.get(id=team_owner_id)
                    if account_owner.team_id != team.id:
                        raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH)
            except User.DoesNotExist:
                raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)

        if team_owner_id is not None:
            try:
                team = Team.objects.get(id=team_owner_id)
                if str(team.organization.client_account_id) != str(client_id):
                    raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH)
            except Team.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)