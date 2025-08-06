# apps/end_users/views/sales_milestone_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime, timedelta
from django.db.models import Q, Count
from django.utils import timezone
from django.db import transaction

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager

from end_users.models import SalesPlan, SalesMilestone, User
from end_users.serializers.sales_milestone_serializer import SalesMilestoneSerializer


class SalesMilestoneViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des Sales Milestones.
    
    ✅ Style cohérent avec SalesQuotaViewSet :
    - Validation systématique des serializers
    - Gestion d'erreurs standardisée  
    - Réponses structurées avec success/message/data
    - Usage des services pour logique métier
    - Transactions atomiques
    - Messages d'erreur cohérents
    
    ✅ SIMPLIFIÉ POUR MVP (7 actions → 2 actions) :
    - CRUD standard (list/retrieve/create/update/delete)
    - update_progress() : Force recalcul milestone
    - my_milestones() : Milestones utilisateur courant
    
    ❌ SUPPRIMÉ (trop complexe pour MVP) :
    - batch_update() : Peut être fait via API standard
    - overdue() : Filtrage via query params suffisant
    - upcoming() : Filtrage via query params suffisant
    - by_plan() : Filtrage via query params suffisant
    - mark_achieved() : update() standard suffisant
    - reset_progress() : update() standard suffisant
    """
    
    # ✅ Attributs obligatoires (style SalesQuotaViewSet)
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
    
    def get_queryset(self):
        """✅ QuerySet optimisé avec client scoping (style SalesQuotaViewSet)"""
        # ✅ Utiliser setup_eager_loading du serializer
        queryset = SalesMilestoneSerializer.setup_eager_loading(SalesMilestone.objects.all())
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # ✅ Filtres simplifiés via query params (remplace actions supprimées)
        
        # Filtre plans actifs seulement
        active_plans_only = self.request.query_params.get('active_plans_only', 'true')
        if active_plans_only.lower() == 'true':
            queryset = queryset.filter(
                sales_plan__status__in=[
                    SalesPlan.Status.ACTIVE,
                    SalesPlan.Status.DRAFT
                ]
            )
        
        # Filtre par période (remplace overdue/upcoming actions)
        period_filter = self.request.query_params.get('period')
        if period_filter:
            today = date.today()
            
            if period_filter == 'overdue':
                queryset = queryset.filter(
                    target_date__lt=today,
                    status__in=[
                        SalesMilestone.Status.PENDING, 
                        SalesMilestone.Status.IN_PROGRESS
                    ]
                )
            elif period_filter == 'upcoming':
                days = int(self.request.query_params.get('days', 30))
                end_date = today + timedelta(days=min(days, 90))  # Limite 90 jours
                queryset = queryset.filter(
                    target_date__gte=today,
                    target_date__lte=end_date,
                    status__in=[
                        SalesMilestone.Status.PENDING,
                        SalesMilestone.Status.IN_PROGRESS
                    ]
                )
            elif period_filter == 'current':
                # Milestones dans les 30 prochains jours
                end_date = today + timedelta(days=30)
                queryset = queryset.filter(
                    target_date__gte=today,
                    target_date__lte=end_date
                )
        
        # Filtre par plan spécifique (remplace by_plan action)
        plan_id = self.request.query_params.get('sales_plan_id')
        if plan_id:
            try:
                queryset = queryset.filter(sales_plan_id=int(plan_id))
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="sales_plan_id must be a valid integer")
                )
        
        return queryset
    
    def get_serializer_context(self):
        """✅ Add client_id to serializer context (style SalesQuotaViewSet)"""
        context = super().get_serializer_context()
        context.update({
            'client_id': self.get_client_id(),
            # Inclure données de progress pour actions détaillées
            'include_progress_data': self.action in [
                'update_progress', 'retrieve', 'list'
            ]
        })
        return context
    
    def list(self, request, *args, **kwargs):
        """
        ✅ Liste tous les milestones avec informations supplémentaires (style SalesQuotaViewSet)
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtres additionnels
        milestone_type = request.query_params.get('milestone_type')
        search = request.query_params.get('search')
        
        if milestone_type:
            queryset = queryset.filter(milestone_type=milestone_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search) |
                Q(sales_plan__name__icontains=search) |
                Q(sales_plan__user__first_name__icontains=search) |
                Q(sales_plan__user__last_name__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # ✅ Ajouter des stats globales (style SalesQuotaViewSet)
        today = date.today()
        stats = {
            'total_milestones': queryset.count(),
            'achieved_count': queryset.filter(status=SalesMilestone.Status.ACHIEVED).count(),
            'overdue_count': queryset.filter(
                target_date__lt=today,
                status__in=[SalesMilestone.Status.PENDING, SalesMilestone.Status.IN_PROGRESS]
            ).count(),
            'milestone_types': list(queryset.values_list('milestone_type', flat=True).distinct())
        }
        
        return Response({
            'success': True,
            'data': serializer.data,
            'meta': {
                'stats': stats,
                'filters_applied': {
                    'milestone_type': milestone_type,
                    'search': search,
                    'period': request.query_params.get('period'),
                    'active_plans_only': request.query_params.get('active_plans_only', 'true'),
                    'sales_plan_id': request.query_params.get('sales_plan_id')
                }
            }
        })
    
    def retrieve(self, request, *args, **kwargs):
        """
        ✅ Récupère un milestone avec toutes ses données (style SalesQuotaViewSet)
        """
        # get_object() applique automatiquement le ClientScope
        instance = self.get_object()
        
        # Utiliser le serializer complet avec progress_data
        serializer = self.get_serializer(instance)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """
        ✅ Crée un nouveau milestone (style SalesQuotaViewSet avec validation)
        """
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                # Validation des données
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Validation sales_plan
                sales_plan = serializer.validated_data.get('sales_plan')
                if not sales_plan:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field='sales_plan')
                    )
                
                # Vérifier que le sales_plan appartient au même client
                if sales_plan.client_id != client_id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Sales Plan doesn't belong to this client"
                        )
                    )
                
                # Validation : target_date dans période du plan
                target_date = serializer.validated_data.get('target_date')
                if target_date and sales_plan:
                    if not (sales_plan.period_start <= target_date <= sales_plan.period_end):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_DATE_RANGE.format(
                                start_date=sales_plan.period_start,
                                end_date=sales_plan.period_end
                            )
                        )
                
                # Créer le milestone avec client_id
                milestone = serializer.save(
                    client_id=client_id,
                    created_by=request.user
                )
                
                # Déclencher calcul initial
                try:
                    milestone.update_progress()
                except Exception:
                    # Ne pas faire échouer la création si le calcul initial échoue
                    pass
                
                return Response({
                    'success': True,
                    'message': f'Sales Milestone "{milestone.name}" created successfully',
                    'data': {
                        'milestone_id': milestone.id,
                        'milestone_name': milestone.name,
                        'milestone_type': milestone.milestone_type,
                        'target_value': float(milestone.target_value),
                        'target_date': milestone.target_date.isoformat(),
                        'sales_plan_name': milestone.sales_plan.name,
                        'status': milestone.status
                    }
                }, status=status.HTTP_201_CREATED)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create milestone: {str(e)}"
                )
            )
    
    def update(self, request, *args, **kwargs):
        """
        ✅ Met à jour un milestone existant (style SalesQuotaViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                partial = kwargs.pop('partial', False)
                
                # Validation des données
                serializer = self.get_serializer(instance, data=request.data, partial=partial)
                serializer.is_valid(raise_exception=True)
                
                # Sauvegarder avec updated_by
                updated_milestone = serializer.save(updated_by=request.user)
                
                # Si target_value ou target_date modifiés, recalculer
                if 'target_value' in serializer.validated_data or 'target_date' in serializer.validated_data:
                    try:
                        updated_milestone.update_progress()
                        updated_milestone.refresh_from_db()
                    except Exception:
                        # Log erreur mais ne pas faire échouer la mise à jour
                        pass
                
                return Response({
                    'success': True,
                    'message': f'Sales Milestone "{updated_milestone.name}" updated successfully',
                    'data': {
                        'milestone_id': updated_milestone.id,
                        'milestone_name': updated_milestone.name,
                        'status': updated_milestone.status,
                        'achievement_rate': float(updated_milestone.achievement_rate),
                        'updated_at': updated_milestone.updated_at.isoformat()
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update milestone: {str(e)}"
                )
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        ✅ Supprime un milestone (style SalesQuotaViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                milestone_name = instance.name
                
                # Validation : ne pas supprimer un milestone achieved avec performance
                if instance.status == SalesMilestone.Status.ACHIEVED and float(instance.achievement_rate) >= 100:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_OPERATION.format(
                            operation="Cannot delete achieved milestone. Please reset it first if needed."
                        )
                    )
                
                instance.delete()
                
                return Response({
                    'success': True,
                    'message': f'Sales Milestone "{milestone_name}" deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to delete milestone: {str(e)}"
                )
            )
    
    # =====================================================================
    # ✅ ACTIONS SIMPLIFIÉES POUR MVP (2 actions seulement)
    # =====================================================================
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """
        ✅ Force la mise à jour du progrès d'un milestone (style SalesQuotaViewSet)
        
        POST /sales-milestones/{id}/update-progress/
        
        Déclenche recalcul via UserPerformanceService et met à jour :
        - current_value, achievement_rate, status, last_progress_update
        """
        try:
            milestone = self.get_object()
            
            # Validation de l'ID
            if not pk:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Milestone ID')
                )
            
            try:
                milestone_id_int = int(pk)
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Milestone ID must be a valid integer")
                )
            
            # ✅ Déclencher mise à jour via modèle corrigé
            result = milestone.update_progress()
            
            # Recharger pour obtenir données fraîches
            milestone.refresh_from_db()
            
            return Response({
                'success': True,
                'message': f'Milestone "{milestone.name}" progress updated successfully',
                'data': {
                    'milestone': SalesMilestoneSerializer(milestone, context=self.get_serializer_context()).data,
                    'update_result': result
                },
                'meta': {
                    'milestone_id': milestone_id_int,
                    'milestone_name': milestone.name,
                    'timestamp': timezone.now().isoformat(),
                    'client_id': self.get_client_id()
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update progress: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def my_milestones(self, request):
        """
        ✅ Milestones utilisateur connecté avec pagination (style SalesQuotaViewSet)
        """
        try:
            user_milestones = self.get_queryset().filter(sales_plan__user=request.user)
            
            if not user_milestones.exists():
                return Response({
                    'success': True,
                    'data': [],
                    'message': 'No milestones found for current user'
                })
            
            # Pagination si nécessaire
            page = self.paginate_queryset(user_milestones)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(user_milestones, many=True)
            
            # Stats utilisateur
            today = date.today()
            stats = {
                'total_milestones': user_milestones.count(),
                'achieved_count': user_milestones.filter(status=SalesMilestone.Status.ACHIEVED).count(),
                'overdue_count': user_milestones.filter(
                    target_date__lt=today,
                    status__in=[SalesMilestone.Status.PENDING, SalesMilestone.Status.IN_PROGRESS]
                ).count(),
                'upcoming_count': user_milestones.filter(
                    target_date__gte=today,
                    target_date__lte=today + timedelta(days=7),
                    status__in=[SalesMilestone.Status.PENDING, SalesMilestone.Status.IN_PROGRESS]
                ).count()
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
                    detail=f"Failed to get user milestones: {str(e)}"
                )
            )