# apps/end_users/views/sales_quota_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import date, datetime
from django.db.models import Q, Count, Max, Min
from django.db import transaction
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager

from end_users.models import SalesQuota, User
from end_users.serializers.sales_quota_serializer import (
    SalesQuotaSerializer,
    SalesQuotaSummarySerializer,
    SalesQuotaListSerializer,
    SalesQuotaViewSetSerializer,
    SalesQuotaCreateSerializer,
    SalesQuotaUpdateSerializer
)
from ..services import UserPerformanceService


class SalesQuotaViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des quotas de vente.
    
    ✅ Style cohérent avec BuyingProcessViewSet :
    - Validation systématique des serializers
    - Gestion d'erreurs standardisée  
    - Réponses structurées avec success/message/data
    - Usage des services pour logique métier
    - Transactions atomiques
    - Messages d'erreur cohérents
    
    ✅ Corrections MVP appliquées :
    - Target types cohérents (lowercase)
    - Filtrage status au lieu de is_active  
    - N+1 queries éliminé avec serializers optimisés
    """
    
    # ✅ Attributs obligatoires (style BuyingProcessViewSet)
    queryset = SalesQuota.objects.all()
    serializer_class = SalesQuotaSerializer
    entity_name = 'sales_quota'
    
    # Filtres et recherche - ✅ CORRIGÉ : status au lieu de is_active
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['target_type', 'status', 'user', 'user__team']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'name']
    ordering_fields = ['created_at', 'period_start', 'period_end', 'target_value']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """✅ QuerySet optimisé avec client scoping (style BuyingProcessViewSet)"""
        queryset = SalesQuotaViewSetSerializer.get_optimized_queryset()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Add annotations for better performance
        queryset = queryset.annotate(
            # Futurs compteurs si nécessaire
        )
        
        # ✅ CORRIGÉ : Filtres sur status='active' au lieu de is_active=True
        active_only = self.request.query_params.get('active_only', 'true')
        if active_only.lower() == 'true':
            queryset = queryset.filter(status='active')
        
        # Filtre par période courante
        current_period = self.request.query_params.get('current_period')
        if current_period and current_period.lower() == 'true':
            today = date.today()
            queryset = queryset.filter(
                period_start__lte=today,
                period_end__gte=today
            )
        
        # Filtre par utilisateur spécifique (utile pour managers)
        user_id = self.request.query_params.get('user_id')
        if user_id:
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="user_id must be a valid integer")
                )
        
        return queryset
    
    def get_serializer_class(self):
        """✅ ÉTAPE 3 : Serializers optimisés selon l'action (évite N+1)"""
        if self.action == 'list':
            return SalesQuotaListSerializer          # ✅ Pas de performance_data = Pas de N+1
        elif self.action == 'retrieve':
            return SalesQuotaSerializer              # ✅ Performance individuelle OK  
        elif self.action == 'create':
            return SalesQuotaCreateSerializer        # ✅ Création simplifiée
        elif self.action in ['update', 'partial_update']:
            return SalesQuotaUpdateSerializer        # ✅ Update optimisé
        elif self.action in ['performance', 'team_summary']:
            return SalesQuotaSummarySerializer       # ✅ Calculs locaux uniquement
        return SalesQuotaViewSetSerializer
    
    def get_serializer_context(self):
        """✅ Add client_id to serializer context (style BuyingProcessViewSet)"""
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context
    
    def list(self, request, *args, **kwargs):
        """
        ✅ Liste tous les quotas avec informations supplémentaires (style BuyingProcessViewSet)
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtres additionnels
        target_type = request.query_params.get('target_type')
        search = request.query_params.get('search')
        
        if target_type:
            queryset = queryset.filter(target_type=target_type)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # ✅ Ajouter des stats globales (style BuyingProcessViewSet)
        stats = {
            'total_quotas': queryset.count(),
            'active_quotas': queryset.filter(status='active').count(),
            'completed_quotas': queryset.filter(status='completed').count(),
            'target_types': list(queryset.values_list('target_type', flat=True).distinct())
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
        ✅ Récupère un quota avec toutes ses données (style BuyingProcessViewSet)
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
        ✅ Crée un nouveau quota (style BuyingProcessViewSet avec validation)
        """
        client_id = self.get_client_id()
        
        try:
            with transaction.atomic():
                # Validation des données
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Validation utilisateur (style BuyingProcessViewSet)
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
                
                # Créer le quota avec client_id
                quota = serializer.save(
                    client_id=client_id,
                    created_by=request.user
                )
                
                return Response({
                    'success': True,
                    'message': f'Quota "{quota.name}" created successfully',
                    'data': {
                        'quota_id': quota.id,
                        'quota_name': quota.name,
                        'target_type': quota.target_type,
                        'target_value': float(quota.target_value),
                        'user_name': quota.user.get_full_name(),
                        'period_start': quota.period_start.isoformat(),
                        'period_end': quota.period_end.isoformat(),
                        'status': quota.status
                    }
                }, status=status.HTTP_201_CREATED)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create quota: {str(e)}"
                )
            )
    
    def update(self, request, *args, **kwargs):
        """
        ✅ Met à jour un quota existant (style BuyingProcessViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                partial = kwargs.pop('partial', False)
                
                # Validation des données
                serializer = self.get_serializer(instance, data=request.data, partial=partial)
                serializer.is_valid(raise_exception=True)
                
                # Sauvegarder avec updated_by
                updated_quota = serializer.save(updated_by=request.user)
                
                return Response({
                    'success': True,
                    'message': f'Quota "{updated_quota.name}" updated successfully',
                    'data': {
                        'quota_id': updated_quota.id,
                        'quota_name': updated_quota.name,
                        'target_type': updated_quota.target_type,
                        'target_value': float(updated_quota.target_value),
                        'status': updated_quota.status,
                        'updated_at': updated_quota.updated_at.isoformat()
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to update quota: {str(e)}"
                )
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        ✅ Supprime un quota (style BuyingProcessViewSet)
        """
        try:
            with transaction.atomic():
                instance = self.get_object()
                quota_name = instance.name
                
                # Validation : ne pas supprimer un quota actif avec performance
                if instance.status == SalesQuota.QuotaStatus.ACTIVE:
                    # Vérifier s'il y a de la performance enregistrée
                    try:
                        current_value = instance.get_current_value()
                        if current_value > 0:
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_OPERATION.format(
                                    operation="Cannot delete active quota with recorded performance. Please complete it first."
                                )
                            )
                    except Exception:
                        pass  # Si erreur de calcul, autoriser suppression
                
                instance.delete()
                
                return Response({
                    'success': True,
                    'message': f'Quota "{quota_name}" deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to delete quota: {str(e)}"
                )
            )
    
    # ===== ACTIONS PERSONNALISÉES =====
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        ✅ Performance détaillée d'un quota spécifique (style BuyingProcessViewSet)
        """
        try:
            quota = self.get_object()
            
            # Validation de l'ID
            if not pk:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Quota ID')
                )
            
            try:
                quota_id_int = int(pk)
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Quota ID must be a valid integer")
                )
            
            # Appel au service pour récupérer les données de performance
            performance_data = UserPerformanceService.get_user_quota_performance(
                user_id=quota.user.id,
                quota_id=quota_id_int,
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': performance_data,
                'meta': {
                    'quota_id': quota_id_int,
                    'quota_name': quota.name,
                    'timestamp': timezone.now().isoformat(),
                    'client_id': self.get_client_id()
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get quota performance: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def team_summary(self, request):
        """
        ✅ Résumé équipe avec validation (style BuyingProcessViewSet)
        """
        try:
            user = request.user
            
            if not user.team:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="User is not assigned to a team"
                    )
                )
            
            # ✅ CORRIGÉ : Filter sur status='active'
            team_quotas = self.get_queryset().filter(
                user__team=user.team,
                status='active'
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
                    },
                    'message': f'No active quotas found for team "{user.team.name}"'
                })
            
            # Utiliser le serializer optimisé (pas de N+1)
            serializer = SalesQuotaSummarySerializer(team_quotas, many=True)
            
            total_quotas = team_quotas.count()
            summary = {
                'team_info': {
                    'id': str(user.team.id),
                    'name': user.team.name,
                    'members_count': user.team.members.filter(is_active=True).count()
                },
                'quotas': serializer.data,
                'summary': {
                    'total_quotas': total_quotas,
                    'active_quotas': total_quotas,
                    'target_types': list(team_quotas.values_list('target_type', flat=True).distinct())
                }
            }
            
            return Response({
                'success': True,
                'data': summary
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get team summary: {str(e)}"
                )
            )
    
    @action(detail=False, methods=['get'])
    def my_quotas(self, request):
        """
        ✅ Quotas utilisateur connecté avec pagination (style BuyingProcessViewSet)
        """
        try:
            user_quotas = self.get_queryset().filter(user=request.user)
            
            if not user_quotas.exists():
                return Response({
                    'success': True,
                    'data': [],
                    'message': 'No quotas found for current user'
                })
            
            # Pagination si nécessaire
            page = self.paginate_queryset(user_quotas)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(user_quotas, many=True)
            
            # Stats utilisateur
            stats = {
                'total_quotas': user_quotas.count(),
                'active_quotas': user_quotas.filter(status='active').count(),
                'completed_quotas': user_quotas.filter(status='completed').count()
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
                    detail=f"Failed to get user quotas: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        """
        ✅ Activer quota avec gestion chevauchements (style BuyingProcessViewSet)
        """
        try:
            with transaction.atomic():
                quota = self.get_object()
                
                # Validation de l'ID
                if not pk:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field='Quota ID')
                    )
                
                try:
                    quota_id_int = int(pk)
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Quota ID must be a valid integer")
                    )
                
                if quota.status == SalesQuota.QuotaStatus.ACTIVE:
                    return Response({
                        'success': True,
                        'message': f'Quota "{quota.name}" is already active'
                    })
                
                # ✅ CORRIGÉ : Désactiver quotas chevauchants avec status
                overlapping_quotas = SalesQuota.objects.filter(
                    user=quota.user,
                    client_id=self.get_client_id(),
                    status='active'
                ).filter(
                    Q(period_start__lte=quota.period_end) &
                    Q(period_end__gte=quota.period_start)
                ).exclude(pk=quota.pk)
                
                overlapping_count = overlapping_quotas.count()
                
                # ✅ CORRIGÉ : Update vers status completed
                overlapping_quotas.update(status='completed')
                
                # Activer le quota
                quota.status = SalesQuota.QuotaStatus.ACTIVE
                quota.activation_date = timezone.now()
                quota.save(update_fields=['status', 'activation_date'])
                
                message = f'Quota "{quota.name}" activated successfully'
                if overlapping_count > 0:
                    message += f'. {overlapping_count} overlapping quotas were completed.'
                
                return Response({
                    'success': True,
                    'message': message,
                    'data': {
                        'quota_id': quota.id,
                        'quota_name': quota.name,
                        'status': quota.status,
                        'activation_date': quota.activation_date.isoformat(),
                        'overlapping_quotas_completed': overlapping_count
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to activate quota: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        """
        ✅ Désactiver quota (style BuyingProcessViewSet)
        """
        try:
            with transaction.atomic():
                quota = self.get_object()
                
                if quota.status != SalesQuota.QuotaStatus.ACTIVE:
                    return Response({
                        'success': True,
                        'message': f'Quota "{quota.name}" is already inactive'
                    })
                
                # Notes optionnelles pour la désactivation
                notes = request.data.get('notes', 'Deactivated via API')
                
                quota.status = SalesQuota.QuotaStatus.COMPLETED
                if notes and hasattr(quota, 'description'):
                    quota.description = f"{quota.description or ''}\n\n{notes}".strip()
                quota.save()
                
                return Response({
                    'success': True,
                    'message': f'Quota "{quota.name}" deactivated successfully',
                    'data': {
                        'quota_id': quota.id,
                        'quota_name': quota.name,
                        'status': quota.status,
                        'deactivated_at': timezone.now().isoformat()
                    }
                })
                
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to deactivate quota: {str(e)}"
                )
            )
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        ✅ Dupliquer quota avec nouvelles dates (style BuyingProcessViewSet)
        """
        try:
            with transaction.atomic():
                original_quota = self.get_object()
                
                # Validation des nouvelles dates
                new_period_start = request.data.get('period_start')
                new_period_end = request.data.get('period_end')
                
                if not new_period_start or not new_period_end:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(
                            field='period_start and period_end for duplicate quota'
                        )
                    )
                
                # Créer la copie
                duplicate_data = {
                    'user': original_quota.user.id,
                    'name': f"{original_quota.name} (Copy)",
                    'target_type': original_quota.target_type,
                    'target_value': original_quota.target_value,
                    'period_start': new_period_start,
                    'period_end': new_period_end,
                    'description': f"Duplicated from quota {original_quota.id}"
                }
                
                # Validation via serializer
                serializer = SalesQuotaCreateSerializer(data=duplicate_data, context=self.get_serializer_context())
                serializer.is_valid(raise_exception=True)
                
                # Créer la copie
                duplicate_quota = serializer.save(
                    client_id=self.get_client_id(),
                    created_by=request.user
                )
                
                return Response({
                    'success': True,
                    'message': f'Quota "{duplicate_quota.name}" duplicated successfully',
                    'data': {
                        'original_quota_id': original_quota.id,
                        'duplicate_quota_id': duplicate_quota.id,
                        'duplicate_quota_name': duplicate_quota.name,
                        'period_start': duplicate_quota.period_start.isoformat(),
                        'period_end': duplicate_quota.period_end.isoformat()
                    }
                }, status=status.HTTP_201_CREATED)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to duplicate quota: {str(e)}"
                )
            )
    
    # ===== ACTIONS MANAGERS =====
    
    @action(detail=False, methods=['get'])
    def team_performance(self, request):
        """
        ✅ Performance consolidée équipe pour managers (style BuyingProcessViewSet)
        """
        try:
            user = request.user
            
            if not user.team:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail="User is not assigned to a team"
                    )
                )
            
            # Récupérer tous les quotas actifs de l'équipe
            team_quotas = self.get_queryset().filter(
                user__team=user.team,
                status='active'
            )
            
            if not team_quotas.exists():
                return Response({
                    'success': True,
                    'data': {
                        'team_info': {
                            'id': str(user.team.id),
                            'name': user.team.name
                        },
                        'performance_data': {},
                        'message': 'No active quotas found for team'
                    }
                })
            
            # Récupérer les IDs utilisateurs de l'équipe
            team_user_ids = list(team_quotas.values_list('user_id', flat=True).distinct())
            
            # Calculer période globale (min start, max end)
            period_data = team_quotas.aggregate(
                min_start=Min('period_start'),
                max_end=Max('period_end')
            )
            
            # Appel au service pour performance équipe
            team_performance = UserPerformanceService.get_team_consolidated_performance_optimized(
                team_user_ids=team_user_ids,
                period_start=period_data['min_start'],
                period_end=period_data['max_end'],
                client_id=self.get_client_id()
            )
            
            return Response({
                'success': True,
                'data': {
                    'team_info': {
                        'id': str(user.team.id),
                        'name': user.team.name,
                        'members_count': len(team_user_ids)
                    },
                    'period': {
                        'start_date': period_data['min_start'].isoformat(),
                        'end_date': period_data['max_end'].isoformat()
                    },
                    'performance_data': team_performance,
                    'quotas_count': team_quotas.count()
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get team performance: {str(e)}"
                )
            )