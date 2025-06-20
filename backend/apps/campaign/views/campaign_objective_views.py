from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.serializers.campaign_objective_serializer import CampaignObjectiveSerializer
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin

class CampaignObjectiveViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign objectives (CRUD uniquement)
    Pour analytics et dashboard : utiliser campaign_management_views.py
    """
    serializer_class = CampaignObjectiveSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign', 'objective_type', 'is_primary']
    ordering_fields = ['name', 'target_value', 'created_at']
    ordering = ['campaign', '-is_primary', 'created_at']
    
    def get_queryset(self):
        """Get objectives for the current client with filters"""
        try:
            queryset = CampaignObjective.objects.select_related('campaign').all()
            
            # Apply client scoping through related campaign
            queryset = queryset.filter(campaign__client_id=self.get_client_id())
            
            return queryset
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve campaign objectives")
            )
    
    def perform_create(self, serializer):
        """Create a new objective with validation"""
        try:
            campaign = self.get_validated_campaign_from_data('campaign', allow_stakeholders=False)
            client_id = self.get_client_id()
            return serializer.save(client_id=client_id)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason="Objective creation failed")
            )
    
    def perform_update(self, serializer):
        """Update an objective with validation"""
        try:
            instance = serializer.instance
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            return serializer.save()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete an objective with validation"""
        try:
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            instance.delete()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective deletion failed")
            )
    
    @action(detail=True, methods=['post'])
    def set_as_primary(self, request, pk=None):
        """
        Set this objective as primary for its campaign
        UNIQUE : Gestion spécifique aux objectifs
        """
        try:
            objective = self.get_object()
            self.validate_campaign_related_object(objective, allow_stakeholders=False)
            
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
        Synchronize objective progress with actual campaign results
        UNIQUE : Gestion spécifique aux objectifs
        """
        try:
            objective = self.get_object()
            self.validate_campaign_related_object(objective, allow_stakeholders=False)
            
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