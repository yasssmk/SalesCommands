# end_users/serializers.py

from rest_framework import serializers
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, AuthErrorMessages
from ..models import ClientAccount, UserRole, Organization, Team, User


class UserListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer léger pour les listes d'utilisateurs (performance optimisée)
    """
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    # Relations (objets pour compatibilité frontend)
    role = serializers.SerializerMethodField(read_only=True)
    organization = serializers.SerializerMethodField(read_only=True)
    team = serializers.SerializerMethodField(read_only=True)

    role_tier = serializers.SerializerMethodField(read_only=True)
    
    # Champ direct timestamp
    last_login = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            # ✅ Identité minimale
            'id', 'email', 'first_name', 'last_name',
            'full_name',  # Pour modal delete
            
            # ✅ Relations (objets complets pour frontend)
            'role', 'role_name', 'role_tier', 'organization', 'team',
            
            # ✅ Status
            'is_active', 'is_superuser',
            
            # ✅ Timestamps
            'last_login'
        ]
        read_only_fields = fields

    def get_role(self, obj):
        """
        Retourner le rôle sous forme d'objet minimal
        Compatible avec l'usage frontend: row.original.role?.name
        """
        if obj.role:
            return {
                'id': str(obj.role_id),
                'name': obj.role_name
            }
        return None
    
    def get_organization(self, obj):
        """
        Retourner l'organisation sous forme d'objet minimal
        Compatible avec l'usage frontend: row.original.organization?.name
        """
        if obj.organization:
            return {
                'id': str(obj.organization_id),
                'name': obj.organization.name
            }
        return None
    
    def get_team(self, obj):
        """
        Retourner l'équipe sous forme d'objet minimal
        Compatible avec l'usage frontend: row.original.team?.name
        """
        if obj.team:
            return {
                'id': str(obj.team_id),
                'name': obj.team.name
            }
        return None
    
    def get_role_tier(self, obj):
        """
        Retourner le tier du rôle pour la logique de couleur frontend.

        Returns:
            str: 'admin', 'manager', 'individual', ou None si pas de rôle
        """
        return obj.role.get_tier() if obj.role else None


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
    role_tier = serializers.SerializerMethodField(read_only=True)
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
            'password', 'is_active', 'is_staff', 'is_superuser', 
            'last_login',
            
            # Relations
            'client_account', 'client_account_name',
            'role', 'role_name', 'role_permissions',
            'organization', 'organization_name',
            'team', 'team_name',
            
            # Status et métriques
            'is_manager', 'role_tier', 'managed_users_count',

            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'role_name',
            'full_name', 'display_name', 'short_name',
            'is_manager', 'role_tier', 'managed_users_count', 'client_account', 'last_login'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'password': {'write_only': True}
        }
    
    def _get_admin_role(self, client):
        # Utilise les helpers de ClientAccount (Étape 1)
        return client.get_or_create_admin_role()

    def _is_last_admin(self, user):
        """
        UPDATED: Check if user is the last superuser instead of last admin role.
        This prevents lockout by ensuring at least one superuser exists.
        
        ✅ SECURITY: Uses select_for_update() to prevent TOCTOU race conditions
        IMPORTANT: Must be called within transaction.atomic() block
        """
        client = user.client_account
        # Check if this is the last superuser (active or inactive) to prevent total lockout
        if user.is_superuser:
            # ✅ VERROU: Count other superusers with pessimistic lock
            # Convert to list() because select_for_update() doesn't work with count()
            # Performance impact is minimal (typically < 10 superusers per tenant)
            other_superusers = list(
                client.users.select_for_update().filter(
                    is_superuser=True
                ).exclude(id=user.id).values_list('id', flat=True)
            )
            return len(other_superusers) == 0
        return False
    
    def _is_last_active_admin(self, user):
        """
        Check if user is the last ACTIVE superuser.
        Used for preventing deactivation of the last active superuser.
        
        ✅ SECURITY: Uses select_for_update() to prevent TOCTOU race conditions
        IMPORTANT: Must be called within transaction.atomic() block
        """
        client = user.client_account
        # Check if this is the last active superuser
        if user.is_superuser and user.is_active:
            # ✅ VERROU: Count other active superusers with pessimistic lock
            other_active_superusers = list(
                client.users.select_for_update().filter(
                    is_superuser=True,
                    is_active=True
                ).exclude(id=user.id).values_list('id', flat=True)
            )
            return len(other_active_superusers) == 0
        return False
        
    def get_role_permissions(self, obj):
        """Permissions du rôle utilisateur"""
        if obj.role:
            return {
                'read': obj.role.read,
                'write': obj.role.write,
                'modify': obj.role.modify,
                'delete': obj.role.can_delete
            }
        return {}
    
    def get_is_manager(self, obj):
        """Vérifier si l'utilisateur est manager"""
        return obj.is_manager()

    def get_role_tier(self, obj):
        """Tier du rôle ('admin' | 'manager' | 'individual' | None) — réutilise
        UserRole.get_tier(), source unique du tier (parité liste / detail)."""
        return obj.role.get_tier() if obj.role else None
    
    def get_managed_users_count(self, obj):
        """
        Nombre d'utilisateurs managés
        
        ✅ OPTIMIZATION: Uses annotation if available to avoid N+1 queries
        The queryset in UserViewSet.list() should include this annotation:
            .annotate(managed_users_count=Count('managed_teams__members', distinct=True))
        """
        # Try to use pre-computed annotation first (if available from queryset)
        if hasattr(obj, 'managed_users_count_annotated'):
            return obj.managed_users_count_annotated
        
        # Fallback to method call (less efficient but functional)
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
        """
        Validate that team assignment is compatible with manager status.

        Business Rule:
        - If user is manager of team(s), user.team must be:
            * null (no team assigned), OR
            * one of the teams they manage

        This prevents conflicts like:
        - User manages Team A but is assigned to Team B as member

        Args:
            value: Team instance or None

        Returns:
            Team instance or None if valid

        Raises:
            StandardizedValidationError: If team assignment conflicts with managed teams
        """
        if not value:
            # null team is always valid
            return value

        # Get the user instance (for updates) or user_id from context (for creates)
        user_instance = self.instance
        if not user_instance:
            # For creates, we can't check managed teams yet (user doesn't exist)
            # The signal will handle assignment after creation
            return value

        # Check if user is manager of any teams
        from ..models import Team

        managed_teams = Team.objects.filter(
            manager=user_instance,
            client_account=user_instance.client_account
        ).values_list('id', flat=True)

        if managed_teams.exists():
            # User is a manager - validate team assignment
            if value.id not in managed_teams:
                # User is trying to assign to a team they don't manage
                managed_team_names = Team.objects.filter(
                    id__in=managed_teams
                ).values_list('name', flat=True)

                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail=f"User is manager of team(s): {', '.join(managed_team_names)}. "
                                f"Cannot assign to team '{value.name}'. "
                                f"Managers must be assigned to a team they manage, or have no team assignment."
                    )
                )

        # Validate team belongs to same client (existing validation)
        client_id = self._get_client_id_from_context()
        if str(value.client_account_id) != str(client_id):
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
    
    # def validate_is_superuser(self, value):
    #     """
    #     Validate that only Admin or SuperUser can grant/revoke superuser status
    #     This is a double-check in addition to view-level validation
    #     """
    #     request = self.context.get('request')
        
    #     # Si pas de request dans le contexte (cas rare), on laisse passer
    #     # La validation sera faite au niveau de la vue
    #     if not request or not hasattr(request, 'user'):
    #         return value
        
    #     current_user = request.user
        
    #     # Récupérer l'instance si c'est une mise à jour
    #     is_update = self.instance is not None
        
    #     # Si on essaie de définir/modifier is_superuser
    #     if is_update:
    #         # Check si la valeur change réellement
    #         if self.instance.is_superuser == value:
    #             # Pas de changement, on laisse passer
    #             return value
        
    #     # Vérifier les permissions pour changer is_superuser
    #     can_grant = False
        
    #     # SuperUsers peuvent accorder le statut superuser
    #     if current_user.is_superuser:
    #         can_grant = True
    #     # Users avec rôle Admin peuvent accorder le statut superuser  
    #     elif current_user.role and current_user.role.name == 'Admin':
    #         can_grant = True
            
    #     if not can_grant:
    #         raise StandardizedValidationError(
    #             "Only administrators and superusers can grant or revoke superuser status"
    #         )
        
    #     # Si on retire le statut superuser, vérifier que ce n'est pas le dernier
    #     if is_update and self.instance.is_superuser and value is False:
    #         # IMPORTANT: Utiliser le client_id du contexte pour garantir le multi-tenant
    #         client_id = self._get_client_id_from_context()
            
    #         other_superusers = User.objects.filter(
    #             client_account_id=client_id,
    #             is_superuser=True
    #         ).exclude(id=self.instance.id).count()
            
    #         if other_superusers == 0:
    #             raise StandardizedValidationError(
    #                 "Cannot remove superuser status from the last superuser. "
    #                 "Promote another user to superuser first."
    #             )
        
    #     return value
    
    def validate_is_staff(self, value):
        """
        Validate is_staff field - should be True if is_superuser is True
        """
        # Si is_superuser est dans les données validées et est True
        # alors is_staff doit aussi être True
        is_superuser = self.initial_data.get('is_superuser')
        
        if is_superuser is True and value is False:
            raise StandardizedValidationError(
                "Superusers must have staff access (is_staff=True)"
            )
        
        return value
    
    def validate(self, data):
        """
        Validation multi-champs complexe
        UPDATED: Add superuser validations while keeping ALL existing validations
        """
        try:
            # === VALIDATION EXISTANTE (NE PAS SUPPRIMER) ===
            # Appeler d'abord la validation parent
            data = super().validate(data)
            
            client_account_id = self._get_client_id_from_context()
            
            # Unicité de l'email (création uniquement)
            if not self.instance:
                email = data.get('email')
                if email and User.objects.filter(email=email).exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields="email")

                    )
                
                if not data.get('role'):
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field='role')
                    )
                            
            # Cohérence team/client
            team = data.get('team') or (self.instance.team if self.instance else None)
            organization = data.get('organization') or (self.instance.organization if self.instance else None)
            
            if team and str(team.client_account_id) != str(client_account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
            
            if organization and str(organization.client_account_id) != str(client_account_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
            
            # === NOUVELLES VALIDATIONS SUPERUSER ===
            # Si on définit is_superuser=True, forcer is_staff=True
            if data.get('is_superuser') is True:
                data['is_staff'] = True
            
            # Si c'est une mise à jour
            if self.instance and client_account_id:
                # Vérifier qu'on ne désactive pas le dernier admin/superuser actif
                is_deactivating = data.get('is_active') is False and self.instance.is_active
                
                if is_deactivating:
                    # Si c'est un superuser, vérifier qu'il n'est pas le dernier actif
                    if self.instance.is_superuser:
                        other_active_superusers = User.objects.filter(
                            client_account_id=client_account_id,
                            is_superuser=True,
                            is_active=True
                        ).exclude(id=self.instance.id).count()
                        
                        if other_active_superusers == 0:
                            raise StandardizedValidationError(
                                "Cannot deactivate the last active superuser. "
                                "Ensure another active superuser exists first."
                            )
                    
                    # Si c'est un admin (par rôle), vérifier qu'il reste un admin ou superuser actif
                    elif self.instance.role and self.instance.role.name == 'Admin':
                        from django.db.models import Q
                        other_active_admins = User.objects.filter(
                            client_account_id=client_account_id,
                            is_active=True
                        ).filter(
                            Q(role__name='Admin') | Q(is_superuser=True)
                        ).exclude(id=self.instance.id).count()
                        
                        if other_active_admins == 0:
                            raise StandardizedValidationError(
                                "Cannot deactivate the last active administrator. "
                                "Ensure another active admin or superuser exists first."
                            )
            
            # === VALIDATION CRÉATION PREMIER USER (compatible superuser) ===
            if not self.instance and client_account_id:  # Création
                try:
                    # Compter les users existants pour ce client
                    existing_users = User.objects.filter(
                        client_account_id=client_account_id
                    ).count()
                    
                    # Si c'est le premier user ET qu'on essaie de le créer sans superuser
                    if existing_users == 0 and not data.get('is_superuser'):
                        # Log warning but allow creation
                        client = ClientAccount.objects.get(id=client_account_id)
                        print(f"[WARNING] Creating first user for client {client.name} without superuser status")
                except ClientAccount.DoesNotExist:
                    pass
            
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
        """
        UPDATED: Handle superuser validation instead of admin role validation
        
        ✅ SECURITY: All validations use select_for_update() to prevent TOCTOU
        Transaction is handled by the calling view (ViewSet.update/partial_update)
        """
        from django.db import transaction
        
        # ✅ Ensure we're in a transaction (defensive check)
        if not transaction.get_connection().in_atomic_block:
            raise StandardizedValidationError(
                "Serializer update must be called within transaction.atomic() block"
            )
        
        client = instance.client_account

        # === RÈGLE DERNIER SUPERUSER ===
        is_last_superuser = self._is_last_admin(instance)
        is_last_active_superuser = self._is_last_active_admin(instance)

        # Tentative de retrait du statut superuser ?
        if 'is_superuser' in validated_data:
            new_is_superuser = validated_data.get('is_superuser')
            if is_last_superuser and new_is_superuser is False:
                # Interdit de retirer is_superuser au dernier superuser
                raise StandardizedValidationError(
                    "Cannot remove superuser status from the last superuser. "
                    "Promote another user to superuser first."
                )

        # Tentative de désactivation ?
        if 'is_active' in validated_data:
            new_active = validated_data.get('is_active')
            if is_last_active_superuser and new_active is False:
                # Interdit de désactiver le dernier superuser actif (évite lock-out)
                raise StandardizedValidationError(
                    "Cannot deactivate the last active superuser. "
                    "Promote another user to superuser first."
                )

        # === RÈGLE SEATS À L'ACTIVATION ===
        if 'is_active' in validated_data and validated_data['is_active'] is True:
            # Si on était inactif et qu'on veut devenir actif : vérifier places
            if not instance.is_active:
                if not client.has_available_seat():
                    raise StandardizedValidationError(CoreErrorMessages.SEAT_LIMIT_REACHED)

        # === RÈGLE CHANGEMENT DE RÔLE (gardée pour compatibilité) ===
        # On garde la logique des rôles car certains users peuvent avoir des rôles sans être superuser
        admin_role = self._get_admin_role(client)
        if 'role' in validated_data:
            new_role = validated_data.get('role')
            # Si c'est le dernier avec le rôle Admin ET qu'il est superuser, on permet le changement
            # car superuser a tous les droits anyway
            old_is_admin_role = (instance.role and instance.role.name == admin_role.name)
            new_is_admin_role = (new_role and new_role.name == admin_role.name)
            
            # Seulement bloquer si on retire le rôle admin à quelqu'un qui n'est PAS superuser
            # et qui est le dernier admin
            if old_is_admin_role and not new_is_admin_role and not instance.is_superuser:
                from django.db.models import Q
                other_admins = list(
                    client.users.filter(
                        Q(role__name=admin_role.name) | Q(is_superuser=True)
                    ).exclude(id=instance.id).values_list('id', flat=True)
                )
                
                if len(other_admins) == 1:
                    raise StandardizedValidationError(CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED)

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

        # Si on modifie is_superuser, gérer is_staff aussi
        if 'is_superuser' in validated_data:
            if validated_data['is_superuser']:
                instance.is_staff = True  # Superuser devrait avoir accès staff

        instance.save()

        # Filet: garantir la présence d'un superuser si besoin
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
                CoreErrorMessages.REQUIRED_FIELD.format(field='Password'),
                CoreErrorMessages.REQUIRED_FIELD.format(field='Password confirmation')
            })
        
        # Vérification d'égalité
        if password != password_confirm:
            raise serializers.ValidationError({
                'Passwords do not match'
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