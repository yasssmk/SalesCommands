# apps/campaign/views/campaign_objective_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign_objective import CampaignObjective
from apps.campaign.serializers.campaign_objective_serializer import CampaignObjectiveSerializer

class CampaignObjectiveViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaign objectives
    """
    serializer_class = CampaignObjectiveSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign', 'objective_type', 'is_primary']
    ordering_fields = ['name', 'target_value', 'current_value', 'created_at']
    ordering = ['campaign', '-is_primary', 'created_at']
    
    def get_queryset(self):
        """Get objectives for the current client with filters"""
        queryset = CampaignObjective.objects.all()
        
        # Apply client scoping through related campaign
        queryset = queryset.filter(campaign__client_id=self.get_client_id())
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new objective with validation"""
        # Get campaign and validate ownership
        campaign = serializer.validated_data['campaign']
        if campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only add objectives to your own campaigns")
            
        client_id = self.get_client_id()

        return serializer.save(client_id=client_id)
    
    def perform_update(self, serializer):
        """Update an objective with validation"""
        instance = serializer.instance
        
        # Validate client scope via campaign
        if str(instance.campaign.client_id) != str(self.get_client_id()):
            raise StandardizedValidationError("Client mismatch")
            
        # Validate owner permissions
        if instance.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only modify objectives for your own campaigns")
            
        return serializer.save()
    
    def perform_destroy(self, instance):
        """Delete an objective with validation"""
        # Validate client scope via campaign
        if str(instance.campaign.client_id) != str(self.get_client_id()):
            raise StandardizedValidationError("Client mismatch")
            
        # Validate owner permissions
        if instance.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only delete objectives for your own campaigns")
            
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update the progress of an objective"""
        objective = self.get_object()
        
        # Validate owner permissions
        if objective.campaign.owner != self.request.user:
            raise StandardizedValidationError("You can only update progress for your own campaigns")
            
        # Get new value from request
        new_value = request.data.get('value', None)
        if new_value is None:
            raise StandardizedValidationError("Value is required")
            
        try:
            new_value = float(new_value)
        except (ValueError, TypeError):
            raise StandardizedValidationError("Value must be a number")
            
        # Get increment flag
        increment = request.data.get('increment', False)
        
        # Update progress
        progress = objective.update_progress(new_value, increment=increment)
        
        return Response({
            'id': objective.id,
            'current_value': objective.current_value,
            'target_value': objective.target_value,
            'progress_percentage': progress
        })