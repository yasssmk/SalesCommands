
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models import Organization, User


class OrganizationSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour Organization avec client scoping
    """
    # Relations en lecture
    client_account_name = serializers.CharField(source='client_account.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    
    # Compteurs
    teams_count = serializers.SerializerMethodField(read_only=True)
    members_count = serializers.SerializerMethodField(read_only=True)
    active_members_count = serializers.SerializerMethodField(read_only=True)
    
    # Relations en écriture avec validation
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
        model = Organization
        fields = [
            'id', 'name', 'client_account', 'client_account_name',
            'manager', 'manager_name',
            'teams_count', 'members_count', 'active_members_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'client_account',
            'teams_count', 'members_count', 'active_members_count'
        ]
    
    def get_teams_count(self, obj):
        """Nombre d'équipes"""
        return obj.teams.count()
    
    def get_members_count(self, obj):
        """Nombre total de membres"""
        return obj.members.count()
    
    def get_active_members_count(self, obj):
        """Nombre de membres actifs"""
        return obj.members.filter(is_active=True).count()
    
    def validate_manager(self, value):
        """Valider que le manager appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
