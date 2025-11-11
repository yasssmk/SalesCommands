# backend/end_users/views/role_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Prefetch, F
from django.db import transaction
from django.utils import timezone
from core.cache_utils import (
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    invalidate_tag,
    _is_redis_backend,
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import get_logger, ctx_from_request
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from ..models import UserRole, User
from ..serializers.role_serializers import (
    RoleSerializer,
    RoleCreateSerializer,
    RoleUpdateSerializer,
    RoleListSerializer,
    RoleBulkCreateSerializer
)


logger = get_logger(__name__)


class UserRoleViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    ViewSet complet pour la gestion des rôles utilisateurs.
    
    Endpoints:
        - GET    /client/roles/           - Liste tous les rôles du client
        - POST   /client/roles/           - Créer un nouveau rôle
        - GET    /client/roles/{id}/      - Détails d'un rôle
        - PUT    /client/roles/{id}/      - Mettre à jour un rôle (complet)
        - PATCH  /client/roles/{id}/      - Modifier permissions uniquement
        - DELETE /client/roles/{id}/      - Supprimer un rôle
    
    Actions supplémentaires:
        - GET    /client/roles/{id}/users/     - Utilisateurs avec ce rôle
        - POST   /client/roles/bulk-create/    - Création en masse
        - GET    /client/roles/summary/        - Résumé des rôles et permissions
    
    Permissions:
        - Lecture : tous les utilisateurs authentifiés
        - Écriture/Modification/Suppression : Admin uniquement
    """
    
    queryset = UserRole.objects.all()
    serializer_class = RoleSerializer
    entity_name = 'role'
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'roles'

    action_policies = {
        'users': {
            'crud': 'read',
            'scope': 'client',
        },
        'summary': {
            'crud': 'read',
            'scope': 'client',
        },
        'bulk_create': {
            'crud': 'create',
            'tier': 'admin',
            'scope': 'client',
        },
        'duplicate': {
            'crud': 'create',
            'tier': 'admin',
            'scope': 'client',
        },
    }
    
    # Configuration des filtres
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['read', 'write', 'modify', 'delete']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']

    def _other_admin_roles_exist(self, role: UserRole) -> bool:
        """Check if another admin-tier role exists for the same client."""
        if role is None:
            return False

        return UserRole.objects.filter(
            client_account_id=role.client_account_id,
            is_admin=True,
        ).exclude(pk=role.pk).exists()

    def _is_last_admin_role(self, role: UserRole) -> bool:
        """Return True when the provided role is the last admin role for the client."""
        if role is None:
            return False

        if not (role.is_admin or role.name == 'Admin'):
            return False

        return not self._other_admin_roles_exist(role)
    
    def _invalidate_role_cache(self, client_id):
        """Invalidate cached payloads for roles and dependent user payloads."""
        if not client_id:
            return

        invalidate_tag(client_id, 'roles')
        invalidate_tag(client_id, 'users')

    def _serialize_list_queryset(self, queryset, client_id):
        """Serialize the queryset with metadata for list responses (cache friendly)."""
        timestamp = timezone.now().isoformat()
        metadata = {
            'client_id': str(client_id) if client_id else None,
            'generated_at': timestamp,
        }

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            total_roles = self.paginator.page.paginator.count
            metadata['total_roles'] = total_roles

            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': total_roles,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                },
                'metadata': metadata,
            }

        serializer = self.get_serializer(queryset, many=True)
        metadata['total_roles'] = len(serializer.data)

        return {
            'success': True,
            'data': {
                'results': serializer.data, 
                'count': len(serializer.data),
            },
            'metadata': metadata,
        }

    def _build_summary_payload(self, client_id):
        """Generate the summary payload with aggregates for caching."""
        roles = UserRole.objects.filter(client_account_id=client_id)

        annotated_roles = roles.annotate(
            active_users=Count('users', filter=Q(users__is_active=True), distinct=True)
        )

        tier_distribution = roles.aggregate(
            admin=Count('id', filter=Q(is_admin=True)),
            manager=Count('id', filter=Q(is_manager=True)),
            individual=Count('id', filter=Q(is_individual=True)),
        )

        permissions_distribution = roles.aggregate(
            read=Count('id', filter=Q(read=True)),
            write=Count('id', filter=Q(write=True)),
            modify=Count('id', filter=Q(modify=True)),
            delete=Count('id', filter=Q(delete=True)),
        )

        total_roles = roles.count()
        total_users_with_roles = User.objects.filter(
            client_account_id=client_id,
            role__isnull=False,
            is_active=True,
        ).count()

        stats = {
            'total_roles': total_roles,
            'total_users_with_roles': total_users_with_roles,
            'permissions_distribution': permissions_distribution,
            'tier_distribution': tier_distribution,
        }

        role_distribution = list(
            annotated_roles.values(
                'name', 'is_admin', 'is_manager', 'is_individual', 'active_users'
            ).order_by('-active_users')
        )

        admin_roles = list(
            annotated_roles.filter(is_admin=True).values('name', 'active_users')
        )

        critical_roles = [
            {
                'role': admin_role['name'],
                'tier': 'admin',
                'active_users': admin_role['active_users'],
                'warning': 'Only one admin user' if admin_role['active_users'] == 1 else None,
            }
            for admin_role in admin_roles
        ]

        if not admin_roles:
            critical_roles.append({'warning': 'No admin role defined!'})

        return {
            'success': True,
            'summary': {
                'statistics': stats,
                'role_distribution': role_distribution,
                'critical_roles': critical_roles,
                'client_id': str(client_id) if client_id else None,
                'generated_at': timezone.now().isoformat(),
            },
        }

    def get_serializer_class(self):
        """
        Sélection du serializer selon l'action.
        Optimise les performances et applique les bonnes validations.
        """
        if self.action == 'list':
            return RoleListSerializer
        elif self.action == 'create':
            return RoleCreateSerializer
        elif self.action == 'partial_update':
            return RoleUpdateSerializer
        # Pas de serializer spécial pour bulk_create, on le gère manuellement
        return RoleSerializer
    
    def get_queryset(self):
        """
        Récupère les rôles du client avec optimisations.
        Applique le client scoping et les annotations pour performance.
        """
        queryset = super().get_queryset().select_related('client_account')

        # Préparer les annotations communes pour supprimer les .count() côté serializers
        queryset = queryset.annotate(
            users_count=Count('users', distinct=True),
            active_users_count=Count(
                'users',
                filter=Q(users__is_active=True),
                distinct=True,
            ),
        )

        # Optimisations spécifiques selon l'action demandée
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'duplicate']:
            queryset = queryset.prefetch_related(
                Prefetch(
                    'users',
                    queryset=User.objects.filter(is_active=True)
                    .select_related('team', 'organization'),
                    to_attr='prefetched_active_users',
                    )
                )

        return queryset
    
    # def check_admin_permission(self):
    #     """
    #     Vérifie que l'utilisateur a les droits admin.
    #     MISE À JOUR : Utilise maintenant is_admin si disponible
    #     """
    #     user = self.request.user
        
    #     # Méthode 1 : Utiliser has_admin_rights() si elle existe
    #     if hasattr(user, 'has_admin_rights'):
    #         if not user.has_admin_rights():
    #             raise StandardizedPermissionDenied(
    #                 CoreErrorMessages.PERMISSION_DENIED + " - Admin rights required"
    #             )
    #     else:
    #         # Méthode 2 : Vérifier directement le tier
    #         is_admin = False
            
    #         # Check superuser
    #         if hasattr(user, 'is_superuser') and user.is_superuser == True:
    #             is_admin = True
    #         # NOUVEAU : Check is_admin flag
    #         elif hasattr(user, 'role') and user.role:
    #             if hasattr(user.role, 'is_admin') and user.role.is_admin:
    #                 is_admin = True
    #             # Fallback sur le nom si is_admin n'existe pas encore
    #             elif hasattr(user.role, 'name') and 'admin' in user.role.name.lower():
    #                 is_admin = True
            
    #         if not is_admin:
    #             raise StandardizedPermissionDenied(
    #                 CoreErrorMessages.PERMISSION_DENIED + " - Admin tier required"
    #             )
        
    #     return True
    
    def list(self, request, *args, **kwargs):
        """
        Liste tous les rôles du client.
        Accessible à tous les utilisateurs authentifiés.
        """
        client_id = self.get_client_id()
        queryset = self.filter_queryset(self.get_queryset())
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'roles_list',
            'client_id': str(client_id) if client_id else None,
        })

        if not _is_redis_backend() or not client_id:
            payload = self._serialize_list_queryset(queryset, client_id)
            metadata = payload.get('metadata', {})
            ctx['result_count'] = metadata.get('total_roles')
            logger.info('roles_list', extra=ctx)
            return Response(payload)

        cache_key = build_drf_cache_key(
            namespace='roles_list',
            client_id=client_id,
            user_id=getattr(request.user, 'id', None),
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='roles',
        )

        def producer():
            return self._serialize_list_queryset(queryset, client_id)

        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=120,
            tag=(client_id, 'roles'),
        )

        metadata = cached_data.get('metadata', {}) if isinstance(cached_data, dict) else {}
        ctx['result_count'] = metadata.get('total_roles')
        logger.info('roles_list', extra=ctx)

        return Response(cached_data)

    def create(self, request, *args, **kwargs):
        """
        Créer un nouveau rôle.
        Réservé aux administrateurs.
        """
        # # Vérifier les permissions admin
        # self.check_admin_permission()
        
        # Validation et création
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        
        # Transaction pour garantir l'intégrité
        with transaction.atomic():
            instance = serializer.save()
            
            client_id = instance.client_account_id
            transaction.on_commit(lambda: self._invalidate_role_cache(client_id))

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'role_create_success',
            'role_id': str(instance.id),
            'role_name': instance.name,
        })
        logger.info('role_create_success', extra=ctx)
        
        # Retourner avec le serializer complet pour affichage
        full_serializer = RoleSerializer(instance, context=self.get_serializer_context())
        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' created successfully",
            'data': full_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Détails d'un rôle spécifique.
        Accessible à tous les utilisateurs authentifiés.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Enrichir avec des informations supplémentaires
        data = serializer.data
        
        # Ajouter la liste des utilisateurs actifs si demandé
        if request.query_params.get('include_users') == 'true':
            prefetched_users = getattr(instance, 'prefetched_active_users', None)
            if prefetched_users is not None:
                active_users = [
                    {
                        'id': user.id,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'team__name': user.team.name if user.team else None,
                    }
                    for user in prefetched_users
                ]
            else:
                active_users = instance.users.filter(is_active=True).values(
                    'id', 'email', 'first_name', 'last_name', 'team__name'
                )
            data['active_users'] = list(active_users)
        
        return Response({
            'success': True,
            'data': data
        })
    
    def update(self, request, *args, **kwargs):
        """
        Mise à jour complète d'un rôle (PUT).
        Réservé aux administrateurs.
        """
        # # Vérifier les permissions admin
        # self.check_admin_permission()
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if self._is_last_admin_role(instance):
            raise StandardizedValidationError(
                CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot modify the last admin role"
            )
      
        # Protection du rôle Admin système
        if instance.name == 'Admin':
            # Empêcher de renommer le rôle Admin
            new_name = request.data.get('name')
            if new_name and new_name != 'Admin':
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot rename the Admin role"
                )
            
            # Empêcher de désactiver les permissions critiques
            if request.data.get('read', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if request.data.get('write', None) == False or request.data.get('create', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write/create permission for Admin role"
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        changed_fields = sorted(serializer.validated_data.keys())
        
        with transaction.atomic():
            instance = serializer.save()
            
            client_id = instance.client_account_id
            transaction.on_commit(lambda: self._invalidate_role_cache(client_id))

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'role_update_success',
            'role_id': str(instance.id),
            'role_name': instance.name,
            'fields_updated': changed_fields,
        })
        logger.info('role_update_success', extra=ctx)

        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' updated successfully",
            'data': serializer.data
        })
    
    def partial_update(self, request, *args, **kwargs):
        """
        Mise à jour partielle (PATCH) - permissions uniquement.
        Réservé aux administrateurs.
        """
        # # Vérifier les permissions admin
        # self.check_admin_permission()
        
        instance = self.get_object()

        if self._is_last_admin_role(instance):
            raise StandardizedValidationError(
                CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot modify the last admin role"
            )
       
        # Protection du rôle Admin - empêcher de désactiver des permissions critiques
        if instance.name == 'Admin':
            # Vérifier si on essaie de désactiver des permissions critiques
            if request.data.get('read', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable read permission for Admin role"
                )
            if request.data.get('write', None) == False or request.data.get('create', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable write/create permission for Admin role"
                )
            if request.data.get('modify', None) == False or request.data.get('update', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable modify/update permission for Admin role"
                )
            if request.data.get('delete', None) == False:
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED + " - Cannot disable delete permission for Admin role"
                )
        
        # Utiliser le serializer spécialisé pour PATCH
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        changed_fields = sorted(serializer.validated_data.keys())
        
        with transaction.atomic():
            instance = serializer.save()
            
            client_id = instance.client_account_id
            transaction.on_commit(lambda: self._invalidate_role_cache(client_id))

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'role_partial_update_success',
            'role_id': str(instance.id),
            'role_name': instance.name,
            'fields_updated': changed_fields,
        })
        logger.info('role_partial_update_success', extra=ctx)

        
        return Response({
            'success': True,
            'message': f"Role '{instance.name}' permissions updated successfully",
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un rôle.
        Réservé aux administrateurs avec validations.
        
        Note importante: Le modèle UserRole a un champ BooleanField nommé 'delete'
        qui masque la méthode delete() héritée de Model. Pour cette raison,
        nous utilisons QuerySet.delete() au lieu de instance.delete().
        """
        # # Vérifier les permissions admin
        # self.check_admin_permission()
        
        instance = self.get_object()
        
        # Validations métier avant suppression
        with transaction.atomic():
             # 1. Empêcher la suppression du dernier rôle admin du client
            if self._is_last_admin_role(instance):
                raise StandardizedValidationError(
                    CoreErrorMessages.LAST_ADMIN_ROLE_LOCKED + " - Cannot delete the last admin role"
                )
            
            # 2. Vérifier qu'aucun utilisateur actif n'a ce rôle
            active_users_count = instance.users.filter(is_active=True).count()
            if active_users_count is None:
                prefetched_users = getattr(instance, 'prefetched_active_users', None)
                if prefetched_users is not None:
                    active_users_count = len(prefetched_users)
                else:
                    active_users_count = instance.users.filter(is_active=True).count()
            if active_users_count > 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_IN_USE.format(
                        fields=f"{active_users_count} active user(s) still have this role"
                    )
                )
            
            # 3. Dissocier les utilisateurs inactifs (soft delete)
            instance.users.filter(is_active=False).update(role=None, role_name=None)
            
            # Log avant suppression
            role_name = instance.name
            role_id = instance.id
            client_id = instance.client_account_id

            # Suppression effective - utiliser QuerySet car le champ 'delete' masque la méthode delete()
            # Le modèle UserRole a un champ BooleanField nommé 'delete' qui entre en conflit
            UserRole.objects.filter(id=role_id).delete()
            transaction.on_commit(lambda: self._invalidate_role_cache(client_id))
        
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'role_delete_success',
            'role_id': str(role_id),
            'role_name': role_name,
        })
        logger.info('role_delete_success', extra=ctx)
        
        # HTTP 204 ne doit pas avoir de body selon la spec REST
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """
        Liste les utilisateurs ayant ce rôle.
        Accessible à tous les utilisateurs authentifiés.
        """
        role = self.get_object()
        
        # Filtres optionnels
        is_active = request.query_params.get('active', 'true').lower() == 'true'
        team_id = request.query_params.get('team_id')
        organization_id = request.query_params.get('organization_id')
        
        # Construction de la requête
        users_qs = role.users.select_related('team', 'organization')
        
        if is_active:
            users_qs = users_qs.filter(is_active=True)
        
        if team_id:
            users_qs = users_qs.filter(team_id=team_id)
        
        if organization_id:
            users_qs = users_qs.filter(organization_id=organization_id)
        
        # Format de sortie
        users_data = users_qs.values(
            'id', 'email', 'first_name', 'last_name',
            'is_active', 'last_login',
            team_name=F('team__name'),
            organization_name=F('organization__name')
        )
        
        return Response({
            'success': True,
            'role': {
                'id': str(role.id),
                'name': role.name
            },
            'users': list(users_data),
            'total_count': users_qs.count()
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Résumé global des rôles et permissions du client.
        MISE À JOUR : Inclut maintenant la distribution par tier
        """
        client_id = self.get_client_id()
        
        roles = UserRole.objects.filter(client_account_id=client_id)
        
        annotated_roles = roles.annotate(
            active_users=Count('users', filter=Q(users__is_active=True), distinct=True)
        )

        tier_distribution = roles.aggregate(
            admin=Count('id', filter=Q(is_admin=True)),
            manager=Count('id', filter=Q(is_manager=True)),
            individual=Count('id', filter=Q(is_individual=True)),
        )

        permissions_distribution = roles.aggregate(
            read=Count('id', filter=Q(read=True)),
            write=Count('id', filter=Q(write=True)),
            modify=Count('id', filter=Q(modify=True)),
            delete=Count('id', filter=Q(delete=True)),
        )

        
        # Compter les utilisateurs par permission
        stats = {
            'total_roles': roles.count(),
            'total_users_with_roles': User.objects.filter(
                client_account_id=client_id,
                role__isnull=False,
                is_active=True
            ).count(),
            'permissions_distribution': permissions_distribution,
            'tier_distribution': tier_distribution,
        }
        
        # Distribution des rôles avec tier
        role_distribution = list(
            annotated_roles.values(
                'name', 'is_admin', 'is_manager', 'is_individual', 'active_users'
            ).order_by('-active_users')
        )

        admin_roles = list(
            annotated_roles.filter(is_admin=True).values('name', 'active_users')
        )

        critical_roles = [
            {
                'role': admin_role['name'],
                'active_users': admin_role['active_users'],
                'warning': 'Only one admin user' if admin_role['active_users'] == 1 else None,
            }
            for admin_role in admin_roles
        ]

        if not admin_roles:
            critical_roles.append({'warning': 'No admin role defined!'})
        
        return Response({
            'success': True,
            'data': {
                'statistics': stats,
                'role_distribution': list(role_distribution),
                'critical_roles': critical_roles,
                'client_id': str(client_id),
                'generated_at': timezone.now().isoformat()
            }
        })
    
    @action(detail=False, methods=['get'], url_path='permissions-matrix')
    def permissions_matrix(self, request):
        """Retourne la matrice complète des permissions (REGISTRY)."""
        from permissions.registry import REGISTRY
        
        ctx = ctx_from_request(request)
        ctx.update({'event': 'permissions_matrix_retrieve'})
        logger.info('permissions_matrix_retrieve', extra=ctx)
        
        return Response({
            'success': True,
            'data': REGISTRY
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Dupliquer un rôle existant avec un nouveau nom.
        MISE À JOUR : Copie aussi les flags de tier
        """
        # # Vérifier les permissions admin
        # self.check_admin_permission()
        
        source_role = self.get_object()
        new_name = request.data.get('name')
        
        if not new_name:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="name")
            )
        
        # Créer le nouveau rôle avec les tiers
        with transaction.atomic():
            new_role = UserRole.objects.create(
                client_account=source_role.client_account,
                name=new_name,
                read=source_role.read,
                write=source_role.write,
                modify=source_role.modify,
                delete=source_role.delete,
                # NOUVEAU : Copier les flags de tier
                is_admin=source_role.is_admin,
                is_manager=source_role.is_manager,
                is_individual=source_role.is_individual
            )
            transaction.on_commit(lambda: self._invalidate_role_cache(source_role.client_account_id))
            
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'role_duplicate_success',
            'source_role_id': str(source_role.id),
            'new_role_id': str(new_role.id),
            'role_name': new_role.name,
        })
        logger.info('role_duplicate_success', extra=ctx)

        serializer = RoleSerializer(new_role, context=self.get_serializer_context())
        
        return Response({
            'success': True,
            'message': f"Role '{new_role.name}' created as duplicate of '{source_role.name}'",
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)