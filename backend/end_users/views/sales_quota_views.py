# apps/end_users/views/sales_quota_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime
from django.db.models import Q

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager

from end_users.models import SalesQuota
from end_users.serializers.sales_quota_serializer import (
    SalesQuotaSerializer,
    SalesQuotaSummarySerializer,
    SalesQuotaListSerializer,
    SalesQuotaViewSetSerializer
)
from end_users.services.user_performance_service import UserPerformanceService


class SalesQuotaViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des quotas de vente.
    
    Basic et nécessaire :
    - CRUD standard
    - Action performance individuelle
    - Action résumé équipe
    - Filtres essentiels
    """
    queryset = SalesQuota.objects.all()
    serializer_class = SalesQuotaSerializer
    entity_name = 'sales_quota'
    
    # Filtres et recherche
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['target_type', 'is_active', 'user', 'user__team']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    ordering_fields = ['created_at', 'period_start', 'period_end', 'target_value']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Serializer selon l'action"""
        if self.action == 'list':
            return SalesQuotaListSerializer
        elif self.action in ['performance', 'team_summary']:
            return SalesQuotaSummarySerializer
        return SalesQuotaViewSetSerializer
    
    def get_queryset(self):
        """QuerySet optimisé avec client scoping"""
        queryset = SalesQuotaViewSetSerializer.get_optimized_queryset()
        
        # Client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filtres pratiques
        active_only = self.request.query_params.get('active_only', 'true')
        if active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        # Filtre par période courante
        current_period = self.request.query_params.get('current_period')
        if current_period and current_period.lower() == 'true':
            today = date.today()
            queryset = queryset.filter(
                period_start__lte=today,
                period_end__gte=today
            )
        
        return queryset
    
    def perform_create(self, serializer):
        """Création avec client_id et user"""
        serializer.save(
            client_id=self.get_client_id(),
            user=self.request.user
        )
    
    def perform_update(self, serializer):
        """Mise à jour avec user"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Performance détaillée d'un quota spécifique.
        GET /sales-quotas/{id}/performance/
        """
        quota = self.get_object()
        
        try:
            performance_data = UserPerformanceService.get_user_quota_performance(
                user_id=quota.user.id,
                quota_id=quota.id,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': performance_data
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get quota performance: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def team_summary(self, request):
        """
        Résumé des quotas pour l'équipe de l'utilisateur connecté.
        GET /sales-quotas/team-summary/
        """
        user = request.user
        
        if not user.team:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail="User is not assigned to a team"
                )
            )
        
        # Récupérer les quotas de l'équipe
        team_quotas = self.get_queryset().filter(
            user__team=user.team,
            is_active=True
        )
        
        if not team_quotas.exists():
            return Response({
                'success': True,
                'data': {
                    'team_info': {
                        'id': str(user.team.id),
                        'name': user.team.name
                    },
                    'quotas': [],
                    'summary': {
                        'total_quotas': 0,
                        'achieved_count': 0,
                        'at_risk_count': 0,
                        'average_progress': 0
                    }
                }
            })
        
        # Sérialiser les quotas
        serializer = SalesQuotaSummarySerializer(team_quotas, many=True)
        
        # Calculer le résumé simple
        total_quotas = team_quotas.count()
        summary = {
            'team_info': {
                'id': str(user.team.id),
                'name': user.team.name
            },
            'quotas': serializer.data,
            'summary': {
                'total_quotas': total_quotas,
                'active_quotas': total_quotas  # Tous sont actifs dans le filtre
            }
        }
        
        return Response({
            'success': True,
            'data': summary
        })
    
    @action(detail=False, methods=['get'])
    def my_quotas(self, request):
        """
        Quotas de l'utilisateur connecté uniquement.
        GET /sales-quotas/my-quotas/
        """
        user_quotas = self.get_queryset().filter(user=request.user)
        
        # Paginer si nécessaire
        page = self.paginate_queryset(user_quotas)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(user_quotas, many=True)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        """
        Activer un quota (désactiver les autres de la même période).
        PATCH /sales-quotas/{id}/activate/
        """
        quota = self.get_object()
        
        if quota.is_active:
            return Response({
                'success': True,
                'message': 'Quota is already active'
            })
        
        try:
            # Désactiver les quotas qui se chevauchent
            overlapping_quotas = SalesQuota.objects.filter(
                user=quota.user,
                client_id=self.get_client_id(),
                is_active=True
            ).filter(
                Q(period_start__lte=quota.period_end) &
                Q(period_end__gte=quota.period_start)
            ).exclude(pk=quota.pk)
            
            overlapping_quotas.update(is_active=False)
            
            # Activer le quota
            quota.is_active = True
            quota.save(user=request.user)
            
            return Response({
                'success': True,
                'message': f'Quota activated. {overlapping_quotas.count()} overlapping quotas deactivated.'
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to activate quota: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        """
        Désactiver un quota.
        PATCH /sales-quotas/{id}/deactivate/
        """
        quota = self.get_object()
        
        if not quota.is_active:
            return Response({
                'success': True,
                'message': 'Quota is already inactive'
            })
        
        quota.is_active = False
        quota.save(user=request.user)
        
        return Response({
            'success': True,
            'message': 'Quota deactivated successfully'
        })