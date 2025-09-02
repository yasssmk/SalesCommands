from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models import Organization, Team, User



class TeamSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour Team avec client scoping
    """
    # Relations en lecture
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    
    # Compteurs
    members_count = serializers.SerializerMethodField(read_only=True)
    active_members_count = serializers.SerializerMethodField(read_only=True)
    
    # Relations en écriture avec validation
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Organization'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Organization')
        }
    )
    
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Manager')
        }
    )
    
    class Meta:
        model = Team
        fields = [
            'id', 'name', 
            'organization', 'organization_name',
            'manager', 'manager_name',
            'members_count', 'active_members_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at',
            'members_count', 'active_members_count'
        ]
    
    def get_members_count(self, obj):
        """Nombre total de membres"""
        return obj.members.count()
    
    def get_active_members_count(self, obj):
        """Nombre de membres actifs"""
        return obj.members.filter(is_active=True).count()
    
    def validate_organization(self, value):
        """Valider que l'organisation appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate_manager(self, value):
        """Valider que le manager appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value