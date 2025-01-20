from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from end_users.models import User, Team
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages

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
        try:
            data = super().validate(data)
            
            # Convert company name to uppercase if it's present
            company_name = data.get('company_name')
            if company_name:
                data['company_name'] = company_name.upper()
            
            instance = getattr(self, 'instance', None)
            
            # Handle unique constraint validation
            unique_fields = ['company_name', 'city', 'country']
            if any(field in data for field in unique_fields):
                validation_data = data
                if instance and self.partial:
                    validation_data = {
                        'company_name': instance.company_name,
                        'city': instance.city,
                        'country': instance.country,
                        **{field: data[field] for field in unique_fields if field in data}
                    }
                
                self.validate_client_scoped_uniqueness(
                    data=validation_data,
                    unique_fields=unique_fields,
                    model_class=Account,
                    error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                        fields="company name, city and country"
                    )
                )
            
            # Validate account_owner and team relationship
            self._validate_account_owner(data)
            
            # Validate parent company relationship
            self._validate_parent_company(data, instance)
            
            return data
            
        except serializers.ValidationError as e:
            raise serializers.ValidationError({
                "error": CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            })

    def _validate_account_owner(self, data):
        """Validate account owner and team relationship"""
        account_owner_id = data.get('account_owner_id')
        team_owner_id = data.get('team_owner_id')
        
        if account_owner_id:
            try:
                account_owner = User.objects.get(id=account_owner_id)
                if not account_owner.is_active:
                    raise serializers.ValidationError({
                        'account_owner_id': AccountErrorMessages.USER_INACTIVE
                    })
                
                if team_owner_id:
                    team = Team.objects.get(id=team_owner_id)
                    if account_owner.team_id != team.id:
                        raise serializers.ValidationError({
                            'account_owner_id': AccountErrorMessages.TEAM_MISMATCH
                        })
                    
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'account_owner_id': AccountErrorMessages.INVALID_USER
                })

    def _validate_parent_company(self, data, instance):
        """Validate parent company relationship"""
        parent_id = data.get('parent_company_id')
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                
                # Check for self-reference
                if instance and str(parent.id) == str(instance.id):
                    raise serializers.ValidationError({
                        'parent_id': AccountErrorMessages.SELF_PARENT
                    })
                
                # Check for circular references
                if instance:
                    current = parent
                    path = {str(current.id)}
                    while current.parent_company:
                        current = current.parent_company
                        if str(current.id) in path or str(current.id) == str(instance.id):
                            raise serializers.ValidationError({
                                'parent_id': AccountErrorMessages.CIRCULAR_HIERARCHY
                            })
                        path.add(str(current.id))
                        
            except Account.DoesNotExist:
                raise serializers.ValidationError({
                    'parent_id': AccountErrorMessages.PARENT_NOT_FOUND
                })
