# end_users/serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, AuthErrorMessages
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
    last_login = serializers.DateTimeField(read_only=True)
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'full_name', 'display_name',
            'role_name', 'team_name', 'organization_name',
            'is_active', 'is_manager',
            'created_at', 'last_login'
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
            'is_manager', 'managed_users_count', 'client_account', 'last_login'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'password': {'write_only': True}
        }
    
    def _get_admin_role(self, client):
        # Utilise les helpers de ClientAccount (Étape 1)
        return client.get_or_create_admin_role()

    def _is_last_admin(self, user):
        client = user.client_account
        # Dernier admin (tous états, actif ou non) pour éviter perte totale d'admin
        is_admin = (user.role and user.role.name == client.ADMIN_ROLE_NAME) or (user.role_name == client.ADMIN_ROLE_NAME)
        return is_admin and client.count_admins(active_only=False) == 1
        
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
    
    
    def validate_role(self, value):
        """Ensure role belongs to the same client"""
        if value:
            client_id = self._get_client_id_from_context()
            # ✅ Use client_account_id on the role
            if str(value.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value

    def validate_team(self, value):
        """Ensure team belongs to the same client"""
        if value:
            client_id = self._get_client_id_from_context()
            # ✅ Team is scoped through its organization
            if str(value.organization.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value

    def validate_organization(self, value):
        """Ensure organization belongs to the same client"""
        if value:
            client_id = self._get_client_id_from_context()
            # ✅ Organization has client_account_id
            if str(value.client_account_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        return value
    
    def validate(self, data):
        """Complete validation of User data with client scoping"""
        try:
            # Call parent validation first  
            data = super().validate(data)
            
            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)
            
            # Validate email uniqueness within client scope
            if 'email' in data:
                email = data['email']
                
                # Check email uniqueness within the client
                queryset = User.objects.filter(
                    email=email,
                    client_account_id=client_id  
                )
                
                # Exclude current instance for updates
                if instance:
                    queryset = queryset.exclude(id=instance.id)
                
                if queryset.exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields="email")
                    )
            
            # Cohérence rôle/client
            role = data.get('role') or (instance.role if instance else None)
            client_account_id = client_id  # Le client_id du contexte
            
            if role and client_account_id:
                if str(role.client_account_id) != str(client_account_id):
                    raise StandardizedValidationError(
                        _("Role must belong to the selected client account.")
                    )
            
            # Cohérence team/organization/client
            team = data.get('team') or (instance.team if instance else None)
            organization = data.get('organization') or (instance.organization if instance else None)
            
            if team and organization:
                if team.organization != organization:
                    raise StandardizedValidationError(
                        _("Team must belong to the selected organization.")
                    )
            
            if team and str(team.organization.client_account_id) != str(client_account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
            
            if organization and str(organization.client_account_id) != str(client_account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
            
            return data
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)
        
    # === CRÉATION ET MISE À JOUR ===
    
    def create(self, validated_data):
        """Création d'utilisateur avec logique seats + premier admin"""
        password = validated_data.pop('password', None)

        # Assigner automatiquement le client_account depuis le contexte (déjà existant)
        client_id = self._get_client_id_from_context()
        if client_id:
            try:
                client_account = ClientAccount.objects.get(id=client_id)
                validated_data['client_account'] = client_account
            except ClientAccount.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Client Account")
                )

        client = validated_data['client_account']

        # Seats: si demande d'activation et plus de sièges dispo -> forcer inactif
        want_active = validated_data.get('is_active', True)
        if want_active and not client.has_available_seat():
            validated_data['is_active'] = False  # MVP: pas d'erreur, créé inactif

        # Premier user du client -> Admin automatiquement
        if client.users.count() == 0:
            admin_role = self._get_admin_role(client)
            validated_data['role'] = admin_role
            validated_data['role_name'] = admin_role.name
            # On laisse is_active tel quel si seat dispo; sinon il restera inactif

        # Création via manager si mot de passe fourni
        if password:
            user = User.objects.create_user(password=password, **validated_data)
        else:
            user = User(**validated_data)
            user.set_unusable_password()
            user.save()

        # Filet: garantir la présence d'un Admin (en cas d'état incohérent)
        client.ensure_admin_invariants()
        return user
    
    def update(self, instance, validated_data):
        client = instance.client_account
        admin_role = self._get_admin_role(client)

        # === RÈGLE DERNIER ADMIN ===
        is_last_admin = self._is_last_admin(instance)

        # Tentative de changement de rôle ?
        if 'role' in validated_data:
            new_role = validated_data.get('role')
            new_is_admin = (new_role and new_role.name == admin_role.name)
            if is_last_admin and not new_is_admin:
                # Interdit de retirer/vider le rôle admin au dernier admin
                raise StandardizedValidationError(CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED)

        # Tentative de désactivation ?
        if 'is_active' in validated_data:
            new_active = validated_data.get('is_active')
            if is_last_admin and new_active is False:
                # Interdit de désactiver le dernier admin (évite lock-out)
                raise StandardizedValidationError(CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED)

        # === RÈGLE SEATS À L’ACTIVATION ===
        if 'is_active' in validated_data and validated_data['is_active'] is True:
            # Si on était inactif et qu'on veut devenir actif : vérifier places
            if not instance.is_active:
                if not client.has_available_seat():
                    raise StandardizedValidationError(CoreErrorMessages.SEAT_LIMIT_REACHED)

        # Appliquer les autres champs
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Gestion du mot de passe
        if password:
            instance.set_password(password)

        # Mettre à jour le cache role_name si rôle modifié
        if 'role' in validated_data:
            if instance.role:
                instance.role_name = instance.role.name
            else:
                instance.role_name = None

        instance.save()

        # Filet: garantir la présence d'un Admin si besoin
        client.ensure_admin_invariants()
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

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer pour le changement de mot de passe utilisateur.
    Validation simple : les deux mots de passe doivent être identiques.
    Pas de règles de complexité selon les specs MVP.
    """
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        min_length=1,  # Au moins 1 caractère, pas de règle de complexité
        help_text='New password'
    )
    
    password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text='Confirm new password'
    )
    
    def validate(self, attrs):
        """
        Validation simple : vérifier que les deux mots de passe sont identiques.
        """
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')
        
        # Vérification de présence (normalement déjà fait par required=True)
        if not password or not password_confirm:
            raise serializers.ValidationError({
                'password': CoreErrorMessages.REQUIRED_FIELD.format(field='Password'),
                'password_confirm': CoreErrorMessages.REQUIRED_FIELD.format(field='Password confirmation')
            })
        
        # Vérification d'égalité
        if password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match'
            })
        
        # On ne retourne que le password (pas besoin de password_confirm après validation)
        return {
            'password': password
        }
    
    def update_password(self, user, validated_data):
        """
        Méthode helper pour mettre à jour le mot de passe de l'utilisateur.
        
        Args:
            user: Instance User à mettre à jour
            validated_data: Données validées contenant le nouveau mot de passe
            
        Returns:
            user: L'instance User mise à jour
        """
        user.set_password(validated_data['password'])
        user.save(update_fields=['password', 'updated_at'])
        return user