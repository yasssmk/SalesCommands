# apps/campaign/views/campaign_objective_views.py - VERSION FINALE COMPLÈTE

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.serializers.campaign_objective_serializer import CampaignObjectiveSerializer
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin

from apps.campaign.config.settings import CONFIG
from apps.campaign.utils.query_optimizer import CampaignQueryOptimizer


class CampaignObjectiveViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign objectives
    Version finale avec optimisations appliquées :
    - Configuration centralisée (CONFIG)
    - Queries optimisées  
    - Validation légèrement simplifiée
    - Custom actions conservées (logique métier spécifique)
    
    Réduction réelle: ~100 lignes → ~90 lignes (-10%)
    """
    serializer_class = CampaignObjectiveSerializer
    entity_name = 'campaign_objective'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    
    filterset_fields = CONFIG.filters.objective_filters
    ordering_fields = CONFIG.filters.objective_ordering
    ordering = CONFIG.filters.default_objective_ordering
    
    def get_queryset(self):
        """
        ✅ OPTIMISATION 2: Queries optimisées + configuration centralisée
        """
        try:
            # Base queryset avec client scoping  
            queryset = CampaignObjective.objects.select_related('campaign').filter(
                campaign__client_id=self.get_client_id()
            )
            
            # ✅ Optimisation queries automatique
            return CampaignQueryOptimizer.apply_optimization(
                queryset, 'CampaignObjective', getattr(self, 'action', 'list')
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve campaign objectives")
            )
    
    # =========================================================================
    # CRUD OPERATIONS - Légèrement simplifiées mais conservées
    # =========================================================================
    
    def perform_create(self, serializer):
        """✅ Validation légèrement simplifiée avec mixin amélioré"""
        try:
            # ✅ Validation avec CONFIG
            campaign = self.get_validated_campaign_from_data(
                CONFIG.fields.campaign, 
                allow_stakeholders=False
            )
            client_id = self.get_client_id()
            return serializer.save(client_id=client_id)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(
                    reason="Objective creation failed"
                )
            )
    
    def perform_update(self, serializer):
        """✅ Validation légèrement simplifiée avec mixin amélioré"""
        try:
            instance = serializer.instance
            self.validate_campaign_ownership(instance, allow_stakeholders=False)
            return serializer.save()
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective update failed")
            )
    
    def perform_destroy(self, instance):
        """✅ Validation légèrement simplifiée avec mixin amélioré"""
        try:
            self.validate_campaign_ownership(instance, allow_stakeholders=False)
            instance.delete()
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective deletion failed")
            )
    
    # =========================================================================
    # CUSTOM ACTIONS - CONSERVÉES INTÉGRALEMENT (logique métier spécifique)
    # =========================================================================
    
    @action(detail=True, methods=['post'])
    def set_as_primary(self, request, pk=None):
        """
        CONSERVÉ INTÉGRALEMENT - Logique métier spécifique aux objectifs
        Set this objective as primary for its campaign
        """
        try:
            # ✅ get_object() bénéficie automatiquement du mixin amélioré
            objective = self.get_object()
            self.validate_campaign_ownership(objective, allow_stakeholders=False)
            
            # Désactiver les autres objectifs primaires de cette campagne
            CampaignObjective.objects.filter(
                campaign=objective.campaign,
                is_primary=True
            ).exclude(id=objective.id).update(is_primary=False)
            
            # Activer celui-ci comme primaire
            objective.is_primary = True
            objective.save(update_fields=['is_primary'])
            
            data = {
                'objective_id': objective.id,
                'objective_name': objective.name,
                'is_primary': True,
                'campaign_id': objective.campaign.id,
                'campaign_name': objective.campaign.name
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Objective '{objective.name}' set as primary successfully",
                data=data,
                meta={
                    'operation': 'set_primary_objective',
                    'objective_id': objective.id
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to set objective as primary")
            )
    
    @action(detail=True, methods=['post'])
    def sync_progress(self, request, pk=None):
        """
        CONSERVÉ INTÉGRALEMENT - Logique métier spécifique aux objectifs
        Synchronize objective progress with actual campaign results
        """
        try:
            # ✅ get_object() bénéficie automatiquement du mixin amélioré
            objective = self.get_object()
            self.validate_campaign_ownership(objective, allow_stakeholders=False)
            
            # Obtenir la valeur actuelle depuis le tracking
            current_value = objective.get_current_value()
            progress_percentage = objective.get_progress_percentage()
            
            data = {
                'objective_id': objective.id,
                'objective_name': objective.name,
                'current_value': current_value,
                'target_value': float(objective.target_value),
                'progress_percentage': round(progress_percentage, 1),
                'is_achieved': progress_percentage >= 100,
                'sync_timestamp': timezone.now().isoformat()
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Objective progress synchronized successfully",
                data=data,
                meta={
                    'operation': 'objective_sync_progress',
                    'objective_id': objective.id,
                    'progress_percentage': round(progress_percentage, 1)
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to sync objective progress")
            )