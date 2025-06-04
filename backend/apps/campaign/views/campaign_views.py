# apps/campaign/views/campaign_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign import Campaign
from django.db.models import Q
from apps.campaign.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignListSerializer
)


class CampaignViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaigns
    """
    queryset = Campaign.objects.all()
    entity_name = 'campaign'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign_type', 'owner', 'status', 'sequence_type']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == 'list':
            return CampaignListSerializer
        return CampaignSerializer
    
    def get_queryset(self):
        """Get campaigns for the current client with filters"""
        queryset = Campaign.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related('owner')
        
        # Filter by owner
        owner_id = self.request.query_params.get('owner')
        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)
        
        # Filter by stakeholder role
        stakeholder_role = self.request.query_params.get('stakeholder_role')
        if stakeholder_role:
            # Find campaigns where the current user has this role
            queryset = queryset.filter(
                stakeholder_links__user=self.request.user,
                stakeholder_links__role=stakeholder_role
            ).distinct()
        
        # My campaigns (either owner or any stakeholder)
        my_campaigns = self.request.query_params.get('my_campaigns', None)
        if my_campaigns and my_campaigns.lower() == 'true':
            queryset = queryset.filter(
                Q(owner=self.request.user) | 
                Q(stakeholder_links__user=self.request.user)
            ).distinct()
        
        # Filter by campaign type
        campaign_type = self.request.query_params.get('campaign_type')
        if campaign_type:
            queryset = queryset.filter(campaign_type=campaign_type)
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by sequence type
        sequence_type = self.request.query_params.get('sequence_type')
        if sequence_type:
            if sequence_type.lower() == 'none':
                queryset = queryset.filter(sequence_type__isnull=True)
            else:
                queryset = queryset.filter(sequence_type=sequence_type)
        
        # Filter by date range
        start_after = self.request.query_params.get('start_after')
        start_before = self.request.query_params.get('start_before')
        
        if start_after:
            queryset = queryset.filter(start_date__gte=start_after)
        
        if start_before:
            queryset = queryset.filter(start_date__lte=start_before)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new campaign for the current client"""
        client_id = self.get_client_id()
        campaign = serializer.save(
            client_id=client_id,
            owner=self.request.user
        )
        return campaign
    
    def perform_update(self, serializer):
        """Update a campaign with validation"""
        instance = serializer.instance
        self.validate_client_id(instance)
        
        # Validate owner permissions
        if instance.owner != self.request.user:
            raise StandardizedValidationError("You can only modify your own campaigns")
            
        return serializer.save()
    
    def perform_destroy(self, instance):
        """Delete a campaign with validation"""
        self.validate_client_id(instance)
        
        # Validate owner permissions
        if instance.owner != self.request.user:
            raise StandardizedValidationError("You can only delete your own campaigns")
            
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get a summary of campaign performance"""
        campaign = self.get_object()
        
        # Get objectives
        objectives = campaign.objectives.all()
        
        # Get targets and their status counts
        targets = campaign.targets.all()
        target_counts = {
            'total': targets.count(),
            'by_status': {}
        }
        
        # Count targets by status
        from apps.campaign.models.campaign_target import CampaignTarget
        for status_choice in CampaignTarget.Status.choices:
            status_code = status_choice[0]
            status_display = status_choice[1]
            count = targets.filter(status=status_code).count()
            target_counts['by_status'][status_code] = {
                'display': status_display,
                'count': count
            }
        
        # Get target type breakdown
        target_summary = campaign.get_target_summary()
        
        # Prepare summary data
        data = {
            'id': campaign.id,
            'name': campaign.name,
            'start_date': campaign.start_date,
            'end_date': campaign.end_date,
            'has_sequence': campaign.has_sequence(),
            'is_call_list': campaign.is_call_list(),
            'target_summary': target_summary,
            'objectives': [
                {
                    'id': obj.id,
                    'name': obj.name,
                    'objective_type': obj.objective_type,
                    'objective_type_display': obj.get_objective_type_display(),
                    'target_value': obj.target_value,
                    'current_value': obj.current_value,
                    'progress_percentage': obj.progress_percentage()
                } for obj in objectives
            ],
            'targets': target_counts
        }
        
        return Response(data)