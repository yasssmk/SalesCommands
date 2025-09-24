# end_users/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from datetime import datetime, date
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from django.http import Http404
from ..models import User
from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from ..serializers.user_serializer import (
    UserSerializer,
    UserListSerializer,

)
import logging
from django.conf import settings

from core.logging import get_logger, ctx_from_request

logger = get_logger(__name__)

class UserViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing users with client scoping and performance integration
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    entity_name = 'user'

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'role', 'team', 'organization', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'created_at']
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
            )
        else:
            # Détails complets
            queryset = queryset.select_related(
                'client_account', 'role', 'team', 'organization'
            ).prefetch_related(
                'managed_teams', 'managed_organizations'
            )
        
        # Filtres spéciaux
        managers_only = self.request.query_params.get('managers_only', None)
        if managers_only and managers_only.lower() == 'true':
            queryset = queryset.filter(
                Q(managed_teams__isnull=False) | Q(managed_organizations__isnull=False)
            ).distinct()
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """
        Récupérer un utilisateur spécifique par son ID
        GET /client/users/{id}/
        """
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
                "target_id": str(kwargs.get('pk', '-')),
                "action": "retrieve",
                "scope": "client",
            })
            logger.info("user_retrieve_not_found", extra=ctx)
            return Response(
                {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        
    def list(self, request, *args, **kwargs):
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
        
    def create(self, request, *args, **kwargs):
        """
        Créer un nouvel utilisateur
        POST /client/users/
        """
        with transaction.atomic():
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
                {"success": False, "error": CoreErrorMessages.OBJECT_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.handle_exception(e)

    
    @action(detail=True, methods=['patch'], url_path='change-password')
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
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un utilisateur
        DELETE /client/users/{id}/
        """
        try:
            with transaction.atomic():
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
                'error': CoreErrorMessages.OBJECT_NOT_FOUND
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
        Valider si l'utilisateur peut être supprimé
        UPDATED: Prevent deletion of last superuser
        """
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
        """Liste des managers avec leurs équipes"""
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
    
    @action(detail=False, methods=['get'], url_path='superusers')
    def superusers(self, request):
        """
        Liste tous les superusers du tenant actuel
        GET /client/users/superusers/
        
        Permissions:
        - Accessible uniquement aux Admin et SuperUser
        
        Returns:
        - Liste des superusers avec leurs informations
        - Statistiques sur les superusers du tenant
        """
        try:
             # Vérifier les permissions - seuls Admin et SuperUser peuvent voir cette liste
            from permissions.compat import get_auth_ctx
            ctx_auth = get_auth_ctx(request)
            is_admin = any(isinstance(r, dict) and r.get('is_admin') for r in ctx_auth.roles) or ctx_auth.is_superuser
            if not is_admin:
                raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
                
            # Récupérer le client_id du contexte pour garantir le multi-tenant
            client_id = self.get_client_id()

            ctx = ctx_from_request(request)
            ctx.update({"event": "superusers_list"})
            logger.debug("superusers_list_access", extra=ctx)
            
            # Filtrer les superusers du tenant actuel
            superusers = self.get_queryset().filter(
                is_superuser=True
            ).select_related('role', 'team', 'organization').order_by('-is_active', 'first_name', 'last_name')
            
            # Préparer les données détaillées pour chaque superuser
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
            
            # Calculer les statistiques
            total_superusers = len(superusers_data)
            active_superusers = superusers.filter(is_active=True).count()
            inactive_superusers = total_superusers - active_superusers
            
            # Compter aussi les admins par rôle pour comparaison
            admin_role_users = self.get_queryset().filter(
                role__name='Admin',
                is_active=True
            ).exclude(is_superuser=True).count()  # Admins qui ne sont PAS superusers
            
            
            return Response({
                'success': True,
                'data': superusers_data,
                'statistics': {
                    'total_superusers': total_superusers,
                    'active_superusers': active_superusers,
                    'inactive_superusers': inactive_superusers,
                    'admin_role_users_non_super': admin_role_users,
                    'total_administrators': active_superusers + admin_role_users  # Total avec droits admin
                },
               'permissions_info': {
                    'description': 'Superusers have full administrative rights within this tenant',
                    'can_grant_superuser': self._can_grant_superuser(request.user),
                    'current_user_is_superuser': request.user.is_superuser
                }
            })
            
        except Exception as e:
            return self.handle_exception(e)
    
    @action(detail=False, methods=['post'], url_path='grant-superuser')
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
