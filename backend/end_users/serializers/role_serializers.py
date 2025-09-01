# backend/end_users/serializers/role_serializers.py

from rest_framework import serializers
from django.db import models
from django.db.models import Count, Q, Prefetch
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied
from core.error_messages import CoreErrorMessages
from ..models.user_model import UserRole, User


class RoleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer principal pour UserRole avec validation complète et client scoping.
    
    Gère le mapping intelligent des permissions:
    - Stockage DB: write, modify
    - API Input: accepte write/create et modify/update via to_internal_value
    - API Output: format canonique avec create, update via to_representation
    
    Note: Le modèle UserRole a un champ 'delete' (BooleanField) qui peut
    entrer en conflit avec la méthode delete() de Django Model. Utilisez
    toujours QuerySet.delete() pour supprimer des instances.
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
            'read', 'write', 'modify', 'delete',
            #tier
            'is_admin', 'is_manager', 'is_individual',
            'tier',
            # Métadonnées
            'client_account', 'client_account_name',
            'users_count', 'active_users_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'client_account', 'client_account_name',
            'users_count', 'active_users_count','tier',
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
        return 'unknown' 
    
    def get_users_count(self, obj):
        """Nombre total d'utilisateurs avec ce rôle"""
        # Optimisé si prefetch_related est utilisé dans la vue
        if hasattr(obj, '_prefetched_users_count'):
            return obj._prefetched_users_count
        return obj.users.count()
    
    def get_active_users_count(self, obj):
        """Nombre d'utilisateurs actifs avec ce rôle"""
        # Optimisé si annotate est utilisé dans la vue
        if hasattr(obj, 'active_users_count'):
            return obj.active_users_count
        return obj.users.filter(is_active=True).count()
    
    def to_internal_value(self, data):
        """
        Gérer les synonymes create/update avant la validation.
        """
        # Copier les données pour ne pas modifier l'original
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
        
        # Appeler la méthode parent avec les données mappées
        return super().to_internal_value(internal_data)
    
    def validate_name(self, value):
        """
        Validation de l'unicité du nom par client.
        Le nom doit être unique dans le contexte du client.
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
        Validation globale.
        """
        try:
            # Récupérer le client_id pour l'injection
            client_id = self._get_client_id_from_context()
            
            # === Validation des permissions logiques ===
            # Si on peut delete, on devrait pouvoir modify
            if attrs.get('delete', False) and not attrs.get('modify', False):
                if not self.partial:  # Seulement en création complète
                    attrs['modify'] = True  # Auto-enable modify si delete est activé
            
            # Si on peut modify ou write, on devrait pouvoir read
            if (attrs.get('modify', False) or attrs.get('write', False)) and not attrs.get('read', True):
                attrs['read'] = True  # Auto-enable read
            
            # Injecter le client_id pour la création
            if not self.instance:
                attrs['client_account_id'] = client_id
            
            rtier_count = sum([
                attrs.get('is_admin', False),
                attrs.get('is_manager', False), 
                attrs.get('is_individual', False)
            ])
            
            if self.instance:
                # Pour update, prendre en compte les valeurs existantes
                tier_count = sum([
                    attrs.get('is_admin', self.instance.is_admin),
                    attrs.get('is_manager', self.instance.is_manager),
                    attrs.get('is_individual', self.instance.is_individual)
                ])
            
            if tier_count == 0:
                # Auto-détection depuis le nom si aucun tier défini
                name = attrs.get('name', self.instance.name if self.instance else '')
                if name:
                    name_lower = name.lower()
                    if 'admin' in name_lower:
                        attrs['is_admin'] = True
                        attrs['is_manager'] = False
                        attrs['is_individual'] = False
                    elif any(w in name_lower for w in ['manager', 'supervisor', 'lead']):
                        attrs['is_admin'] = False
                        attrs['is_manager'] = True
                        attrs['is_individual'] = False
                    else:
                        attrs['is_admin'] = False
                        attrs['is_manager'] = False
                        attrs['is_individual'] = True
                else:
                    # Par défaut : individual
                    attrs['is_admin'] = False
                    attrs['is_manager'] = False
                    attrs['is_individual'] = True
            elif tier_count > 1:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Exactly one tier (is_admin, is_manager, is_individual) must be active"
                    )
                )
            
            return super().validate(attrs)
            
        except StandardizedValidationError:
            # Re-raise nos erreurs standardisées
            raise
        except Exception as e:
            # Attraper et convertir les autres erreurs
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """
        Création avec injection automatique du client_id.
        """
        # Le client_id est déjà injecté dans validate()
        instance = super().create(validated_data)
        
        # Log pour audit
        user = self.context.get('request').user if self.context.get('request') else None
        if user:
            user_email = user.email if hasattr(user, 'email') else str(user)
            print(f"[AUDIT] Role '{instance.name}' created by {user_email} for client {instance.client_account_id}")
        
        return instance
    
    def update(self, instance, validated_data):
        """
        Mise à jour avec validation des contraintes métier.
        """
        # Protection du rôle Admin contre modifications dangereuses
        if instance.name == 'Admin':
            # Ne pas permettre de désactiver des permissions critiques
            if not validated_data.get('read', instance.read):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if not validated_data.get('write', instance.write):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write permission for Admin role"
                )
        
        # Mise à jour standard
        instance = super().update(instance, validated_data)
        
        # Log pour audit
        user = self.context.get('request').user if self.context.get('request') else None
        if user:
            user_email = user.email if hasattr(user, 'email') else str(user)
            print(f"[AUDIT] Role '{instance.name}' updated by {user_email}")
        
        return instance
    
    def to_representation(self, instance):
        """
        Format de sortie uniforme avec le format canonique.
        """
        data = super().to_representation(instance)
        
        # Ajouter les champs canoniques en sortie
        data['create'] = instance.write
        data['update'] = instance.modify
        
        return data


class RoleCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer spécialisé pour la création de rôles.
    Accepte les synonymes create/update en plus de write/modify.
    """
    
    class Meta:
        model = UserRole
        fields = [
            'name',
            'read', 'write', 'modify', 'delete',
        ]
        extra_kwargs = {
            'name': {'required': True},
            'read': {'required': False, 'default': True},
            'write': {'required': False, 'default': False},
            'modify': {'required': False, 'default': False},
            'delete': {'required': False, 'default': False},
            'is_admin': {'required': False, 'default': False},
            'is_manager': {'required': False, 'default': False},
            'is_individual': {'required': False, 'default': True}
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
        Validation pour la création.
        """
        try:
            # Récupérer le client_id
            client_id = self._get_client_id_from_context()
            attrs['client_account_id'] = client_id
            
            # Valeurs par défaut
            attrs.setdefault('read', True)
            attrs.setdefault('write', False)
            attrs.setdefault('modify', False)
            attrs.setdefault('delete', False)
            
            # Validation cohérence permissions
            if attrs['delete'] and not attrs['modify']:
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
            
            if not any([attrs.get('is_admin'), attrs.get('is_manager'), attrs.get('is_individual')]):
                name = attrs.get('name', '').lower()
                if 'admin' in name:
                    attrs['is_admin'] = True
                    attrs['is_manager'] = False
                    attrs['is_individual'] = False
                elif any(w in name for w in ['manager', 'supervisor', 'lead']):
                    attrs['is_admin'] = False
                    attrs['is_manager'] = True
                    attrs['is_individual'] = False
                else:
                    attrs['is_admin'] = False
                    attrs['is_manager'] = False
                    attrs['is_individual'] = True
            else:
                # Vérifier qu'exactement un tier est actif
                tier_count = sum([attrs.get('is_admin', False), 
                                 attrs.get('is_manager', False),
                                 attrs.get('is_individual', False)])
                if tier_count != 1:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_DATA.format(
                            detail="Exactly one tier must be active"
                        )
                    )
            
            return attrs
            
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
        return data


class RoleUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour PATCH - modification des permissions uniquement.
    Le nom ne peut pas être modifié via PATCH.
    """
    
    class Meta:
        model = UserRole
        fields = [
            # Permissions modifiables (champs réels du modèle)
            'read', 'write', 'modify', 'delete',
        ]
        extra_kwargs = {
            'read': {'required': False},
            'write': {'required': False},
            'modify': {'required': False},
            'delete': {'required': False},
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
        """Validation de cohérence des permissions pour PATCH"""
        try:
            instance = self.instance
            
            # Si delete est activé, modify devrait l'être aussi
            current_delete = attrs.get('delete', instance.delete if instance else False)
            current_modify = attrs.get('modify', instance.modify if instance else False)
            
            if current_delete and not current_modify:
                attrs['modify'] = True
            
            # Si modify ou write sont activés, read devrait l'être
            current_write = attrs.get('write', instance.write if instance else False)
            current_modify = attrs.get('modify', instance.modify if instance else False)
            current_read = attrs.get('read', instance.read if instance else True)
            
            if (current_write or current_modify) and not current_read:
                attrs['read'] = True
            
            is_admin = attrs.get('is_admin', instance.is_admin if instance else False)
            is_manager = attrs.get('is_manager', instance.is_manager if instance else False)
            is_individual = attrs.get('is_individual', instance.is_individual if instance else False)
            
            # Vérifier qu'exactement un tier reste actif
            tier_count = sum([is_admin, is_manager, is_individual])
            
            if tier_count == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="At least one tier must be active"
                    )
                )
            elif tier_count > 1:
                # Si plusieurs sont activés, garder le plus élevé
                if is_admin:
                    attrs['is_admin'] = True
                    attrs['is_manager'] = False
                    attrs['is_individual'] = False
                elif is_manager:
                    attrs['is_admin'] = False
                    attrs['is_manager'] = True
                    attrs['is_individual'] = False
                else:
                    attrs['is_admin'] = False
                    attrs['is_manager'] = False
                    attrs['is_individual'] = True
            
            return super().validate(attrs)
            
            
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
            'delete': instance.delete,
            # Tier
            'is_admin': instance.is_admin,
            'is_manager': instance.is_manager,
            'is_individual': instance.is_individual,
            'tier': instance.get_tier(), 
            # Ajout des champs canoniques
            'create': instance.write,
            'update': instance.modify,
            'users_count': instance.users.filter(is_active=True).count(),
            'updated_at': instance.updated_at.isoformat()
        }


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
            'read', 'write', 'modify', 'delete',
            'is_admin', 'is_manager', 'is_individual',
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
        return 'unknown'
    
    def to_representation(self, instance):
        """Ajouter les champs canoniques en sortie"""
        data = super().to_representation(instance)
        # Format canonique
        data['create'] = instance.write
        data['update'] = instance.modify
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