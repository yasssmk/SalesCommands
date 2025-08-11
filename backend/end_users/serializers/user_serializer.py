# end_users/serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models.user_model import ClientAccount, UserRole, Organization, Team, User


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


class UserRoleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour UserRole avec client scoping
    """
    users_count = serializers.SerializerMethodField(read_only=True)
    permissions_summary = serializers.SerializerMethodField(read_only=True)
    
    # Relation client_account
    client_account_name = serializers.CharField(source='client_account.name', read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'name', 'read', 'write', 'modify', 'delete',
            'client_account', 'client_account_name',
            'users_count', 'permissions_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'users_count', 'permissions_summary']
    
    def get_users_count(self, obj):
        """Nombre d'utilisateurs avec ce rôle"""
        return obj.users.filter(is_active=True).count()
    
    def get_permissions_summary(self, obj):
        """Résumé des permissions"""
        permissions = []
        if obj.read: permissions.append('read')
        if obj.write: permissions.append('write') 
        if obj.modify: permissions.append('modify')
        if obj.delete: permissions.append('delete')
        return permissions
    
    def validate(self, data):
        """Validation métier"""
        data = super().validate(data)
        
        # Vérifier l'unicité nom + client dans le même tenant
        client_id = self._get_client_id_from_context()
        name = data.get('name')
        
        if name:
            # Exclure l'instance actuelle en cas d'update
            queryset = UserRole.objects.filter(name=name, client_id=client_id)
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
                
            if queryset.exists():
                raise StandardizedValidationError(
                    CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields="role name")
                )
        
        return data


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


class UserListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer léger pour les listes d'utilisateurs (performance optimisée)
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    display_name = serializers.CharField(source='get_display_name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    is_manager = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'full_name', 'display_name',
            'role_name', 'team_name', 'organization_name',
            'is_active', 'is_manager',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_is_manager(self, obj):
        """Vérifier si l'utilisateur est manager"""
        return obj.is_manager()


class UserSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer complet pour User avec client scoping et validation robuste
    """
    
    # === CHAMPS CALCULÉS EN LECTURE ===
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    display_name = serializers.CharField(source='get_display_name', read_only=True)
    short_name = serializers.CharField(source='get_short_name', read_only=True)
    
    # Relations en lecture
    client_account_name = serializers.CharField(source='client_account.name', read_only=True)
    role_permissions = serializers.SerializerMethodField(read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    # Status et métriques
    is_manager = serializers.SerializerMethodField(read_only=True)
    managed_users_count = serializers.SerializerMethodField(read_only=True)
    
    # === CHAMPS ÉCRITURE AVEC VALIDATION ===
    password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
        help_text=_('Password must be at least 8 characters long')
    )
    
    # Relations avec validation client scope
    client_account = serializers.PrimaryKeyRelatedField(
        queryset=ClientAccount.objects.all(),
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Client Account'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Client Account')
        }
    )
    
    role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Role')
        }
    )
    
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Team')
        }
    )
    
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Organization')
        }
    )
    
    class Meta:
        model = User
        fields = [
            # Identité
            'id', 'email', 'first_name', 'last_name',
            'full_name', 'display_name', 'short_name',
            
            # Authentification
            'password', 'is_active', 'is_staff',
            
            # Relations
            'client_account', 'client_account_name',
            'role', 'role_name', 'role_permissions',
            'organization', 'organization_name',
            'team', 'team_name',
            
            # Status et métriques
            'is_manager', 'managed_users_count',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'role_name',
            'full_name', 'display_name', 'short_name',
            'is_manager', 'managed_users_count'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'password': {'write_only': True}
        }
    
    # === MÉTHODES CALCULÉES ===
    
    def get_role_permissions(self, obj):
        """Permissions du rôle utilisateur"""
        if obj.role:
            return {
                'read': obj.role.read,
                'write': obj.role.write,
                'modify': obj.role.modify,
                'delete': obj.role.delete
            }
        return {}
    
    def get_is_manager(self, obj):
        """Vérifier si l'utilisateur est manager"""
        return obj.is_manager()
    
    def get_managed_users_count(self, obj):
        """Nombre d'utilisateurs managés"""
        return obj.get_managed_users().count()
    
    # === VALIDATION MÉTIER ===
    
    def validate_password(self, value):
        """Validation du mot de passe"""
        if value:
            try:
                validate_password(value)
            except Exception as e:
                raise StandardizedValidationError(str(e))
        return value
    
    def validate_email(self, value):
        """Validation email unique"""
        if value:
            # Vérifier unicité globale (pas par client pour les emails)
            queryset = User.objects.filter(email=value)
            if self.instance:
                queryset = queryset.exclude(id=self.instance.id)
            
            if queryset.exists():
                raise StandardizedValidationError(
                    _("A user with this email already exists.")
                )
        return value
    
    def validate_role(self, value):
        """Valider que le rôle appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate_team(self, value):
        """Valider que l'équipe appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate_organization(self, value):
        """Valider que l'organisation appartient au même client"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate(self, data):
        """Validation métier croisée"""
        data = super().validate(data)
        
        # Cohérence équipe/organisation
        team = data.get('team') or (self.instance.team if self.instance else None)
        organization = data.get('organization') or (self.instance.organization if self.instance else None)
        
        if team and organization:
            if team.organization != organization:
                raise StandardizedValidationError(
                    _("Team must belong to the selected organization.")
                )
        
        # Cohérence rôle/client
        role = data.get('role') or (self.instance.role if self.instance else None)
        client_account = data.get('client_account') or (self.instance.client_account if self.instance else None)
        
        if role and client_account:
            if role.client_account != client_account:
                raise StandardizedValidationError(
                    _("Role must belong to the selected client account.")
                )
        
        return data
    
    # === CRÉATION ET MISE À JOUR ===
    
    def create(self, validated_data):
        """Création d'utilisateur avec logique métier"""
        password = validated_data.pop('password', None)
        
        # Utiliser le manager pour la création
        if password:
            user = User.objects.create_user(password=password, **validated_data)
        else:
            user = User(**validated_data)
            user.set_unusable_password()
            user.save()
        
        return user
    
    def update(self, instance, validated_data):
        """Mise à jour avec gestion du mot de passe"""
        password = validated_data.pop('password', None)
        
        # Mettre à jour les autres champs
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Gérer le mot de passe séparément
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class UserPerformanceAccessSerializer(ClientScopeManager.SerializerMixin, serializers.Serializer):
    """
    Serializer pour vérifier l'accès aux performances utilisateur
    Utilisé par UserPerformanceService
    """
    target_user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Target User'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Target User ID')
        }
    )
    
    def validate_target_user_id(self, value):
        """Valider l'accès aux performances de l'utilisateur cible"""
        request = self.context.get('request')
        if not request or not request.user:
            raise StandardizedValidationError(AuthErrorMessages.AUTH_REQUIRED)
        
        # Utiliser la logique métier du modèle
        if not request.user.can_access_user_performance(value):
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        return value