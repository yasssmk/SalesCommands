# end_users/views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import datetime, date, timedelta
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed
from core.error_messages import CoreErrorMessages, AuthErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.auth_service import AuthService
from core.jwt_helpers import CustomJWTAuthentication
from ..models.user_model import ClientAccount, UserRole, Organization, Team, User
from ..serializers.user_serializer import (
    ClientAccountSerializer,
    OrganizationSerializer,
    TeamSerializer,
    UserSerializer,
    UserListSerializer,
    UserPerformanceAccessSerializer
)


class ClientAccountViewSet(BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing client accounts
    Note: Pas de ClientScopeManager car c'est le niveau root du multi-tenant
    """
    queryset = ClientAccount.objects.all()
    serializer_class = ClientAccountSerializer
    entity_name = 'client_account'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_b2b']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at', 'max_users']
    ordering = ['name']
    
    def get_queryset(self):
        """Get client accounts with optimized queries"""
        queryset = ClientAccount.objects.all()
        
        # Optimiser avec compteurs
        queryset = queryset.prefetch_related(
            Prefetch('users', queryset=User.objects.filter(is_active=True)),
            'organizations'
        )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Statistiques détaillées d'un client"""
        client = self.get_object()

        active = client.users.filter(is_active=True).count()
        max_users = client.max_users or 0
        left = max(0, max_users - active)
        
        stats = {
            'seats':{
                'seats': max_users,
                'seats_used': active,
                'seats_left': left,
            },
            'users': {
                'total': client.users.count(),
                'active': client.users.filter(is_active=True).count(),
                'inactive': client.users.filter(is_active=False).count(),
                'with_teams': client.users.exclude(team=None).count()
            },
            'organizations': {
                'total': client.organizations.count(),
                'with_teams': client.organizations.annotate(
                    teams_count=Count('teams')
                ).filter(teams_count__gt=0).count()
            },
            'teams': {
                'total': Team.objects.filter(organization__client_account=client).count(),
                'with_members': Team.objects.filter(
                    organization__client_account=client
                ).annotate(
                    members_count=Count('members')
                ).filter(members_count__gt=0).count()
            },
            'roles': {
                'total': client.roles.count(),
                'in_use': client.roles.annotate(
                    users_count=Count('users')
                ).filter(users_count__gt=0).count()
            }
        }
        
        return Response({
            'success': True,
            'data': stats,
            'client_info': {
                'id': str(client.id),
                'name': client.name,
                'is_b2b': client.is_b2b,
                'max_users': client.max_users
            }
        })




# class UserRoleViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
#     """
#     API endpoints for managing user roles with client scoping
#     """
#     queryset = UserRole.objects.all()
#     serializer_class = UserRoleSerializer
#     entity_name = 'user_role'
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['read', 'write', 'modify', 'delete']
#     search_fields = ['name']
#     ordering_fields = ['name', 'created_at']
#     ordering = ['name']
    
#     def get_queryset(self):
#         """Get user roles for the current client with optimized queries"""
#         queryset = UserRole.objects.all()
        
#         # Apply client scoping
#         queryset = self.filter_queryset_by_client(queryset)
        
#         # Optimiser avec relations
#         queryset = queryset.select_related('client_account').prefetch_related(
#             Prefetch('users', queryset=User.objects.filter(is_active=True))
#         )
        
#         return queryset
    
#     @action(detail=False, methods=['get'])
#     def permissions_matrix(self, request):
#         """Matrix des permissions par rôle"""
#         roles = self.get_queryset()
        
#         matrix = []
#         for role in roles:
#             matrix.append({
#                 'id': str(role.id),
#                 'name': role.name,
#                 'permissions': {
#                     'read': role.read,
#                     'write': role.write,
#                     'modify': role.modify,
#                     'delete': role.delete
#                 },
#                 'users_count': role.users.filter(is_active=True).count()
#             })
        
#         return Response({
#             'success': True,
#             'data': matrix,
#             'total_roles': len(matrix)
#         })


class OrganizationViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing organizations with client scoping
    """
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    entity_name = 'organization'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['manager']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Get organizations for the current client with optimized queries"""
        queryset = Organization.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimiser avec relations
        queryset = queryset.select_related(
            'client_account', 'manager'
        ).prefetch_related(
            'teams',
            Prefetch('members', queryset=User.objects.filter(is_active=True))
        )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def hierarchy(self, request, pk=None):
        """Hiérarchie complète de l'organisation"""
        organization = self.get_object()
        
        teams_data = []
        for team in organization.teams.all():
            team_data = {
                'id': str(team.id),
                'name': team.name,
                'manager': {
                    'id': str(team.manager.id),
                    'name': team.manager.get_full_name(),
                    'email': team.manager.email
                } if team.manager else None,
                'members': []
            }
            
            for member in team.members.filter(is_active=True):
                team_data['members'].append({
                    'id': str(member.id),
                    'name': member.get_full_name(),
                    'email': member.email,
                    'role': member.role_name
                })
            
            teams_data.append(team_data)
        
        return Response({
            'success': True,
            'data': {
                'organization': {
                    'id': str(organization.id),
                    'name': organization.name,
                    'manager': {
                        'id': str(organization.manager.id),
                        'name': organization.manager.get_full_name(),
                        'email': organization.manager.email
                    } if organization.manager else None
                },
                'teams': teams_data,
                'summary': {
                    'total_teams': len(teams_data),
                    'total_members': sum(len(team['members']) for team in teams_data)
                }
            }
        })


class TeamViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing teams with client scoping
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    entity_name = 'team'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['organization', 'manager']
    search_fields = ['name', 'organization__name']
    ordering_fields = ['name', 'created_at']
    ordering = ['organization__name', 'name']
    
    def get_queryset(self):
        """Get teams for the current client with optimized queries"""
        queryset = Team.objects.all()
        
        # Apply client scoping
        client_id = self.get_client_id()
        if client_id:
            queryset = queryset.filter(organization__client_account_id=client_id)

        
        # Optimiser avec relations
        queryset = queryset.select_related(
            'organization', 'organization__client_account', 'manager'
        ).prefetch_related(
            Prefetch('members', queryset=User.objects.filter(is_active=True))
        )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def members_performance_summary(self, request, pk=None):
        """Résumé des performances des membres d'équipe"""
        team = self.get_object()
        
        # Pour le MVP, on retourne la structure basique
        # Sera connecté au UserPerformanceService en Phase 2
        members_data = []
        for member in team.members.filter(is_active=True):
            members_data.append({
                'id': str(member.id),
                'name': member.get_full_name(),
                'email': member.email,
                'role': member.role_name,
                'performance': {
                    'status': 'MVP_PLACEHOLDER',
                    'message': 'Will be connected to UserPerformanceService'
                }
            })
        
        return Response({
            'success': True,
            'data': {
                'team': {
                    'id': str(team.id),
                    'name': team.name,
                    'organization': team.organization.name,
                    'manager': team.manager.get_full_name() if team.manager else None
                },
                'members': members_data,
                'summary': {
                    'total_members': len(members_data),
                    'performance_integration': 'Coming in Phase 2'
                }
            }
        })


class UserViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing users with client scoping and performance integration
    """
    queryset = User.objects.all()
    entity_name = 'user'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'role', 'team', 'organization', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'created_at']
    ordering = ['first_name', 'last_name']
    
    def get_serializer_class(self):
        """Choisir le serializer selon l'action"""
        if self.action == 'list':
            return UserListSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Get users for the current client with optimized queries"""
        queryset = User.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Optimiser selon l'action
        if self.action == 'list':
            # Liste légère
            queryset = queryset.select_related(
                'team', 'organization', 'role'
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
            user_id = kwargs.get('pk')
            user = self.get_queryset().get(id=user_id)
            
            # Validation client scoping
            self.validate_client_id(user)
            
            serializer = UserSerializer(user)
            print(serializer.data)
            return Response({
                'success': True,
                'data': serializer.data
            })
            
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': CoreErrorMessages.OBJECT_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return self.handle_exception(e)
        
    def create(self, request, *args, **kwargs):
        """
        Créer un nouvel utilisateur
        POST /client/users/
        
        Permissions:
        - Tous les utilisateurs authentifiés peuvent créer des users SANS is_superuser
        - Seuls Admin et SuperUser peuvent créer des users AVEC is_superuser=True
        """
        try:
            with transaction.atomic():
                print(f"Create Requete data: {request.data}")
                # Validate superuser permission if trying to create a superuser
                self._validate_superuser_modification(request.user, request.data)
                
                # Serializer avec validation
                serializer = UserSerializer(
                    data=request.data, 
                    context={'request': request, 'client_id': self.get_client_id()}
                )
                
                # Validation avec raise_exception=True
                serializer.is_valid(raise_exception=True)
                
                # Créer l'utilisateur
                user = serializer.save()
                
                # Assurer les invariants
                user.client_account.ensure_admin_invariants()
                
                return Response({
                    'success': True,
                    'message': f'User "{user.get_full_name()}" created successfully',
                    'data': UserSerializer(user).data
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return self.handle_exception(e)

    
    def partial_update(self, request, *args, **kwargs):
        """
        Mise à jour partielle d'un utilisateur (PATCH)
        PATCH /client/users/{id}/
        """
        try:
            with transaction.atomic():
                print(f"PATCH Requete data: {request.data}")
                user_id = kwargs.get('pk')
                user = self.get_queryset().get(id=user_id)
                
                # Validation client scoping
                self.validate_client_id(user)
                
                # Validation des permissions
                self._validate_user_update_permissions(request.user, user)

                self._validate_superuser_modification(request.user, request.data, user)
                
                # Serializer avec validation
                serializer = UserSerializer(
                    user,
                    data=request.data,
                    partial=True,
                    context={'request': request, 'client_id': self.get_client_id()}
                )
                
                serializer.is_valid(raise_exception=True)
                
                # Sauvegarder les modifications
                updated_user = serializer.save()

                updated_user.client_account.ensure_admin_invariants()
                
                return Response({
                    'success': True,
                    'message': f'User "{updated_user.get_full_name()}" updated successfully',
                    'data': UserSerializer(updated_user).data
                })
                
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': CoreErrorMessages.OBJECT_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
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
            # Récupérer l'utilisateur cible
            target_user = self.get_object()
            
            # Validation client scoping (vérifie que l'utilisateur appartient au bon client)
            self.validate_client_id(target_user)
            
            # Récupérer l'utilisateur connecté et son rôle
            current_user = request.user
            current_role = request.auth.get('role') if request.auth else None
            
            # Vérification des permissions
            if current_role != 'Admin' and str(current_user.id) != str(target_user.id):
                raise StandardizedValidationError(
                    "You can only change your own password"
                )
            
            # Import du serializer (à ajouter en haut du fichier si pas déjà fait)
            from ..serializers.user_serializer import ChangePasswordSerializer
            
            # Validation avec le serializer
            serializer = ChangePasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Mettre à jour le mot de passe
            serializer.update_password(target_user, serializer.validated_data)
            
            # Logger l'action si nécessaire (optionnel)
            if current_role == 'Admin' and str(current_user.id) != str(target_user.id):
                # Admin a changé le mot de passe d'un autre utilisateur
                print(f"Admin {current_user.email} changed password for {target_user.email}")
            
            return Response({
                'success': True,
                'message': 'Password changed successfully',
                'user': {
                    'id': str(target_user.id),
                    'email': target_user.email,
                    'name': target_user.get_full_name()
                }
            })
            
        except User.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        except StandardizedValidationError:
            # Re-raise les erreurs de validation déjà formatées
            raise

    
    def destroy(self, request, *args, **kwargs):
        """
        Supprimer un utilisateur
        DELETE /client/users/{id}/
        """
        try:
            with transaction.atomic():
                user_id = kwargs.get('pk')
                user = self.get_queryset().get(id=user_id)

                # Mémoriser le client avant suppression
                client = user.client_account

                # Validation client scoping
                self.validate_client_id(user)

                # Validation des permissions
                self._validate_user_delete_permissions(request.user, user)

                # Vérifications métier avant suppression
                self._validate_user_deletion(user)

                user_name = user.get_full_name()
                user.delete()

                # ✅ Filet de sécurité: s'assurer qu'un admin existe toujours
                client.ensure_admin_invariants()

                return Response({
                    'success': True,
                    'message': f'User "{user_name}" deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)

        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': CoreErrorMessages.OBJECT_NOT_FOUND
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return self.handle_exception(e)
    
    # === OPÉRATIONS BULK - TO DO IF NEEDED===
    
    # === MÉTHODES UTILITAIRES PRIVÉES ===
    
    def _validate_user_update_permissions(self, current_user, target_user):
        """Valider les permissions de mise à jour"""
        # L'utilisateur peut se modifier lui-même
        if current_user == target_user:
            return True
        
        # SuperUser peut modifier tout le monde dans son tenant
        if current_user.is_superuser:
            return True
        
        # Admin peut modifier tout le monde
        if current_user.role and current_user.role.name == 'Admin':
            return True
        
        # Manager peut modifier les membres de son équipe
        if target_user in current_user.get_managed_users():
            return True
        
        raise StandardizedValidationError(
            CoreErrorMessages.PERMISSION_DENIED
        )
    
    def _validate_user_delete_permissions(self, current_user, target_user):
        """Valider les permissions de suppression"""
        # On ne peut pas se supprimer soi-même
        if current_user == target_user:
            raise StandardizedValidationError(
                "You cannot delete your own account"
            )
        
        # SuperUser peut supprimer tout le monde (sauf lui-même) dans son tenant
        if current_user.is_superuser:
            return True
        
        # Admin peut supprimer tout le monde (sauf lui-même)
        if current_user.role and current_user.role.name == 'Admin':
            return True
                
        raise StandardizedValidationError(
            CoreErrorMessages.PERMISSION_DENIED
        )
    
    def _can_grant_superuser(self, current_user):
        """
        Check if the current user can grant/revoke superuser status
        Only SuperUsers and Admin role users can grant superuser status
        """
        # SuperUsers can grant superuser status
        if current_user.is_superuser:
            return True
        
        # Users with Admin role can grant superuser status
        if current_user.role and current_user.role.name == 'Admin':
            return True
        
        return False
    
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
        if not request.user.can_access_user_performance(target_user):
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
        
        # Utiliser UserPerformanceService
        try:
            from ..services.user_performance_service_obsolete import UserPerformanceService
            
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
        """
        user = request.user
        
        if not user.team:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="User is not assigned to a team"
                )
            )
        
        # Récupérer les membres de l'équipe
        team_members = user.team.members.filter(is_active=True)
        team_user_ids = list(team_members.values_list('id', flat=True))
        
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
        if not request.user.can_access_user_performance(manager):
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
            current_user = request.user
            
            is_authorized = False
            if current_user.is_superuser:
                is_authorized = True
            elif current_user.role and current_user.role.name == 'Admin':
                is_authorized = True
            
            if not is_authorized:
                raise StandardizedValidationError(
                    "Only administrators and superusers can view the superusers list"
                )
            
            # Récupérer le client_id du contexte pour garantir le multi-tenant
            client_id = self.get_client_id()
            
            # Filtrer les superusers du tenant actuel
            superusers = User.objects.filter(
                client_account_id=client_id,
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
            admin_role_users = User.objects.filter(
                client_account_id=client_id,
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
                    'can_grant_superuser': current_user.is_superuser or (current_user.role and current_user.role.name == 'Admin'),
                    'current_user_is_superuser': current_user.is_superuser
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
                
                # Log l'action
                action = "granted to" if grant else "revoked from"
                print(f"[AUDIT] Superuser status {action} {target_user.email} by {request.user.email}")
                
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


# ===== VUES D'AUTHENTIFICATION =====
# Garder les vues existantes pour la compatibilité

class UserLoginView(BaseAPIView):
    """View to authenticate users and return tokens."""
    authentication_classes = []  # Pas d'auth requise pour login
    permission_classes = []
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')


        if not email or not password:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Email and Password')
            )


        from django.conf import settings
        auth_service = AuthService(
            user_model=User,
            origin='end_users',
            refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
            serializer_class=UserSerializer
        )
        
        response = Response(status=status.HTTP_200_OK)
        user = auth_service.authenticate_user(email, password, response)
        response.data.update({
            "origin": "end_users",
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "role": user.role_name
            }
        })

        return response

