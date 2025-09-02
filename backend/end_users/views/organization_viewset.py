from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch
from core.client_scope import ClientScopeManager
from core.apps_shared_methods import BaseAPIView
from ..models import Organization,  User
from ..serializers import OrganizationSerializer




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