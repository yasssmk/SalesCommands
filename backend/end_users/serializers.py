# # serializers.py
# from rest_framework import serializers
# from .models import ClientAccount, UserRole, Organization, Team, User


# class ClientAccountSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ClientAccount
#         fields = ['id', 'name', 'is_b2b', 'max_users', 'created_at', 'updated_at']
#         read_only_fields = ['created_at', 'updated_at']


# class UserRoleSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserRole
#         fields = ['id', 'name', 'read', 'write', 'modify', 'delete', 'client_account', 'created_at', 'updated_at']
#         read_only_fields = ['created_at', 'updated_at']
    
#     def validate(self, data):
#         # Example validation to avoid conflicting role names for the same client
#         if UserRole.objects.filter(name=data['name'], client_account=data['client_account']).exists():
#             raise serializers.ValidationError("Role with this name already exists for the client.")
#         return data
    
# class OrganizationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Organization
#         fields = ['id', 'name', 'client_account', 'manager', 'created_at', 'updated_at']
#         read_only_fields = ['created_at', 'updated_at']


# class TeamSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Team
#         fields = ['id', 'name', 'organization', 'manager', 'created_at', 'updated_at']
#         read_only_fields = ['created_at', 'updated_at']

# class UserSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True, required=True, min_length=8)
#     organization = serializers.PrimaryKeyRelatedField(read_only=True)
#     role_name = serializers.ReadOnlyField()
#     client_account = serializers.UUIDField(format='hex_verbose')
#     role = serializers.UUIDField(format='hex_verbose')
#     team = serializers.UUIDField(format='hex_verbose', required=False, allow_null=True)

#     class Meta:
#         model = User
#         fields = [
#             'id', 'email', 'password', 'first_name', 'last_name', 'is_active', 'is_staff',
#             'client_account', 'role', 'role_name', 'organization', 'team', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'role_name', 'organization']

#     def validate(self, data):
#         # Validate that role belongs to client_account
#         try:
#             role = UserRole.objects.get(id=data['role'], client_account_id=data['client_account'])
#             data['role'] = role
#         except UserRole.DoesNotExist:
#             raise serializers.ValidationError("Invalid role for this client account")

#         # Validate team if provided
#         if 'team' in data and data['team']:
#             try:
#                 team = Team.objects.get(
#                     id=data['team'],
#                     organization__client_account_id=data['client_account']
#                 )
#                 data['team'] = team
#             except Team.DoesNotExist:
#                 raise serializers.ValidationError("Invalid team for this client account")

#         return data

#     def create(self, validated_data):
#         # Get the actual model instances
#         client_account = ClientAccount.objects.get(id=validated_data['client_account'])
#         validated_data['client_account'] = client_account
        
#         # Set role_name
#         role = validated_data.get('role')
#         if role:
#             validated_data['role_name'] = role.name

#         # Create user with create_user method
#         password = validated_data.pop('password')
#         user = User.objects.create_user(
#             password=password,
#             **validated_data
#         )
#         return user

