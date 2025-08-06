# apps/end_users/views/sales_plan_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime
from django.db.models import Q, Count
from django.utils import timezone
from django.db import transaction

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager

from end_users.models import SalesPlan, SalesQuota, User
from end_users.serializers.sales_plan_serializer import SalesPlanSerializer
from ..services.sales_planning_service import SalesPlanningService


class SalesPlanViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des Sales Plans.
    
    ✅ Style cohérent avec SalesQuotaViewSet :
    - Validation systématique des serializers
    - Gestion d'erreurs standardisée  
    - Réponses structurées avec success/message/data
    - Usage des services pour logique métier
    - Transactions atomiques
    - Messages d'erreur cohérents
    
    ✅ SIMPLIFIÉ POUR MVP (7 actions → 3 actions) :
    - CRUD standard (list/retrieve/create/update/delete)
    - dashboard() : Analyse complète via SalesPlanningService
    - my_plans() : Plans utilisateur courant
    - activate() : Activation/désactivation des plans
    
    ❌ SUPPRIMÉ (trop complexe pour MVP) :
    - planning_analysis() : Doublonne avec dashboard
    - team_plans() : Complexité manager non essentielle
    - pause() : activate() gère tout
    - refresh_data() : Signaux automatiques suffisants
    """
    
    # ✅ Attributs obligatoires (style SalesQuotaViewSet)
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
    
    def get_queryset(self):
        """✅ QuerySet optimisé avec client scoping (style SalesQuotaViewSet)"""
        # ✅ Utiliser setup_eager_loading du serializer
        queryset = SalesPlanSerializer.setup_eager_loading(SalesPlan.objects.all())
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filtres pratiques
        active_only = self.request.query_params.get('active_only', 'true')
        if active_only.lower() == 'true':
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
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="user_id must be a valid integer")
                )
        
        return queryset
    
    def get_serializer_context(self):
        """✅ Add client_id to serializer context (style SalesQuotaViewSet)"""
        context = super().get_serializer_context()
        context.update({
            'client_id': self.get_client_id(),
            # Inclure données de performance pour actions détaillées
            'include_performance_data': self.action in [
                'dashboard', 'retrieve', 'list'
            ]
        })
        return context
    
    def list(self, request, *args, **kwargs):
        """
        ✅ Liste tous les plans avec informations supplémentaires (style SalesQuotaViewSet)
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtres additionnels
        target_type = request.query_params.get('target_type')
        search = request.query_params.get('search')
        
        if target_type:
            queryset = queryset.filter(quota__target_type=target_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # ✅ Ajouter des stats globales (style SalesQuotaViewSet)
        stats = {
            'total_plans': queryset.count(),
            'active_plans': queryset.filter(status=SalesPlan.Status.ACTIVE).count(),
            'completed_plans': queryset.filter(status=SalesPlan.Status.COMPLETED).count(),
            'quota_types': list(queryset.values_list('quota__target_type', flat=True).distinct())
        }
        
        return Response({
            'success': True,
            'data': serializer.data,
            'meta': {
                'stats': stats,
                'filters_applied': {
                    'target_type': target_type,
                    'search': search,
                    'active_only': request.query_params.get('active_only', 'true'),
                    'current_period': request.query_params.get('current_period')
                }
            }
        })
    
    def retrieve(self, request, *args, **kwargs):
        """
        ✅ Récupère un plan avec toutes ses données (style SalesQuotaViewSet)
        """
        # get_object() applique automatiquement le ClientScope
        instance = self.get_object()
        
        # Utiliser le serializer complet avec performance_data
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """
        ✅ Crée un nouveau plan (style SalesQuotaViewSet avec validation)
        """
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                # Validation des données
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Validation utilisateur (style SalesQuotaViewSet)
                user_id = serializer.validated_data.get('user')
                if not user_id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field='user')
                    )
                
                # Vérifier que l'utilisateur appartient au même client
                try:
                    user = User.objects.get(id=user_id.id, client_account_id=client_id)
                except User.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="User not found or doesn't belong to this client"
                        )
                    )
                
                # Valider que le quota est actif
                quota = serializer.validated_data.get('quota')
                if quota and not quota.is_active:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="quota must be active"
                        )
                    )
                
                # Créer le plan avec client_id
                sales_plan = serializer.save(
                    client_id=client_id,
                    created_by=request.user
                )
                
                return Response({
                    'success': True,
                    'message': f'Sales Plan "{sales_plan.name}" created successfully',
                    'data': {
                        'plan_id': sales_plan.id,
                        'plan_name': sales_plan.name,
                        'status': sales_plan.status,
                        'user_name': sales_plan.user.get_full_name(),
                        'quota_type': sales_plan.quota.target_type if sales_plan.quota else None,
                        'period_start': sales_plan.period_start.isoformat(),
                        'period_end': sales_plan.period_end.isoformat()
                    }
                }, status=status.HTTP_201_CREATED)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create sales plan: {str(e)}"
                )
            )
    
    def update(self, request, *args, **kwargs):
        """
        ✅ Met à jour un plan existant (style SalesQuotaViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                partial = kwargs.pop('partial', False)
                
                # Validation des données
                serializer = self.get_serializer(instance, data=request.data, partial=partial)
                serializer.is_valid(raise_exception=True)
                
                # Validation : empêcher modification du quota si le plan est actif
                if (instance.status == SalesPlan.Status.ACTIVE and 
                    'quota' in serializer.validated_data):
                    new_quota = serializer.validated_data['quota']
                    if new_quota != instance.quota:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_OPERATION.format(
                                operation="Cannot change quota of active plan"
                            )
                        )
                
                # Sauvegarder avec updated_by
                updated_plan = serializer.save(updated_by=request.user)
                
                return Response({
                    'success': True,
                    'message': f'Sales Plan "{updated_plan.name}" updated successfully',
                    'data': {
                        'plan_id': updated_plan.id,
                        'plan_name': updated_plan.name,
                        'status': updated_plan.status,
                        'updated_at': updated_plan.updated_at.isoformat()
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update sales plan: {str(e)}"
                )
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        ✅ Supprime un plan (style SalesQuotaViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                plan_name = instance.name
                
                # Validation : ne pas supprimer un plan actif avec milestones
                if instance.status == SalesPlan.Status.ACTIVE:
                    milestones_count = instance.milestones.count()
                    if milestones_count > 0:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_OPERATION.format(
                                operation=f"Cannot delete active plan with {milestones_count} milestones. Please complete it first."
                            )
                        )
                
                instance.delete()
                
                return Response({
                    'success': True,
                    'message': f'Sales Plan "{plan_name}" deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to delete sales plan: {str(e)}"
                )
            )
    
    # =====================================================================
    # ✅ ACTIONS SIMPLIFIÉES POUR MVP (3 actions seulement)
    # =====================================================================
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        ✅ Dashboard complet du Sales Plan avec analyse temps réel (style SalesQuotaViewSet)
        
        GET /sales-plans/{id}/dashboard/
        
        Utilise SalesPlanningService corrigé pour analyse complète.
        """
        try:
            sales_plan = self.get_object()
            
            # Validation de l'ID
            if not pk:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Sales Plan ID')
                )
            
            try:
                plan_id_int = int(pk)
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Sales Plan ID must be a valid integer")
                )
            
            # ✅ Utiliser le service corrigé
            analysis = SalesPlanningService.generate_complete_analysis(sales_plan)
            
            return Response({
                'success': True,
                'data': {
                    'sales_plan': SalesPlanSerializer(
                        sales_plan, 
                        context=self.get_serializer_context()
                    ).data,
                    'analysis': analysis
                },
                'meta': {
                    'plan_id': plan_id_int,
                    'plan_name': sales_plan.name,
                    'timestamp': timezone.now().isoformat(),
                    'client_id': self.get_client_id()
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Dashboard analysis failed: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def my_plans(self, request):
        """
        ✅ Plans utilisateur connecté avec pagination (style SalesQuotaViewSet)
        """
        try:
            user_plans = self.get_queryset().filter(user=request.user)
            
            if not user_plans.exists():
                return Response({
                    'success': True,
                    'data': [],
                    'message': 'No sales plans found for current user'
                })
            
            # Pagination si nécessaire
            page = self.paginate_queryset(user_plans)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(user_plans, many=True)
            
            # Stats utilisateur
            stats = {
                'total_plans': user_plans.count(),
                'active_plans': user_plans.filter(status=SalesPlan.Status.ACTIVE).count(),
                'completed_plans': user_plans.filter(status=SalesPlan.Status.COMPLETED).count()
            }
            
            return Response({
                'success': True,
                'data': serializer.data,
                'meta': {
                    'user_stats': stats,
                    'user_info': {
                        'id': str(request.user.id),
                        'name': request.user.get_full_name(),
                        'team': request.user.team.name if request.user.team else None
                    }
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get user plans: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        """
        ✅ Activer/désactiver plan avec gestion statuts (style SalesQuotaViewSet)
        
        PATCH /sales-plans/{id}/activate/
        Body: {"status": "ACTIVE"} ou {"status": "PAUSED"} ou {"status": "COMPLETED"}
        """
        try:
            with transaction.atomic():
                sales_plan = self.get_object()
                
                # Validation de l'ID
                if not pk:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field='Sales Plan ID')
                    )
                
                try:
                    plan_id_int = int(pk)
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Sales Plan ID must be a valid integer")
                    )
                
                # Récupérer le nouveau statut
                new_status = request.data.get('status', 'ACTIVE')
                
                # Validation du statut
                valid_statuses = [choice[0] for choice in SalesPlan.Status.choices]
                if new_status not in valid_statuses:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"status must be one of {valid_statuses}"
                        )
                    )
                
                # Validation : ne peut activer que si quota actif
                if new_status == SalesPlan.Status.ACTIVE:
                    if not sales_plan.quota.is_active:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_OPERATION.format(
                                operation="Cannot activate plan with inactive quota"
                            )
                        )
                
                # Appliquer le changement
                old_status = sales_plan.status
                sales_plan.status = new_status
                sales_plan.save(update_fields=['status'])
                
                # Message adapté
                if new_status == old_status:
                    message = f'Sales Plan "{sales_plan.name}" is already {new_status.lower()}'
                else:
                    message = f'Sales Plan "{sales_plan.name}" status changed from {old_status} to {new_status}'
                
                return Response({
                    'success': True,
                    'message': message,
                    'data': {
                        'plan_id': sales_plan.id,
                        'plan_name': sales_plan.name,
                        'old_status': old_status,
                        'new_status': new_status,
                        'updated_at': timezone.now().isoformat()
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update plan status: {str(e)}"
                )
            )