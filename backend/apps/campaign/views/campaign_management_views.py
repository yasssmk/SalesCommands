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
from apps.campaign.services.campaign_manager import CampaignManager
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.campaign.models.campaign_target import CampaignTarget
from apps.campaign.services.campaign_activity_service import CampaignActivityService
from apps.campaign.services.campaign_target_service import CampaignTargetService
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
            
            # Create campaign and activities - CampaignManager now returns Response directly
            return CampaignManager.create_campaign_with_activities(
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
        
        # CampaignManager.start_campaign now returns Response directly
        return CampaignManager.start_campaign(campaign)
    
    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """
        Get the current playlist of activities for a campaign
        
        Query params:
        - limit: Number of activities to return (default: 20)
        """
        campaign = self.get_validated_campaign(require_ownership=True, check_state=False)
        
        limit = int(request.query_params.get(QUERY_PARAMS['LIMIT'], DEFAULT_PLAYLIST_LIMIT))
        
        # CampaignManager.get_campaign_playlist now returns Response directly
        return CampaignManager.get_campaign_playlist(campaign, limit=limit)
    
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
        
        # CampaignManager.get_campaign_summary now returns Response directly
        return CampaignManager.get_campaign_summary(campaign)
    
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
        
        # CampaignManager.pause_campaign now returns Response directly
        return CampaignManager.pause_campaign(campaign, pause_until=pause_until)
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """
        Resume a paused campaign
        """
        campaign = self.get_validated_campaign(require_ownership=True)
        
        # CampaignManager.resume_campaign now returns Response directly
        return CampaignManager.resume_campaign(campaign)
    
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
        
        # CampaignManager.get_campaign_contacts_with_responses now returns Response directly
        return CampaignManager.get_campaign_contacts_with_responses(campaign)
    
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
        
        try:
            from apps.accounts.models import Account
            account = Account.objects.get(id=account_id)
            
            # Check client scope
            self.validate_client_id(account)
            
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
            
        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
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
            try:
                from apps.accounts.models import Account
                account = Account.objects.get(id=account_id)
            except Account.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validate client scope
            self.validate_client_id(account)
            
            # Validate account is actually targeted by this campaign
            campaign_target = campaign.targets.filter(account=account).first()
            if not campaign_target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            # Remove account from campaign - CampaignManager now returns Response directly
            return CampaignManager.remove_account_from_campaign(
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
        
        try:
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            
            # Validate client scope
            self.validate_client_id(contact)
            
            # Remove contact from campaign - CampaignManager now returns Response directly
            return CampaignManager.remove_contact_from_campaign(
                campaign=campaign,
                contact=contact,
                notes=notes
            )
            
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
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
        
        # CampaignManager.get_campaign_activities now returns Response directly
        return CampaignManager.get_campaign_activities(
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
        
        try:
            from apps.accounts.models import Account
            account = Account.objects.get(id=account_id)
            
            # Validate client scope
            self.validate_client_id(account)
            
            # CampaignManager.get_account_activities_in_campaign now returns Response directly
            return CampaignManager.get_account_activities_in_campaign(
                campaign=campaign,
                account=account,
                status_filter=status_filter
            )
            
        except Account.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

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
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        try:
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            
            # Validate client scope
            self.validate_client_id(contact)
            
            # CampaignManager.get_contact_activities_in_campaign now returns Response directly
            return CampaignManager.get_contact_activities_in_campaign(
                campaign=campaign,
                contact=contact,
                status_filter=status_filter
            )
            
        except Contact.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

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
            
            # CampaignManager.add_manual_activity_to_campaign now returns Response directly
            return CampaignManager.add_manual_activity_to_campaign(
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


class ActivityResultViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ViewSet):
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
            
            # Process the result - CampaignManager.complete_activity now returns Response directly
            return CampaignManager.complete_activity(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
        except Activity.DoesNotExist:
            raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
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