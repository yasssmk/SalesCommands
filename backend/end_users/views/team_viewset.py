from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch
from core.client_scope import ClientScopeManager
from core.apps_shared_methods import BaseAPIView
from ..models import Team, User
from ..serializers import TeamSerializer



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