class UserCurrentView(BaseAPIView):
    """View to get current authenticated user info."""
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    http_method_names = ['get']

    def get(self, request):
        """Return current user information"""
        try:
            user = request.user
            serializer = UserSerializer(user)
            
            return Response({
                "success": True,
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name(),
                    "email": user.email,
                    "role": user.role_name if hasattr(user, 'role_name') else None,
                    "avatar": None, 
                    "client_id": str(user.client_account_id) if user.client_account_id else None,
                    "client_name": user.client_account.name if getattr(user, "client_account", None) else None,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            raise StandardizedValidationError(f"Failed to get user info: {str(e)}")


class UserLogoutView(BaseAPIView):
    """View to logout users and clear tokens."""
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )
            
            response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
            auth_service.logout_user(request, response)
            return response
        except Exception as e:
            raise StandardizedValidationError(str(e))


class UserRefreshTokenView(BaseAPIView):
    """View to refresh user tokens."""
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        try:
            print("Refreshing token")
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )

             # Create response object first so cookies can be set on it
            response = Response(status=status.HTTP_200_OK)
            
            # refresh_tokens will set cookies on the response and return user data
            result = auth_service.refresh_tokens(request, response)
            
            # Set the enriched data (message + user)
            response.data = result
            
            return response
        
        except Exception as e:
            raise StandardizedValidationError(str(e))