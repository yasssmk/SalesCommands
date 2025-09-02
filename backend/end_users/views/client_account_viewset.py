from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Prefetch
from core.apps_shared_methods import BaseAPIView
from ..models import ClientAccount, Team, User
from ..serializers import ClientAccountSerializer


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