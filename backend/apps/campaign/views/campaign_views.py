# apps/campaign/views/campaign_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models.campaign import Campaign
from django.db.models import Q
from apps.campaign.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignListSerializer
)
from apps.campaign.services.campaign_manager import CampaignManager
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin


class CampaignViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaigns
    Now returns standardized responses consistently with centralized permissions
    
    ✅ Ordre d'héritage simplifié - CampaignPermissionMixin inclut déjà ClientScopeManager.ViewMixin
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
        campaign_status = self.request.query_params.get('status')
        if campaign_status:
            queryset = queryset.filter(status=campaign_status)
        
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
        try:
            client_id = self.get_client_id()
            campaign = serializer.save(
                client_id=client_id,
                owner=self.request.user
            )
            return campaign
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    def perform_update(self, serializer):
        """Update a campaign with validation"""
        try:
            instance = serializer.instance
            
            # ✅ APRÈS: Validation centralisée (1 ligne)
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
                
            return serializer.save()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state="update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete a campaign with validation"""
        try:
            # ✅ APRÈS: Validation centralisée (1 ligne)
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
                
            instance.delete()
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign deletion failed")
            )
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get a summary of campaign performance
        Now uses CampaignManager for standardized response
        """
        try:
            # ✅ APRÈS: Validation centralisée avec stakeholders autorisés (1 ligne)
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Use CampaignManager.get_campaign_summary for standardized response
            summary_response = CampaignManager.get_campaign_summary(campaign)
            
            # Extract data from the standardized Response and enhance with additional info
            if hasattr(summary_response, 'data') and 'data' in summary_response.data:
                summary_data = summary_response.data['data']
                
                # Get objectives using direct query (for additional detail)
                objectives = campaign.objectives.all()
                
                # Get targets and their status counts using direct query (for additional detail)
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
                
                # Enhance the summary data with ViewSet-specific details
                enhanced_data = summary_data.copy()
                enhanced_data.update({
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
                    'detailed_targets': target_counts,
                    'target_breakdown': target_summary
                })
                
                # Return enhanced standardized response
                return StandardizedSuccessResponse.success(
                    message="Campaign summary retrieved successfully",
                    data=enhanced_data,
                    meta={
                        'operation': 'campaign_summary_detailed',
                        'objectives_count': len(objectives),
                        'targets_count': target_counts['total']
                    }
                )
            else:
                # Fallback if summary response format is unexpected
                raise StandardizedValidationError(
                    CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )