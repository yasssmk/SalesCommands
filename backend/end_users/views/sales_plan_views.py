# apps/end_users/views/sales_plan_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime
from django.db.models import Q, Count, Prefetch
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager

from end_users.models import SalesPlan, SalesQuota, SalesMilestone, User
from end_users.serializers.sales_plan_serializer import SalesPlanSerializer
from ..services.sales_planning_service import SalesPlanningService


class SalesPlanViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des Sales Plans.
    
    Architecture complète avec :
    - CRUD standard pour les Sales Plans
    - Actions spécialisées pour dashboards (utilise SalesPlanningService)
    - Intégration temps réel via signaux
    - Support multi-utilisateur et équipe
    - Filtres et recherche avancée
    
    Actions principales :
    - dashboard() : Analyse complète du plan avec visualisation
    - planning_analysis() : Analyse détaillée de planification
    - quick_summary() : Résumé rapide pour widgets
    - my_plans() : Plans de l'utilisateur courant
    - team_plans() : Vue consolidée pour managers
    """
    queryset = SalesPlan.objects.all()
    serializer_class = SalesPlanSerializer
    entity_name = 'sales_plan'
    
    # Configuration filtres et recherche
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'status', 'user', 'user__team', 'quota__target_type',
        'period_start', 'period_end'
    ]
    search_fields = ['name', 'description', 'user__first_name', 'user__last_name', 'user__email']
    ordering_fields = ['created_at', 'period_start', 'period_end', 'name']
    ordering = ['-period_start']
    
    def get_serializer_class(self):
        """Utilise SalesPlanSerializer pour toutes les actions"""
        return SalesPlanSerializer
    
    def get_queryset(self):
        """QuerySet optimisé avec relations et client scoping"""
        queryset = SalesPlan.objects.select_related(
            'user', 'quota', 'user__team', 'user__organization'
        ).prefetch_related(
            Prefetch(
                'milestones',
                queryset=SalesMilestone.objects.select_related().order_by('target_date')
            )
        )
        
        # Client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filtres pratiques
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(status__in=[
                SalesPlan.Status.ACTIVE, 
                SalesPlan.Status.DRAFT
            ])
        
        # Filtre par période courante
        current_period = self.request.query_params.get('current_period')
        if current_period and current_period.lower() == 'true':
            today = date.today()
            queryset = queryset.filter(
                period_start__lte=today,
                period_end__gte=today
            )
        
        # Filtre par utilisateur spécifique
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset
    
    def get_serializer_context(self):
        """Ajoute contexte pour les serializers"""
        context = super().get_serializer_context()
        context.update({
            'client_id': self.get_client_id(),
            # Inclure données de performance pour actions détaillées
            'include_performance_data': self.action in [
                'dashboard', 'planning_analysis', 'retrieve', 'list'
            ]
        })
        return context
    
    def perform_create(self, serializer):
        """Création avec client_id et validation"""
        # Valider que l'utilisateur a un quota actif si nécessaire
        quota = serializer.validated_data.get('quota')
        if quota and not quota.is_active:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="quota must be active"
                )
            )
        
        serializer.save(client_id=self.get_client_id())
    
    def perform_update(self, serializer):
        """Mise à jour avec validation"""
        instance = serializer.instance
        
        # Empêcher modification du quota si le plan est actif
        if (instance.status == SalesPlan.Status.ACTIVE and 
            'quota' in serializer.validated_data):
            new_quota = serializer.validated_data['quota']
            if new_quota != instance.quota:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_OPERATION.format(
                        operation="Cannot change quota of active plan"
                    )
                )
        
        serializer.save()
    
    # =====================================================================
    # ACTIONS SPÉCIALISÉES - DASHBOARDS ET ANALYSE
    # =====================================================================
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        Dashboard complet du Sales Plan avec analyse temps réel.
        
        GET /sales-plans/{id}/dashboard/
        
        Retourne :
        - Analyse temporelle (jours restants, pourcentages)
        - État des milestones avec gaps et requirements
        - Contribution des campagnes liées
        - Métriques de performance vs quota
        - Données pour visualisations (graphiques)
        """
        sales_plan = self.get_object()
        
        try:
            # Utiliser le service de planification pour analyse complète
            analysis = SalesPlanningService.generate_complete_analysis(sales_plan)
            
            return Response({
                'success': True,
                'data': {
                    'sales_plan': SalesPlanSerializer(
                        sales_plan, 
                        context=self.get_serializer_context()
                    ).data,
                    'planning_analysis': analysis,
                    'dashboard_metadata': {
                        'generated_at': analysis['generated_at'],
                        'refresh_interval': '5_minutes',  # Suggéré pour frontend
                        'data_sources': ['UserPerformanceService', 'CRM_realtime'],
                        'last_signal_update': sales_plan.last_progress_update.isoformat() if sales_plan.last_progress_update else None
                    }
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Dashboard analysis failed: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['get'])
    def planning_analysis(self, request, pk=None):
        """
        Analyse détaillée de planification - version extended du dashboard.
        
        GET /sales-plans/{id}/planning-analysis/
        
        Inclut données additionnelles pour :
        - Projections avancées
        - Recommandations d'actions
        - Analyse comparative historique
        """
        sales_plan = self.get_object()
        
        try:
            # Analyse complète
            analysis = SalesPlanningService.generate_complete_analysis(sales_plan)
            
            # Données supplémentaires pour planning analysis
            extended_data = {
                'planning_recommendations': self._generate_planning_recommendations(sales_plan, analysis),
                'historical_context': self._get_historical_context(sales_plan),
                'risk_assessment': self._assess_plan_risks(sales_plan, analysis)
            }
            
            return Response({
                'success': True,
                'data': {
                    'sales_plan': SalesPlanSerializer(
                        sales_plan, 
                        context=self.get_serializer_context()
                    ).data,
                    'core_analysis': analysis,
                    'extended_analysis': extended_data
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Planning analysis failed: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['get'])
    def quick_summary(self, request, pk=None):
        """
        Résumé rapide pour widgets de dashboard.
        
        GET /sales-plans/{id}/quick-summary/
        
        Version légère avec métriques essentielles :
        - Achievement rate
        - Jours restants
        - Statut on-track/off-track
        - Prochaine action critique
        """
        sales_plan = self.get_object()
        
        try:
            # Utiliser méthode rapide du service
            summary = SalesPlanningService.get_quick_summary(sales_plan)
            
            return Response({
                'success': True,
                'data': summary
            })
            
        except Exception as e:
            # Fallback gracieux pour widgets
            return Response({
                'success': True,
                'data': {
                    'plan_name': sales_plan.name,
                    'error': 'Summary unavailable',
                    'fallback_data': {
                        'achievement_rate': 0,
                        'time_remaining_percentage': 50,
                        'is_on_track': False
                    }
                }
            })
    
    @action(detail=False, methods=['get'])
    def my_plans(self, request):
        """
        Plans de l'utilisateur courant avec résumés.
        
        GET /sales-plans/my-plans/
        
        Filtre automatiquement par request.user
        Inclut résumé de performance pour chaque plan
        """
        user_plans = self.get_queryset().filter(user=request.user)
        
        # Paginer si nécessaire
        page = self.paginate_queryset(user_plans)
        if page is not None:
            # Ajouter résumés rapides pour chaque plan
            plans_with_summary = []
            for plan in page:
                plan_data = SalesPlanSerializer(
                    plan, 
                    context=self.get_serializer_context()
                ).data
                
                # Ajouter quick summary
                try:
                    quick_summary = SalesPlanningService.get_quick_summary(plan)
                    plan_data['quick_metrics'] = quick_summary
                except Exception:
                    plan_data['quick_metrics'] = {'error': 'Metrics unavailable'}
                
                plans_with_summary.append(plan_data)
            
            return self.get_paginated_response(plans_with_summary)
        
        # Version non paginée
        serializer = SalesPlanSerializer(
            user_plans, 
            many=True, 
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': user_plans.count()
        })
    
    @action(detail=False, methods=['get'])
    def team_plans(self, request):
        """
        Vue consolidée des plans d'équipe pour managers.
        
        GET /sales-plans/team-plans/?team_id=123
        GET /sales-plans/team-plans/?user_ids=1,2,3
        
        Paramètres :
        - team_id : Plans de tous les membres d'une équipe
        - user_ids : Plans d'utilisateurs spécifiques (CSV)
        - include_summary : true/false pour inclure métriques agrégées
        """
        queryset = self.get_queryset()
        
        # Filtrage par équipe
        team_id = request.query_params.get('team_id')
        if team_id:
            queryset = queryset.filter(user__team_id=team_id)
        
        # Filtrage par utilisateurs spécifiques
        user_ids = request.query_params.get('user_ids')
        if user_ids:
            user_id_list = [int(uid.strip()) for uid in user_ids.split(',')]
            queryset = queryset.filter(user_id__in=user_id_list)
        
        # Si aucun filtre, utiliser l'équipe du requester
        if not team_id and not user_ids:
            if hasattr(request.user, 'team') and request.user.team:
                queryset = queryset.filter(user__team=request.user.team)
            else:
                # Fallback : seulement les plans de l'utilisateur
                queryset = queryset.filter(user=request.user)
        
        # Paginer
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SalesPlanSerializer(
                page, 
                many=True, 
                context=self.get_serializer_context()
            )
            
            # Ajouter métriques agrégées si demandé
            response_data = serializer.data
            if request.query_params.get('include_summary', '').lower() == 'true':
                response_data = {
                    'plans': serializer.data,
                    'team_summary': self._calculate_team_summary(page)
                }
            
            return self.get_paginated_response(response_data)
        
        # Version non paginée
        serializer = SalesPlanSerializer(
            queryset, 
            many=True, 
            context=self.get_serializer_context()
        )
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': queryset.count()
        })
    
    # =====================================================================
    # ACTIONS DE GESTION DU PLAN
    # =====================================================================
    
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        """
        Activer un Sales Plan.
        
        PATCH /sales-plans/{id}/activate/
        
        Passe le statut à ACTIVE et déclenche recalcul des milestones.
        """
        sales_plan = self.get_object()
        
        if sales_plan.status == SalesPlan.Status.ACTIVE:
            return Response({
                'success': True,
                'message': 'Sales Plan is already active'
            })
        
        # Valider que le quota est actif
        if not sales_plan.quota.is_active:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation="Cannot activate plan with inactive quota"
                )
            )
        
        try:
            sales_plan.status = SalesPlan.Status.ACTIVE
            sales_plan.save()
            
            # Déclencher recalcul des milestones (via signaux automatiques)
            return Response({
                'success': True,
                'message': 'Sales Plan activated successfully',
                'data': SalesPlanSerializer(sales_plan).data
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to activate plan: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['patch'])
    def pause(self, request, pk=None):
        """
        Mettre en pause un Sales Plan.
        
        PATCH /sales-plans/{id}/pause/
        """
        sales_plan = self.get_object()
        
        if sales_plan.status == SalesPlan.Status.PAUSED:
            return Response({
                'success': True,
                'message': 'Sales Plan is already paused'
            })
        
        sales_plan.status = SalesPlan.Status.PAUSED
        sales_plan.save()
        
        return Response({
            'success': True,
            'message': 'Sales Plan paused successfully',
            'data': SalesPlanSerializer(sales_plan).data
        })
    
    @action(detail=True, methods=['post'])
    def refresh_data(self, request, pk=None):
        """
        Forcer actualisation des données du plan.
        
        POST /sales-plans/{id}/refresh-data/
        
        Déclenche manuellement recalcul de tous les milestones.
        Utile pour debug ou après corrections manuelles.
        """
        sales_plan = self.get_object()
        
        try:
            # Déclencher mise à jour manuelle via signaux
            from end_users.signals import trigger_manual_update_for_user
            
            updated_plans = trigger_manual_update_for_user(
                sales_plan.user.id,
                reason="manual_refresh_from_api"
            )
            
            return Response({
                'success': True,
                'message': f'Data refreshed for {updated_plans} plan(s)',
                'refresh_timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to refresh data: {str(e)}"
                )
            )
    
    # =====================================================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =====================================================================
    
    def _generate_planning_recommendations(self, sales_plan, analysis):
        """Génère recommandations d'actions basées sur l'analyse"""
        recommendations = []
        
        # Analyser les gaps des milestones
        timeline = analysis.get('timeline_analysis', {}).get('timeline', [])
        for milestone_data in timeline:
            if milestone_data.get('gap_value', 0) > 0:
                gap = milestone_data['gap_value']
                days_remaining = milestone_data.get('days_to_milestone', 0)
                daily_pace = milestone_data.get('daily_pace_needed', 0)
                
                if days_remaining < 7:
                    urgency = 'HIGH'
                elif days_remaining < 30:
                    urgency = 'MEDIUM'
                else:
                    urgency = 'LOW'
                
                recommendations.append({
                    'milestone_name': milestone_data['milestone_name'],
                    'urgency': urgency,
                    'gap': gap,
                    'daily_pace_needed': daily_pace,
                    'suggested_action': f"Focus on {milestone_data['milestone_type'].lower().replace('_', ' ')}"
                })
        
        return recommendations
    
    def _get_historical_context(self, sales_plan):
        """Récupère contexte historique pour comparaison"""
        # Version MVP simple
        return {
            'previous_plans_count': SalesPlan.objects.filter(
                user=sales_plan.user,
                created_at__lt=sales_plan.created_at
            ).count(),
            'user_avg_achievement_rate': 'N/A',  # À implémenter plus tard
            'team_benchmark': 'N/A'  # À implémenter plus tard
        }
    
    def _assess_plan_risks(self, sales_plan, analysis):
        """Évalue les risques du plan"""
        risks = []
        
        # Risque temporel
        time_analysis = analysis.get('time_analysis', {})
        time_remaining = time_analysis.get('time_remaining_percentage', 100)
        
        if time_remaining < 25:
            risks.append({
                'type': 'TIME_PRESSURE',
                'severity': 'HIGH',
                'description': 'Less than 25% of time remaining'
            })
        
        # Risque de performance
        quota_analysis = analysis.get('quota_analysis', {})
        achievement_rate = quota_analysis.get('achievement_rate', 0)
        
        if achievement_rate < 50 and time_remaining < 50:
            risks.append({
                'type': 'UNDERPERFORMANCE',
                'severity': 'HIGH',
                'description': 'Low achievement rate with limited time'
            })
        
        return risks
    
    def _calculate_team_summary(self, plans):
        """Calcule métriques agrégées pour l'équipe"""
        if not plans:
            return {}
        
        total_plans = len(plans)
        active_plans = len([p for p in plans if p.status == SalesPlan.Status.ACTIVE])
        
        return {
            'total_plans': total_plans,
            'active_plans': active_plans,
            'completion_rate': f"{(active_plans/total_plans*100):.1f}%" if total_plans > 0 else "0%",
            'team_members': len(set(p.user.id for p in plans))
        }