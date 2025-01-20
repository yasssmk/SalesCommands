from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from end_users.models import User, Team
from core.client_scope import ClientScopeManager

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

class AccountSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    # Field for write operations
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
            'number_of_employees', 'potential', 'classification',
            'parent_company', 'parent_id', 'direct_child_companies',
            'email', 'linkedin', 'account_owner', 'account_owner_id', 
            'team_owner', 'team_owner_id', 'client_id'
        ]
        read_only_fields = ['created_at', 'updated_at', 'client_id']
    
    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': obj.parent_company.id,
                'company_name': obj.parent_company.company_name,
                'type': obj.parent_company.type
            }
        return None
    
    def get_direct_child_companies(self, obj):
        return [{
            'id': child.id,
            'company_name': child.company_name,
            'type': child.type
        } for child in obj.direct_child_companies.all()]
    
    def validate(self, data):
        data = super().validate(data)

        # Convert company name to uppercase if it's present
        company_name = data.get('company_name')
        if company_name:
            data['company_name'] = company_name.upper()
        
        # Get the current instance for update operations
        instance = getattr(self, 'instance', None)
        
        # Only validate uniqueness if any of the unique constraint fields are being updated
        unique_fields = ['company_name', 'city', 'country']
        if any(field in data for field in unique_fields):
            # For PATCH requests, merge with existing data to check complete uniqueness
            if instance and self.partial:
                validation_data = {
                    'company_name': instance.company_name,
                    'city': instance.city,
                    'country': instance.country,
                    **{field: data[field] for field in unique_fields if field in data}
                }
            else:
                validation_data = data

            self.validate_client_scoped_uniqueness(
                data=validation_data,
                unique_fields=unique_fields,
                model_class=Account,
                error_message=_("An account with this name already exists in your organization for this city and country.")
            )
        
        # Validate account_owner user
        account_owner_id = data.get('account_owner_id')
        team_owner_id = data.get('team_owner_id')  # Fixed field name from assigned_team_id
        
        if account_owner_id:
            try:
                account_owner = User.objects.get(id=account_owner_id)
                if not account_owner.is_active:
                    raise serializers.ValidationError({
                        'account_owner_id': _("Selected user is not active.")
                    })
                
                # If team is specified, ensure user belongs to that team
                if team_owner_id:
                    team = Team.objects.get(id=team_owner_id)
                    if account_owner.team_id != team.id:
                        raise serializers.ValidationError({
                            'account_owner_id': _("Account manager must belong to the assigned team.")
                        })
                    
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'account_owner_id': _("Invalid user ID.")
                })
        
        # Validate parent-child relationship
        parent_id = data.get('parent_company_id')
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                if instance and str(parent.id) == str(instance.id):
                    raise serializers.ValidationError({
                        'parent_id': _("A company cannot be its own parent.")
                    })
                
                # Check for circular references
                if instance:
                    current = parent
                    path = {str(current.id)}
                    while current.parent_company:
                        current = current.parent_company
                        if str(current.id) in path or str(current.id) == str(instance.id):
                            raise serializers.ValidationError({
                                'parent_id': _("Cannot create a circular parent-child relationship.")
                            })
                        path.add(str(current.id))
            except Account.DoesNotExist:
                raise serializers.ValidationError({
                    'parent_id': _("Invalid parent company ID.")
                })
        
        return data

