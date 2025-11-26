# end_users/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Exists, OuterRef
from datetime import datetime, date
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, UsersErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from django.http import Http404
from ..models import User, Team, Organization
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from core.throttling import PasswordChangeThrottle, SensitiveActionThrottle, StandardRateThrottle
from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, disable_signals, invalidate_tag
from ..serializers.user_serializer import (
    UserSerializer,
    UserListSerializer,

)

from django.urls import reverse
from django.conf import settings
import uuid as _uuid
from core.idempotency import (
    start_op,
    complete_op,
    fail_op,
    compute_payload_hash,
    get_owner_from_request)

from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from rest_framework.exceptions import PermissionDenied, APIException

logger = get_logger(__name__)

class UserViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing users with client scoping and performance integration
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    entity_name = 'user'

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'role', 'team', 'organization', 'is_staff', "is_superuser"]
    search_fields = ['email', 'first_name', 'last_name', 'role__name',  'team__name' ]
    ordering_fields = [
        'email', 
        'first_name', 
        'last_name', 
        'created_at',
        'is_superuser',   
        'is_active',      
        'last_login',      
        'role__name',      
        'team__name'       
    ]
    ordering = ['first_name', 'last_name']
    
    # Security configuration
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'users'

    # ===== ACTION POLICIES =====
    # Declarative permission configuration for custom actions
    action_policies = {
        'change_password': {
            'crud': 'update',
            'scope': 'client'  # Autoriser tout le monde, la logique custom dans la méthode fera le filtrage
            # Admin can change anyone's password, others only their own
            # This needs custom logic in the method
        },
        'grant_superuser': {
            'crud': 'update',
            'scope': 'client'     # Admin can grant to anyone in client
        },
        'revoke_superuser': {
            'crud': 'update',
            'scope': 'client'
        },
        'activate': {
            'crud': 'update',     # Only admin can activate users
            'scope': 'client'     # Admin can activate anyone in client
        },
        'deactivate': {
            'crud': 'update',
            'scope': 'client'     # Admin can deactivate anyone in client
        },
        'performance': {
            'crud': 'read',
            'scope': 'client'  # Tout le monde peut accéder, filtrage dans la méthode
            # All users can see performance (but scoped appropriately)
            # Custom logic handles scope in the method
        },
        'team_performance': {
            'crud': 'read',
            'scope': 'client'  # Tout le monde peut accéder, filtrage dans la méthode
            # All team members can see team performance
            # Custom logic ensures team membership
        },
        'managed_users_performance': {
            'crud': 'read',
            'scope': 'client'  # Filtrage dans la méthode
        },
        'managers': {
            'crud': 'read',
            'scope': 'client'  
        },
        'superusers': {
            'crud': 'read',
            'scope': 'client'
        },
        'grant_superuser': {
            'crud': 'update',
            'scope': 'client'
        },
        # ===== BULK ACTIONS =====
        'bulk_create': {
            'crud': 'create',
            'tier': 'admin', 
            'scope': 'client'     # Admin can create users in their client
        },
        'bulk_update': {
            'crud': 'update',
            'tier': 'admin',
            'scope': 'client'     # Admin can update users in their client
        },
        'bulk_delete': {
            'crud': 'delete',
            'tier': 'admin', 
            'scope': 'client'     # Admin can delete users in their client
        },
    }
    
    def get_serializer_class(self):
        """Choisir le serializer selon l'action"""
        if self.action == 'list':
            return UserListSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Get users for the current client with optimized queries"""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'UserViewSet'
        })

        queryset = super().get_queryset()

        logger.debug("queryset_filtered", extra={
            'action': self.action,
            'count': queryset.count(),
            'user_tier': getattr(self.request, '_user_tier', 'unknown')
        })

        # ✅ HIERARCHICAL TEAM FILTERING
        # Support multiple team IDs (comma-separated) for hierarchical filtering
        # Example: ?team=uuid1,uuid2,uuid3
        team_param = self.request.query_params.get('team')
        if team_param:
            # Check if multiple teams (comma-separated)
            if ',' in team_param:
                # Split and filter by UUIDs
                team_ids = [t.strip() for t in team_param.split(',') if t.strip()]
                queryset = queryset.filter(team_id__in=team_ids)
                logger.debug("Applied hierarchical team filter", extra={
                    'team_ids': team_ids,
                    'count': len(team_ids)
                })
        
        # Optimiser selon l'action
        if self.action == 'list':
            # Liste légère
            queryset = queryset.select_related(
                'team', 'organization', 'role', 'client_account'
            ).annotate(
                # ✅ Annotation: Vérifie si l'utilisateur manage au moins une équipe
                has_managed_teams=Exists(
                    Team.objects.filter(manager_id=OuterRef('pk'))
                ),
                # ✅ Annotation: Vérifie si l'utilisateur manage au moins une organisation
                has_managed_orgs=Exists(
                    Organization.objects.filter(manager_id=OuterRef('pk'))
                )
            )
            
            logger.debug("Applied list optimizations", extra={'action': 'list'})
        
        elif self.action == 'retrieve':
            # ✅ OPTIMISATION: Pas de prefetch_related pour retrieve simple
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            )
            logger.debug("Applied retrieve optimizations", extra={'action': 'retrieve'})
        
        elif self.action in ['managed_users_performance', 'managers']:
            # Garder prefetch seulement pour les actions qui en ont vraiment besoin
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            ).prefetch_related(
                'managed_teams', 'managed_organizations'
            )
            logger.debug("Applied full optimizations", extra={'action': self.action})
        
        else:
            # Autres actions: select_related basique
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            )
        
        # Filtres spéciaux
        managers_only = self.request.query_params.get('managers_only', None)
        if managers_only and managers_only.lower() == 'true':
            queryset = queryset.filter(
                Q(managed_teams__isnull=False) | Q(managed_organizations__isnull=False)
            ).distinct()
        
        role_tier = self.request.query_params.get('role_tier', None)
        if role_tier:
            tier_values = [t.strip().lower() for t in role_tier.split(',') if t.strip()]
            tier_filter = Q()
            
            for tier in tier_values:
                if tier == 'admin':
                    tier_filter |= Q(role__is_admin=True)
                elif tier == 'manager':
                    tier_filter |= Q(role__is_manager=True)
                elif tier == 'individual':
                    tier_filter |= Q(role__is_individual=True)
            
            if tier_filter:
                queryset = queryset.filter(tier_filter)
                logger.debug("Applied role_tier filter", extra={
                    'tiers': tier_values
                })

                
        return queryset
    
    def filter_queryset(self, queryset):
        """
        Override filter_queryset to handle multiple team IDs before DjangoFilterBackend validation.
        
        Supports hierarchical team filtering: ?team=uuid1,uuid2,uuid3
        """
        # Extract team parameter before standard filtering
        team_param = self.request.query_params.get('team')
        
        if team_param and ',' in team_param:
            # Multiple teams (hierarchical filtering)
            team_ids = [t.strip() for t in team_param.split(',') if t.strip()]
            
            # Apply filter manually
            queryset = queryset.filter(team_id__in=team_ids)
            
            logger.debug("Applied hierarchical team filter", extra={
                'team_ids': team_ids,
                'count': len(team_ids)
            })
            
            # Remove 'team' from query params to prevent DjangoFilterBackend from processing it
            mutable_params = self.request.query_params.copy()
            mutable_params.pop('team', None)
            self.request._request.GET = mutable_params
        
        # Apply all other filters (including single team if not comma-separated)
        return super().filter_queryset(queryset)
    
    # def retrieve(self, request, *args, **kwargs):
    #     """
    #     Récupérer un utilisateur spécifique par son ID
    #     GET /client/users/{id}/
    #     """
    #     try:
    #         user = self.get_object()
    #         is_self = str(user.id) == str(request.user.id)

    #         ctx = ctx_from_request(request)
    #         ctx.update({
    #             "target_user_id": str(user.id),
    #             "is_self": is_self,
    #             "event": "user_retrieve",
    #             "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
    #         })
    #         logger.info("user_retrieve", extra=ctx)

    #         serializer = UserSerializer(user)
    #         return Response({"success": True, "data": serializer.data})

    #     except (User.DoesNotExist, Http404):
    #         ctx = ctx_from_request(request)
    #         ctx.update({
    #             "event": "user_retrieve_not_found",
    #             "resource": "user",
    #             "target_id": str(kwargs.get('pk', '-')),
    #             "action": "retrieve",
    #             "scope": "client",
    #         })
    #         logger.info("user_retrieve_not_found", extra=ctx)
    #         return Response(
    #             {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND},
    #             status=status.HTTP_404_NOT_FOUND,
    #         )

    def retrieve(self, request, *args, **kwargs):
        """
        Récupérer un utilisateur spécifique par son ID
        GET /client/users/{id}/
        
        Cache: 180s sur les données sérialisées
        """
        from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, _is_redis_backend
        # raise Exception("Test 500: Server error on retrieve")
        
        pk = kwargs.get('pk')

        
        # Skip cache si pas Redis
        if not _is_redis_backend():
            try:
                user = self.get_object()
                is_self = str(user.id) == str(request.user.id)

                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(user.id),
                    "is_self": is_self,
                    "event": "user_retrieve",
                    "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
                })
                logger.info("user_retrieve", extra=ctx)

                serializer = UserSerializer(user)
                return Response({"success": True, "data": serializer.data})

            except (User.DoesNotExist, Http404):
                ctx = ctx_from_request(request)
                ctx.update({
                    "event": "user_retrieve_not_found",
                    "resource": "user",
                    "target_id": str(pk),
                    "action": "retrieve",
                    "scope": "client",
                })
                logger.info("user_retrieve_not_found", extra=ctx)
                return Response(
                    {"success": False, "error": UsersErrorMessages.USER_NOT_FOUND},
                    status=status.HTTP_404_NOT_FOUND,
                )
        
        # Construire clé de cache
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        
        cache_key = build_drf_cache_key(
            namespace='user_detail',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            extra=str(pk),  # L'ID de l'user demandé
            tag_namespace='users',
        )
        
        # Producer : retourne un dict sérialisable
        def producer():
            try:
                user = self.get_object()
                is_self = str(user.id) == str(request.user.id)
                
                # Log
                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(user.id),
                    "is_self": is_self,
                    "event": "user_retrieve",
                    "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
                })
                logger.info("user_retrieve", extra=ctx)
                
                serializer = UserSerializer(user)
                return {"success": True, "data": serializer.data}
                
            except (User.DoesNotExist, Http404):
                ctx = ctx_from_request(request)
                ctx.update({
                    "event": "user_retrieve_not_found",
                    "resource": "user",
                    "target_id": str(pk),
                    "action": "retrieve",
                    "scope": "client",
                })
                logger.info("user_retrieve_not_found", extra=ctx)
                # Retourner dict avec flag d'erreur
                return {"success": False, "error": UsersErrorMessages.USER_NOT_FOUND, "status": 404}
        
        # Cache les données
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,  # 5 minutes
            tag=(client_id, 'users')
        )
        
        # Gérer le cas 404 depuis le cache
        if not cached_data.get('success'):
            return Response(
                {"success": False, "error": cached_data.get('error')},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(cached_data)
        
    def list(self, request, *args, **kwargs):
        """
        Liste des utilisateurs avec cache applicatif
        GET /client/users/
        
        Cache: 300s sur les données sérialisées (dict Python, pas Response)
        """
        from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, _is_redis_backend
        # raise PermissionDenied("Test 403: You do not have permission to view users")
        # raise Exception("Test 500: Simulated server error")
        # from rest_framework.response import Response
        # raise Http404("Ressource introuvable")
        # return Response(
        #     {"detail": "Not Found"},
        #     status=404
        # )
        # import time
        # time.sleep(2)  # Simuler lenteur
        # from rest_framework.response import Response
        # return Response(
        #     {"detail": "Request timeout"},
        #     status=408
        # )
        
        # Skip cache si pas Redis (FileBasedCache trop lent)
        if not _is_redis_backend():
            response = super().list(request, *args, **kwargs)
            ctx = ctx_from_request(request)
            total = response.data.get('count', '-') if isinstance(response.data, dict) else '-'
            ctx.update({
                "event": "user_list",
                "result_count": total,
                "role_name": getattr(request.user, 'role_name', '-') if getattr(request, 'user', None) else '-',
            })
            logger.info("user_list", extra=ctx)
            return response

        
        # Construire clé de cache
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        query_string = request.META.get('QUERY_STRING', '')
        
        cache_key = build_drf_cache_key(
            namespace='users_list',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            query_string=query_string,
            tag_namespace='users',
        )
        
        # Producer : retourne un dict sérialisable, PAS un Response
        def producer():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # Retourner un dict Python simple (sérialisable par Redis)
                return {
                    'success': True,
                    'data': {
                        'results': serializer.data,
                        'count': self.paginator.page.paginator.count,
                        'next': self.paginator.get_next_link(),
                        'previous': self.paginator.get_previous_link(),
                    }
                }
            
            # Pas de pagination
            serializer = self.get_serializer(queryset, many=True)
            return {
                'success': True,
                'data': serializer.data
            }
        # Cache les données (dict Python, pas Response)
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'users')
        )
        
        # Logging
        ctx = ctx_from_request(request)
        if isinstance(cached_data, dict):
            if isinstance(cached_data.get('data'), dict) and 'count' in cached_data['data']:
                total = cached_data['data']['count']
            elif 'count' in cached_data:
                total = cached_data['count']
            elif isinstance(cached_data.get('data'), list):
                total = len(cached_data['data'])
            else:
                total = '-'
        elif isinstance(cached_data, list):
            total = len(cached_data)
        else:
            total = '-'

        ctx.update({
            "event": "user_list",
            "result_count": total,
            "role_name": getattr(request.user, 'role_name', '-') if getattr(request, 'user', None) else '-',
        })
        logger.info("user_list", extra=ctx)
        
        # Construire Response depuis les données cachées
        return Response(cached_data)

        
    def create(self, request, *args, **kwargs):
        """
        Créer un nouvel utilisateur
        POST /client/users/
        """
        with transaction.atomic():

            # raise PermissionDenied("Test 403: You do not have permission to view users")
            # raise Exception("Test 500: Simulated server error")
            # from rest_framework.response import Response
            # raise Http404("Ressource introuvable")
            # return Response(
            #     {"detail": "User Not Found"},
            #     status=404
            # )
            # import time
            # time.sleep(3)  # Simuler lenteur
            # from rest_framework.response import Response
            # return Response(
            #     {"detail": "Request timeout"},
            #     status=429
            # )

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            audit_log(
                event='user_create_success',
                action='create',
                actor_id=str(request.user.id),
                client_id=str(user.client_account_id),
                target_type='user',
                target_id=str(user.id),
                outcome='success',
            )

            return Response(
                {
                    "success": True,
                    'message': f'User "{user.get_full_name()}" created successfully',
                    "data": UserSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )

    
    def partial_update(self, request, *args, **kwargs):
        """
        Mise à jour partielle d'un utilisateur (PATCH)
        PATCH /client/users/{id}/
        """
        try:
            with transaction.atomic():

                # import time
                # time.sleep(3)
                user = self.get_object()
                serializer = self.get_serializer(user, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                updated_user = serializer.save()

                changed_fields = sorted([k for k in serializer.validated_data.keys()])

                audit_log(
                    event='user_update_success',
                    action='partial_update',
                    actor_id=str(request.user.id),
                    client_id=str(updated_user.client_account_id),
                    target_type='user',
                    target_id=str(user.id),
                    fields_changed=changed_fields,
                    outcome='success',
                    extra={'is_self': str(user.id) == str(request.user.id)}
                )

                return Response({
                    "success": True,
                    'message': f'User "{updated_user.get_full_name()}" updated successfully',
                    "data": UserSerializer(updated_user).data,
                })

        except (User.DoesNotExist, Http404):

            audit_log(
                event='user_update_not_found',
                action='partial_update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='user',
                target_id=str(kwargs.get('pk', '-')),
                outcome='not_found',
            )

            return Response(
                {"success": False, "error": UsersErrorMessages.USER_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)

    
    @action(detail=True, methods=['patch'], url_path='change-password', throttle_classes=[PasswordChangeThrottle, StandardRateThrottle])
    def change_password(self, request, pk=None):
        """
        Change le mot de passe d'un utilisateur.
        PATCH /client/users/{id}/change-password/
        
        Permissions:
        - Admin: peut changer le mot de passe de n'importe quel utilisateur de son client
        - User: peut seulement changer son propre mot de passe
        
        Body:
        {
            "password": "new_password",
            "password_confirm": "new_password"
        }
        """
        try:
            user = self.get_object()
        
            # Check if admin or self
            from permissions.compat import get_auth_ctx
            ctx = get_auth_ctx(request)
            
            # Déterminer le tier effectif
            is_admin = False
            for role in ctx.roles:
                if isinstance(role, dict) and role.get('is_admin'):
                    is_admin = True
                    break
            is_admin = is_admin or ctx.is_superuser
            
            is_self = str(user.id) == str(request.user.id)
            
            # Admin peut tout
            if not (is_admin or is_self):
                return Response({
                    'success': False,
                    'error': 'You can only change your own password'
                }, status=status.HTTP_403_FORBIDDEN)

            # Import du serializer
            from ..serializers.user_serializer import ChangePasswordSerializer
            
            # Validation avec le serializer
            serializer = ChangePasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Mettre à jour le mot de passe
            serializer.update_password(user, serializer.validated_data)

            audit_log(
                event='user_password_change_success',
                action='change_password',
                actor_id=str(request.user.id),
                client_id=str(user.client_account_id),
                target_type='user',
                target_id=str(user.id),
                outcome='success',
                extra={
                    'is_self': is_self,
                    'is_admin': is_admin,
                }
)

            ctx = ctx_from_request(request)
            ctx.update({
                "actor_user_id": str(request.user.id),
                "target_user_id": str(user.id),
                "is_self": is_self,
                "is_admin": is_admin,
                "event": "password_change_success",
            })
            logger.info("password_change_success", extra=ctx)
            
            
            return Response({
                'success': True,
                'message': 'Password changed successfully',
                'user': {
                    'id': str(user.id),  
                    'email': user.email,
                    'name': user.get_full_name()
                }
            })
            
        except User.DoesNotExist:
            raise StandardizedValidationError(UsersErrorMessages.USER_NOT_FOUND)
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un utilisateur
        DELETE /client/users/{id}/
        """
        try:
            with transaction.atomic():

                # raise PermissionDenied("Test 403: You do not have permission to view users")
                # raise Exception("Test 500: Simulated server error")
                # from rest_framework.response import Response
                # raise Http404("Ressource introuvable")
                # return Response(
                #     {"detail": "User Not Found"},
                #     status=404
                # )
                # import time
                # time.sleep(3)  # Simuler lenteur
                # from rest_framework.response import Response
                # return Response(
                #     {"detail": "Request timeout"},
                #     status=429
                # )

                # return Response({
                #     'success': False,
                #     'error': UsersErrorMessages.USER_NOT_FOUND
                # }, status=status.HTTP_404_NOT_FOUND)
                
                client_id = self.get_client_id()
                user_id = kwargs.get('pk')

                user = User.objects.select_for_update().filter(
                    id=user_id,
                    client_account_id=client_id
                ).first()
                
                if not user:
                    audit_log(
                        event='user_delete_not_found',
                        action='delete',
                        actor_id=str(request.user.id),
                        client_id=str(client_id),
                        target_type='user',
                        target_id=str(user_id or '-'),
                        outcome='not_found',
                    )

                    return Response({
                        'success': False,
                        'error': UsersErrorMessages.USER_NOT_FOUND
                    }, status=status.HTTP_404_NOT_FOUND)

                # Mémoriser le client avant suppression
                client = user.client_account

                # Validation client scoping
                self.validate_client_id(user)

                # Vérifications métier avant suppression (TOCTOU-safe via modèle)
                self._validate_user_deletion(user)

                user_name = user.get_full_name()
                user.delete()

                audit_log(
                    event='user_delete_success',
                    action='delete',
                    actor_id=str(request.user.id),
                    client_id=str(client.id),
                    target_type='user',
                    target_id=str(user.id),
                    outcome='success',
                )

                # Filet de sécurité: s'assurer qu'un admin existe toujours
                client.ensure_admin_invariants()

                # Je te mets 200 pour garder le message dans le body
                return Response({
                    'success': True,
                    'message': f'User \"{user_name}\" deleted successfully'
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return self.handle_exception(e)

    
    @action(detail=True, methods=['delete'], url_path='soft')
    def soft_destroy(self, request, pk=None):
        """
        Soft delete a user (set is_active=False instead of physical deletion)
        DELETE /client/users/{id}/soft/
        
        This is a non-destructive operation. The user is archived but data is preserved.
        The user can be reactivated later by setting is_active=True.
        
        Response:
        {
            "success": true,
            "message": "User 'John Doe' archived successfully",
            "user": {
                "id": "...",
                "email": "...",
                "is_active": false
            }
        }
        """
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(
                    id=pk,
                    client_account_id=self.get_client_id()
                ).first()
                
                if not user:
                   raise StandardizedValidationError(
                        UsersErrorMessages.USER_NOT_FOUND
                    )

                # Mémoriser le client et infos avant modification
                client = user.client_account
                
                # Validation client scoping
                self.validate_client_id(user)

                # ===== SECURITY VALIDATIONS =====
                
                # 1. Empêcher de se supprimer soi-même
                if user.id == request.user.id:
                    raise StandardizedValidationError(
                        "Cannot archive your own account. Please ask another administrator."
                    )
                
                # 2. Empêcher d'archiver le dernier admin actif (TOCTOU-safe via is_last_active_admin)
                if user.is_active and user.is_last_active_admin():
                    raise StandardizedValidationError(
                        f"Cannot archive user '{user.email}': last active administrator. "
                        "Promote another user to admin first."
                    )
                
                # 3. Vérifier les permissions superuser
                if user.is_superuser and not request.user.is_superuser:
                    raise StandardizedValidationError(
                        "Only superusers can archive other superusers"
                    )

                # ===== SOFT DELETE: SET is_active=False =====
                user_name = user.get_full_name()
                user_email = user.email
                was_already_inactive = not user.is_active
                
                user.is_active = False
                user.save(update_fields=['is_active', 'updated_at'])

                # Logging
                audit_log(
                    event='user_soft_delete_success',
                    action='soft_delete',
                    actor_id=str(request.user.id),
                    client_id=str(client.id),
                    target_type='user',
                    target_id=str(user.id),
                    outcome='success',
                    extra={'was_already_inactive': was_already_inactive}
                )

                # Filet de sécurité: s'assurer qu'un admin actif existe toujours
                client.ensure_admin_invariants()

                return Response({
                    'success': True,
                    'message': f'User "{user_name}" archived successfully',
                    'user': {
                        'id': str(user.id),
                        'email': user_email,
                        'name': user_name,
                        'is_active': user.is_active
                    }
                }, status=status.HTTP_200_OK)

        except (User.DoesNotExist, Http404):
            audit_log(
                event='user_soft_delete_not_found',
                action='soft_delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='user',
                target_id=str(pk),
                outcome='not_found',
            )

            return Response({
                'success': False,
                'error': UsersErrorMessages.USER_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return self.handle_exception(e)

    
    def _can_grant_superuser(self, current_user):
        """
        Check if the current user can grant/revoke superuser status
        Only SuperUsers and Admin role users can grant superuser status
        """
        from permissions.compat import get_auth_ctx
        ctx = get_auth_ctx(self.request)
        
        # Check roles for admin flag
        for role in ctx.roles:
            if isinstance(role, dict) and role.get('is_admin'):
                return True
        return ctx.is_superuser
    
    def _validate_superuser_modification(self, current_user, request_data, target_user=None):
        """
        Validate if the current user can modify superuser status
        Called before create or update operations
        """
        # Check if trying to set/modify is_superuser
        if 'is_superuser' in request_data:
            if not self._can_grant_superuser(current_user):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # If removing superuser status, check it's not the last one
            if target_user and target_user.is_superuser and request_data.get('is_superuser') is False:
                # This will be double-checked in the serializer, but good to check here too
                client = target_user.client_account
                other_superusers = client.users.filter(
                    is_superuser=True
                ).exclude(id=target_user.id).count()
                
                if other_superusers == 0:
                    raise StandardizedValidationError(
                        "Cannot remove superuser status from the last superuser. "
                        "Promote another user to superuser first."
                    )
    
    def _validate_user_deletion(self, user):
        """
        Valider si l'utilisateur peut être supprimé.
        Utilise les méthodes modèle TOCTOU-safe pour les invariants :
        - Ne pas supprimer le dernier superuser
        - Ne pas supprimer le dernier admin actif (Admin role ou superuser)
        """
        # Empêcher la suppression de son propre compte
        if user.id == self.request.user.id:
            raise StandardizedValidationError(
                CoreErrorMessages.SELF_DELETE_FORBIDDEN
            )
    
        # 1) Invariant "au moins un superuser" par tenant
        if user.is_last_superuser():
            raise StandardizedValidationError(
                "Cannot delete the last superuser. "
                "Promote another user to superuser first."
            )

        # 2) Invariant "au moins un admin actif (role Admin OU superuser)"
        if user.is_last_active_admin():
            # On garde ta sémantique existante
            raise StandardizedValidationError(
                CoreErrorMessages.LAST_ADMIN_REQUIRED
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Récupérer les performances d'un utilisateur
        Intégration avec UserPerformanceService
        """
        target_user = self.get_object()
        
        # Vérifier l'accès aux performances
        from permissions.compat import get_auth_ctx
        ctx = get_auth_ctx(request)
        
        is_admin = False
        is_manager = False
        for role in ctx.roles:
            if isinstance(role, dict):
                if role.get('is_admin'):
                    is_admin = True
                if role.get('is_manager'):
                    is_manager = True
        is_admin = is_admin or ctx.is_superuser
        
        is_self = str(target_user.id) == str(request.user.id)
        
        # Vérifications d'accès
        if not is_admin:
            if is_manager:
                # Manager peut voir son équipe
                if target_user.team_id != request.user.team_id:
                    raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
            elif not is_self:
                # User normal peut voir seulement lui-même
                raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        
        # Paramètres de période
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        if not period_start or not period_end:
            # Période par défaut : mois actuel
            today = date.today()
            period_start = today.replace(day=1)
            period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, '%Y-%m-%d').date()
                period_end = datetime.strptime(period_end, '%Y-%m-%d').date()
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Invalid date format. Use YYYY-MM-DD"
                    )
                )
        
        # Log

        ctx = ctx_from_request(request)
        ctx.update({
            "target_user_id": str(target_user.id),
            "is_self": is_self,
            "period_start": str(period_start),
            "period_end": str(period_end),
            "event": "performance_view",
        })
        logger.debug("user_performance_access", extra=ctx)

        
        # Utiliser UserPerformanceService
        try:
            from ..services.user_performance_service import UserPerformanceService
            
            performance_data = UserPerformanceService.get_user_complete_performance_optimized(
                user_id=target_user.id,
                period_start=period_start,
                period_end=period_end,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': performance_data
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve performance data: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def team_performance(self, request):
        """
        Performances consolidées de l'équipe de l'utilisateur connecté

        Permissions:
        - Admin: peut voir toutes les équipes (avec param team_id)
        - Manager et membres: peuvent voir leur équipe
        """
        user = request.user

        # Vérifier les permissions
        from permissions.compat import get_auth_ctx
        ctx = get_auth_ctx(request)

        # Gérer le paramètre team_id pour les admins
        target_team_id = request.query_params.get('team_id')
        if target_team_id:
            is_admin = False
            for role in ctx.roles:
                if isinstance(role, dict) and role.get('is_admin'):
                    is_admin = True
                    break
            is_admin = is_admin or ctx.is_superuser
            
            if not is_admin:
                raise StandardizedValidationError(
                    "Only administrators can view other teams' performance"
                )
            
            from ..models import Team
            try:
                team = Team.objects.get(id=target_team_id, organization__client_account_id=self.get_client_id())
                team_members = team.members.filter(is_active=True)
                team_user_ids = list(team_members.values_list('id', flat=True))
                team_info = {
                    'id': str(team.id),
                    'name': team.name,
                    'organization': team.organization.name
                }
            except Team.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        else:
            # Utiliser l'équipe de l'utilisateur
            if not user.team:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="User is not assigned to a team"
                    )
                )
            
            team_members = user.team.members.filter(is_active=True)
            team_user_ids = list(team_members.values_list('id', flat=True))
            team_info = {
                'id': str(user.team.id),
                'name': user.team.name,
                'organization': user.team.organization.name
            }

        # Paramètres de période
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        if not period_start or not period_end:
            today = date.today()
            period_start = today.replace(day=1)
            period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, '%Y-%m-%d').date()
                period_end = datetime.strptime(period_end, '%Y-%m-%d').date()
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Invalid date format. Use YYYY-MM-DD"
                    )
                )
        
        # Utiliser UserPerformanceService
        try:
            from ..services.user_performance_service import UserPerformanceService
            
            team_performance = UserPerformanceService.get_team_consolidated_performance_optimized(
                team_user_ids=team_user_ids,
                period_start=period_start,
                period_end=period_end,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': team_performance,
                'team_info': {
                    'id': str(user.team.id),
                    'name': user.team.name,
                    'organization': user.team.organization.name
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve team performance: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['get'])
    def managed_users_performance(self, request, pk=None):
        """
        Performances des utilisateurs managés (pour managers)
        """

        manager = self.get_object()

        # Vérifier que l'utilisateur connecté peut accéder à ces données
        # Seuls les admins et le manager lui-même peuvent voir
        from permissions.compat import get_auth_ctx
        ctx = get_auth_ctx(request)
        
        is_admin = False
        for role in ctx.roles:
            if isinstance(role, dict) and role.get('is_admin'):
                is_admin = True
                break
        is_admin = is_admin or ctx.is_superuser
        
        is_self = str(manager.id) == str(request.user.id)
        
        if not (is_admin or is_self):
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        # Récupérer les utilisateurs managés
        managed_users = manager.get_managed_users()
        if not managed_users.exists():
            return Response({
                'success': True,
                'data': {
                    'manager': {
                        'id': str(manager.id),
                        'name': manager.get_full_name(),
                        'is_manager': manager.is_manager()
                    },
                    'managed_users': [],
                    'message': 'No managed users found'
                }
            })
        
        managed_user_ids = list(managed_users.values_list('id', flat=True))
        
        # Paramètres de période
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        if not period_start or not period_end:
            today = date.today()
            period_start = today.replace(day=1)
            period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, '%Y-%m-%d').date()
                period_end = datetime.strptime(period_end, '%Y-%m-%d').date()
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="Invalid date format. Use YYYY-MM-DD"
                    )
                )
        
        # Utiliser UserPerformanceService
        try:
            from ..services.user_performance_service_obsolete import UserPerformanceService
            
            consolidated_performance = UserPerformanceService.get_team_consolidated_performance_optimized(
                team_user_ids=managed_user_ids,
                period_start=period_start,
                period_end=period_end,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': consolidated_performance,
                'manager_info': {
                    'id': str(manager.id),
                    'name': manager.get_full_name(),
                    'managed_teams': list(manager.managed_teams.values('id', 'name')),
                    'managed_organizations': list(manager.managed_organizations.values('id', 'name'))
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve managed users performance: {str(e)}"
                )
            )
    

    @action(detail=False, methods=['get'])
    def managers(self, request):
        """
        Liste des managers avec leurs équipes
        GET /client/users/managers/
        
        Cache: 300s sur les données sérialisées
        """
        from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, _is_redis_backend
        
        # Skip cache si pas Redis
        if not _is_redis_backend():
            managers = self.get_queryset().filter(
                Q(managed_teams__isnull=False) | Q(managed_organizations__isnull=False)
            ).distinct()
            
            managers_data = []
            for manager in managers:
                managers_data.append({
                    'id': str(manager.id),
                    'name': manager.get_full_name(),
                    'email': manager.email,
                    'role': manager.role_name,
                    'managed_teams': list(manager.managed_teams.values('id', 'name')),
                    'managed_organizations': list(manager.managed_organizations.values('id', 'name')),
                    'managed_users_count': manager.get_managed_users().count()
                })
            
            return Response({
                'success': True,
                'data': managers_data,
                'total_managers': len(managers_data)
            })
        
        # Construire clé de cache
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        
        cache_key = build_drf_cache_key(
            namespace='users_managers',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            tag_namespace='users',
        )
        
        # Producer : retourne un dict sérialisable
        def producer():
            managers = self.get_queryset().filter(
                Q(managed_teams__isnull=False) | Q(managed_organizations__isnull=False)
            ).distinct()
            
            managers_data = []
            for manager in managers:
                managers_data.append({
                    'id': str(manager.id),
                    'name': manager.get_full_name(),
                    'email': manager.email,
                    'role': manager.role_name,
                    'managed_teams': list(manager.managed_teams.values('id', 'name')),
                    'managed_organizations': list(manager.managed_organizations.values('id', 'name')),
                    'managed_users_count': manager.get_managed_users().count()
                })
            
            return {
                'success': True,
                'data': managers_data,
                'total_managers': len(managers_data)
            }
        
        # Cache les données
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,  # 5 minutes
            tag=(client_id, 'users')
        )
        
        return Response(cached_data)
    
    @action(detail=False, methods=['get'], url_path='superusers')
    def superusers(self, request):
        """
        Liste tous les superusers du tenant actuel
        GET /client/users/superusers/
        
        Permissions:
        - Accessible uniquement aux Admin et SuperUser
        
        Cache: 300s sur les données sérialisées
        
        Returns:
        - Liste des superusers avec leurs informations
        - Statistiques sur les superusers du tenant
        """
        from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, _is_redis_backend
        
        # Vérifier les permissions - seuls Admin et SuperUser peuvent voir cette liste
        from permissions.compat import get_auth_ctx
        ctx_auth = get_auth_ctx(request)
        is_admin = any(isinstance(r, dict) and r.get('is_admin') for r in ctx_auth.roles) or ctx_auth.is_superuser
        if not is_admin:
            raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
        
        # Skip cache si pas Redis
        if not _is_redis_backend():
            try:
                client_id = self.get_client_id()

                ctx = ctx_from_request(request)
                ctx.update({"event": "superusers_list"})
                logger.debug("superusers_list_access", extra=ctx)
                
                superusers = self.get_queryset().filter(
                    is_superuser=True
                ).select_related('role', 'team', 'organization').order_by('-is_active', 'first_name', 'last_name')
                
                superusers_data = []
                for user in superusers:
                    superusers_data.append({
                        'id': str(user.id),
                        'email': user.email,
                        'name': user.get_full_name(),
                        'is_active': user.is_active,
                        'is_staff': user.is_staff,
                        'role': {
                            'id': str(user.role.id) if user.role else None,
                            'name': user.role.name if user.role else None
                        },
                        'organization': {
                            'id': str(user.organization.id) if user.organization else None,
                            'name': user.organization.name if user.organization else None
                        },
                        'team': {
                            'id': str(user.team.id) if user.team else None,
                            'name': user.team.name if user.team else None
                        },
                        'last_login': user.last_login.isoformat() if user.last_login else None,
                        'created_at': user.created_at.isoformat(),
                        'updated_at': user.updated_at.isoformat()
                    })
                
                total_superusers = len(superusers_data)
                active_superusers = superusers.filter(is_active=True).count()
                inactive_superusers = total_superusers - active_superusers
                
                admin_role_users = self.get_queryset().filter(
                    role__name='Admin',
                    is_active=True
                ).exclude(is_superuser=True).count()
                
                return Response({
                    'success': True,
                    'data': superusers_data,
                    'statistics': {
                        'total_superusers': total_superusers,
                        'active_superusers': active_superusers,
                        'inactive_superusers': inactive_superusers,
                        'admin_role_users_non_super': admin_role_users,
                        'total_administrators': active_superusers + admin_role_users
                    },
                'permissions_info': {
                        'description': 'Superusers have full administrative rights within this tenant',
                        'can_grant_superuser': self._can_grant_superuser(request.user),
                        'current_user_is_superuser': request.user.is_superuser
                    }
                })
                
            except Exception as e:
                return self.handle_exception(e)
        
        # Construire clé de cache
        client_id = self.get_client_id()
        user_id = request.user.id
        perm_version = get_permissions_version()
        
        cache_key = build_drf_cache_key(
            namespace='users_superusers',
            client_id=client_id,
            user_id=user_id,
            perm_version=perm_version,
            tag_namespace='users',
        )
        
        # Producer : retourne un dict sérialisable
        def producer():
            try:
                ctx = ctx_from_request(request)
                ctx.update({"event": "superusers_list"})
                logger.debug("superusers_list_access", extra=ctx)
                
                superusers = self.get_queryset().filter(
                    is_superuser=True
                ).select_related('role', 'team', 'organization').order_by('-is_active', 'first_name', 'last_name')
                
                superusers_data = []
                for user in superusers:
                    superusers_data.append({
                        'id': str(user.id),
                        'email': user.email,
                        'name': user.get_full_name(),
                        'is_active': user.is_active,
                        'is_staff': user.is_staff,
                        'role': {
                            'id': str(user.role.id) if user.role else None,
                            'name': user.role.name if user.role else None
                        },
                        'organization': {
                            'id': str(user.organization.id) if user.organization else None,
                            'name': user.organization.name if user.organization else None
                        },
                        'team': {
                            'id': str(user.team.id) if user.team else None,
                            'name': user.team.name if user.team else None
                        },
                        'last_login': user.last_login.isoformat() if user.last_login else None,
                        'created_at': user.created_at.isoformat(),
                        'updated_at': user.updated_at.isoformat()
                    })
                
                total_superusers = len(superusers_data)
                active_superusers = superusers.filter(is_active=True).count()
                inactive_superusers = total_superusers - active_superusers
                
                admin_role_users = self.get_queryset().filter(
                    role__name='Admin',
                    is_active=True
                ).exclude(is_superuser=True).count()
                
                return {
                    'success': True,
                    'data': superusers_data,
                    'statistics': {
                        'total_superusers': total_superusers,
                        'active_superusers': active_superusers,
                        'inactive_superusers': inactive_superusers,
                        'admin_role_users_non_super': admin_role_users,
                        'total_administrators': active_superusers + admin_role_users
                    },
                'permissions_info': {
                        'description': 'Superusers have full administrative rights within this tenant',
                        'can_grant_superuser': self._can_grant_superuser(request.user),
                        'current_user_is_superuser': request.user.is_superuser
                    }
                }
                
            except Exception as e:
                return self.handle_exception(e)
        
        # Cache les données
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,  # 1 minutes
            tag=(client_id, 'users')
        )
        
        return Response(cached_data)
    
    @action(detail=False, methods=['post'], url_path='grant-superuser', throttle_classes=[SensitiveActionThrottle, StandardRateThrottle])
    def grant_superuser(self, request):  
        """
        Accorder le statut superuser à un utilisateur
        POST /client/users/grant-superuser/
        
        Body:
        {
            "user_id": "uuid",
            "grant": true/false  // true pour accorder, false pour retirer
        }
        
        Permissions:
        - Accessible uniquement aux Admin et SuperUser
        """
        try:
            # Vérifier les permissions
            if not self._can_grant_superuser(request.user):
                raise StandardizedValidationError(
                    "Only administrators and superusers can grant or revoke superuser status"
                )
            
            # Récupérer les paramètres
            user_id = request.data.get('user_id')
            grant = request.data.get('grant', True)
            
            if not user_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='user_id')
                )
            
            # Récupérer l'utilisateur cible
            client_id = self.get_client_id()
            try:
                target_user = User.objects.get(
                    id=user_id,
                    client_account_id=client_id
                )
            except User.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            
            # Vérifier qu'on ne modifie pas son propre statut
            if target_user == request.user:
                raise StandardizedValidationError(
                    "You cannot modify your own superuser status"
                )
            
            # Si on retire le statut, vérifier que ce n'est pas le dernier
            if not grant and target_user.is_superuser:
                other_superusers = User.objects.filter(
                    client_account_id=client_id,
                    is_superuser=True
                ).exclude(id=target_user.id).count()
                
                if other_superusers == 0:
                    raise StandardizedValidationError(
                        "Cannot remove superuser status from the last superuser"
                    )
            
            # Appliquer le changement
            with transaction.atomic():
                target_user.is_superuser = grant
                if grant:
                    target_user.is_staff = True  # Superuser doit avoir is_staff
                target_user.save(update_fields=['is_superuser', 'is_staff', 'updated_at'])

                audit_log(
                    event='superuser_status_changed',
                    action='grant_superuser',
                    actor_id=str(request.user.id),
                    client_id=str(client_id),
                    target_type='user',
                    target_id=str(target_user.id),
                    outcome='success',
                    extra={'granted': bool(grant)}
                )
                
                # Assurer les invariants
                target_user.client_account.ensure_admin_invariants()
            
            return Response({
                'success': True,
                'message': f"Superuser status {'granted' if grant else 'revoked'} successfully",
                'user': {
                    'id': str(target_user.id),
                    'email': target_user.email,
                    'name': target_user.get_full_name(),
                    'is_superuser': target_user.is_superuser,
                    'is_staff': target_user.is_staff
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
