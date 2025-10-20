from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Exists, OuterRef, Prefetch
from django.http import Http404
import time
import logging
from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from ..models import ClientAccount, Team, User
from ..serializers import ClientAccountSerializer

logger = logging.getLogger(__name__)


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
        
        # Optimiser avec prefetch pour list/retrieve standard
        if self.action in ['list', 'retrieve']:
            queryset = queryset.prefetch_related(
                Prefetch('users', queryset=User.objects.filter(is_active=True)),
                'organizations'
            )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def seats(self, request, pk=None):
        """
        Endpoint ultra-optimisé pour récupérer uniquement les informations de seats
        Utilisé par: SeatsSummary component dans la page users
        Performance cible: P95 < 50ms
        
        GET /client/client-accounts/{uuid}/seats/
        
        Response:
        {
            "success": true,
            "data": {
                "seats": 100,
                "seats_used": 47,
                "seats_left": 53
            },
            "_meta": {
                "timing_ms": 12.45
            }
        }
        """
        start_time = time.time()
        
        try:
            # ✅ Une seule requête avec annotation minimale
            client = ClientAccount.objects.filter(
                id=pk
            ).annotate(
                active_users_count=Count('users', filter=Q(users__is_active=True))
            ).values(
                'id', 'name', 'max_users', 'active_users_count'
            ).first()
            
            if not client:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            
            
            # Calcul simple des seats
            max_users = client['max_users'] or 0
            seats_used = client['active_users_count']
            seats_left = max(0, max_users - seats_used)
            
            return Response({
                'success': True,
                'data': {
                    'seats': max_users,
                    'seats_used': seats_used,
                    'seats_left': seats_left
                },
                '_meta': {
                    'timing_ms': round((time.time() - start_time) * 1000, 2)
                }
            })
            
        except StandardizedValidationError:
            # Re-raise les erreurs standardisées
            raise
            
        except Exception as e:
            # Log l'erreur pour debugging
            logger.error(f"Error in seats endpoint for client {pk}: {str(e)}", exc_info=True)
            
            # Retourner une erreur standardisée
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve seats information: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Statistiques complètes optimisées avec aggregations
        Utilisé par: Dashboard admin, vue détaillée client
        Performance cible: P95 < 400ms (avant: 1084ms)
        
        GET /client/client-accounts/{uuid}/stats/
        
        Response: Statistiques complètes users, organizations, teams, roles
        """
        start_time = time.time()
        
        try:
            # ✅ Une seule requête avec toutes les annotations
            client = ClientAccount.objects.filter(
                id=pk
            ).annotate(
                # Users stats - tout en une seule passe
                total_users=Count('users', distinct=True),
                active_users=Count('users', filter=Q(users__is_active=True), distinct=True),
                inactive_users=Count('users', filter=Q(users__is_active=False), distinct=True),
                users_with_teams=Count('users', filter=Q(users__team__isnull=False), distinct=True),
                
                # Organizations stats
                total_orgs=Count('organizations', distinct=True),
                
                # Roles stats
                total_roles=Count('roles', distinct=True),
                roles_in_use=Count('roles', filter=Q(roles__users__isnull=False), distinct=True)
            ).first()
            
            if not client:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            
            # ✅ Subqueries optimisées pour éviter les JOINs complexes
            # Teams count - requête séparée mais optimisée
            teams_stats = Team.objects.filter(
                organization__client_account_id=pk
            ).aggregate(
                total=Count('id'),
                with_members=Count('id', filter=Q(members__isnull=False), distinct=True)
            )
            
            # Organizations avec teams - utilisation d'Exists pour performance
            orgs_with_teams = client.organizations.filter(
                Exists(Team.objects.filter(organization=OuterRef('pk')))
            ).count()
            
            # Calculer les seats
            max_users = client.max_users or 0
            seats_used = client.active_users
            seats_left = max(0, max_users - seats_used)
            
            # ✅ Construction de la réponse
            return Response({
                'success': True,
                'data': {
                    'seats': {
                        'seats': max_users,
                        'seats_used': seats_used,
                        'seats_left': seats_left,
                    },
                    'users': {
                        'total': client.total_users,
                        'active': client.active_users,
                        'inactive': client.inactive_users,
                        'with_teams': client.users_with_teams
                    },
                    'organizations': {
                        'total': client.total_orgs,
                        'with_teams': orgs_with_teams
                    },
                    'teams': {
                        'total': teams_stats['total'],
                        'with_members': teams_stats['with_members']
                    },
                    'roles': {
                        'total': client.total_roles,
                        'in_use': client.roles_in_use
                    }
                },
                'client_info': {
                    'id': str(client.id),
                    'name': client.name,
                    'is_b2b': client.is_b2b,
                    'max_users': max_users
                },
                '_meta': {
                    'timing_ms': round((time.time() - start_time) * 1000, 2),
                    'query_count': 3  # 1 main + 1 teams + 1 orgs_with_teams
                }
            })
            
        except StandardizedValidationError:
            # Re-raise les erreurs standardisées
            raise
            
        except Exception as e:
            # Log l'erreur pour debugging
            logger.error(f"Error in stats endpoint for client {pk}: {str(e)}", exc_info=True)
            
            # Retourner une erreur standardisée
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve statistics: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['get'])
    def users_summary(self, request, pk=None):
        """
        Statistiques users uniquement (futur endpoint si besoin)
        Performance cible: P95 < 100ms
        
        GET /client/client-accounts/{uuid}/users-summary/
        """
        start_time = time.time()
        
        try:
            client = ClientAccount.objects.filter(
                id=pk
            ).annotate(
                total_users=Count('users', distinct=True),
                active_users=Count('users', filter=Q(users__is_active=True)),
                inactive_users=Count('users', filter=Q(users__is_active=False)),
                users_with_teams=Count('users', filter=Q(users__team__isnull=False), distinct=True),
                superusers=Count('users', filter=Q(users__is_superuser=True)),
                staff_users=Count('users', filter=Q(users__is_staff=True))
            ).values(
                'id', 'name', 'total_users', 'active_users', 'inactive_users',
                'users_with_teams', 'superusers', 'staff_users'
            ).first()
            
            if not client:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
            
            return Response({
                'success': True,
                'data': {
                    'total': client['total_users'],
                    'active': client['active_users'],
                    'inactive': client['inactive_users'],
                    'with_teams': client['users_with_teams'],
                    'superusers': client['superusers'],
                    'staff': client['staff_users']
                },
                '_meta': {
                    'timing_ms': round((time.time() - start_time) * 1000, 2)
                }
            })
            
        except StandardizedValidationError:
            # Re-raise les erreurs standardisées
            raise
            
        except Exception as e:
            # Log l'erreur pour debugging
            logger.error(f"Error in users_summary endpoint for client {pk}: {str(e)}", exc_info=True)
            
            # Retourner une erreur standardisée
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to retrieve users summary: {str(e)}"
                )
            )