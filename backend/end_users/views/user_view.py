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
from core.throttling import PasswordChangeThrottle, SensitiveActionThrottle, BurstRateThrottle
from core.cache_utils import build_drf_cache_key, cache_get_set, get_permissions_version, disable_signals, invalidate_tag
from ..serializers.user_serializer import (
    UserSerializer,
    UserListSerializer,

)
import logging
from django.conf import settings

from core.logging import get_logger, ctx_from_request
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
            'scope': 'client'     # Admin can create users in their client
        },
        'bulk_update': {
            'crud': 'update',
            'scope': 'client'     # Admin can update users in their client
        },
        'bulk_delete': {
            'crud': 'delete',
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
        print(f"[UserViewSet] get_queryset called - action: {self.action}")

        queryset = super().get_queryset()

        print(f"[UserViewSet] Queryset count after super: {queryset.count()}")

        # Debug pour comprendre ce qui se passe
        print(f"[DEBUG] Action: {self.action}")
        print(f"[DEBUG] User tier: {getattr(self.request, '_user_tier', 'unknown')}")
        print(f"[DEBUG] Queryset count before: {queryset.count()}")
        print(f"[DEBUG] Queryset count after super: {queryset.count()}")
        
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
            
            if settings.DEBUG:
                print("[UserViewSet] Applied list optimizations: select_related + annotations for is_manager")
        
        elif self.action == 'retrieve':
            # ✅ OPTIMISATION: Pas de prefetch_related pour retrieve simple
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            )
            # ❌ SUPPRIMÉ: .prefetch_related('managed_teams', 'managed_organizations')
            if settings.DEBUG:
                print("[UserViewSet] Applied retrieve optimizations: select_related only (no prefetch)")
        
        elif self.action in ['managed_users_performance', 'managers']:
            # Garder prefetch seulement pour les actions qui en ont vraiment besoin
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            ).prefetch_related(
                'managed_teams', 'managed_organizations'
            )
            if settings.DEBUG:
                print("[UserViewSet] Applied full optimizations for manager actions")
        
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
        
        return queryset
    
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
                return {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND, "status": 404}
        
        # Cache les données
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=180,  # 3 minutes
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
        
        Cache: 120s sur les données sérialisées (dict Python, pas Response)
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
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            
            # Pas de pagination
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data
        
        # Cache les données (dict Python, pas Response)
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=120,
            tag=(client_id, 'users')
        )
        
        # Logging
        ctx = ctx_from_request(request)
        if isinstance(cached_data, dict) and 'count' in cached_data:
            total = cached_data['count']
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

            ctx = ctx_from_request(request)
            ctx.update({
                "new_user_id": str(user.id),
                "event": "user_create_success",
                "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
            })
            logger.info("user_create_success", extra=ctx)

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

                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(user.id),
                    "changed_fields": changed_fields,
                    "is_self": str(user.id) == str(request.user.id),
                    "event": "user_update_success",
                    "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
                })
                logger.info("user_update_success", extra=ctx)

                return Response({
                    "success": True,
                    'message': f'User "{updated_user.get_full_name()}" updated successfully',
                    "data": UserSerializer(updated_user).data,
                })

        except (User.DoesNotExist, Http404):

            ctx = ctx_from_request(request)
            ctx.update({
                "event": "user_update_not_found",
                "resource": "user",
                "target_id": str(kwargs.get('pk', '-')),
                "action": "update",
                "scope": "client",
            })
            logger.info("user_update_not_found", extra=ctx)

            return Response(
                {"success": False, "error": UsersErrorMessages.USER_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)

    
    @action(detail=True, methods=['patch'], url_path='change-password', throttle_classes=[PasswordChangeThrottle, BurstRateThrottle])
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

                ctx = ctx_from_request(request)
                ctx.update({
                    "event": "user_delete_not_found",
                    "resource": "user",
                    "target_id": str(kwargs.get('pk', '-')),
                    "action": "delete",
                    "scope": "client",
                })
                logger.info("user_delete_not_found", extra=ctx)

                # return Response({
                #     'success': False,
                #     'error': UsersErrorMessages.USER_NOT_FOUND
                # }, status=status.HTTP_404_NOT_FOUND)

                user = self.get_object()

                # Mémoriser le client avant suppression
                client = user.client_account

                # Validation client scoping
                self.validate_client_id(user)

                # Vérifications métier avant suppression
                self._validate_user_deletion(user)

                user_name = user.get_full_name()
                user.delete()

                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(user.id),
                    "deleted_user_name": user_name,
                    "event": "user_delete_success",
                    "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
                })
                logger.info("user_delete_success", extra=ctx)

                # Filet de sécurité: s'assurer qu'un admin existe toujours
                client.ensure_admin_invariants()

                return Response({
                    'success': True,
                    'message': f'User "{user_name}" deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)

        except (User.DoesNotExist, Http404):

            ctx = ctx_from_request(request)
            ctx.update({
                "event": "user_delete_not_found",
                "resource": "user",
                "target_id": str(kwargs.get('pk', '-')),
                "action": "delete",
                "scope": "client",
            })
            logger.info("user_delete_not_found", extra=ctx)

            return Response({
                'success': False,
                'error': UsersErrorMessages.USER_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
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
                user = self.get_object()

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
                
                # 2. Empêcher de supprimer le dernier admin actif
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
                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(user.id),
                    "archived_user_name": user_name,
                    "archived_user_email": user_email,
                    "was_already_inactive": was_already_inactive,
                    "event": "user_soft_delete_success",
                    "role_name": request.user.role_name if hasattr(request.user, 'role_name') else '-',
                })
                logger.info("user_soft_delete_success", extra=ctx)

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
            ctx = ctx_from_request(request)
            ctx.update({
                "event": "user_soft_delete_not_found",
                "resource": "user",
                "target_id": str(pk),
                "action": "soft_delete",
                "scope": "client",
            })
            logger.info("user_soft_delete_not_found", extra=ctx)

            return Response({
                'success': False,
                'error': UsersErrorMessages.USER_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return self.handle_exception(e)
        
    # =============== BULK ACTIONS =======================

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Create multiple users in bulk - VERSION DEBUG
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_create_users',
            'client_id': self.get_client_id()
        })

        # raise PermissionDenied("Test 403: You do not have permission to view users")
        # raise Exception("Test 500: Simulated server error")
        # from rest_framework.response import Response
        # raise Http404("Ressource introuvable")
        # return Response(
        #     {"detail": "sssmendouuu"},
        #     status=429
        # )
        # import time
        # time.sleep(3)  # Simuler lenteur
        # from rest_framework.response import Response
        # return Response(
        #     {"detail": "Request timeout"},
        #     status=429
        # )

        try:
            # Validate input
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")

            users_data = request.data.get('users', [])
            mode = request.data.get('mode', 'partial')

            if not isinstance(users_data, list):
                raise StandardizedValidationError("'users' must be a list")

            if not users_data:
                raise StandardizedValidationError("No users provided")

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(
                    f"Invalid mode '{mode}'. Choose 'partial' or 'strict'"
                )

            ctx['users_count'] = len(users_data)
            ctx['mode'] = mode
            logger.info("Starting bulk user creation", extra=ctx)

            # Initialize results
            results = {
                'success': [],
                'failed': [],
                'skipped': []
            }

            # Pre-check for duplicate emails
            seen_emails = {}
            for idx, user_data in enumerate(users_data):
                row_num = idx + 1
                email = (user_data.get('email') or '').lower().strip()
                if not email:
                    continue
                if email in seen_emails:
                    results['skipped'].append({
                        'row': row_num,
                        'email': email,
                        'error': f'Duplicate email in request (first at row {seen_emails[email]})'
                    })
                else:
                    seen_emails[email] = row_num

            if mode == 'strict' and results['skipped']:
                return self._build_bulk_error_response(
                    results, 
                    len(users_data),
                    f"Strict mode: {len(results['skipped'])} duplicate(s) found in request"
                )

            client_id = self.get_client_id()

            # ⭐ NOUVEAU: Désactiver signals pendant bulk operation
            with disable_signals():
                if mode == 'strict':
                    # All must succeed or none
                    try:
                        with transaction.atomic():
                            for idx, user_data in enumerate(users_data):
                                row_num = idx + 1
                                
                                if any(s['row'] == row_num for s in results['skipped']):
                                    continue

                                user_data = user_data.copy()
                                user_data['client_account'] = client_id

                                self._resolve_role_name(user_data)
                                self._validate_superuser_modification(request.user, user_data)

                                serializer = self.get_serializer(
                                    data=user_data,
                                    context=self.get_serializer_context()
                                )
                                serializer.is_valid(raise_exception=True)
                                user = serializer.save()

                                results['success'].append({
                                    'row': row_num,
                                    'email': user.email,
                                    'id': str(user.id),
                                    'name': user.get_full_name()
                                })
                            
                            # ⭐ NOUVEAU: Invalidation unique APRÈS commit
                            transaction.on_commit(
                                lambda: invalidate_tag(client_id, 'users')
                            )
                            
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        ctx['event'] = 'bulk_create_strict_mode_failed'
                        ctx['error'] = error_msg
                        logger.error("Bulk create strict mode failed", extra=ctx, exc_info=True)
                        
                        return self._build_bulk_error_response(
                            {'success': [], 'failed': [], 'skipped': results['skipped']}, 
                            len(users_data),
                            f"Strict mode failed: {error_msg}"
                        )
                else:
                    # Partial mode
                    for idx, user_data in enumerate(users_data):
                        row_num = idx + 1
                        email_display = user_data.get('email', 'Unknown')

                        if any(s['row'] == row_num for s in results['skipped']):
                            continue

                        with transaction.atomic():
                            try:
                                user_data = user_data.copy()
                                user_data['client_account'] = client_id

                                if 'email' in user_data and user_data['email']:
                                    exists = User.objects.filter(
                                        email__iexact=user_data['email']
                                    ).exists()
                                    if exists:
                                        raise StandardizedValidationError(
                                            f"Email address already exists"
                                        )

                                self._resolve_role_name(user_data)
                                self._validate_superuser_modification(request.user, user_data)

                                serializer = self.get_serializer(
                                    data=user_data,
                                    context=self.get_serializer_context()
                                )

                                if serializer.is_valid():
                                    user = serializer.save()
                                    results['success'].append({
                                        'row': row_num,
                                        'email': user.email,
                                        'id': str(user.id),
                                        'name': user.get_full_name()
                                    })
                                else:
                                    errors = self._format_serializer_errors(serializer.errors)
                                    results['failed'].append({
                                        'row': row_num,
                                        'email': email_display,
                                        'errors': errors
                                    })
                                    transaction.set_rollback(True)
                                    
                            except StandardizedValidationError as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'email': email_display,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                            except Exception as e:
                                ctx['event'] = 'bulk_create_unexpected_error'
                                ctx['row'] = row_num
                                ctx['error'] = str(e)
                                logger.error("Unexpected error in bulk create", extra=ctx, exc_info=True)
                                
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'email': email_display,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                    
                    # ⭐ NOUVEAU: Invalidation unique en mode partial
                    invalidate_tag(client_id, 'users')

            # Build successful response
            return self._build_bulk_success_response(results, len(users_data), operation='create')

        except StandardizedValidationError as e:
            # Extract message properly from detail dict
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            # Use the existing _build_bulk_error_response helper
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )
        

    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Update multiple users in bulk
        """
        ctx = ctx_from_request(request) 
        ctx.update({
            'event': 'bulk_update_users',
            'client_id': self.get_client_id()
        })

        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")

            ids = request.data.get('ids', [])
            patch = request.data.get('patch', {})
            mode = request.data.get('mode', 'partial')

            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
                )

            if not ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_NO_DATA.format(entity="user IDs")
                )

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            if not isinstance(patch, dict):
                raise StandardizedValidationError("Patch data must be a JSON object")

            if not patch:
                raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_NO_FIELDS)

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            ctx['ids_count'] = len(ids)
            ctx['mode'] = mode
            logger.info("Starting bulk user update", extra=ctx)

            # ===== VALIDATE ALLOWED FIELDS =====
            ALLOWED_FIELDS = {'is_active', 'is_superuser', 'role', 'team', 'organization'}
            invalid_fields = set(patch.keys()) - ALLOWED_FIELDS
            
            if invalid_fields:
                raise StandardizedValidationError(
                    f"Fields not allowed in bulk update: {', '.join(invalid_fields)}. "
                    f"Allowed fields: {', '.join(ALLOWED_FIELDS)}"
                )

            # ===== SECURITY: PREVENT SELF-MODIFICATION =====
            requester_id = str(request.user.id)
            if requester_id in ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_UPDATE_SELF_MODIFY
                )

            # ===== FETCH USERS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            users_qs = User.objects.filter(
                id__in=ids,
                client_account_id=client_id
            ).select_related('role', 'team', 'organization', 'client_account')
            users_dict = {str(u.id): u for u in users_qs}

            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(users_dict.keys())
            
            results = {
                'success': [],
                'failed': [],
                'skipped': [] 
            }

            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'email': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_UPDATE_INVALID_ID.format(id=invalid_id)]
                })

            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )

            # Désactiver signals pendant bulk operation
            with disable_signals():
                if mode == 'strict':
                    try:
                        with transaction.atomic():
                            for user_id in ids:
                                if user_id in invalid_ids:
                                    continue
                                user = users_dict[user_id]
                                
                                try:
                                    self._validate_and_apply_patch(user, patch, client_id)
                                    
                                    results['success'].append({
                                        'id': str(user.id),
                                        'email': user.email,
                                        'name': user.get_full_name()
                                    })
                                except StandardizedValidationError as e:
                                    error_msg = self._format_bulk_error_message(e)
                                    results['failed'].append({
                                        'id': user_id,
                                        'email': user.email,
                                        'errors': [error_msg]
                                    })
                                    raise
                            
                            # ⭐ NOUVEAU: Invalidation unique APRÈS commit
                            transaction.on_commit(
                                lambda: invalidate_tag(client_id, 'users')
                            )
                            
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        ctx['event'] = 'bulk_update_strict_mode_failed'
                        ctx['error'] = error_msg
                        logger.error("Bulk update strict mode failed", extra=ctx, exc_info=True)
                        
                        return self._build_bulk_error_response(
                            {'success': [], 'failed': results['failed']},
                            len(ids),
                            f"Strict mode failed: {error_msg}"
                        )
                else:
                    # Partial mode
                    totalCount = 0
                    for user_id in ids:
                        totalCount += 1
                        if user_id in invalid_ids:
                            continue
                        user = users_dict[user_id]
                        
                        with transaction.atomic():
                            try:
                                self._validate_and_apply_patch(user, patch, client_id)
                                
                                results['success'].append({
                                    'id': str(user.id),
                                    'email': user.email,
                                    'name': user.get_full_name()
                                })
                            except StandardizedValidationError as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                            except Exception as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                                ctx['event'] = 'bulk_update_unexpected_error'
                                ctx['user_id'] = user_id
                                ctx['error'] = str(e)
                                logger.error("Unexpected error in bulk update", extra=ctx, exc_info=True)
                    
                    # ⭐ NOUVEAU: Invalidation unique en mode partial
                    invalidate_tag(client_id, 'users')

            return self._build_bulk_success_response(results, len(ids), operation='update')

        except StandardizedValidationError as e:
            # ✅ FIX: Extract message properly from detail dict
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            ctx['event'] = 'bulk_update_validation_error'
            ctx['error'] = error_msg
            logger.warning("Bulk update validation error", extra=ctx)
            
            # ✅ Use bulk error response format (matches existing pattern)
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )

        except Exception as e:
            ctx['event'] = 'bulk_update_fatal_error'
            ctx['error'] = str(e)
            logger.error("Fatal error in bulk update", extra=ctx, exc_info=True)
            
            # ✅ Use bulk error response format (matches existing pattern in bulk operations)
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message='An unexpected error occurred. Please try again or contact support.'
            )


        
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Physically delete multiple users in bulk (hard delete)
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_delete_users_hard',
            'client_id': self.get_client_id()
        })

        # raise PermissionDenied("Test 403: You do not have permission to view users")
        # raise Exception("Test 500: Simulated server error")
        # from rest_framework.response import Response
        # raise Http404("Ressource introuvable")
        # return Response(
        #     {"detail": "sssmendouuu"},
        #     status=429
        # )
        # import time
        # time.sleep(3)  # Simuler lenteur
        # from rest_framework.response import Response
        # return Response(
        #     {"detail": "Request timeout"},
        #     status=429
        # )


        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")

            ids = request.data.get('ids', [])
            mode = request.data.get('mode', 'partial')

            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
                )

            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            ctx['ids_count'] = len(ids)
            ctx['mode'] = mode
            logger.info("Starting bulk user delete (hard)", extra=ctx)

            # ===== SECURITY: PREVENT SELF-DELETE =====
            requester_id = str(request.user.id)
            if requester_id in ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_SELF)

            # ===== FETCH USERS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            users_qs = User.objects.filter(
                id__in=ids,
                client_account_id=client_id
            ).select_related('role', 'team', 'organization', 'client_account')
            users_dict = {str(u.id): u for u in users_qs}

            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(users_dict.keys())
            
            results = {
                'success': [],
                'failed': []
            }

            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'email': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_DELETE_INVALID_ID.format(id=invalid_id)]
                })

            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )

            # ===== PRE-VALIDATION: CHECK FOR PROTECTED USERS =====
            protected_users = []
            
            for user_id in ids:
                if user_id in invalid_ids:
                    continue
                    
                user = users_dict[user_id]
                
                if user.is_last_active_admin():
                    protected_users.append({
                        'id': str(user.id),
                        'email': user.email,
                        'reason': CoreErrorMessages.BULK_DELETE_LAST_ADMIN.format(email=user.email)
                    })

            if mode == 'strict' and protected_users:
                for protected in protected_users:
                    results['failed'].append({
                        'id': protected['id'],
                        'email': protected['email'],
                        'errors': [protected['reason']]
                    })
                
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(protected_users)} protected user(s) found"
                )

            # Désactiver signals pendant bulk operation
            with disable_signals():
                if mode == 'strict':
                    try:
                        with transaction.atomic():
                            for user_id in ids:
                                if user_id in invalid_ids:
                                    continue
                                user = users_dict[user_id]
                                
                                try:
                                    user_email = user.email
                                    user_name = user.get_full_name()
                                    user.delete()
                                    
                                    results['success'].append({
                                        'id': user_id,
                                        'email': user_email,
                                        'name': user_name
                                    })
                                except Exception as e:
                                    error_msg = self._format_bulk_error_message(e)
                                    results['failed'].append({
                                        'id': user_id,
                                        'email': user.email,
                                        'errors': [error_msg]
                                    })
                                    raise
                            
                            # Ensure admin invariants
                            client = User.objects.get(id=requester_id).client_account
                            client.ensure_admin_invariants()
                            
                            # ⭐ NOUVEAU: Invalidation unique APRÈS commit
                            transaction.on_commit(
                                lambda: invalidate_tag(client_id, 'users')
                            )
                            
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        ctx['event'] = 'bulk_delete_strict_mode_failed'
                        ctx['error'] = error_msg
                        logger.error("Bulk delete strict mode failed", extra=ctx, exc_info=True)
                        
                        return self._build_bulk_error_response(
                            {'success': [], 'failed': results['failed']},
                            len(ids),
                            f"Strict mode failed: {error_msg}"
                        )
                else:
                    # Partial mode
                    for user_id in ids:
                        

                        if user_id in invalid_ids:
                            continue

                        is_protected = any(p['id'] == user_id for p in protected_users)
                        if is_protected:
                            protected_info = next(p for p in protected_users if p['id'] == user_id)
                            results['failed'].append({
                                'id': user_id,
                                'email': protected_info['email'],
                                'errors': [protected_info['reason']]
                            })
                            continue
                        
                        user = users_dict[user_id]
                        
                        with transaction.atomic():
                            try:
                                user_email = user.email
                                user_name = user.get_full_name()
                                user.delete()
                                
                                results['success'].append({
                                    'id': user_id,
                                    'email': user_email,
                                    'name': user_name
                                })
                            except Exception as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                                ctx['event'] = 'bulk_delete_unexpected_error'
                                ctx['user_id'] = user_id
                                ctx['error'] = str(e)
                                logger.error("Unexpected error in bulk delete", extra=ctx, exc_info=True)
                    
                    # Ensure admin invariants (partial mode)
                    try:
                        client = User.objects.get(id=requester_id).client_account
                        client.ensure_admin_invariants()
                    except Exception as e:
                        logger.warning(f"Failed to ensure admin invariants: {e}", extra=ctx)
                    
                    # ⭐ NOUVEAU: Invalidation unique en mode partial
                    invalidate_tag(client_id, 'users')

            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])

            ctx.update({
                'event': 'bulk_delete_users_completed',
                'requested': len(ids),
                'deleted': success_count,
                'failed': failed_count
            })
            logger.info("Bulk user deletion completed", extra=ctx)

            clean_results = {
                'success': results['success'][:],
                'failed': []
            }
            
            for failed_item in results['failed']:
                clean_item = failed_item.copy()
                if 'errors' in clean_item:
                    clean_item['errors'] = [str(error) for error in clean_item['errors']]
                clean_results['failed'].append(clean_item)

            if success_count == 0 and failed_count > 0:
                status_code = status.HTTP_400_BAD_REQUEST
                success = False
                message = f"Bulk delete failed: all {failed_count} user(s) failed"
            elif failed_count > 0:
                status_code = status.HTTP_200_OK
                success = True
                message = f"Bulk delete: {success_count} deleted, {failed_count} failed"
            else:
                status_code = status.HTTP_200_OK
                success = True
                message = f"Bulk delete: {success_count} user(s) deleted successfully"

            # return Response({
            #     'success': success,
            #     'summary': {
            #         'requested': len(ids),
            #         'deleted': success_count,
            #         'failed': failed_count
            #     },
            #     'results': clean_results,
            #     'message': message
            # }, status=status_code)

            return self._build_bulk_success_response(results, len(ids), operation='delete')

        except StandardizedValidationError as e:
            # Extract message properly from detail dict
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            # Use the existing _build_bulk_error_response helper
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )
        
    @action(detail=False, methods=['delete'], url_path='bulk-soft-delete')
    def bulk_soft_delete(self, request):
        """
        Soft delete multiple users in bulk (set is_active=False)
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_soft_delete_users',
            'client_id': self.get_client_id()
        })

        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")

            ids = request.data.get('ids', [])
            mode = request.data.get('mode', 'partial')

            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
                )

            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            ctx['ids_count'] = len(ids)
            ctx['mode'] = mode
            logger.info("Starting bulk user soft delete", extra=ctx)

            # ===== SECURITY: PREVENT SELF-DELETE =====
            requester_id = str(request.user.id)
            if requester_id in ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_SELF)

            # ===== FETCH USERS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            users_qs = User.objects.filter(
                id__in=ids,
                client_account_id=client_id
            ).select_related('role', 'team', 'organization', 'client_account')
            users_dict = {str(u.id): u for u in users_qs}

            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(users_dict.keys())
            
            results = {
                'success': [],
                'failed': [],
                'skipped': []
            }

            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'email': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_DELETE_INVALID_ID.format(id=invalid_id)]
                })

            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )

            # ===== PRE-VALIDATION: CHECK FOR PROTECTED USERS & ALREADY INACTIVE =====
            protected_users = []
            
            for user_id in ids:
                if user_id in invalid_ids:
                    continue
                    
                user = users_dict[user_id]
                
                if not user.is_active:
                    results['skipped'].append({
                        'id': str(user.id),
                        'email': user.email,
                        'reason': 'Already inactive'
                    })
                    continue
                
                if user.is_last_active_admin():
                    protected_users.append({
                        'id': str(user.id),
                        'email': user.email,
                        'reason': CoreErrorMessages.BULK_DELETE_LAST_ADMIN.format(email=user.email)
                    })

            if mode == 'strict' and (protected_users or results['skipped']):
                for protected in protected_users:
                    results['failed'].append({
                        'id': protected['id'],
                        'email': protected['email'],
                        'errors': [protected['reason']]
                    })
                
                error_count = len(protected_users) + len(results['skipped'])
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {error_count} user(s) cannot be archived"
                )

            # ⭐ NOUVEAU: Désactiver signals pendant bulk operation
            with disable_signals():
                if mode == 'strict':
                    try:
                        with transaction.atomic():
                            for user_id in ids:
                                if user_id in invalid_ids:
                                    continue
                                
                                if any(s['id'] == user_id for s in results['skipped']):
                                    continue
                                
                                user = users_dict[user_id]
                                
                                try:
                                    user.is_active = False
                                    user.save(update_fields=['is_active', 'updated_at'])
                                    
                                    results['success'].append({
                                        'id': str(user.id),
                                        'email': user.email,
                                        'name': user.get_full_name()
                                    })
                                except Exception as e:
                                    error_msg = self._format_bulk_error_message(e)
                                    results['failed'].append({
                                        'id': user_id,
                                        'email': user.email,
                                        'errors': [error_msg]
                                    })
                                    raise
                            
                            # Ensure admin invariants
                            client = User.objects.get(id=requester_id).client_account
                            client.ensure_admin_invariants()
                            
                            # ⭐ NOUVEAU: Invalidation unique APRÈS commit
                            transaction.on_commit(
                                lambda: invalidate_tag(client_id, 'users')
                            )
                            
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        ctx['event'] = 'bulk_soft_delete_strict_mode_failed'
                        ctx['error'] = error_msg
                        logger.error("Bulk soft delete strict mode failed", extra=ctx, exc_info=True)
                        
                        return self._build_bulk_error_response(
                            {'success': [], 'failed': results['failed'], 'skipped': results['skipped']},
                            len(ids),
                            f"Strict mode failed: {error_msg}"
                        )
                else:
                    # Partial mode
                    for user_id in ids:
                        if user_id in invalid_ids:
                            continue
                        
                        if any(s['id'] == user_id for s in results['skipped']):
                            continue
                        
                        is_protected = any(p['id'] == user_id for p in protected_users)
                        if is_protected:
                            protected_info = next(p for p in protected_users if p['id'] == user_id)
                            results['failed'].append({
                                'id': user_id,
                                'email': protected_info['email'],
                                'errors': [protected_info['reason']]
                            })
                            continue
                        
                        user = users_dict[user_id]
                        
                        with transaction.atomic():
                            try:
                                user.is_active = False
                                user.save(update_fields=['is_active', 'updated_at'])
                                
                                results['success'].append({
                                    'id': str(user.id),
                                    'email': user.email,
                                    'name': user.get_full_name()
                                })
                            except Exception as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                                ctx['event'] = 'bulk_soft_delete_unexpected_error'
                                ctx['user_id'] = user_id
                                ctx['error'] = str(e)
                                logger.error("Unexpected error in bulk soft delete", extra=ctx, exc_info=True)
                    
                    # Ensure admin invariants (partial mode)
                    try:
                        client = User.objects.get(id=requester_id).client_account
                        client.ensure_admin_invariants()
                    except Exception as e:
                        logger.warning(f"Failed to ensure admin invariants: {e}", extra=ctx)
                    
                    # ⭐ NOUVEAU: Invalidation unique en mode partial
                    invalidate_tag(client_id, 'users')

            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            skipped_count = len(results['skipped'])

            ctx.update({
                'event': 'bulk_soft_delete_users_completed',
                'requested': len(ids),
                'archived': success_count,
                'failed': failed_count,
                'skipped': skipped_count
            })
            logger.info("Bulk user soft deletion completed", extra=ctx)

            clean_results = {
                'success': results['success'][:],
                'failed': [],
                'skipped': []
            }
            
            for failed_item in results['failed']:
                clean_item = failed_item.copy()
                if 'errors' in clean_item:
                    clean_item['errors'] = [str(error) for error in clean_item['errors']]
                clean_results['failed'].append(clean_item)
            
            for skipped_item in results['skipped']:
                clean_item = skipped_item.copy()
                if 'reason' in clean_item:
                    clean_item['reason'] = str(clean_item['reason'])
                clean_results['skipped'].append(clean_item)

            if success_count == 0 and failed_count > 0:
                status_code = status.HTTP_400_BAD_REQUEST
                success = False
                message = f"Bulk archive failed: all {failed_count} user(s) failed"
            elif failed_count > 0:
                status_code = status.HTTP_200_OK
                success = True
                message = f"Bulk archive: {success_count} archived, {failed_count} failed"
            else:
                status_code = status.HTTP_200_OK
                success = True
                message = f"Bulk archive: {success_count} user(s) archived successfully"

            # return Response({
            #     'success': success,
            #     'summary': {
            #         'requested': len(ids),
            #         'archived': success_count,
            #         'failed': failed_count,
            #         'skipped': skipped_count
            #     },
            #     'results': clean_results,
            #     'message': message
            # }, status=status_code)

            return self._build_bulk_success_response(results, len(ids), operation='archive')

        except StandardizedValidationError as e:
            # Extract message properly from detail dict
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            # Use the existing _build_bulk_error_response helper
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )
            
    def _validate_and_apply_patch(self, user, patch, client_id):
        """
        Validate and apply patch to a user
        
        Args:
            user: User instance to update
            patch: Dict of fields to update
            client_id: Current client ID for validation
            
        Raises:
            StandardizedValidationError: If validation fails
        """
        from ..models import UserRole, Team, Organization
        
        # Track what will change
        changes = {}
        
        # ===== VALIDATE AND PREPARE CHANGES =====
        
        # 1. is_active
        if 'is_active' in patch:
            new_active = patch['is_active']
            if not isinstance(new_active, bool):
                raise StandardizedValidationError(
                    "is_active must be a boolean"
                )
            
            # Prevent deactivating last active admin
            if new_active is False and user.is_active:
                if user.is_last_active_admin():
                    raise StandardizedValidationError(
                        f"Cannot deactivate user '{user.email}': last active administrator. "
                        "Promote another user first."
                    )
            
            changes['is_active'] = new_active

        # 2. is_superuser
        if 'is_superuser' in patch:
            new_superuser = patch['is_superuser']
            if not isinstance(new_superuser, bool):
                raise StandardizedValidationError(
                    "is_superuser must be a boolean"
                )
            
            # Prevent removing superuser status from last superuser
            if new_superuser is False and user.is_superuser:
                if user.is_last_superuser():
                    raise StandardizedValidationError(
                        f"Cannot remove superuser status from user '{user.email}': last superuser. "
                        "Promote another user first."
                    )
            
            changes['is_superuser'] = new_superuser
            # If promoting to superuser, must also have is_staff
            if new_superuser is True:
                changes['is_staff'] = True

        # 3. role
        if 'role' in patch:
            role_id = patch['role']
            
            if role_id is None or role_id == '':
                changes['role'] = None
                changes['role_name'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(role_id))
                except ValueError:
                    raise StandardizedValidationError(
                        f"Invalid role ID format: {role_id}"
                    )
                
                # Fetch role
                try:
                    role = UserRole.objects.get(
                        id=role_id,
                        client_account_id=client_id
                    )
                    changes['role'] = role
                    changes['role_name'] = role.name
                except UserRole.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.BULK_CREATE_INVALID_ROLE.format(role=role_id)
                    )

        # 4. organization
        if 'organization' in patch:
            org_id = patch['organization']
            
            if org_id is None or org_id == '':
                changes['organization'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(org_id))
                except ValueError:
                    raise StandardizedValidationError(
                        f"Invalid organization ID format: {org_id}"
                    )
                
                # Fetch organization
                try:
                    organization = Organization.objects.get(
                        id=org_id,
                        client_account_id=client_id
                    )
                    changes['organization'] = organization
                except Organization.DoesNotExist:
                    raise StandardizedValidationError(
                        f"Organization '{org_id}' not found or doesn't belong to this client"
                    )

        # 5. team
        if 'team' in patch:
            team_id = patch['team']
            
            if team_id is None or team_id == '':
                changes['team'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(team_id))
                except ValueError:
                    raise StandardizedValidationError(
                        f"Invalid team ID format: {team_id}"
                    )
                
                # Fetch team
                try:
                    team = Team.objects.select_related('organization').get(
                        id=team_id,
                        organization__client_account_id=client_id
                    )
                    
                    # Verify team belongs to user's organization
                    if user.organization and str(team.organization_id) != str(user.organization_id):
                        raise StandardizedValidationError(
                            f"Team '{team.name}' does not belong to user's organization"
                        )
                    
                    changes['team'] = team
                except Team.DoesNotExist:
                    raise StandardizedValidationError(
                        f"Team '{team_id}' not found or doesn't belong to this client"
                    )

        # 4. first_name
        if 'first_name' in patch:
            first_name = patch['first_name']
            if first_name is not None:
                first_name = str(first_name).strip()
                if len(first_name) > 50:
                    raise StandardizedValidationError(
                        "first_name must be 50 characters or less"
                    )
            changes['first_name'] = first_name

        # 5. last_name
        if 'last_name' in patch:
            last_name = patch['last_name']
            if last_name is not None:
                last_name = str(last_name).strip()
                if len(last_name) > 50:
                    raise StandardizedValidationError(
                        "last_name must be 50 characters or less"
                    )
            changes['last_name'] = last_name

        # ===== APPLY CHANGES =====
        if not changes:
            raise StandardizedValidationError(
                "No valid changes to apply"
            )

        for field, value in changes.items():
            setattr(user, field, value)
        
        user.save()
    
    def _resolve_role_name(self, user_data):
        """
        Convert role name to ID if needed
        Modifies user_data in place
        """
        # Import at the beginning to avoid UnboundLocalError
        from ..models import UserRole
        import uuid
        
        if 'role' not in user_data or not user_data['role']:
            return
            
        role_value = user_data['role']
        
        # If it's already None or empty, do nothing
        if not role_value:
            return
        
        # If it's a string, check if it's a UUID or a name
        if isinstance(role_value, str):
            try:
                # Try to parse as UUID
                uuid.UUID(role_value)
                # It's already a valid UUID, do nothing
                return
            except ValueError:
                # It's not a UUID, it's probably a role name
                # Search for the role by name
                role = UserRole.objects.filter(
                    client_account_id=self.get_client_id(),
                    name__iexact=role_value.strip()
                ).first()
                
                if role:
                    user_data['role'] = str(role.id)
                else:
                    # If role not found, raise exception
                    raise StandardizedValidationError(
                        f"Role '{role_value}' not found"
                    )

    def _format_bulk_error_message(self, error):
        """
        Format error message for user-friendly display
        """
        error_type = type(error).__name__
        
        # Handle specific error types
        if isinstance(error, StandardizedValidationError):
            if hasattr(error, 'detail'):
                if isinstance(error.detail, dict):
                    return error.detail.get('error', str(error))
                elif isinstance(error.detail, list):
                    return ', '.join(str(x) for x in error.detail)
                elif error.detail:
                    return str(error.detail)
            return str(error)
        
        # Handle common Python errors
        elif "UnboundLocalError" in error_type:
            return "Internal configuration error. Please contact support."
        elif "ValueError" in error_type and "UUID" in str(error):
            return "Invalid ID format provided"
        elif "DoesNotExist" in error_type:
            return "Referenced resource not found"
        elif "IntegrityError" in error_type:
            return "Data integrity error. Check for duplicates or invalid references."
        
        # Generic error
        return "Processing failed. Please check your data and try again."

    def _format_serializer_errors(self, errors):
        """
        Format DRF serializer errors into list of strings
        """
        formatted = []
        for field, field_errors in errors.items():
            if isinstance(field_errors, list):
                for error in field_errors:
                    if field == 'non_field_errors':
                        formatted.append(str(error))
                    else:
                        # Make field names user-friendly
                        field_name = field.replace('_', ' ').title()
                        formatted.append(f"{field_name}: {error}")
            else:
                field_name = field.replace('_', ' ').title()
                formatted.append(f"{field_name}: {field_errors}")
        return formatted

    def _build_bulk_error_response(self, results, total, error_message):
        """
        Build error response for bulk operation
        """
        return Response({
            'success': False,
            'message': error_message,
            'summary': {
                'total': total,
                'success': len(results.get('success', [])),
                'failed': len(results.get('failed', [])),
                'skipped': len(results.get('skipped', []))
            },
            'results': results
        }, status=status.HTTP_400_BAD_REQUEST)

    def _build_bulk_success_response(self, results, total, operation='create'):
        """
        Build success/partial success response for bulk operation
        
        This method creates standardized responses for bulk operations with
        intelligent status determination and operation-specific messaging.
        
        Args:
            results (dict): Dict with 'success', 'failed', 'skipped' lists
            total (int): Total number of items requested
            operation (str): Type of operation - 'create', 'update', 'delete', or 'archive'
        
        Returns:
            Response: DRF Response object with appropriate status code
            
        Response Format:
            {
                'success': True | 'partial' | False,
                'message': str,
                'summary': {
                    'requested': int,
                    'updated': int,  # or 'created', 'deleted', 'archived'
                    'failed': int,
                    'skipped': int
                },
                'results': {
                    'success': [...],
                    'failed': [...],
                    'skipped': [...]
                }
            }
        
        Status Determination:
            - success=True: 100% success (failed=0, skipped=0) → HTTP 200/201
            - success='partial': Some succeeded (>0% but <100%) → HTTP 207
            - success=False: Total failure (0% success) → HTTP 400
        """
        from rest_framework import status
        from rest_framework.response import Response
        
        # ====================================================================
        # STEP 1: Count results
        # ====================================================================
        
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        skipped_count = len(results.get('skipped', []))
        
        # ====================================================================
        # STEP 2: Determine success status
        # ====================================================================
        
        if failed_count == 0 and skipped_count == 0:
            # ✅ Full success (100%)
            success_status = True
            status_code = status.HTTP_201_CREATED if operation == 'create' else status.HTTP_200_OK
        elif success_count == 0:
            # ❌ Total failure (0%)
            success_status = False
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            # ⚠️ Partial success (>0% but <100%)
            success_status = 'partial'
            status_code = status.HTTP_207_MULTI_STATUS
        
        # ====================================================================
        # STEP 3: Build operation-specific message
        # ====================================================================
        
        # Map operation to past tense verb and label
        OPERATION_LABELS = {
            'create': ('created', 'Importing Users'),
            'update': ('updated', 'Bulk Update'),
            'delete': ('deleted', 'Bulk Delete'),
            'archive': ('archived', 'Bulk Archive')
        }
        
        verb, operation_label = OPERATION_LABELS.get(
            operation, 
            ('processed', 'Bulk Operation')  # Fallback
        )
        
        # Construct message based on status
        if success_status is True:
            # Full success
            message = f"{operation_label} complete"
        elif success_status == 'partial':
            # Partial success
            message = f"{operation_label} partially complete"
        else:
            # Total failure
            message = f"{operation_label} failed"
        
        # ====================================================================
        # STEP 4: Clean results (convert ErrorDetail to strings)
        # ====================================================================
        
        # CRITICAL: Convert all ErrorDetail objects to strings
        # This prevents serialization issues in DRF Response
        clean_results = {
            'success': results.get('success', [])[:]  # Simple copy (no ErrorDetail here)
        }
        
        # Clean failed items
        clean_failed = []
        for failed_item in results.get('failed', []):
            clean_item = failed_item.copy()
            if 'errors' in clean_item:
                # Convert each ErrorDetail to string
                clean_item['errors'] = [str(error) for error in clean_item['errors']]
            clean_failed.append(clean_item)
        clean_results['failed'] = clean_failed
        
        # Clean skipped items
        clean_skipped = []
        for skipped_item in results.get('skipped', []):
            clean_item = skipped_item.copy()
            if 'error' in clean_item:
                # Convert ErrorDetail to string
                clean_item['error'] = str(clean_item['error'])
            if 'reason' in clean_item:
                # Convert ErrorDetail to string
                clean_item['reason'] = str(clean_item['reason'])
            clean_skipped.append(clean_item)
        clean_results['skipped'] = clean_skipped
        
        # ====================================================================
        # STEP 5: Build summary with operation-specific key
        # ====================================================================
        
        # Use verb as key name (e.g., 'updated', 'created', 'deleted')
        summary = {
            'requested': total,
            verb: success_count,  # Dynamic key: 'created', 'updated', 'deleted', etc.
            'failed': failed_count,
            'skipped': skipped_count
        }
        
        # ====================================================================
        # STEP 6: Log completion
        # ====================================================================
        
        ctx = ctx_from_request(self.request)
        ctx.update({
            'event': f'bulk_{operation}_completed',
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'success_status': str(success_status)
        })
        logger.info(f"Bulk {operation} completed", extra=ctx)
        
        # ====================================================================
        # STEP 7: Return Response
        # ====================================================================
        
        return Response({
            'success': success_status,  # True | 'partial' | False
            'message': message,
            'summary': summary,
            'results': clean_results
        }, status=status_code)
        
    # ====================================================
    
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
        Valider si l'utilisateur peut être supprimé
        UPDATED: Prevent deletion of last superuser
        """
        if user.id == self.request.user.id:
            raise StandardizedValidationError(
                CoreErrorMessages.SELF_DELETE_FORBIDDEN
            )
    
        client = user.client_account
        
        # Check if this is the last superuser
        if user.is_superuser:
            other_superusers = client.users.filter(
                is_superuser=True
            ).exclude(id=user.id).count()
            
            if other_superusers == 0:
                raise StandardizedValidationError(
                    "Cannot delete the last superuser. "
                    "Promote another user to superuser first."
                )
        
        # Ancienne logique pour les rôles (conservée pour compatibilité)
        # Si c'est le dernier admin ET qu'il n'y a pas de superuser
        if user.role and user.role.name == 'Admin':
            # Compter les autres admins ou superusers
            from django.db.models import Q
            other_admins_or_super = client.users.filter(
                Q(role__name='Admin') | Q(is_superuser=True)
            ).exclude(id=user.id).count()
            
            if other_admins_or_super == 0:
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
            ttl=300,  # 5 minutes
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
            ttl=300,  # 5 minutes
            tag=(client_id, 'users')
        )
        
        return Response(cached_data)
    
    @action(detail=False, methods=['post'], url_path='grant-superuser', throttle_classes=[SensitiveActionThrottle, BurstRateThrottle])
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

                ctx = ctx_from_request(request)
                ctx.update({
                    "target_user_id": str(target_user.id),
                    "client_id": client_id,
                    "granted": bool(grant),
                    "event": "superuser_status_changed",
                })
                logger.info("superuser_status_changed", extra=ctx)
                
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
