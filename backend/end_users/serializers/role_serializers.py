# backend/end_users/serializers/role_serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.logging import get_logger, ctx_from_request
from ..models import UserRole


def _has_other_admin_roles(role: UserRole) -> bool:
    """Return True when another admin-tier role exists for the same client."""
    if role is None:
        return False

    return UserRole.objects.filter(
        client_account_id=role.client_account_id,
        is_admin=True,
    ).exclude(pk=role.pk).exists()

logger = get_logger(__name__)

class RoleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer principal pour UserRole avec validation complète et client scoping.
    
    Gère le mapping intelligent des permissions:
    - Stockage DB: write, modify
    - API Input: accepte write/create et modify/update via to_internal_value
    - API Output: format canonique avec create, update via to_representation
    """
    
    # === Champs calculés en lecture seule ===
    client_account_name = serializers.CharField(
        source='client_account.name', 
        read_only=True
    )
    
    users_count = serializers.SerializerMethodField(read_only=True)
    active_users_count = serializers.SerializerMethodField(read_only=True)
    tier = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'name',
            # Permissions réelles du modèle
            'read', 'write', 'modify', 'can_delete',
            # Champs de tier - IMPORTANT : doivent être dans fields
            'is_admin', 'is_manager', 'is_individual',
            'tier',
            # Métadonnées
            'client_id','client_account', 'client_account_name',
            'users_count', 'active_users_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'client_account', 'client_id', 'client_account_name',
            'users_count', 'active_users_count', 'tier',
            'created_at', 'updated_at'
        ]
    
    def get_tier(self, obj):
        """Retourne le tier actif sous forme de string"""
        if obj.is_admin:
            return 'admin'
        elif obj.is_manager:
            return 'manager'
        elif obj.is_individual:
            return 'individual'
        return 'individual'
    
    def get_client_account(self, obj):
        return self.client_id
    
    def get_users_count(self, obj):
        """Nombre total d'utilisateurs avec ce rôle"""
        if hasattr(obj, 'users_count'):
            return obj.users_count
        if hasattr(obj, '_prefetched_users_count'):
            return obj._prefetched_users_count
        return obj.users.count()
    
    def get_active_users_count(self, obj):
        """Nombre d'utilisateurs actifs avec ce rôle"""
        if hasattr(obj, 'active_users_count'):
            return obj.active_users_count
        if hasattr(obj, 'prefetched_active_users'):
            return len(obj.prefetched_active_users)
        return obj.users.filter(is_active=True).count()
    
    def to_internal_value(self, data):
        """
        Gérer les synonymes create/update avant la validation.
        """
        internal_data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Mapping des synonymes (si présents)
        if 'create' in internal_data:
            if 'write' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'create' and 'write'. Use one or the other."
                })
            internal_data['write'] = internal_data.pop('create')
        
        if 'update' in internal_data:
            if 'modify' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'update' and 'modify'. Use one or the other."
                })
            internal_data['modify'] = internal_data.pop('update')
        
        return super().to_internal_value(internal_data)
    
    def validate_name(self, value):
        """
        Validation de l'unicité du nom par client.
        """
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Role name")
            )
        
        # Normaliser le nom (trim et capitalisation)
        value = value.strip()
        
        # Récupérer le client_id depuis le contexte
        client_id = self._get_client_id_from_context()
        
        # Vérifier l'unicité (case-insensitive)
        queryset = UserRole.objects.filter(
            client_account_id=client_id,
            name__iexact=value
        )
        
        # Exclure l'instance actuelle en cas d'update
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise StandardizedValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields=f"role name '{value}' for this client"
                )
            )
        
        return value
    
    def validate(self, attrs):
        """
        Validation globale avec validation STRICTE des tiers.
        """
        try:
            # Récupérer le client_id pour l'injection
            client_id = self._get_client_id_from_context()
            
            # === VALIDATION STRICTE DES TIERS ===
            # Pour CREATE (pas d'instance)
            if not self.instance:
                attrs['client_account_id'] = client_id
                
                # Récupérer les valeurs des tiers
                is_admin = attrs.get('is_admin', False)
                is_manager = attrs.get('is_manager', False)
                is_individual = attrs.get('is_individual', False)
                
                tier_count = sum([is_admin, is_manager, is_individual])
                
                # Si plusieurs tiers sont activés = ERREUR
                if tier_count > 1:
                    active_tiers = []
                    if is_admin:
                        active_tiers.append('is_admin')
                    if is_manager:
                        active_tiers.append('is_manager')
                    if is_individual:
                        active_tiers.append('is_individual')
                    
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail=f"Only one tier can be active. You specified: {', '.join(active_tiers)}. "
                                   f"Please set exactly one of is_admin, is_manager, or is_individual to true."
                        )
                    )
                
                # Si aucun tier n'est défini
                if tier_count == 0:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_DATA.format(
                                detail="At least one tier must be active. "
                                       "Please set one of is_admin, is_manager, or is_individual to true."
                            )
                        )
                    
            
            # Pour UPDATE (instance existe)
            else:
                tier_fields_in_request = []
                for field in ['is_admin', 'is_manager', 'is_individual']:
                    if field in attrs:
                        tier_fields_in_request.append(field)
                        
                if tier_fields_in_request:
                    # Calculer l'état final
                    final_is_admin = attrs.get('is_admin', self.instance.is_admin)
                    final_is_manager = attrs.get('is_manager', self.instance.is_manager)
                    final_is_individual = attrs.get('is_individual', self.instance.is_individual)
                    
                    final_tier_count = sum([final_is_admin, final_is_manager, final_is_individual])
                    
                    if final_tier_count == 0:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_DATA.format(
                                detail="At least one tier must remain active."
                            )
                        )
                    elif final_tier_count > 1:
                        active_tiers = []
                        if final_is_admin:
                            active_tiers.append('is_admin')
                        if final_is_manager:
                            active_tiers.append('is_manager')
                        if final_is_individual:
                            active_tiers.append('is_individual')
                        
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_DATA.format(
                                detail=f"Only one tier can be active. "
                                    f"These would be active after update: {', '.join(active_tiers)}"
                            )
                        )
                
                if (self.instance.is_admin or self.instance.name == 'Admin') and not _has_other_admin_roles(self.instance):
                    raise StandardizedValidationError(
                        CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot modify the last admin role"
                    )
            
            # === Validation des permissions logiques ===
            # Si on peut delete, on devrait pouvoir modify
            if attrs.get('can_delete', False) and not attrs.get('modify', False):
                attrs['modify'] = True
            
            # Si on peut modify ou write, on devrait pouvoir read
            if (attrs.get('modify', False) or attrs.get('write', False)) and not attrs.get('read', True):
                attrs['read'] = True
            
            return super().validate(attrs)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """
        Création avec injection automatique du client_id.
        """
        instance = super().create(validated_data)
        
        request = self.context.get('request') if self.context else None
        if request and getattr(request, 'user', None):
            ctx = ctx_from_request(request)
            ctx.update({
                'event': 'role_serializer_create',
                'role_id': str(instance.id),
                'role_name': instance.name,
                'tier': instance.get_tier() if hasattr(instance, 'get_tier') else 'unknown',
                'client_id': str(getattr(instance, 'client_account_id', '-')),
            })
            logger.info('role_serializer_create', extra=ctx)

        return instance
    
    def update(self, instance, validated_data):
        """
        Mise à jour avec validation des contraintes métier.
        """
        # Protection du rôle Admin contre modifications dangereuses
        if instance.name == 'Admin':
            if not validated_data.get('read', instance.read):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if not validated_data.get('write', instance.write):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write permission for Admin role"
                )
        
        if (instance.is_admin or instance.name == 'Admin') and not _has_other_admin_roles(instance):
            raise StandardizedValidationError(
                CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot modify the last admin role"
            )
        
        instance = super().update(instance, validated_data)
        
        request = self.context.get('request') if self.context else None
        if request and getattr(request, 'user', None):
            ctx = ctx_from_request(request)
            ctx.update({
                'event': 'role_serializer_update',
                'role_id': str(instance.id),
                'role_name': instance.name,
                'fields_updated': sorted(validated_data.keys()),
            })
            logger.info('role_serializer_update', extra=ctx)
        
        return instance
    
    def to_representation(self, instance):
        """
        Format de sortie uniforme avec le format canonique.
        """
        data = super().to_representation(instance)
        
        # Ajouter les champs canoniques en sortie
        data['create'] = instance.write
        data['update'] = instance.modify
        data['delete'] = instance.can_delete 
        
        return data


class RoleCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer spécialisé pour la création de rôles.
    Validation STRICTE des tiers - exactement UN doit être true.
    """
    
    class Meta:
        model = UserRole
        fields = [
            'name',
            'read', 'write', 'modify', 'can_delete',
            # IMPORTANT: Inclure les champs de tier dans fields
            'is_admin', 'is_manager', 'is_individual'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'read': {'required': False, 'default': True},
            'write': {'required': False, 'default': False},
            'modify': {'required': False, 'default': False},
            'can_delete': {'required': False, 'default': False},
            # PAS de default pour les tiers - on gère ça dans validate()
            'is_admin': {'required': False},
            'is_manager': {'required': False},
            'is_individual': {'required': False}
        }
    
    def to_internal_value(self, data):
        """
        Gérer les synonymes create/update avant la validation.
        Cette méthode est appelée avant validate().
        """
        # Copier les données pour ne pas modifier l'original
        internal_data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Mapping des synonymes
        if 'create' in internal_data:
            if 'write' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'create' and 'write'. Use one or the other."
                })
            internal_data['write'] = internal_data.pop('create')
        
        if 'update' in internal_data:
            if 'modify' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'update' and 'modify'. Use one or the other."
                })
            internal_data['modify'] = internal_data.pop('update')
        
        # Appeler la méthode parent avec les données mappées
        return super().to_internal_value(internal_data)
        
    def validate(self, attrs):
        """
        Validation STRICTE pour la création de rôle.
        - Exactement UN tier doit être défini
        - Pas d'auto-détection basée sur le nom
        """
        try:
            # Récupérer le client_id
            client_id = self._get_client_id_from_context()
            attrs['client_account_id'] = client_id
            
            # Valeurs par défaut pour les permissions
            attrs.setdefault('read', True)
            attrs.setdefault('write', False)
            attrs.setdefault('modify', False)
            attrs.setdefault('can_delete', False)
            
            # VALIDATION STRICTE DES TIERS - PAS DE FALLBACK
            # Récupérer les valeurs fournies ou False par défaut
            is_admin = attrs.get('is_admin', False)
            is_manager = attrs.get('is_manager', False)
            is_individual = attrs.get('is_individual', False)
            
            # Compter combien de tiers sont activés
            tier_count = sum([is_admin, is_manager, is_individual])
            
            # Validation stricte
            if tier_count == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="At least one tier must be active for role creation. "
                            "Please set one of is_admin, is_manager, or is_individual to true."
                    )
                )
            elif tier_count > 1:
                active_tiers = []
                if is_admin:
                    active_tiers.append('is_admin')
                if is_manager:
                    active_tiers.append('is_manager')
                if is_individual:
                    active_tiers.append('is_individual')
                
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail=f"Only one tier can be active. You specified: {', '.join(active_tiers)}. "
                            f"Please set exactly one of is_admin, is_manager, or is_individual to true."
                    )
                )
            
            # Log l'action
            request = self.context.get('request') if self.context else None
            if request:
                ctx = ctx_from_request(request)
                ctx.update({
                    'event': 'role_create_validate',
                    'role_name': attrs.get('name'),
                    'is_admin': bool(is_admin),
                    'is_manager': bool(is_manager),
                    'is_individual': bool(is_individual),
                })
                logger.info('role_create_validate', extra=ctx)
            
            # Validation cohérence permissions
            if attrs['can_delete'] and not attrs['modify']:
                attrs['modify'] = True
            
            if (attrs['modify'] or attrs['write']) and not attrs['read']:
                attrs['read'] = True
            
            # Validation de l'unicité du nom
            name = attrs.get('name')
            if name:
                name = name.strip()
                attrs['name'] = name  # Normaliser
                
                existing = UserRole.objects.filter(
                    client_account_id=client_id,
                    name__iexact=name
                )
                if existing.exists():
                    raise StandardizedValidationError(
                        CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                            fields=f"role name '{name}'"
                        )
                    )
            else:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='name')
                )
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def to_representation(self, instance):
        """Format de sortie avec mapping canonique"""
        data = super().to_representation(instance)
        # Ajouter les champs canoniques pour la sortie
        data['create'] = instance.write
        data['update'] = instance.modify
        data['tier'] = instance.get_tier() if hasattr(instance, 'get_tier') else None
        data['delete'] = instance.can_delete
        return data

class RoleUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour PATCH - modification des permissions et tiers.
    Validation STRICTE : un seul tier peut être actif à la fois.
    """
    
    class Meta:
        model = UserRole
        fields = [
            # Permissions modifiables
            'read', 'write', 'modify', 'can_delete',
            # Tiers modifiables
            'is_admin', 'is_manager', 'is_individual'
        ]
        extra_kwargs = {
            'read': {'required': False},
            'write': {'required': False},
            'modify': {'required': False},
            'can_delete': {'required': False},
            'is_admin': {'required': False},
            'is_manager': {'required': False},
            'is_individual': {'required': False}
        }
    
    def to_internal_value(self, data):
        """
        Gérer les synonymes create/update avant la validation.
        """
        # Copier les données pour ne pas modifier l'original
        internal_data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Mapping des synonymes
        if 'create' in internal_data:
            if 'write' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'create' and 'write'. Use one or the other."
                })
            internal_data['write'] = internal_data.pop('create')
        
        if 'update' in internal_data:
            if 'modify' in internal_data:
                raise serializers.ValidationError({
                    'permissions': "Cannot specify both 'update' and 'modify'. Use one or the other."
                })
            internal_data['modify'] = internal_data.pop('update')
        
        # Appeler la méthode parent avec les données mappées
        return super().to_internal_value(internal_data)
    
    def validate(self, attrs):
        """
        Validation de cohérence des permissions et des tiers pour PATCH.
        RÈGLES STRICTES :
        - Si des tiers sont fournis, exactement UN doit être true
        - Si aucun tier n'est fourni, on garde les valeurs existantes
        """
        try:
            instance = self.instance
            
            # === VALIDATION DES TIERS ===
            # Vérifier si des tiers sont fournis dans la requête
            tier_fields_in_request = []
            for field in ['is_admin', 'is_manager', 'is_individual']:
                if field in attrs:
                    tier_fields_in_request.append(field)
            
            # Si au moins un tier est fourni, valider
            if tier_fields_in_request:
                # Calculer l'état final après le patch
                final_is_admin = attrs.get('is_admin', instance.is_admin)
                final_is_manager = attrs.get('is_manager', instance.is_manager)
                final_is_individual = attrs.get('is_individual', instance.is_individual)
                
                # Compter les tiers actifs dans l'état final
                final_tier_count = sum([final_is_admin, final_is_manager, final_is_individual])
                
                # Validation stricte
                if final_tier_count == 0:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail="At least one tier must remain active. "
                                "You cannot disable all tiers."
                        )
                    )
                elif final_tier_count > 1:
                    active_tiers = []
                    if final_is_admin:
                        active_tiers.append('is_admin')
                    if final_is_manager:
                        active_tiers.append('is_manager')
                    if final_is_individual:
                        active_tiers.append('is_individual')
                    
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail=f"Only one tier can be active at a time. "
                                f"After this update, these would be active: {', '.join(active_tiers)}. "
                                f"Please ensure exactly one tier is true."
                        )
                    )
                
                request = self.context.get('request') if self.context else None
                if request:
                    ctx = ctx_from_request(request)
                    ctx.update({
                        'event': 'role_update_validate',
                        'role_id': str(getattr(instance, 'id', '-')),
                        'final_is_admin': bool(final_is_admin),
                        'final_is_manager': bool(final_is_manager),
                        'final_is_individual': bool(final_is_individual),
                    })
                    logger.info('role_update_validate', extra=ctx)
            
            if (instance.is_admin or instance.name == 'Admin') and not _has_other_admin_roles(instance):
                raise StandardizedValidationError(
                    CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot modify the last admin role"
                )
            
            # === VALIDATION DES PERMISSIONS ===
            # Si delete est activé, modify devrait l'être aussi
            current_delete = attrs.get('can_delete', instance.delete if instance else False)
            current_modify = attrs.get('modify', instance.modify if instance else False)
            
            if current_delete and not current_modify:
                attrs['modify'] = True
            
            # Si modify ou write sont activés, read devrait l'être
            current_write = attrs.get('write', instance.write if instance else False)
            current_modify = attrs.get('modify', instance.modify if instance else False)
            current_read = attrs.get('read', instance.read if instance else True)
            
            if (current_write or current_modify) and not current_read:
                attrs['read'] = True
            
            return super().validate(attrs)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def to_representation(self, instance):
        """Retour en format canonique après PATCH"""
        return {
            'id': str(instance.id),
            'name': instance.name,
            'read': instance.read,
            'write': instance.write,
            'modify': instance.modify,
            'can_delete': instance.can_delete, 
            'delete': instance.can_delete,
            # Tiers
            'is_admin': instance.is_admin,
            'is_manager': instance.is_manager,
            'is_individual': instance.is_individual,
            'tier': instance.get_tier() if hasattr(instance, 'get_tier') else None,
            # Ajout des champs canoniques
            'create': instance.write,
            'update': instance.modify,
            'users_count': self._get_active_users_count(instance),
            'updated_at': instance.updated_at.isoformat()
        }
    
    @staticmethod
    def _get_active_users_count(instance):
        if hasattr(instance, 'active_users_count'):
            return instance.active_users_count
        if hasattr(instance, 'prefetched_active_users'):
            return len(instance.prefetched_active_users)
        return instance.users.filter(is_active=True).count()


