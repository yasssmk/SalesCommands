# apps/campaign/views/campaign_objective_views.py

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

class CampaignObjectiveViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign objectives
    Now returns standardized responses consistently
    """
    serializer_class = CampaignObjectiveSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign', 'objective_type', 'is_primary']
    ordering_fields = ['name', 'target_value', 'current_value', 'created_at']
    ordering = ['campaign', '-is_primary', 'created_at']
    
    def get_queryset(self):
        """Get objectives for the current client with filters"""
        try:
            queryset = CampaignObjective.objects.all()
            
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
            # Get campaign and validate ownership
            campaign = serializer.validated_data['campaign']
            if campaign.owner != self.request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
                
            client_id = self.get_client_id()

            return serializer.save(client_id=client_id)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason="Objective creation failed")
            )
    
    def perform_update(self, serializer):
        """Update an objective with validation"""
        try:
            instance = serializer.instance
            
            # Validate client scope via campaign
            if str(instance.campaign.client_id) != str(self.get_client_id()):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
            # Validate owner permissions
            if instance.campaign.owner != self.request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
                
            return serializer.save()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete an objective with validation"""
        try:
            # Validate client scope via campaign
            if str(instance.campaign.client_id) != str(self.get_client_id()):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
                
            # Validate owner permissions
            if instance.campaign.owner != self.request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
                
            instance.delete()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective deletion failed")
            )
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """
        Update the progress of an objective
        Now returns standardized response
        """
        try:
            objective = self.get_object()
            
            # Validate owner permissions
            if objective.campaign.owner != self.request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
                
            # Get new value from request
            new_value = request.data.get('value', None)
            if new_value is None:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="value")
                )
                
            try:
                new_value = float(new_value)
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="value (must be a number)")
                )
                
            # Validate value is not negative
            if new_value < 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="value (cannot be negative)")
                )
            
            # Get increment flag
            increment = request.data.get('increment', False)
            
            # Update progress
            progress = objective.update_progress(new_value, increment=increment)
            
            # Prepare response data
            data = {
                'objective_id': objective.id,
                'objective_name': objective.name,
                'current_value': float(objective.current_value),
                'target_value': float(objective.target_value),
                'progress_percentage': progress,
                'increment_applied': increment,
                'value_added': new_value if increment else None,
                'new_value_set': new_value if not increment else None
            }
            
            meta = {
                'operation': 'objective_progress_update',
                'increment_mode': increment,
                'progress_percentage': progress
            }
            
            # Return standardized success response
            return StandardizedSuccessResponse.success(
                message=f"Objective progress updated successfully to {progress:.1f}%",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Progress update failed")
            )