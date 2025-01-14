# serializers.py
from rest_framework import serializers
from .models import ClientAccount, UserRole, Organization, Team, User


class ClientAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientAccount
        fields = ['id', 'name', 'is_b2b', 'max_users', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'name', 'read', 'write', 'modify', 'delete', 'client_account', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def validate(self, data):
        # Example validation to avoid conflicting role names for the same client
        if UserRole.objects.filter(name=data['name'], client_account=data['client_account']).exists():
            raise serializers.ValidationError("Role with this name already exists for the client.")
        return data
    
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'client_account', 'manager', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'name', 'organization', 'manager', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)  # Optional for updates
    organization = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'password', 'first_name', 'last_name', 'is_active', 'is_staff',
            'client_account', 'role', 'organization', 'team', 'last_time_connected', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_time_connected', 'organization']

    def create(self, validated_data):
        # Let the model handle setting the organization based on the team
        return User.objects.create_user(**validated_data)

    # def update(self, instance, validated_data):
    #     # Password updates are handled separately
    #     validated_data.pop('password', None)
    #     return super().update(instance, validated_data)

