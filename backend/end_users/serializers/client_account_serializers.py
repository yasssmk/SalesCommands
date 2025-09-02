from rest_framework import serializers
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, AuthErrorMessages
from ..models import ClientAccount, UserRole, Organization, Team, User


class ClientAccountSerializer(serializers.ModelSerializer):
    """
    Serializer pour ClientAccount - reste simple car c'est le point d'entrée multi-tenant
    """
    users_count = serializers.SerializerMethodField(read_only=True)
    organizations_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ClientAccount
        fields = [
            'id', 'name', 'is_b2b', 'max_users', 
            'users_count', 'organizations_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'users_count', 'organizations_count']
    
    def get_users_count(self, obj):
        """Nombre d'utilisateurs actifs"""
        return obj.users.filter(is_active=True).count()
    
    def get_organizations_count(self, obj):
        """Nombre d'organisations"""
        return obj.organizations.count()