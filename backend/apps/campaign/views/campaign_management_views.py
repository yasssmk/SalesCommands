# apps/campaign/views/campaign_management_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from datetime import datetime
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
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
from apps.campaign.config.variables import DEFAULT_PLAYLIST_LIMIT


class CampaignManagementViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing campaigns with sequence and activity management
    """
    serializer_class = CampaignSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['campaign_type', 'owner', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get campaigns for the current client"""
        queryset = Campaign.objects.all()
        queryset = self.filter_queryset_by_client(queryset)
        
        # Filter by owner if requested
        owner_filter = self.request.query_params.get('my_campaigns', None)
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
            campaign_data = request.data.get('campaign', {})
            target_account_ids = request.data.get('target_account_ids', [])
            target_contact_ids = request.data.get('target_contact_ids', [])
            target_lead_ids = request.data.get('target_lead_ids', [])
            target_opportunity_ids = request.data.get('target_opportunity_ids', [])
            
            # Validation
            if not campaign_data.get('name'):
                raise StandardizedValidationError("Campaign name is required")
            
            if not any([target_account_ids, target_contact_ids, target_lead_ids, target_opportunity_ids]):
                raise StandardizedValidationError("campaign_management_views.py : At least one target leads, opportunity, account or contact is required")
            
            # Prepare campaign targets using our new service
            target_result = CampaignTargetService.prepare_campaign_targets(
                target_account_ids=target_account_ids,
                target_contact_ids=target_contact_ids,
                target_lead_ids=target_lead_ids,
                target_opportunity_ids=target_opportunity_ids
            )
            
            # Get client_id from auth
            client_id = self.get_client_id()
            campaign_data['client_id'] = client_id

            # Set owner in campaign_data
            campaign_data['owner_id'] = request.user.id

            
            # Use CampaignManager to create the campaign and activities in one step
            result = CampaignManager.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_result['target_accounts'],
                target_contacts=target_result['target_contacts'],
                target_leads=target_result['target_leads'],
                target_opportunities=target_result['target_opportunities']
            )

            
            # Add target preparation stats to the result
            result.update({
                'targeting_stats': target_result['stats'],
                'invalid_ids': target_result['stats']['invalid_ids']
            })
            
            return Response(result, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
 
    @action(detail=True, methods=['post'])
    def start_campaign(self, request, pk=None):
        """
        Start/activate a campaign and get initial playlist
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only start your own campaigns")
        
        try:
            result = CampaignManager.start_campaign(campaign)
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def playlist(self, request, pk=None):
        """
        Get the current playlist of activities for a campaign
        
        Query params:
        - limit: Number of activities to return (default: 20)
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only view your own campaigns")
        
        limit = int(request.query_params.get('limit', DEFAULT_PLAYLIST_LIMIT))
        
        try:
            result = CampaignManager.get_campaign_playlist(campaign, limit=limit)
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """
        Get comprehensive campaign summary
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only view your own campaigns")
        
        try:
            result = CampaignManager.get_campaign_summary(campaign)
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """
        Pause a campaign
        
        Payload:
        {
            "pause_until": "2025-02-01"  # Optional
        }
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only pause your own campaigns")
        
        pause_until = request.data.get('pause_until', None)
        if pause_until:
            from datetime import datetime
            pause_until = datetime.strptime(pause_until, '%Y-%m-%d').date()
        
        try:
            result = CampaignManager.pause_campaign(campaign, pause_until=pause_until)
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def resume_campaign(self, request, pk=None):
        """
        Resume a paused campaign
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only resume your own campaigns")
        
        try:
            result = CampaignManager.resume_campaign(campaign)
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def contacts_with_responses(self, request, pk=None):
        """
        Get all contacts in campaign with email/LinkedIn activities that might have responses
        """
        campaign = self.get_object()
        
        # Validate ownership
        if campaign.owner != request.user:
            raise StandardizedValidationError("You can only view your own campaigns")
        
        try:
            result = CampaignManager.get_campaign_contacts_with_responses(campaign)
            
            # Format the response for frontend
            formatted_result = []
            for item in result:
                contact = item['contact']
                account = item['account']
                
                formatted_result.append({
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'contact_email': contact.email,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities': item['activities']
                })
            
            return Response({
                'success': True,
                'contacts': formatted_result
            })
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def account_campaigns(self, request):
        """
        Get all campaigns that the specified account is a target of
        
        Query params:
        - account_id: ID of the account to get campaigns for
        """
        account_id = request.query_params.get('account_id')
        
        if not account_id:
            return Response(
                {'success': False, 'error': 'Account ID is required'},
                status=status.HTTP_400_BAD_REQUEST
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
            
            return Response({
                'success': True,
                'account_id': account.id,
                'account_name': account.company_name,
                'campaigns': campaigns_data
            })
        except Account.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
        campaign = self.get_object()
        
        # Validate ownership or permissions
        if campaign.owner != request.user and not request.user.has_perm('campaign.change_campaign'):
            raise StandardizedValidationError("You don't have permission to modify this campaign")
        
        account_id = request.data.get('account_id')
        notes = request.data.get('notes')
        
        if not account_id:
            return Response(
                {'success': False, 'error': 'Account ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.accounts.models import Account
            account = Account.objects.get(id=account_id)
            
            # Validate client scope
            self.validate_client_id(account)
            
            result = CampaignManager.remove_account_from_campaign(
                campaign=campaign,
                account=account,
                notes=notes
            )
            
            return Response(result)
        except Account.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
        campaign = self.get_object()
        
        # Validate ownership or permissions
        if campaign.owner != request.user and not request.user.has_perm('campaign.change_campaign'):
            raise StandardizedValidationError("You don't have permission to modify this campaign")
        
        contact_id = request.data.get('contact_id')
        notes = request.data.get('notes')
        
        if not contact_id:
            return Response(
                {'success': False, 'error': 'Contact ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            
            # Validate client scope
            self.validate_client_id(contact)
            
            result = CampaignManager.remove_contact_from_campaign(
                campaign=campaign,
                contact=contact,
                notes=notes
            )
            
            return Response(result)
        except Contact.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Contact not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """
        Get all activities for a campaign with optional status filtering
        
        Query params:
        - status: Comma-separated list of activity statuses to filter by
        """
        campaign = self.get_object()
        
        # Validate ownership or permissions
        if campaign.owner != request.user and not request.user.has_perm('campaign.view_campaign'):
            raise StandardizedValidationError("You don't have permission to view this campaign")
        
        # Parse status filter
        status_filter = None
        status_param = request.query_params.get('status')
        if status_param:
            status_filter = status_param.split(',')
        
        try:
            result = CampaignManager.get_campaign_activities(
                campaign=campaign,
                status_filter=status_filter
            )
            
            return Response(result)
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def account_activities(self, request, pk=None):
        """
        Get all activities for a specific account in a campaign
        
        Query params:
        - account_id: ID of the account to get activities for
        - status: Comma-separated list of activity statuses to filter by
        """
        campaign = self.get_object()
        
        # Validate ownership or permissions
        if campaign.owner != request.user and not request.user.has_perm('campaign.view_campaign'):
            raise StandardizedValidationError("You don't have permission to view this campaign")
        
        # Get account ID
        account_id = request.query_params.get('account_id')
        if not account_id:
            return Response(
                {'success': False, 'error': 'Account ID is required'},
                status=status.HTTP_400_BAD_REQUEST
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
            
            result = CampaignManager.get_account_activities_in_campaign(
                campaign=campaign,
                account=account,
                status_filter=status_filter
            )
            
            return Response(result)
        except Account.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def contact_activities(self, request, pk=None):
        """
        Get all activities for a specific contact in a campaign
        
        Query params:
        - contact_id: ID of the contact to get activities for
        - status: Comma-separated list of activity statuses to filter by
        """
        campaign = self.get_object()
        
        # Validate ownership or permissions
        if campaign.owner != request.user and not request.user.has_perm('campaign.view_campaign'):
            raise StandardizedValidationError("You don't have permission to view this campaign")
        
        # Get contact ID
        contact_id = request.query_params.get('contact_id')
        if not contact_id:
            return Response(
                {'success': False, 'error': 'Contact ID is required'},
                status=status.HTTP_400_BAD_REQUEST
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
            
            result = CampaignManager.get_contact_activities_in_campaign(
                campaign=campaign,
                contact=contact,
                status_filter=status_filter
            )
            
            return Response(result)
        except Contact.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Contact not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class ActivityResultViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ViewSet):
    """
    ViewSet for handling activity results and completion
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
                raise StandardizedValidationError("You can only complete your own activities")
            
            # Get result data
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            if not result:
                raise StandardizedValidationError("Result is required")
            
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
            
            # Process the result
            result_info = CampaignManager.complete_activity(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
            return Response(result_info)
            
        except Activity.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
                raise StandardizedValidationError("You can only add responses to your own activities")
            
            # Validate activity type
            if activity.activity_type not in [Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN]:
                raise StandardizedValidationError("Can only add responses to email/LinkedIn activities")
            
            # Get result data
            result = request.data.get('result')
            notes = request.data.get('notes', '')
            
            # Prepare kwargs
            kwargs = {}
            if request.data.get('meeting_date'):
                kwargs['meeting_date'] = datetime.strptime(
                    request.data.get('meeting_date'), '%Y-%m-%d'
                ).date()
            
            # Process the response
            result_info = CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
            return Response(result_info)
            
        except Activity.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Activity not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
        campaign = self.get_object()
        
        # Verify this is a non-sequence campaign
        if campaign.sequence_type:
            return Response({
                'success': False,
                'error': 'This endpoint is only for campaigns without sequences'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate required fields
        contact_id = request.data.get('contact_id')
        activity_type = request.data.get('activity_type')
        result = request.data.get('result')
        
        if not all([contact_id, activity_type, result]):
            return Response({
                'success': False,
                'error': 'contact_id, activity_type, and result are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get the contact
            from apps.accounts.models import Contact
            contact = Contact.objects.get(id=contact_id)
            
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
                return Response({
                    'success': False,
                    'error': 'Contact not found in campaign targets'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Use current datetime for the activity
            now = timezone.now()
            
            # Transaction to ensure consistency
            with transaction.atomic():
                # Create activity
                activity = Activity.objects.create(
                    title=f"{Activity.ActivityType(activity_type).label} with {contact.first_name} {contact.last_name}",
                    activity_type=activity_type,
                    description=request.data.get('notes', ''),
                    account=contact.account,
                    owner=request.user,
                    status=Activity.Status.COMPLETED,
                    scheduled_start=now,
                    completed_at=now,
                    outcome_notes=request.data.get('notes', ''),
                    client_id=campaign.client_id
                )
                
                # Add contact relationship
                activity.contacts.add(contact)
                
                # Create campaign relationship
                ActivityCampaign.objects.create(
                    activity=activity,
                    campaign=campaign,
                    campaign_target=target,
                    client_id=campaign.client_id
                )
                
                # Add sequence info for consistent tracking (with manual source type)
                ActivitySequence.objects.create(
                    activity=activity,
                    source_type=ActivitySequence.SourceType.MANUAL,
                    sequence_position=1,  # Always position 1 for manual activities
                    min_delay_days=0,
                    client_id=campaign.client_id
                )
                
                # Process the result
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
                
                # Process the result
                from apps.campaign.services.campaign_result_service import CampaignResultService
                result_info = CampaignResultService.process_activity_result(
                    activity=activity,
                    result=result,
                    notes=request.data.get('notes', ''),
                    **kwargs
                )
            
            # Get updated playlist
            updated_playlist = self.get_campaign_playlist(campaign, limit=10)
            
            return Response({
                'success': True,
                'activity_id': activity.id,
                'result': result_info,
                'updated_playlist': updated_playlist
            })
            
        except Contact.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Contact not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)