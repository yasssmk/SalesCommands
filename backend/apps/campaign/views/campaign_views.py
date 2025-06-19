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

# Import configuration variables
from apps.campaign.config.variables import (
    QUERY_PARAMS,
    FILTER_CONFIGS,
    SEARCH_CONFIGS,
    ORDERING_CONFIGS,
    DEFAULT_ORDERINGS
)


class CampaignViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    API endpoints for managing campaigns
    Now returns standardized responses consistently with centralized permissions
    
    ✅ Ordre d'héritage simplifié - CampaignPermissionMixin inclut déjà ClientScopeManager.ViewMixin
    """
    queryset = Campaign.objects.all()
    entity_name = 'campaign'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = FILTER_CONFIGS['CAMPAIGN_FILTERS']
    search_fields = SEARCH_CONFIGS['CAMPAIGN_SEARCH']
    ordering_fields = ORDERING_CONFIGS['CAMPAIGN_ORDERING']
    ordering = DEFAULT_ORDERINGS['CAMPAIGNS']
    
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
        
        # ✅ Apply filters using helper methods
        queryset = self._apply_ownership_filters(queryset)
        queryset = self._apply_campaign_attribute_filters(queryset)
        queryset = self._apply_date_filters(queryset)
        
        return queryset

    def _apply_ownership_filters(self, queryset):
        """Apply ownership and stakeholder related filters"""
        # Filter by owner
        owner_id = self.request.query_params.get(QUERY_PARAMS['OWNER'])
        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)
        
        # Filter by stakeholder role
        stakeholder_role = self.request.query_params.get(QUERY_PARAMS['STAKEHOLDER_ROLE'])
        if stakeholder_role:
            queryset = queryset.filter(
                stakeholder_links__user=self.request.user,
                stakeholder_links__role=stakeholder_role
            ).distinct()
        
        # My campaigns (either owner or any stakeholder)
        my_campaigns = self.request.query_params.get(QUERY_PARAMS['MY_CAMPAIGNS'], None)
        if my_campaigns and my_campaigns.lower() == 'true':
            queryset = queryset.filter(
                Q(owner=self.request.user) | 
                Q(stakeholder_links__user=self.request.user)
            ).distinct()
        
        return queryset

    def _apply_campaign_attribute_filters(self, queryset):
        """Apply filters based on campaign attributes"""
        # Filter by campaign type
        campaign_type = self.request.query_params.get('campaign_type')
        if campaign_type:
            queryset = queryset.filter(campaign_type=campaign_type)
        
        # Filter by status
        campaign_status = self.request.query_params.get(QUERY_PARAMS['STATUS'])
        if campaign_status:
            queryset = queryset.filter(status=campaign_status)
        
        # Filter by sequence type
        sequence_type = self.request.query_params.get('sequence_type')
        if sequence_type:
            if sequence_type.lower() == 'none':
                queryset = queryset.filter(sequence_type__isnull=True)
            else:
                queryset = queryset.filter(sequence_type=sequence_type)
        
        return queryset

    def _apply_date_filters(self, queryset):
        """Apply date range filters"""
        start_after = self.request.query_params.get(QUERY_PARAMS['START_AFTER'])
        start_before = self.request.query_params.get(QUERY_PARAMS['START_BEFORE'])
        
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
        """Get a summary of campaign performance"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # ✅ Use CampaignManager for base summary
        summary_response = CampaignManager.get_campaign_summary(campaign)
        
        # ✅ Extract and enhance data using helper methods
        if hasattr(summary_response, 'data') and 'data' in summary_response.data:
            base_data = summary_response.data['data']
            enhanced_data = self._enhance_summary_data(campaign, base_data)
            
            return StandardizedSuccessResponse.success(
                message="Campaign summary retrieved successfully",
                data=enhanced_data,
                meta=self._build_summary_meta(enhanced_data)
            )
        else:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    def _enhance_summary_data(self, campaign, base_data):
        """
        Enhance base summary data with ViewSet-specific details
        Méthode helper locale au ViewSet
        """
        enhanced_data = base_data.copy()
        
        # Add objectives details
        enhanced_data['objectives'] = self._get_objectives_summary(campaign)
        
        # Add detailed targets information
        enhanced_data['detailed_targets'] = self._get_targets_summary(campaign)
        
        # Add target breakdown
        enhanced_data['target_breakdown'] = campaign.get_target_summary()
        
        return enhanced_data

    def _get_objectives_summary(self, campaign):
        """Get detailed objectives information"""
        objectives = campaign.objectives.all()
        return [
            {
                'id': obj.id,
                'name': obj.name,
                'objective_type': obj.objective_type,
                'objective_type_display': obj.get_objective_type_display(),
                'target_value': obj.target_value,
                'current_value': obj.current_value,
                'progress_percentage': obj.progress_percentage()
            } for obj in objectives
        ]

    def _get_targets_summary(self, campaign):
        """Get detailed targets information with status counts"""
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
        
        return target_counts

    def _build_summary_meta(self, enhanced_data):
        """Build meta information for summary response"""
        return {
            'operation': 'campaign_summary_detailed',
            'objectives_count': len(enhanced_data.get('objectives', [])),
            'targets_count': enhanced_data.get('detailed_targets', {}).get('total', 0)
        }