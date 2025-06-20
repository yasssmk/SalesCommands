# apps/campaign/views/campaign_views.py
# REMPLACER complètement le contenu par cette version unifiée

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, date
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from core.apps_shared_methods import BaseAPIView

from apps.campaign.models.campaign import Campaign
from apps.campaign.serializers.campaign_serializer import (
    CampaignSerializer,
    CampaignListSerializer,
    CampaignDetailSerializer
)
from apps.campaign.services.campaign_core_service import CampaignCoreService
from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
from apps.campaign.services.campaign_target_service import CampaignTargetService
from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.activities.models.activity import Activity


# Import configuration variables
from apps.campaign.config.variables import (
    QUERY_PARAMS,
    FILTER_CONFIGS,
    SEARCH_CONFIGS,
    ORDERING_CONFIGS,
    DEFAULT_ORDERINGS,
    DEFAULT_PLAYLIST_LIMIT,
    FIELD_NAMES,
    DATE_FORMATS,
    VALIDATION_LIMITS
)


class CampaignViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    Unified Campaign ViewSet - Combines CRUD operations and campaign management
    Replaces both CampaignViewSet and CampaignManagementViewSet
    """
    queryset = Campaign.objects.all()
    entity_name = 'campaign'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = FILTER_CONFIGS['CAMPAIGN_FILTERS']
    search_fields = SEARCH_CONFIGS['CAMPAIGN_SEARCH']
    ordering_fields = ORDERING_CONFIGS['CAMPAIGN_ORDERING']
    ordering = DEFAULT_ORDERINGS['CAMPAIGNS']
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'list':
            return CampaignListSerializer
        elif self.action in ['retrieve', 'dashboard', 'summary']:
            return CampaignDetailSerializer
        return CampaignSerializer
    
    def get_queryset(self):
        """Get campaigns for the current client with filters"""
        queryset = Campaign.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related('owner')
        
        # Apply filters using helper methods
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
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            return serializer.save()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state="update failed")
            )
    
    def perform_destroy(self, instance):
        """Delete a campaign with validation"""
        try:
            self.validate_campaign_related_object(instance, allow_stakeholders=False)
            instance.delete()
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign deletion failed")
            )
    
    # ===== CAMPAIGN CREATION WITH TARGETS =====
    
    @action(detail=False, methods=['post'])
    def create_with_targets(self, request):
        """
        Create a campaign with targets and generate activities
        Unified endpoint from CampaignManagementViewSet
        """
        try:
            # Extract input data
            campaign_data = request.data.get('campaign', {})
            target_account_ids = request.data.get('target_account_ids', [])
            target_contact_ids = request.data.get('target_contact_ids', [])
            target_lead_ids = request.data.get('target_lead_ids', [])
            target_opportunity_ids = request.data.get('target_opportunity_ids', [])
            
            # Validate required fields
            if not campaign_data.get('name'):
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Campaign name")
                )
            
            if not any([target_account_ids, target_contact_ids, target_lead_ids, target_opportunity_ids]):
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_TARGETS_REQUIRED)
            
            # Validate campaign dates
            start_date = campaign_data.get('start_date')
            end_date = campaign_data.get('end_date')
            if start_date and end_date:
                try:
                    start_dt = datetime.strptime(start_date, DATE_FORMATS['INPUT_DATE']).date()
                    end_dt = datetime.strptime(end_date, DATE_FORMATS['INPUT_DATE']).date()
                    
                    if end_dt < start_dt:
                        raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_DATE_INVALID)
                    if end_dt < date.today():
                        raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_DATE_PAST)
                        
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Date format (YYYY-MM-DD expected)")
                    )
            
            # Prepare campaign targets
            target_result = CampaignTargetService.prepare_campaign_targets(
                target_account_ids=target_account_ids,
                target_contact_ids=target_contact_ids,
                target_lead_ids=target_lead_ids,
                target_opportunity_ids=target_opportunity_ids
            )
            
            # Validate that we have valid targets
            stats = target_result['stats']
            if (stats['total_accounts'] == 0 and stats['total_contacts'] == 0 and 
                stats['total_leads'] == 0 and stats['total_opportunities'] == 0):
                raise StandardizedValidationError(
                    "No valid targets found. Check the provided IDs and ensure they exist."
                )
            
            # Set client and ownership
            client_id = self.get_client_id()
            campaign_data['client_id'] = client_id
            campaign_data['owner_id'] = request.user.id
            
            # Create campaign and activities
            return CampaignCoreService.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_result['target_accounts'],
                target_contacts=target_result['target_contacts'],
                target_leads=target_result['target_leads'],
                target_opportunities=target_result['target_opportunities'],
                targeting_stats=target_result['stats']
            )
            
        except (StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied):
            raise
        except ValueError as e:
            if "client_id is required" in str(e):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
            raise StandardizedValidationError(f"Campaign creation failed: {str(e)}")
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign creation failed")
            )
    
    # ===== CAMPAIGN LIFECYCLE MANAGEMENT =====
    
    @action(detail=True, methods=['post'])
    def start_campaign(self, request, pk=None):
        """Start/activate a campaign and get initial playlist"""        
        campaign = self.get_validated_campaign(require_ownership=True)
        return CampaignCoreService.start_campaign(campaign)
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """Pause a campaign"""
        campaign = self.get_validated_campaign(require_ownership=True)
        
        pause_until = request.data.get('pause_until', None)
        if pause_until:
            pause_until = datetime.strptime(pause_until, '%Y-%m-%d').date()
        
        return CampaignCoreService.pause_campaign(campaign, pause_until=pause_until)
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """Resume a paused campaign"""
        campaign = self.get_validated_campaign(require_ownership=True)
        return CampaignCoreService.resume_campaign(campaign)
    
    # ===== CAMPAIGN EXECUTION =====
    
    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """Get the current playlist of activities for a campaign"""
        campaign = self.get_validated_campaign(require_ownership=True, check_state=False)
        
        limit = int(request.query_params.get(QUERY_PARAMS['LIMIT'], DEFAULT_PLAYLIST_LIMIT))
        return CampaignCoreService.get_campaign_playlist(campaign, limit=limit)
    
    @action(detail=True, methods=['get'])
    def contacts_with_responses(self, request, pk=None):
        """Get all contacts in campaign with email/LinkedIn activities that might have responses"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        return CampaignCoreService.get_campaign_contacts_with_responses(campaign)
    
    # ===== CAMPAIGN MANAGEMENT =====
    
    @action(detail=True, methods=['post'])
    def remove_account(self, request, pk=None):
        """Remove an account from the campaign"""
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True,
                check_state=True
            )
            
            account_id = request.data.get('account_id')
            notes = request.data.get('notes')
            
            if not account_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
                )
            
            account = self._get_validated_account(account_id)
            
            # Validate account is actually targeted by this campaign
            campaign_target = campaign.targets.filter(account=account).first()
            if not campaign_target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            return CampaignCoreService.remove_account_from_campaign(
                campaign=campaign,
                account=account,
                notes=notes
            )
            
        except (StandardizedValidationError, StandardizedPermissionDenied):
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to remove account from campaign")
            )
    
    @action(detail=True, methods=['post'])
    def remove_contact(self, request, pk=None):
        """Remove a contact from the campaign"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True,
            check_state=True
        )
        
        contact_id = request.data.get('contact_id')
        notes = request.data.get('notes')
        
        if not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="Contact ID")
            )
        
        contact = self._get_validated_contact(contact_id)
        
        return CampaignCoreService.remove_contact_from_campaign(
            campaign=campaign,
            contact=contact,
            notes=notes
        )
    
    @action(detail=True, methods=['post'], url_path='add-manual-activity')
    def add_manual_activity(self, request, pk=None):
        """Add a manual activity for a contact in a non-sequence campaign"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Verify this is a non-sequence campaign
        if campaign.sequence_type:
            raise StandardizedValidationError(
                "This operation is only for campaigns without sequences"
            )
        
        # Validate required fields
        contact_id = request.data.get(FIELD_NAMES['CONTACT_ID'])
        activity_type = request.data.get('activity_type')
        result = request.data.get(FIELD_NAMES['RESULT'])
        
        if not all([contact_id, activity_type, result]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id, activity_type, and result")
            )
        
        try:
            # Get the contact
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            self.validate_client_id(contact)
            
            # Get the campaign target for this contact
            target = None
            for t in campaign.targets.all():
                if t.contact_id == contact_id:
                    target = t
                    break
                    
                # Check if contact belongs to this target's account
                if (t.account_id == contact.account_id or 
                    (t.lead and t.lead.account_id == contact.account_id) or
                    (t.target_opportunity and t.target_opportunity.account_id == contact.account_id)):
                    target = t
                    break
            
            if not target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            # Prepare additional data
            kwargs = {}
            if request.data.get('meeting_date'):
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            if request.data.get('callback_date'):
                kwargs['callback_date'] = datetime.strptime(
                    request.data.get('callback_date'), '%Y-%m-%d'
                ).date()
            
            return CampaignCoreService.add_manual_activity_to_campaign(
                campaign=campaign,
                contact=contact,
                activity_type=activity_type,
                result=result,
                notes=request.data.get('notes', ''),
                user=request.user,
                **kwargs
            )
            
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
    # ===== ANALYTICS & REPORTING =====
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get comprehensive campaign summary - Enhanced version"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Use CampaignCoreService for base summary
        summary_response = CampaignCoreService.get_campaign_summary(campaign)
        
        # Extract and enhance data using helper methods
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
        """Enhance base summary data with ViewSet-specific details"""
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
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """Get all activities for a campaign with optional status filtering"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        return CampaignCoreService.get_campaign_activities(
            campaign=campaign,
            status_filter=status_filter
        )

    @action(detail=True, methods=['get'])
    def account_activities(self, request, pk=None):
        """Get all activities for a specific account in a campaign"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Get account ID
        account_id = request.query_params.get('account_id')
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        account = self._get_validated_account(account_id)
            
        return CampaignCoreService.get_account_activities_in_campaign(
            campaign=campaign,
            account=account,
            status_filter=status_filter
        )

    @action(detail=True, methods=['get'])
    def contact_activities(self, request, pk=None):
        """Get all activities for a specific contact in a campaign"""
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # Get contact ID
        contact_id = request.query_params.get('contact_id')
        if not contact_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id")
            )
    
        contact = self._get_validated_contact(contact_id)
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
                    
        return CampaignCoreService.get_contact_activities_in_campaign(
            campaign=campaign,
            contact=contact,
            status_filter=status_filter
        )
    
    # ===== DASHBOARD ENDPOINTS =====
    
    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        Get unified campaign dashboard with configurable sections and format
        
        Query Parameters:
        - include: Comma-separated list of sections (objectives,tracking,activities,targets)
        - format: detailed|summary (default: detailed)
        
        Examples:
        /campaigns/123/dashboard/                                    # Full detailed dashboard
        /campaigns/123/dashboard/?format=summary                     # Quick summary
        /campaigns/123/dashboard/?include=objectives,tracking        # Only specific sections
        /campaigns/123/dashboard/?include=metrics&format=summary     # Simple metrics only
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Parse query parameters
            include_param = request.query_params.get('include', '')
            format_param = request.query_params.get('format', 'detailed')
            
            # Parse included sections
            if include_param:
                included_sections = [s.strip() for s in include_param.split(',')]
            else:
                # Default: include all sections for detailed, only basic for summary
                if format_param == 'summary':
                    included_sections = ['basic', 'metrics']
                else:
                    included_sections = ['basic', 'objectives', 'tracking', 'activities', 'targets']
            
            # Validate format parameter
            if format_param not in ['detailed', 'summary']:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="format (must be 'detailed' or 'summary')")
                )
            
            # Build dashboard data based on included sections
            dashboard_data = {}
            
            # Basic campaign information (always included)
            dashboard_data['campaign_info'] = {
                'id': campaign.id,
                'name': campaign.name,
                'type': campaign.campaign_type,
                'type_display': campaign.get_campaign_type_display(),
                'status': campaign.status,
                'start_date': campaign.start_date.isoformat(),
                'end_date': campaign.end_date.isoformat(),
                'has_sequence': campaign.sequence_type is not None,
                'sequence_type': campaign.sequence_type
            }
            
            # Metrics section (simple or detailed)
            if 'metrics' in included_sections or 'basic' in included_sections:
                if format_param == 'summary':
                    # Simple metrics using campaign helper methods
                    dashboard_data['metrics'] = campaign.get_dashboard_summary()
                else:
                    # Detailed metrics using tracking service
                    dashboard_data['metrics'] = CampaignTrackingService.get_campaign_metrics(campaign)
            
            # Objectives section
            if 'objectives' in included_sections:
                objectives = campaign.objectives.all()
                if format_param == 'summary':
                    dashboard_data['objectives'] = {
                        'total_count': objectives.count(),
                        'primary_objective': None
                    }
                    primary_obj = objectives.filter(is_primary=True).first()
                    if primary_obj:
                        dashboard_data['objectives']['primary_objective'] = {
                            'id': primary_obj.id,
                            'name': primary_obj.name,
                            'progress_percentage': primary_obj.progress_percentage()
                        }
                else:
                    dashboard_data['objectives'] = self._get_objectives_summary(campaign)
            
            # Tracking section (detailed analytics)
            if 'tracking' in included_sections:
                if format_param == 'detailed':
                    # Use analytics service for comprehensive tracking data
                    analytics_response = CampaignAnalyticsService.get_campaign_dashboard_data(campaign)
                    if hasattr(analytics_response, 'data') and 'data' in analytics_response.data:
                        dashboard_data['tracking'] = analytics_response.data['data']
                    else:
                        dashboard_data['tracking'] = {'error': 'Analytics data unavailable'}
                else:
                    # Simple tracking summary
                    dashboard_data['tracking'] = {
                        'activities_completed': campaign.get_completed_activities_count(),
                        'activities_pending': campaign.get_pending_activities_count()
                    }
            
            # Activities section
            if 'activities' in included_sections:
                if format_param == 'summary':
                    dashboard_data['activities'] = {
                        'total_count': campaign.get_total_activities_count(),
                        'completed_count': campaign.get_completed_activities_count(),
                        'pending_count': campaign.get_pending_activities_count()
                    }
                else:
                    # Get recent activities
                    from apps.activities.models.activity import Activity
                    recent_activities = Activity.objects.filter(
                        campaign_target__campaign=campaign
                    ).order_by('-created_at')[:10]
                    
                    dashboard_data['activities'] = {
                        'total_count': campaign.get_total_activities_count(),
                        'completed_count': campaign.get_completed_activities_count(),
                        'pending_count': campaign.get_pending_activities_count(),
                        'recent_activities': [
                            {
                                'id': activity.id,
                                'type': activity.activity_type,
                                'status': activity.status,
                                'created_at': activity.created_at.isoformat()
                            } for activity in recent_activities
                        ]
                    }
            
            # Targets section
            if 'targets' in included_sections:
                if format_param == 'summary':
                    dashboard_data['targets'] = campaign.get_target_summary()
                else:
                    dashboard_data['targets'] = self._get_targets_summary(campaign)
            
            # Build response metadata
            meta = {
                'operation': 'unified_campaign_dashboard',
                'campaign_id': campaign.id,
                'format': format_param,
                'included_sections': included_sections,
                'data_timestamp': timezone.now().isoformat()
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Dashboard data retrieved for campaign '{campaign.name}' ({format_param} format)",
                data=dashboard_data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to generate campaign dashboard")
            )
    
    # ===== UTILITY ENDPOINTS =====
    
    @action(detail=False, methods=['get'])
    def account_campaigns(self, request):
        """Get all campaigns that the specified account is a target of"""
        account_id = request.query_params.get(QUERY_PARAMS['ACCOUNT_ID'])
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )

        account = self._get_validated_account(account_id)
            
        # Get campaign targets for this account
        from apps.campaign.models.campaign_target import CampaignTarget
        targets = CampaignTarget.objects.filter(
                account=account
            ).select_related('campaign', 'campaign__owner')
            
        # Format response
        campaigns_data = []
        for target in targets:
            campaign = target.campaign
            campaigns_data.append({
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'campaign_type': campaign.campaign_type,
                'campaign_type_display': campaign.get_campaign_type_display(),
                'start_date': campaign.start_date,
                'end_date': campaign.end_date,
                'owner_name': f"{campaign.owner.first_name} {campaign.owner.last_name}",
                'status': target.status,
                'status_display': target.get_status_display()
            })
        
        # Return standardized response
        data = {
            'account_id': account.id,
            'account_name': account.company_name,
            'campaigns': campaigns_data
        }
        
        meta = {
            'operation': 'account_campaigns_retrieval',
            'campaigns_count': len(campaigns_data)
        }
        
        return StandardizedSuccessResponse.success(
            message=f"Retrieved {len(campaigns_data)} campaigns for account {account.company_name}",
            data=data,
            meta=meta
        )
    
class ActivityResultViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ViewSet):
    """
    ViewSet for handling activity results and completion
    Optimized version with reduced duplication and cleaner error handling
    """
    
    def _get_validated_activity(self, pk):
        """
        Helper method to get and validate activity ownership
        Reduces duplication across methods
        """
        try:
            activity = Activity.objects.get(id=pk)
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
        
        # Validate ownership
        if activity.owner != self.request.user:
            raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
        
        return activity
    
    def _parse_date_field(self, data, field_name):
        """
        Helper method to parse date fields with consistent error handling
        """
        date_value = data.get(field_name)
        if date_value:
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field=f"{field_name} (expected YYYY-MM-DD format)")
                )
        return None
    
    def _build_activity_kwargs(self, data):
        """
        Helper method to build kwargs from request data
        """
        kwargs = {}
        
        # Parse callback date
        callback_date = self._parse_date_field(data, 'callback_date')
        if callback_date:
            kwargs['callback_date'] = callback_date
        
        # Parse meeting date
        meeting_date = self._parse_date_field(data, 'meeting_date')
        if meeting_date:
            kwargs['meeting_date'] = meeting_date
        
        # Add disqualify account flag
        if 'disqualify_account' in data:
            kwargs['disqualify_account'] = data.get('disqualify_account')
        
        return kwargs
    
    @action(detail=True, methods=['post'])
    def complete_activity(self, request, pk=None):
        """
        Complete an activity with result - Simplified with helper methods
        
        Payload:
        {
            "result": "NO_ANSWER",
            "notes": "Contact did not pick up",
            "callback_date": "2025-01-15",  # For callback results
            "meeting_date": "2025-01-20",   # For successful results
            "disqualify_account": false     # For not interested results
        }
        """
        try:
            # Use helper method for validation
            activity = self._get_validated_activity(pk)
            
            # Get result data
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="result")
                )
            
            # Use helper method to build kwargs
            kwargs = self._build_activity_kwargs(request.data)
            
            # Process the result - CampaignCoreService.complete_activity returns Response directly
            return CampaignCoreService.complete_activity(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to complete activity")
            )
    
    @action(detail=True, methods=['post'])
    def add_email_response(self, request, pk=None):
        """
        Add a response to an already completed email/LinkedIn activity - Simplified
        
        Payload:
        {
            "result": "POSITIVE_RESPONSE",
            "notes": "Contact replied interested in meeting",
            "meeting_date": "2025-01-20"  # For positive responses
        }
        """
        try:
            # Use helper method for validation
            activity = self._get_validated_activity(pk)
            
            # Validate activity type
            if activity.activity_type not in [Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN]:
                raise StandardizedValidationError(
                    "Can only add responses to email/LinkedIn activities"
                )
            
            # Get result data
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="result")
                )
            
            # Use helper method to build kwargs
            kwargs = self._build_activity_kwargs(request.data)
            
            # Process the response using the result service directly - returns Response directly
            return CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to add email response")
            )
    
    @action(detail=False, methods=['get'])
    def get_next_step_options(self, request):
        """
        Get available next step options based on campaign target type - Unchanged
        
        Query params:
        - campaign_target_id: ID of the campaign target
        """
        try:
            campaign_target_id = request.query_params.get('campaign_target_id')
            
            if not campaign_target_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="campaign_target_id")
                )
            
            # Get campaign target and validate access
            try:
                from apps.campaign.models import CampaignTarget
                campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
                
                # Validate client scope
                self.validate_client_id(campaign_target)
                
                # Validate campaign ownership/stakeholder access
                campaign = campaign_target.campaign
                self.validate_campaign_related_object(campaign_target, allow_stakeholders=True)
                
            except CampaignTarget.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Determine target type and available options
            target_type = campaign_target.get_target_type()
            target_object = campaign_target.get_target()
            
            available_options = []
            
            # Meeting is always available as next step
            available_options.append({
                'type': 'meeting',
                'label': 'Schedule Meeting',
                'description': 'Schedule a follow-up meeting',
                'requires_fields': ['meeting_date', 'notes']
            })
            
            # Lead creation (only for account/contact targets)
            if target_type in ['account', 'contact']:
                available_options.append({
                    'type': 'lead',
                    'label': 'Create Lead',
                    'description': 'Create a new lead for this prospect',
                    'requires_fields': ['lead_title', 'description', 'notes']
                })
            
            # Opportunity creation (valid for account/contact/lead targets)
            if target_type in ['account', 'contact', 'lead']:
                available_options.append({
                    'type': 'opportunity',
                    'label': 'Create Opportunity',
                    'description': 'Create a new sales opportunity',
                    'requires_fields': ['opportunity_title', 'expected_close_date', 'amount', 'notes']
                })
            
            # Opportunity advancement (only for opportunity targets)
            if target_type == 'opportunity':
                available_options.append({
                    'type': 'opportunity_advance',
                    'label': 'Advance Opportunity',
                    'description': 'Update existing opportunity (stage, amount, etc.)',
                    'requires_fields': ['notes'],  # Simple for MVP
                    'disabled': True,  # Disabled until stages are implemented
                    'disabled_reason': 'Opportunity stages not yet implemented'
                })
            
            # Other/Custom option
            available_options.append({
                'type': 'other',
                'label': 'Other Action',
                'description': 'Custom next step with notes only',
                'requires_fields': ['notes']
            })
            
            # Prepare response data
            data = {
                'campaign_target_id': campaign_target.id,
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'target_type': target_type,
                'target_info': {
                    'id': target_object.id,
                    'name': getattr(target_object, 'company_name', None) or 
                            getattr(target_object, 'title', None) or 
                            f"{getattr(target_object, 'first_name', '')} {getattr(target_object, 'last_name', '')}".strip(),
                    'type': target_type
                },
                'available_options': available_options
            }
            
            meta = {
                'operation': 'next_step_options',
                'target_type': target_type,
                'options_count': len(available_options)
            }
            
            return StandardizedSuccessResponse.success(
                message="Next step options retrieved successfully",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to get next step options")
            )

    @action(detail=False, methods=['post'])
    def process_next_step_choice(self, request):
        """
        Process user's choice for next step after successful campaign activity - Simplified validation
        
        Expected payload:
        {
            "campaign_target_id": 123,
            "source_activity_id": 456,
            "choice_type": "meeting|lead|opportunity|other",
            "contact_id": 789,  # Required for meeting/lead/opportunity
            
            // For meeting:
            "meeting_date": "2025-01-15",
            "notes": "Follow up on pricing discussion",
            
            // For lead:
            "lead_title": "Interested in Enterprise Plan", 
            "description": "Contact showed interest...",
            "notes": "Next: send proposal",
            
            // For opportunity:
            "opportunity_title": "Q2 Enterprise Deal",
            "expected_close_date": "2025-03-30",
            "amount": 50000,
            "opportunity_type": "NEW_BUSINESS",
            "notes": "Strong buying signals",
            
            // For other:
            "notes": "Custom action taken"
        }
        """
        try:
            # Extract and validate required fields using helper
            campaign_target_id, source_activity_id, choice_type = self._validate_next_step_required_fields(request.data)
            
            # Get and validate campaign target and source activity
            campaign_target, source_activity = self._get_validated_next_step_objects(
                campaign_target_id, source_activity_id
            )
            
            # Import service
            from apps.campaign.services.campaign_business_result_service import CampaignBusinessResultService
            
            # Route to appropriate handler based on choice_type
            if choice_type == 'meeting':
                return self._process_meeting_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'lead':
                return self._process_lead_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'opportunity':
                return self._process_opportunity_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
            elif choice_type == 'other':
                return self._process_other_choice(request.data, campaign_target, source_activity, CampaignBusinessResultService)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to process next step choice")
            )
    
    def _validate_next_step_required_fields(self, data):
        """Helper to validate required fields for next step processing"""
        campaign_target_id = data.get('campaign_target_id')
        source_activity_id = data.get('source_activity_id')
        choice_type = data.get('choice_type')
        
        if not all([campaign_target_id, source_activity_id, choice_type]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="campaign_target_id, source_activity_id, and choice_type"
                )
            )
        
        # Validate choice_type
        valid_choices = ['meeting', 'lead', 'opportunity', 'other']
        if choice_type not in valid_choices:
            raise StandardizedValidationError(
                f"Invalid choice_type. Must be one of: {', '.join(valid_choices)}"
            )
        
        return campaign_target_id, source_activity_id, choice_type
    
    def _get_validated_next_step_objects(self, campaign_target_id, source_activity_id):
        """Helper to get and validate campaign target and source activity"""
        # Get and validate campaign target
        try:
            from apps.campaign.models import CampaignTarget
            campaign_target = CampaignTarget.objects.get(id=campaign_target_id)
            self.validate_client_id(campaign_target)
            self.validate_campaign_related_object(campaign_target, allow_stakeholders=True)
        except CampaignTarget.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND + " (campaign target)")
        
        # Get and validate source activity
        try:
            source_activity = Activity.objects.get(id=source_activity_id)
            self.validate_client_id(source_activity)
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND + " (source activity)")
        
        return campaign_target, source_activity
    
    def _process_meeting_choice(self, data, campaign_target, source_activity, service):
        """Helper to process meeting choice"""
        contact_id = data.get('contact_id')
        meeting_date = self._parse_date_field(data, 'meeting_date')
        
        if not all([contact_id, meeting_date]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and meeting_date for meeting creation")
            )
        
        return service.create_meeting_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            meeting_date=meeting_date,
            contact_id=contact_id,
            source_activity=source_activity,
            notes=data.get('notes', '')
        )
    
    def _process_lead_choice(self, data, campaign_target, source_activity, service):
        """Helper to process lead choice"""
        contact_id = data.get('contact_id')
        lead_title = data.get('lead_title')
        
        if not all([contact_id, lead_title]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and lead_title for lead creation")
            )
        
        return service.create_lead_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            contact_id=contact_id,
            source_activity=source_activity,
            lead_title=lead_title,
            description=data.get('description', ''),
            notes=data.get('notes', '')
        )
    
    def _process_opportunity_choice(self, data, campaign_target, source_activity, service):
        """Helper to process opportunity choice"""
        contact_id = data.get('contact_id')
        opportunity_title = data.get('opportunity_title')
        expected_close_date = self._parse_date_field(data, 'expected_close_date')
        
        if not all([contact_id, opportunity_title, expected_close_date]):
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(
                    field="contact_id, opportunity_title, and expected_close_date for opportunity creation"
                )
            )
        
        # Parse amount (optional, default to 0)
        amount = 0
        if data.get('amount'):
            try:
                amount = float(data.get('amount'))
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="amount (must be a number)")
                )
        
        return service.create_opportunity_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            contact_id=contact_id,
            source_activity=source_activity,
            opportunity_title=opportunity_title,
            expected_close_date=expected_close_date,
            amount=amount,
            opportunity_type=data.get('opportunity_type'),
            notes=data.get('notes', '')
        )
    
    def _process_other_choice(self, data, campaign_target, source_activity, service):
        """Helper to process other choice"""
        notes = data.get('notes', '')
        if not notes:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="notes for custom action")
            )
        
        return service.create_other_next_step(
            campaign_target=campaign_target,
            user=self.request.user,
            source_activity=source_activity,
            notes=notes
        )