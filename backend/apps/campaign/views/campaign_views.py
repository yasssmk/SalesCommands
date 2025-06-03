# apps/campaign/views/campaign_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign import Campaign
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
        
        # Prefetch related data
        queryset = queryset.select_related('owner').prefetch_related('targets')
        
        # Filter by owner (current user) if requested
        owner_filter = self.request.query_params.get('my_campaigns', None)
        if owner_filter and owner_filter.lower() == 'true':
            queryset = queryset.filter(owner=self.request.user)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
            
        # Filter by active status (campaigns with current date between start and end)
        active_filter = self.request.query_params.get('active', None)
        if active_filter and active_filter.lower() == 'true':
            from django.utils import timezone
            today = timezone.now().date()
            queryset = queryset.filter(start_date__lte=today, end_date__gte=today)
        
        # Filter by has_sequence
        has_sequence = self.request.query_params.get('has_sequence', None)
        if has_sequence:
            if has_sequence.lower() == 'true':
                queryset = queryset.exclude(sequence_type__isnull=True)
            else:
                queryset = queryset.filter(sequence_type__isnull=True)
        
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