class RoleListSerializer(serializers.ModelSerializer):
    """
    Serializer optimisé pour les listes - moins de champs pour performance.
    """
    
    # Compteurs optimisés
    users_count = serializers.IntegerField(read_only=True)
    tier = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'name',
            'read', 'write', 'modify', 'can_delete',
            'tier', 'is_admin', 'is_manager', 'is_individual',
            'tier',
            'users_count'
        ]
    
    def get_tier(self, obj):
        """Retourne le tier actif"""
        if obj.is_admin:
            return 'admin'
        elif obj.is_manager:
            return 'manager'
        elif obj.is_individual:
            return 'individual'
        return 'individual'
    
    def to_representation(self, instance):
        """Ajouter les champs canoniques en sortie"""
        data = super().to_representation(instance)
        # Format canonique
        data['create'] = instance.write
        data['update'] = instance.modify
        data['delete'] = instance.can_delete
        return data


class RoleBulkCreateSerializer(serializers.ListSerializer):
    """
    Serializer pour création en masse de rôles.
    Utilise RoleCreateSerializer pour chaque élément.
    """
    
    def create(self, validated_data):
        """Création en masse avec transaction"""
        from django.db import transaction
        
        roles = []
        with transaction.atomic():
            for item in validated_data:
                # Créer chaque rôle individuellement
                role = UserRole.objects.create(**item)
                roles.append(role)
        
        return roles
    
    def validate(self, attrs):
        """Validation pour éviter les doublons dans le batch"""
        names = [item.get('name') for item in attrs if item.get('name')]
        
        # Vérifier les doublons dans le batch (case-insensitive)
        names_lower = [n.lower() for n in names if n]
        if len(names_lower) != len(set(names_lower)):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="Duplicate role names in batch"
                )
            )
        
        return attrs