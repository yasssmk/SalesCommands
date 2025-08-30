# backend/end_users/serializers/role_serializers.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from ..models.user_model import UserRole


class RoleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer principal pour UserRole avec format canonique de sortie.
    
    Sortie API : name, read, create, update, delete (mapping write→create, modify→update)
    Entrée API : Accepte les synonymes write/modify et les mappe automatiquement
    """
    
    # Champs calculés pour sortie canonique
    create = serializers.BooleanField(source='write', read_only=True)
    update = serializers.BooleanField(source='modify', read_only=True)
    
    # Relation client_account
    client_account_name = serializers.CharField(source='client_account.name', read_only=True)
    
    # Métadonnées utiles
    users_count = serializers.SerializerMethodField(read_only=True)
    permissions_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'name', 
            # Format canonique en sortie
            'read', 'create', 'update', 'delete',
            # Métadonnées
            'client_account', 'client_account_name',
            'users_count', 'permissions_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'create', 'update',  # create/update sont dérivés en read-only
            'client_account_name', 'users_count', 'permissions_summary',
            'created_at', 'updated_at'
        ]
    
    def get_users_count(self, obj):
        """Nombre d'utilisateurs actifs avec ce rôle"""
        return obj.users.filter(is_active=True).count()
    
    def get_permissions_summary(self, obj):
        """Résumé textuel des permissions pour UI"""
        permissions = []
        if obj.read:
            permissions.append('read')
        if obj.write:  # Stockage interne "write"
            permissions.append('create')
        if obj.modify:  # Stockage interne "modify"
            permissions.append('update')
        if obj.delete:
            permissions.append('delete')
        
        return ', '.join(permissions) if permissions else 'none'
    
    def validate_name(self, value):
        """Validation unicité du nom par client"""
        # Récupérer client_id du contexte (ClientScopeManager)
        client_id = self.get_client_id()
        if not client_id:
            raise serializers.ValidationError(
                CoreErrorMessages.CLIENT_ID_REQUIRED
            )
        
        # Vérifier unicité (exclure instance actuelle si update)
        queryset = UserRole.objects.filter(
            client_account_id=client_id,
            name__iexact=value  # Case-insensitive
        )
        
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
            
        if queryset.exists():
            raise serializers.ValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(fields="role name")
            )
        
        return value
    
    def to_representation(self, instance):
        """Personnaliser la sortie pour format canonique"""
        data = super().to_representation(instance)
        
        # Assurer format canonique en sortie
        data['create'] = instance.write
        data['update'] = instance.modify
        
        return data


class RoleUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer spécialisé pour PATCH - permissions uniquement avec mapping synonymes.
    
    Accepte en entrée :
    - Format canonique : read, create, update, delete
    - Synonymes : write→create, modify→update
    
    Contrainte : Seules les permissions peuvent être modifiées via PATCH
    """
    
    # Champs synonymes acceptés en entrée (write_only)
    write = serializers.BooleanField(write_only=True, required=False,
                                   help_text="Synonym for 'create'. Will be mapped automatically.")
    modify = serializers.BooleanField(write_only=True, required=False,
                                    help_text="Synonym for 'update'. Will be mapped automatically.")
    
    # Format canonique accepté aussi
    create = serializers.BooleanField(write_only=True, required=False,
                                    help_text="Create permission (mapped to internal 'write' field)")
    update = serializers.BooleanField(write_only=True, required=False,
                                    help_text="Update permission (mapped to internal 'modify' field)")
    
    class Meta:
        model = UserRole
        fields = [
            # Permissions modifiables
            'read', 'delete',
            # Synonymes acceptés
            'write', 'modify',
            # Format canonique accepté  
            'create', 'update'
        ]
        
        # Tous les champs sont optionnels en PATCH
        extra_kwargs = {
            'read': {'required': False},
            'delete': {'required': False},
        }
    
    def validate(self, attrs):
        """
        Validation et mapping des synonymes vers champs internes.
        
        Priorité : format canonique (create/update) > synonymes (write/modify)
        """
        # Mapping write → create (internal: write field)
        if 'create' in attrs and 'write' in attrs:
            raise serializers.ValidationError({
                'permissions': [CoreErrorMessages.INVALID_DATA.format(
                    detail='Cannot specify both "create" and "write". Use "create" (recommended).'
                )]
            })
        
        if 'create' in attrs:
            attrs['write'] = attrs.pop('create')
        elif 'write' in attrs:
            attrs['write'] = attrs.pop('write')
        
        # Mapping update → modify (internal: modify field)
        if 'update' in attrs and 'modify' in attrs:
            raise serializers.ValidationError({
                'permissions': [CoreErrorMessages.INVALID_DATA.format(
                    detail='Cannot specify both "update" and "modify". Use "update" (recommended).'
                )]
            })
        
        if 'update' in attrs:
            attrs['modify'] = attrs.pop('update')
        elif 'modify' in attrs:
            attrs['modify'] = attrs.pop('modify')
        
        return attrs
    
    def to_representation(self, instance):
        """Retourner format canonique même après PATCH"""
        return {
            'id': str(instance.id),
            'name': instance.name,
            'read': instance.read,
            'create': instance.write,  # Mapping sortie
            'update': instance.modify,  # Mapping sortie
            'delete': instance.delete,
            'updated_at': instance.updated_at
        }


class RoleListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer optimisé pour les listes - moins de champs pour performance
    """
    
    # Format canonique en sortie
    create = serializers.BooleanField(source='write', read_only=True)
    update = serializers.BooleanField(source='modify', read_only=True)
    
    users_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'name', 
            'read', 'create', 'update', 'delete',
            'users_count'
        ]
    
    def get_users_count(self, obj):
        """Optimisé avec prefetch_related depuis ViewSet"""
        # Si prefetch_related configuré correctement dans ViewSet, 
        # cette annotation devrait être disponible
        if hasattr(obj, '_prefetched_objects_cache') and 'users' in obj._prefetched_objects_cache:
            return len([u for u in obj.users.all() if u.is_active])
        
        # Fallback standard
        return obj.users.filter(is_active=True).count()


class RolePermissionsMatrixSerializer(serializers.Serializer):
    """
    Serializer pour l'action permissions_matrix - format spécifique UI
    """
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    permissions = serializers.DictField(child=serializers.BooleanField())
    users_count = serializers.IntegerField()
    
    def to_representation(self, instance):
        """Format optimisé pour matrice UI"""
        return {
            'id': str(instance.id),
            'name': instance.name,
            'permissions': {
                'read': instance.read,
                'create': instance.write,  # Mapping canonique
                'update': instance.modify,  # Mapping canonique
                'delete': instance.delete
            },
            'users_count': instance.users.filter(is_active=True).count()
        }