# apps/campaign/views/campaign_management_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from datetime import datetime
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.apps_shared_methods import BaseAPIView
from apps.campaign.models import Campaign
from apps.campaign.serializers import CampaignSerializer
from apps.campaign.services.campaign_manager import CampaignManager
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.activities.models import Activity
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
            "target_accounts": [1, 2, 3],
            "target_contacts": [1, 2, 3]  # Optional
        }
        """
        try:
            campaign_data = request.data.get('campaign', {})
            target_accounts = request.data.get('target_accounts', [])
            target_contacts = request.data.get('target_contacts', None)
            
            # Validation
            if not campaign_data.get('name'):
                raise StandardizedValidationError("Campaign name is required")
            
            if not target_accounts:
                raise StandardizedValidationError("At least one target account is required")
            
            # Set owner
            campaign_data['owner'] = request.user
            campaign_data['client_id'] = self.get_client_id()
            
            # Create campaign with activities
            result = CampaignManager.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_accounts,
                target_contacts=target_contacts
            )
            
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