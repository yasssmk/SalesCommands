# apps/end_users/views/sales_milestone_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime, timedelta
from django.db.models import Q, Count, Avg
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView

from end_users.models import SalesPlan, SalesMilestone, User
from end_users.serializers.sales_milestone_serializer import SalesMilestoneSerializer


class SalesMilestoneViewSet(BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des Sales Milestones.
    
    Architecture complète avec :
    - CRUD standard pour les milestones
    - Mise à jour automatique du tracking via update_progress()
    - Actions spécialisées pour monitoring et debug
    - Intégration avec signaux temps réel
    - Support filtrage avancé par type, statut, dates
    
    Actions principales :
    - update_progress() : Force recalcul d'un milestone
    - batch_update() : Mise à jour en lot
    - overdue() : Liste milestones en retard
    - upcoming() : Milestones à venir
    - by_plan() : Tous milestones d'un plan spécifique
    """
    queryset = SalesMilestone.objects.all()
    serializer_class = SalesMilestoneSerializer
    entity_name = 'sales_milestone'
    
    # Configuration filtres et recherche
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'milestone_type', 'status', 'sales_plan', 'sales_plan__user',
        'sales_plan__user__team', 'target_date'
    ]
    search_fields = ['name', 'description', 'sales_plan__name', 'sales_plan__user__email']
    ordering_fields = ['created_at', 'target_date', 'achievement_rate', 'target_value']
    ordering = ['target_date']
    
    def get_serializer_class(self):
        """Utilise SalesMilestoneSerializer pour toutes les actions"""
        return SalesMilestoneSerializer
    
    def get_queryset(self):
        """QuerySet optimisé avec relations et client scoping"""
        queryset = SalesMilestone.objects.select_related(
            'sales_plan', 'sales_plan__user', 'sales_plan__quota',
            'sales_plan__user__team', 'sales_plan__user__organization'
        )
        
        # Client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filtres pratiques
        active_plans_only = self.request.query_params.get('active_plans_only')
        if active_plans_only and active_plans_only.lower() == 'true':
            queryset = queryset.filter(
                sales_plan__status__in=[
                    SalesPlan.Status.ACTIVE,
                    SalesPlan.Status.DRAFT
                ]
            )
        
        # Filtre par période
        period_filter = self.request.query_params.get('period')
        if period_filter:
            today = date.today()
            
            if period_filter == 'current':
                # Milestones dans les 90 prochains jours
                end_date = today + timedelta(days=90)
                queryset = queryset.filter(
                    target_date__gte=today,
                    target_date__lte=end_date
                )
            elif period_filter == 'overdue':
                queryset = queryset.filter(
                    target_date__lt=today,
                    status__in=['PENDING', 'IN_PROGRESS']
                )
            elif period_filter == 'this_month':
                start_month = today.replace(day=1)
                if today.month == 12:
                    end_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    end_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
                
                queryset = queryset.filter(
                    target_date__gte=start_month,
                    target_date__lte=end_month
                )
        
        return queryset
    
    def get_serializer_context(self):
        """Ajoute contexte pour les serializers"""
        context = super().get_serializer_context()
        context.update({
            'client_id': self.get_client_id(),
            # Inclure données de progress pour toutes les actions détaillées
            'include_progress_data': self.action in [
                'retrieve', 'update_progress', 'list', 'overdue', 'upcoming', 'by_plan'
            ]
        })
        return context
    
    def perform_create(self, serializer):
        """Création avec client_id et validation"""
        sales_plan = serializer.validated_data.get('sales_plan')
        
        # Validation : le milestone doit être dans la période du plan
        target_date = serializer.validated_data.get('target_date')
        if target_date and sales_plan:
            if not (sales_plan.period_start <= target_date <= sales_plan.period_end):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATE_RANGE.format(
                        field="target_date must be within sales plan period"
                    )
                )
        
        # Création
        milestone = serializer.save(client_id=self.get_client_id())
        
        # Déclencher calcul initial
        try:
            milestone.update_progress()
        except Exception as e:
            # Ne pas faire échouer la création si le calcul initial échoue
            pass
    
    def perform_update(self, serializer):
        """Mise à jour avec recalcul automatique"""
        milestone = serializer.save()
        
        # Si target_value ou target_date modifiés, recalculer
        if 'target_value' in serializer.validated_data or 'target_date' in serializer.validated_data:
            try:
                milestone.update_progress()
            except Exception as e:
                # Log erreur mais ne pas faire échouer la mise à jour
                pass
    
    # =====================================================================
    # ACTIONS SPÉCIALISÉES - TRACKING ET MONITORING
    # =====================================================================
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """
        Force la mise à jour du progrès d'un milestone.
        
        POST /sales-milestones/{id}/update-progress/
        
        Déclenche recalcul via UserPerformanceService et met à jour :
        - current_value
        - achievement_rate
        - status
        - last_progress_update
        """
        milestone = self.get_object()
        
        try:
            # Déclencher mise à jour
            result = milestone.update_progress()
            
            # Recharger pour obtenir données fraîches
            milestone.refresh_from_db()
            
            return Response({
                'success': True,
                'message': 'Milestone progress updated successfully',
                'data': {
                    'milestone': SalesMilestoneSerializer(milestone).data,
                    'update_result': result
                },
                'updated_at': milestone.last_progress_update.isoformat() if milestone.last_progress_update else None
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update progress: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """
        Mise à jour en lot de milestones.
        
        POST /sales-milestones/batch-update/
        Body: {
            "milestone_ids": [1, 2, 3],
            "user_id": 123,  // Optionnel : tous milestones d'un user
            "sales_plan_id": 456  // Optionnel : tous milestones d'un plan
        }
        
        Utile pour forcer recalcul après corrections manuelles CRM.
        """
        milestone_ids = request.data.get('milestone_ids')
        user_id = request.data.get('user_id')
        sales_plan_id = request.data.get('sales_plan_id')
        
        # Construire queryset
        queryset = self.get_queryset()
        
        if milestone_ids:
            queryset = queryset.filter(id__in=milestone_ids)
        elif user_id:
            queryset = queryset.filter(sales_plan__user_id=user_id)
        elif sales_plan_id:
            queryset = queryset.filter(sales_plan_id=sales_plan_id)
        else:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="milestone_ids, user_id, or sales_plan_id"
                )
            )
        
        # Limite de sécurité
        if queryset.count() > 100:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation="Cannot update more than 100 milestones at once"
                )
            )
        
        # Effectuer mises à jour
        updated_count = 0
        failed_count = 0
        errors = []
        
        for milestone in queryset:
            try:
                milestone.update_progress()
                updated_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    'milestone_id': milestone.id,
                    'error': str(e)
                })
        
        return Response({
            'success': True,
            'message': f'Batch update completed: {updated_count} updated, {failed_count} failed',
            'data': {
                'updated_count': updated_count,
                'failed_count': failed_count,
                'errors': errors[:10]  # Limiter les erreurs retournées
            }
        })
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Liste des milestones en retard.
        
        GET /sales-milestones/overdue/
        GET /sales-milestones/overdue/?user_id=123
        GET /sales-milestones/overdue/?team_id=456
        
        Filtre automatiquement par target_date < today et status non atteint.
        """
        queryset = self.get_queryset()
        today = date.today()
        
        # Filtre overdue
        queryset = queryset.filter(
            target_date__lt=today,
            status__in=[
                SalesMilestone.Status.PENDING,
                SalesMilestone.Status.IN_PROGRESS
            ]
        ).order_by('target_date')
        
        # Filtres additionnels
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(sales_plan__user_id=user_id)
        
        team_id = request.query_params.get('team_id')
        if team_id:
            queryset = queryset.filter(sales_plan__user__team_id=team_id)
        
        # Paginer
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SalesMilestoneSerializer(
                page, 
                many=True, 
                context=self.get_serializer_context()
            )
            
            return self.get_paginated_response({
                'milestones': serializer.data,
                'summary': {
                    'total_overdue': queryset.count(),
                    'avg_days_overdue': self._calculate_avg_days_overdue(queryset),
                    'most_overdue_date': queryset.first().target_date.isoformat() if queryset.exists() else None
                }
            })
        
        # Version non paginée
        serializer = SalesMilestoneSerializer(
            queryset, 
            many=True, 
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'data': {
                'milestones': serializer.data,
                'count': queryset.count()
            }
        })
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Milestones à venir dans les prochains jours.
        
        GET /sales-milestones/upcoming/?days=30
        GET /sales-milestones/upcoming/?user_id=123&days=7
        
        Par défaut : 30 prochains jours
        """
        days = int(request.query_params.get('days', 30))
        if days > 90:  # Limite de sécurité
            days = 90
        
        today = date.today()
        end_date = today + timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            target_date__gte=today,
            target_date__lte=end_date,
            status__in=[
                SalesMilestone.Status.PENDING,
                SalesMilestone.Status.IN_PROGRESS
            ]
        ).order_by('target_date')
        
        # Filtres additionnels
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(sales_plan__user_id=user_id)
        
        # Paginer
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SalesMilestoneSerializer(
                page, 
                many=True, 
                context=self.get_serializer_context()
            )
            
            return self.get_paginated_response({
                'milestones': serializer.data,
                'period': f'Next {days} days',
                'summary': {
                    'total_upcoming': queryset.count(),
                    'urgent_count': queryset.filter(target_date__lte=today + timedelta(days=7)).count()
                }
            })
        
        # Version non paginée
        serializer = SalesMilestoneSerializer(
            queryset, 
            many=True, 
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'data': {
                'milestones': serializer.data,
                'count': queryset.count(),
                'period': f'Next {days} days'
            }
        })
    
    @action(detail=False, methods=['get'], url_path='by-plan/(?P<plan_id>[^/.]+)')
    def by_plan(self, request, plan_id=None):
        """
        Tous les milestones d'un Sales Plan spécifique.
        
        GET /sales-milestones/by-plan/{plan_id}/
        
        Retourne milestones ordonnés par target_date avec statut d'avancement.
        """
        try:
            # Valider que le plan existe et appartient au client
            sales_plan = SalesPlan.objects.get(
                id=plan_id,
                client_id=self.get_client_id()
            )
        except SalesPlan.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND.format(
                    object="Sales Plan"
                )
            )
        
        # Récupérer milestones du plan
        milestones = self.get_queryset().filter(
            sales_plan_id=plan_id
        ).order_by('target_date')
        
        serializer = SalesMilestoneSerializer(
            milestones, 
            many=True, 
            context=self.get_serializer_context()
        )
        
        # Calculer métriques du plan
        total_milestones = milestones.count()
        achieved_count = milestones.filter(status=SalesMilestone.Status.ACHIEVED).count()
        overdue_count = milestones.filter(
            target_date__lt=date.today(),
            status__in=[SalesMilestone.Status.PENDING, SalesMilestone.Status.IN_PROGRESS]
        ).count()
        
        return Response({
            'success': True,
            'data': {
                'sales_plan': {
                    'id': sales_plan.id,
                    'name': sales_plan.name,
                    'status': sales_plan.status
                },
                'milestones': serializer.data,
                'summary': {
                    'total_milestones': total_milestones,
                    'achieved_count': achieved_count,
                    'overdue_count': overdue_count,
                    'completion_rate': f"{(achieved_count/total_milestones*100):.1f}%" if total_milestones > 0 else "0%"
                }
            }
        })
    
    # =====================================================================
    # ACTIONS DE GESTION
    # =====================================================================
    
    @action(detail=True, methods=['patch'])
    def mark_achieved(self, request, pk=None):
        """
        Marquer un milestone comme atteint manuellement.
        
        PATCH /sales-milestones/{id}/mark-achieved/
        
        Utile pour milestones CUSTOM ou corrections manuelles.
        """
        milestone = self.get_object()
        
        if milestone.status == SalesMilestone.Status.ACHIEVED:
            return Response({
                'success': True,
                'message': 'Milestone is already achieved'
            })
        
        # Marquer comme atteint
        milestone.status = SalesMilestone.Status.ACHIEVED
        milestone.achievement_rate = 100.00
        milestone.last_progress_update = timezone.now()
        milestone.save()
        
        return Response({
            'success': True,
            'message': 'Milestone marked as achieved',
            'data': SalesMilestoneSerializer(milestone).data
        })
    
    @action(detail=True, methods=['patch'])
    def reset_progress(self, request, pk=None):
        """
        Reset le progrès d'un milestone.
        
        PATCH /sales-milestones/{id}/reset-progress/
        
        Remet à zéro et force recalcul.
        """
        milestone = self.get_object()
        
        # Reset valeurs
        milestone.current_value = 0.00
        milestone.achievement_rate = 0.00
        milestone.status = SalesMilestone.Status.PENDING
        milestone.save()
        
        # Recalculer
        try:
            milestone.update_progress()
            milestone.refresh_from_db()
        except Exception:
            pass  # Ne pas faire échouer si recalcul échoue
        
        return Response({
            'success': True,
            'message': 'Milestone progress reset and recalculated',
            'data': SalesMilestoneSerializer(milestone).data
        })
    
    # =====================================================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =====================================================================
    
    def _calculate_avg_days_overdue(self, queryset):
        """Calcule nombre moyen de jours de retard"""
        today = date.today()
        total_days = 0
        count = 0
        
        for milestone in queryset:
            days_overdue = (today - milestone.target_date).days
            total_days += days_overdue
            count += 1
        
        return round(total_days / count, 1) if count > 0 else 0