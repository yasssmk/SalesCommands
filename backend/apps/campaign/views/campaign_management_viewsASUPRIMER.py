# apps/campaign/views/campaign_management_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from datetime import datetime
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied
from core.error_messages import CampaignErrorMessages
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models import Campaign
from apps.campaign.serializers import CampaignSerializer
from apps.campaign.services.campaign_core_service import CampaignCoreService
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.services.campaign_activity_service import CampaignActivityService
from apps.campaign.services.campaign_target_service import CampaignTargetService
from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from django.db import transaction
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse, CampaignSuccessMessages
from apps.campaign.mixins.permission_mixins import CampaignPermissionMixin
from apps.campaign.config.variables import (
    DEFAULT_PLAYLIST_LIMIT,
    FIELD_NAMES,
    QUERY_PARAMS,
    URL_PATTERNS,
    DATE_FORMATS,
    VALIDATION_LIMITS,
    FILTER_CONFIGS
)


class CampaignManagementViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing campaigns with sequence and activity management
    Now returns standardized responses consistently
    """
    serializer_class = CampaignSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = FILTER_CONFIGS['CAMPAIGN_FILTERS']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get campaigns for the current client"""
        queryset = Campaign.objects.all()
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filter by owner if requested
        owner_filter = self.request.query_params.get(QUERY_PARAMS['MY_CAMPAIGNS'], None)
        if owner_filter and owner_filter.lower() == 'true':
            queryset = queryset.filter(owner=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create campaign with owner set to current user"""
        campaign = serializer.save(owner=self.request.user)
        return campaign
    
    @action(detail=False, methods=['post'])
    def create_with_targets(self, request):
        """
        Create a campaign with targets and generate activities
        
        Expected payload:
        {
            "campaign": {
                "name": "Q1 Outreach",
                "description": "...",
                "start_date": "2025-01-01",
                "end_date": "2025-03-31",
                "campaign_type": "CHASING"
            },
            "target_account_ids": [1, 2, 3],     # Accounts to target (all contacts)
            "target_contact_ids": [4, 5, 6]      # Specific contacts to target
        }
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
                from datetime import datetime, date
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
            
            # Validate sequence type for call lists
            campaign_type = campaign_data.get('campaign_type')
            sequence_type = campaign_data.get('sequence_type')
            if campaign_type == Campaign.CampaignType.CALL_LIST and sequence_type is not None:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_NO_SEQUENCE_TYPE)
            
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
            
            # Create campaign and activities - CampaignCoreService now returns Response directly
            return CampaignCoreService.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_result['target_accounts'],
                target_contacts=target_result['target_contacts'],
                target_leads=target_result['target_leads'],
                target_opportunities=target_result['target_opportunities'],
                targeting_stats=target_result['stats']
            )
            
        except (StandardizedValidationError, StandardizedAuthenticationFailed, StandardizedPermissionDenied):
            # Re-raise our standardized exceptions
            raise
        except ValueError as e:
            if "client_id is required" in str(e):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
            raise StandardizedValidationError(f"Campaign creation failed: {str(e)}")
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign creation failed")
            )
 
    @action(detail=True, methods=['post'])
    def start_campaign(self, request, pk=None):
        """
        Start/activate a campaign and get initial playlist
        """        
        # Validate ownership
        campaign = self.get_validated_campaign(require_ownership=True)
        
        # CampaignCoreService.start_campaign now returns Response directly
        return CampaignCoreService.start_campaign(campaign)
    
    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """
        Get the current playlist of activities for a campaign
        
        Query params:
        - limit: Number of activities to return (default: 20)
        """
        campaign = self.get_validated_campaign(require_ownership=True, check_state=False)
        
        limit = int(request.query_params.get(QUERY_PARAMS['LIMIT'], DEFAULT_PLAYLIST_LIMIT))
        
        # CampaignCoreService.get_campaign_playlist now returns Response directly
        return CampaignCoreService.get_campaign_playlist(campaign, limit=limit)
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get comprehensive campaign summary
        """
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # CampaignCoreService.get_campaign_summary now returns Response directly
        return CampaignCoreService.get_campaign_summary(campaign)
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """
        Pause a campaign
        
        Payload:
        {
            "pause_until": "2025-02-01"  # Optional
        }
        """
        campaign = self.get_validated_campaign(require_ownership=True)
        
        pause_until = request.data.get('pause_until', None)
        if pause_until:
            from datetime import datetime
            pause_until = datetime.strptime(pause_until, '%Y-%m-%d').date()
        
        # CampaignCoreService.pause_campaign now returns Response directly
        return CampaignCoreService.pause_campaign(campaign, pause_until=pause_until)
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """
        Resume a paused campaign
        """
        campaign = self.get_validated_campaign(require_ownership=True)
        
        # CampaignCoreService.resume_campaign now returns Response directly
        return CampaignCoreService.resume_campaign(campaign)
    
    @action(detail=True, methods=['get'])
    def contacts_with_responses(self, request, pk=None):
        """
        Get all contacts in campaign with email/LinkedIn activities that might have responses
        """
        campaign = self.get_validated_campaign(
            require_ownership=True, 
            allow_stakeholders=True, 
            check_state=False
        )
        
        # CampaignCoreService.get_campaign_contacts_with_responses now returns Response directly
        return CampaignCoreService.get_campaign_contacts_with_responses(campaign)
    
    @action(detail=False, methods=['get'])
    def account_campaigns(self, request):
        """
        Get all campaigns that the specified account is a target of
        
        Query params:
        - account_id: ID of the account to get campaigns for
        """
        account_id = request.query_params.get(QUERY_PARAMS['ACCOUNT_ID'])
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field="account_id")
            )
        

        account = self._get_validated_account(account_id)
            
        # Get campaign targets for this account
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
            
    
    @action(detail=True, methods=['post'])
    def remove_account(self, request, pk=None):
        """
        Remove an account from the campaign
        
        Payload:
        {
            "account_id": 1,
            "notes": "Optional notes about removal reason"
        }
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True,
                check_state=True
            )
            
            # Extract and validate required data
            account_id = request.data.get('account_id')
            notes = request.data.get('notes')
            
            if not account_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Account ID")
                )
            
            # Validate account exists and is accessible
            account = self._get_validated_account(account_id)
            
            # Validate account is actually targeted by this campaign
            campaign_target = campaign.targets.filter(account=account).first()
            if not campaign_target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            # Remove account from campaign - CampaignCoreService now returns Response directly
            return CampaignCoreService.remove_account_from_campaign(
                campaign=campaign,
                account=account,
                notes=notes
            )
            
        except (StandardizedValidationError, StandardizedPermissionDenied):
            # Re-raise standardized exceptions
            raise
        except Exception as e:
            # Convert unexpected errors
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to remove account from campaign")
            )
    
    @action(detail=True, methods=['post'])
    def remove_contact(self, request, pk=None):
        """
        Remove a contact from the campaign
        
        Payload:
        {
            "contact_id": 1,
            "notes": "Optional notes about removal reason"
        }
        """
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
        
            
        # Remove contact from campaign - CampaignCoreService now returns Response directly
        return CampaignCoreService.remove_contact_from_campaign(
            campaign=campaign,
            contact=contact,
            notes=notes
        )
            
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """
        Get all activities for a campaign with optional status filtering
        
        Query params:
        - status: Comma-separated list of activity statuses to filter by
        """
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
        
        # CampaignCoreService.get_campaign_activities now returns Response directly
        return CampaignCoreService.get_campaign_activities(
            campaign=campaign,
            status_filter=status_filter
        )

    @action(detail=True, methods=['get'])
    def account_activities(self, request, pk=None):
        """
        Get all activities for a specific account in a campaign
        
        Query params:
        - account_id: ID of the account to get activities for
        - status: Comma-separated list of activity statuses to filter by
        """
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

            
        # CampaignCoreService.get_account_activities_in_campaign now returns Response directly
        return CampaignCoreService.get_account_activities_in_campaign(
            campaign=campaign,
            account=account,
            status_filter=status_filter
        )


    @action(detail=True, methods=['get'])
    def contact_activities(self, request, pk=None):
        """
        Get all activities for a specific contact in a campaign
        
        Query params:
        - contact_id: ID of the contact to get activities for
        - status: Comma-separated list of activity statuses to filter by
        """
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
                    
        # CampaignCoreService.get_contact_activities_in_campaign now returns Response directly
        return CampaignCoreService.get_contact_activities_in_campaign(
            campaign=campaign,
            contact=contact,
            status_filter=status_filter
        )
            

    @action(detail=True, methods=['post'], url_path='add-manual-activity')
    def add_manual_activity(self, request, pk=None):
        """
        Add a manual activity for a contact in a non-sequence campaign
        
        Expected payload:
        {
            "contact_id": 123,
            "activity_type": "CALL",
            "result": "SUCCESSFUL",  # Activity result
            "notes": "Optional notes",
            "meeting_date": "2025-01-15",  # Optional, for successful calls
            "callback_date": "2025-01-10",  # Optional, for callbacks
        }
        """
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
            
            # Validate client scope
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
                from datetime import datetime
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            if request.data.get('callback_date'):
                from datetime import datetime
                kwargs['callback_date'] = datetime.strptime(
                    request.data.get('callback_date'), '%Y-%m-%d'
                ).date()
            
            # CampaignCoreService.add_manual_activity_to_campaign now returns Response directly
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
    
    # @action(detail=True, methods=['get'])
    # def dashboard(self, request, pk=None):
    #     """
    #     Get campaign dashboard with metrics vs objectives
    #     VERSION MVP : Simple et direct
        
    #     Response includes:
    #     - Current metrics (leads, meetings, opportunities, deals)
    #     - Objectives vs achieved comparison
    #     - Quick health indicators
    #     """
    #     try:
    #         campaign = self.get_validated_campaign(
    #             require_ownership=True, 
    #             allow_stakeholders=True, 
    #             check_state=False
    #         )
            
    #         # Obtenir les métriques actuelles
    #         current_metrics = CampaignTrackingService.get_campaign_metrics(campaign)
            
    #         # Obtenir les objectifs
    #         objectives = campaign.objectives.all()
    #         objectives_data = []
            
    #         for objective in objectives:
    #             # Mapper les types d'objectifs aux métriques
    #             metric_value = 0
    #             if objective.objective_type == 'LEADS':
    #                 metric_value = current_metrics['leads_created']
    #             elif objective.objective_type == 'MEETINGS':
    #                 metric_value = current_metrics['meetings_secured']
    #             elif objective.objective_type == 'OPPORTUNITIES':
    #                 metric_value = current_metrics['opportunities_created']
    #             elif objective.objective_type == 'CLOSED_DEALS':
    #                 metric_value = current_metrics['deals_closed']
    #             elif objective.objective_type == 'PIPELINE_VALUE':
    #                 metric_value = current_metrics['pipeline_value']
    #             elif objective.objective_type == 'REVENUE':
    #                 metric_value = current_metrics['revenue_generated']
                
    #             # Calculer progression
    #             target_value = float(objective.target_value)
    #             progress_percentage = (metric_value / target_value * 100) if target_value > 0 else 0
                
    #             objectives_data.append({
    #                 'id': objective.id,
    #                 'name': objective.name,
    #                 'type': objective.objective_type,
    #                 'type_display': objective.get_objective_type_display(),
    #                 'target_value': target_value,
    #                 'current_value': metric_value,
    #                 'progress_percentage': round(progress_percentage, 1),
    #                 'status': 'achieved' if progress_percentage >= 100 else 'in_progress' if progress_percentage > 0 else 'not_started',
    #                 'is_primary': objective.is_primary
    #             })
            
    #         # Calculer indicateurs de santé
    #         health_indicators = {
    #             'overall_health': 'good',  # good, warning, critical
    #             'total_results': (
    #                 current_metrics['leads_created'] + 
    #                 current_metrics['meetings_secured'] + 
    #                 current_metrics['opportunities_created'] + 
    #                 current_metrics['deals_closed']
    #             ),
    #             'conversion_rates': {},
    #             'alerts': []
    #         }
            
    #         # Taux de conversion
    #         if current_metrics['leads_created'] > 0:
    #             meeting_rate = (current_metrics['meetings_secured'] / current_metrics['leads_created']) * 100
    #             health_indicators['conversion_rates']['leads_to_meetings'] = round(meeting_rate, 1)
                
    #             if meeting_rate < 10:
    #                 health_indicators['overall_health'] = 'critical'
    #                 health_indicators['alerts'].append('Low meeting conversion rate (<10%)')
    #             elif meeting_rate < 25:
    #                 health_indicators['overall_health'] = 'warning'
    #                 health_indicators['alerts'].append('Meeting conversion rate could be improved')
            
    #         if current_metrics['meetings_secured'] > 0:
    #             opp_rate = (current_metrics['opportunities_created'] / current_metrics['meetings_secured']) * 100
    #             health_indicators['conversion_rates']['meetings_to_opportunities'] = round(opp_rate, 1)
            
    #         if current_metrics['opportunities_created'] > 0:
    #             deal_rate = (current_metrics['deals_closed'] / current_metrics['opportunities_created']) * 100
    #             health_indicators['conversion_rates']['opportunities_to_deals'] = round(deal_rate, 1)
            
    #         # Vérifier si campagne active sans résultats
    #         if campaign.status == 'ACTIVE' and health_indicators['total_results'] == 0:
    #             health_indicators['overall_health'] = 'warning'
    #             health_indicators['alerts'].append('Active campaign with no results yet')
            
    #         # Vérifier objectifs en retard
    #         behind_objectives = [obj for obj in objectives_data if obj['progress_percentage'] < 50]
    #         if len(behind_objectives) > len(objectives_data) / 2:
    #             health_indicators['overall_health'] = 'warning'
    #             health_indicators['alerts'].append('Multiple objectives behind target')
            
    #         # Préparer réponse finale
    #         dashboard_data = {
    #             'campaign': {
    #                 'id': campaign.id,
    #                 'name': campaign.name,
    #                 'status': campaign.status,
    #                 'start_date': campaign.start_date,
    #                 'end_date': campaign.end_date,
    #                 'campaign_type': campaign.campaign_type,
    #                 'has_sequence': campaign.sequence_type is not None
    #             },
    #             'current_metrics': current_metrics,
    #             'objectives': objectives_data,
    #             'health_indicators': health_indicators,
    #             'summary': {
    #                 'total_objectives': len(objectives_data),
    #                 'achieved_objectives': len([obj for obj in objectives_data if obj['status'] == 'achieved']),
    #                 'primary_objective': next((obj for obj in objectives_data if obj['is_primary']), None),
    #                 'last_updated': current_metrics['last_updated']
    #             }
    #         }
            
    #         return StandardizedSuccessResponse.success(
    #             message=f"Dashboard data retrieved for campaign '{campaign.name}'",
    #             data=dashboard_data,
    #             meta={
    #                 'operation': 'campaign_dashboard',
    #                 'campaign_id': campaign.id,
    #                 'health_status': health_indicators['overall_health']
    #             }
    #         )
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to generate campaign dashboard")


    #         )

    @action(detail=True, methods=['get'])
    def dashboard(self, request, pk=None):
        """
        Get campaign dashboard with factual metrics
        VERSION MVP : Données factuelles uniquement, sans interprétations
        
        Response includes:
        - Current metrics (leads, meetings, opportunities, deals)
        - Objectives vs achieved comparison (factuel)
        - Activities progress (compteurs factuels)
        - Timeline progress (progression temporelle factuelle)
        - Conversion rates (taux factuels)
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Utiliser le service analytics pour obtenir toutes les données
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            
            # Le service retourne déjà une Response standardisée
            return CampaignAnalyticsService.get_campaign_dashboard_data(campaign)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to generate campaign dashboard")
            )

    @action(detail=True, methods=['get'])
    def dashboard_summary(self, request, pk=None):
        """
        Get simplified dashboard summary using campaign helper methods
        VERSION MVP : Résumé rapide via les helpers du modèle
        
        Alternative plus légère au dashboard complet
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Utiliser les helpers du modèle Campaign
            dashboard_summary = campaign.get_dashboard_summary()
            
            # Ajouter info de base sur la campagne
            summary_data = {
                'campaign_info': {
                    'id': campaign.id,
                    'name': campaign.name,
                    'type': campaign.campaign_type,
                    'type_display': campaign.get_campaign_type_display(),
                    'status': campaign.status,
                    'start_date': campaign.start_date.isoformat(),
                    'end_date': campaign.end_date.isoformat(),
                    'has_sequence': campaign.sequence_type is not None
                },
                'summary': dashboard_summary
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Dashboard summary retrieved for campaign '{campaign.name}'",
                data=summary_data,
                meta={
                    'operation': 'campaign_dashboard_summary',
                    'campaign_id': campaign.id,
                    'summary_type': 'factual_only'
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to generate campaign dashboard summary")
            )

    @action(detail=True, methods=['get'])
    def objectives_progress(self, request, pk=None):
        """
        Get detailed objectives progress only
        VERSION MVP : Focus sur les objectifs uniquement
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Utiliser helper du modèle
            objectives_summary = campaign.get_objectives_progress_summary()
            
            # Ajouter détails des objectifs individuels si demandé
            include_details = request.query_params.get('include_details', 'false').lower() == 'true'
            
            response_data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'objectives_summary': objectives_summary
            }
            
            if include_details and objectives_summary.get('has_objectives', False):
                # Utiliser le service pour obtenir les détails
                from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
                from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
                
                tracking_metrics = CampaignTrackingService.get_campaign_metrics(campaign)
                objectives_data = CampaignAnalyticsService._calculate_objectives_vs_results(campaign, tracking_metrics)
                response_data['objectives_details'] = objectives_data['objectives']
            
            return StandardizedSuccessResponse.success(
                message=f"Objectives progress retrieved for campaign '{campaign.name}'",
                data=response_data,
                meta={
                    'operation': 'objectives_progress',
                    'campaign_id': campaign.id,
                    'include_details': include_details
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve objectives progress")
            )

    @action(detail=True, methods=['get'])
    def conversion_analysis(self, request, pk=None):
        """
        Get detailed conversion rates analysis
        VERSION MVP : Focus sur les taux de conversion uniquement
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Utiliser helper du modèle pour obtenir les taux
            conversion_rates = campaign.get_conversion_rates()
            
            # Ajouter métriques brutes pour contexte
            tracking_metrics = campaign.get_metrics_summary()
            
            response_data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'raw_metrics': tracking_metrics,
                'conversion_rates': conversion_rates,
                'funnel_data': {
                    'leads': tracking_metrics['leads_created'],
                    'meetings': tracking_metrics['meetings_secured'],
                    'opportunities': tracking_metrics['opportunities_created'],
                    'deals': tracking_metrics['deals_closed']
                }
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Conversion analysis retrieved for campaign '{campaign.name}'",
                data=response_data,
                meta={
                    'operation': 'conversion_analysis',
                    'campaign_id': campaign.id,
                    'data_type': 'factual_rates_only'
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve conversion analysis")
            )

    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """
        Get raw campaign metrics (simpler endpoint)
        VERSION MVP : Métriques brutes sans comparaison objectifs
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Obtenir les métriques directement
            metrics = CampaignTrackingService.get_campaign_metrics(campaign)
            
            # Ajouter quelques infos de contexte
            metrics['campaign_id'] = campaign.id
            metrics['campaign_name'] = campaign.name
            metrics['campaign_status'] = campaign.status
            
            return StandardizedSuccessResponse.success(
                message=f"Metrics retrieved for campaign '{campaign.name}'",
                data=metrics,
                meta={
                    'operation': 'campaign_metrics',
                    'campaign_id': campaign.id
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to retrieve campaign metrics")
            )


    @action(detail=True, methods=['post'])
    def integrity_check(self, request, pk=None):
        """
        Check campaign tracking data integrity
        VERSION MVP : Vérification manuelle sur demande
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=True, 
                check_state=False
            )
            
            # Obtenir le result tracking
            result_tracking = CampaignTrackingService.get_or_create_result_tracking(campaign)
            
            # Générer rapport d'intégrité
            integrity_report = result_tracking.get_integrity_report()
            
            # Ajouter recommandations simples
            recommendations = []
            if integrity_report['integrity_score'] < 90:
                recommendations.append("Consider running cleanup - some tracked objects may no longer exist")
            if integrity_report.get('has_orphaned_objects', False):
                recommendations.append("Orphaned objects detected - review campaign relationships")
            if not recommendations:
                recommendations.append("Campaign tracking integrity is healthy")
            
            integrity_report['recommendations'] = recommendations
            
            return StandardizedSuccessResponse.success(
                message=f"Integrity check completed for campaign '{campaign.name}'",
                data=integrity_report,
                meta={
                    'operation': 'integrity_check',
                    'campaign_id': campaign.id,
                    'needs_cleanup': integrity_report.get('needs_cleanup', False)
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to check campaign integrity")
            )

    @action(detail=True, methods=['post'])
    def cleanup_tracking(self, request, pk=None):
        """
        Clean up invalid tracking data
        VERSION MVP : Nettoyage manuel sur demande
        """
        try:
            campaign = self.get_validated_campaign(
                require_ownership=True, 
                allow_stakeholders=False,  # Only owners can cleanup
                check_state=False
            )
            
            # Obtenir le result tracking
            result_tracking = CampaignTrackingService.get_or_create_result_tracking(campaign)
            
            # Faire le nettoyage
            cleanup_report = CampaignTrackingService.cleanup_invalid_tracking_data(campaign)
            
            return StandardizedSuccessResponse.success(
                message=f"Cleanup completed for campaign '{campaign.name}'",
                data=cleanup_report,
                meta={
                    'operation': 'tracking_cleanup',
                    'campaign_id': campaign.id,
                    'cleanup_successful': cleanup_report.get('cleanup_successful', False)
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to cleanup campaign tracking")
            )


class ActivityResultViewSet(BaseAPIView, CampaignPermissionMixin, viewsets.ViewSet):
    """
    ViewSet for handling activity results and completion
    Now returns standardized responses consistently
    """
    
    @action(detail=True, methods=['post'])
    def complete_activity(self, request, pk=None):
        """
        Complete an activity with result
        
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
            activity = Activity.objects.get(id=pk)
            
            # Validate ownership
            if activity.owner != request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
            
            # Get result data
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="result")
                )
            
            # Prepare kwargs for additional data
            kwargs = {}
            if request.data.get('callback_date'):
                kwargs['callback_date'] = datetime.strptime(
                    request.data.get('callback_date'), '%Y-%m-%d'
                ).date()
            
            if request.data.get('meeting_date'):
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            if 'disqualify_account' in request.data:
                kwargs['disqualify_account'] = request.data.get('disqualify_account')
            
            # Process the result - CampaignCoreService.complete_activity now returns Response directly
            return CampaignCoreService.complete_activity(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def get_next_step_options(self, request):
        """
        Get available next step options based on campaign target type
        
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
        Process user's choice for next step after successful campaign activity
        
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
            # Extract and validate required fields
            campaign_target_id = request.data.get('campaign_target_id')
            source_activity_id = request.data.get('source_activity_id')
            choice_type = request.data.get('choice_type')
            
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
            
            # Import service
            from apps.campaign.services.campaign_business_result_service import CampaignBusinessResultService
            
            # Route to appropriate handler based on choice_type
            if choice_type == 'meeting':
                # Validate required fields for meeting
                contact_id = request.data.get('contact_id')
                meeting_date = request.data.get('meeting_date')
                
                if not all([contact_id, meeting_date]):
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and meeting_date for meeting creation")
                    )
                
                # Parse meeting date
                try:
                    from datetime import datetime
                    meeting_date = datetime.strptime(meeting_date, '%Y-%m-%d').date()
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="meeting_date (expected YYYY-MM-DD format)")
                    )
                
                return CampaignBusinessResultService.create_meeting_next_step(
                    campaign_target=campaign_target,
                    user=request.user,
                    meeting_date=meeting_date,
                    contact_id=contact_id,
                    source_activity=source_activity,
                    notes=request.data.get('notes', '')
                )
            
            elif choice_type == 'lead':
                # Validate required fields for lead
                contact_id = request.data.get('contact_id')
                lead_title = request.data.get('lead_title')
                
                if not all([contact_id, lead_title]):
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field="contact_id and lead_title for lead creation")
                    )
                
                return CampaignBusinessResultService.create_lead_next_step(
                    campaign_target=campaign_target,
                    user=request.user,
                    contact_id=contact_id,
                    source_activity=source_activity,
                    lead_title=lead_title,
                    description=request.data.get('description', ''),
                    notes=request.data.get('notes', '')
                )
            
            elif choice_type == 'opportunity':
                # Validate required fields for opportunity
                contact_id = request.data.get('contact_id')
                opportunity_title = request.data.get('opportunity_title')
                expected_close_date = request.data.get('expected_close_date')
                
                if not all([contact_id, opportunity_title, expected_close_date]):
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(
                            field="contact_id, opportunity_title, and expected_close_date for opportunity creation"
                        )
                    )
                
                # Parse expected close date
                try:
                    from datetime import datetime
                    expected_close_date = datetime.strptime(expected_close_date, '%Y-%m-%d').date()
                except ValueError:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="expected_close_date (expected YYYY-MM-DD format)")
                    )
                
                # Parse amount (optional, default to 0)
                amount = 0
                if request.data.get('amount'):
                    try:
                        amount = float(request.data.get('amount'))
                    except (ValueError, TypeError):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(field="amount (must be a number)")
                        )
                
                return CampaignBusinessResultService.create_opportunity_next_step(
                    campaign_target=campaign_target,
                    user=request.user,
                    contact_id=contact_id,
                    source_activity=source_activity,
                    opportunity_title=opportunity_title,
                    expected_close_date=expected_close_date,
                    amount=amount,
                    opportunity_type=request.data.get('opportunity_type'),
                    notes=request.data.get('notes', '')
                )
            
            elif choice_type == 'other':
                # Only notes required for other
                notes = request.data.get('notes', '')
                if not notes:
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field="notes for custom action")
                    )
                
                return CampaignBusinessResultService.create_other_next_step(
                    campaign_target=campaign_target,
                    user=request.user,
                    source_activity=source_activity,
                    notes=notes
                )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to process next step choice")
            )
        

    @action(detail=True, methods=['post'])
    def add_email_response(self, request, pk=None):
        """
        Add a response to an already completed email/LinkedIn activity
        
        Payload:
        {
            "result": "POSITIVE_RESPONSE",
            "notes": "Contact replied interested in meeting",
            "meeting_date": "2025-01-20"  # For positive responses
        }
        """
        try:
            activity = Activity.objects.get(id=pk)
            
            # Validate ownership
            if activity.owner != request.user:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_OWNER_REQUIRED)
            
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
            
            # Prepare kwargs
            kwargs = {}
            if request.data.get('meeting_date'):
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            # Process the response using the result service directly - returns Response directly
            return CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)