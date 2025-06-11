# apps/campaign/services/campaign_creation_service.py
from typing import Dict, List, Optional
from datetime import date
from django.utils import timezone
from django.db import transaction
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact, Account
from .campaign_activity_service import CampaignActivityService
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from rest_framework.response import Response
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)


class CampaignCreationService:
    """
    Service specialized in campaign creation and configuration
    Handles creation, state management, and initial setup
    """
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, 
                                    target_accounts: List[int] = None,
                                    target_contacts: List[int] = None,
                                    target_leads: List[int] = None,
                                    target_opportunities: List[int] = None,
                                    targeting_stats: Dict = None) -> Response:
        """
        Create a new campaign and generate all activities with optimized queries
        
        Args:
            campaign_data: Dictionary with campaign fields (name, description, etc.)
            target_accounts: List of account IDs to target
            target_contacts: Optional list of specific contact IDs
            target_leads: Optional list of specific lead IDs
            target_opportunities: Optional list of specific opportunity IDs
            targeting_stats: Optional targeting statistics from preparation
            
        Returns:
            Response: Standardized API response with campaign creation results
        """
        try:
            with transaction.atomic():
                # Validate required client_id
                client_id = campaign_data.get('client_id')
                if not client_id:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
                
                # Create the campaign
                campaign = Campaign.objects.create(**campaign_data)
                
                # Create campaign targets
                targets_created = cls._create_campaign_targets(
                    campaign, 
                    target_accounts, 
                    target_contacts,
                    target_leads,
                    target_opportunities
                )

                # Generate activities for all targets
                activity_result = CampaignActivityService.create_activities_for_campaign(
                    campaign, target_contacts=target_contacts
                )
                
                # Use standardized response builder
                return CampaignResponseBuilder.campaign_created(
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    targets_created=targets_created,
                    activities_created=activity_result['total_activities_created'],
                    skipped_contacts=activity_result.get('skipped_contacts', []),
                    targeting_stats=targeting_stats
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors (they're already properly formatted)
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def start_campaign(cls, campaign: Campaign) -> Response:
        """
        Start/activate a campaign - ONE TIME ACTION
        - Mark campaign as active
        - Initialize campaign state
        - Return initial playlist
        """
        try:
            # Validate campaign can be started
            if campaign.status == 'ACTIVE':
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_ALREADY_STARTED)
            
            if campaign.status in ['COMPLETED', 'CANCELLED']:
                raise StandardizedValidationError(
                    CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=campaign.status)
                )
            
            # Mark campaign as started
            campaign.status = 'ACTIVE'
            campaign.started_at = timezone.now()
            campaign.save()
            
            # Import here to avoid circular imports
            from .campaign_queue_service import CampaignQueueService
            
            # Get the initial active activities using standardized queue service
            playlist_response = CampaignQueueService.get_active_activities_for_campaign(
                campaign, 
                limit=20,
                prefetch_relations=True  # Enable serialization for response
            )
            
            # Extract data from the standardized Response object
            if hasattr(playlist_response, 'data') and 'data' in playlist_response.data:
                playlist_data = playlist_response.data['data']
                items = playlist_data.get('items', [])
                
                # Create enhanced response with campaign started info
                additional_data = {
                    'total_pending': playlist_data.get('total_pending', 0),
                    'queue_info': playlist_data.get('queue_info', {}),
                    'campaign_started': True,
                    'started_at': campaign.started_at.isoformat(),
                    'activity_types_breakdown': playlist_data.get('activity_types_breakdown', {})
                }
                
                return CampaignResponseBuilder.campaign_playlist(
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    items=items,
                    queue_type=playlist_data.get('queue_type', 'activity'),
                    is_sequence=playlist_data.get('is_sequence', bool(campaign.sequence_type)),
                    total_items=len(items),
                    additional_data=additional_data
                )
            else:
                # Fallback if response format is unexpected
                raise StandardizedValidationError(
                    CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
                )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"start failed: {str(e)}")
            )
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Response:
        """
        Pause a campaign (pause all active activities)
        
        Args:
            campaign: The campaign to pause
            pause_until: Optional date to pause until
            
        Returns:
            Response: Standardized API response with pause result
        """
        try:
            from apps.activities.models import Activity
            
            # Update all planned activities to set pause date
            activities_paused = 0
            
            for activity in Activity.objects.filter(
                campaign_info__campaign=campaign,
                status=Activity.Status.PLANNED
            ):
                if hasattr(activity, 'sequence_info'):
                    activity.sequence_info.sequence_paused_until = pause_until
                    activity.sequence_info.save()
                    activities_paused += 1
            
            # Update campaign status
            campaign.status = 'PAUSED'
            campaign.save()
            
            # Prepare message with pause date info
            message = CampaignSuccessMessages.CAMPAIGN_PAUSED.format(name=campaign.name)
            if pause_until:
                message += f" until {pause_until}"
            
            data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'activities_paused': activities_paused,
                'pause_until': pause_until.isoformat() if pause_until else None,
                'paused_at': timezone.now().isoformat()
            }
            
            meta = {
                'operation': 'campaign_pause',
                'activities_affected': activities_paused,
                'pause_until': pause_until.isoformat() if pause_until else None
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"pause failed: {str(e)}")
            )
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign) -> Response:
        """
        Resume a paused campaign
        
        Args:
            campaign: The campaign to resume
            
        Returns:
            Response: Standardized API response with resume result
        """
        try:
            from apps.activities.models import Activity
            
            # Clear pause dates from all activities
            activities_resumed = 0
            
            for activity in Activity.objects.filter(campaign_info__campaign=campaign):
                if hasattr(activity, 'sequence_info') and activity.sequence_info.sequence_paused_until:
                    activity.sequence_info.sequence_paused_until = None
                    activity.sequence_info.save()
                    activities_resumed += 1
            
            # Update campaign status
            campaign.status = 'ACTIVE'
            campaign.save()
            
            # Import here to avoid circular imports
            from .campaign_execution_service import CampaignExecutionService
            
            # Get updated playlist using standardized execution service
            updated_playlist_response = CampaignExecutionService.get_campaign_playlist(campaign)
            
            # Extract active activities count from the standardized Response
            active_activities_count = 0
            if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
                playlist_data = updated_playlist_response.data['data']
                items = playlist_data.get('items', [])
                active_activities_count = len(items)
            
            data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'activities_resumed': activities_resumed,
                'active_activities': active_activities_count,
                'resumed_at': timezone.now().isoformat()
            }
            
            meta = {
                'operation': 'campaign_resume',
                'activities_affected': activities_resumed,
                'active_activities_available': active_activities_count
            }
            
            return StandardizedSuccessResponse.success(
                message=CampaignSuccessMessages.CAMPAIGN_RESUMED.format(name=campaign.name),
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"resume failed: {str(e)}")
            )
    
    @classmethod
    def _create_campaign_targets(cls, campaign: Campaign, 
                                target_accounts: List[int] = None,
                                target_contacts: List[int] = None,
                                target_leads: List[int] = None,
                                target_opportunities: List[int] = None) -> int:
        """
        Create campaign targets for the specified accounts/contacts/leads/opportunities
        All targets will eventually generate activities for their associated contacts
        
        Args:
            campaign: Campaign to create targets for
            target_accounts: List of account IDs
            target_contacts: List of contact IDs
            target_leads: List of lead IDs
            target_opportunities: List of opportunity IDs
            
        Returns:
            int: Number of targets created
        """
        from apps.accounts.models import Account, Contact
        from apps.leads.models import Lead
        from apps.opportunities.models import Opportunity
        
        targets_created = 0
        client_id = campaign.client_id
        
        # Create account targets
        if target_accounts:
            for account_id in target_accounts:
                try:
                    account = Account.objects.get(id=account_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(campaign=campaign, account=account).exists():
                        CampaignTarget.objects.create(
                            campaign=campaign,
                            account=account,
                            client_id=client_id  
                        )
                        targets_created += 1
                            
                except Account.DoesNotExist:
                    continue
        
        # Create contact targets
        if target_contacts:
            for contact_id in target_contacts:
                try:
                    contact = Contact.objects.get(id=contact_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(campaign=campaign, contact=contact).exists():
                        CampaignTarget.objects.create(
                            campaign=campaign,
                            contact=contact,
                            client_id=client_id  
                        )
                        targets_created += 1
                            
                except Contact.DoesNotExist:
                    continue
        
        # Create lead targets
        if target_leads:
            for lead_id in target_leads:
                try:
                    lead = Lead.objects.get(id=lead_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(campaign=campaign, lead=lead).exists():
                        CampaignTarget.objects.create(
                            campaign=campaign,
                            lead=lead,
                            client_id=client_id  
                        )
                        targets_created += 1
                            
                except Lead.DoesNotExist:
                    continue
        
        # Create opportunity targets
        if target_opportunities:
            for opportunity_id in target_opportunities:
                try:
                    opportunity = Opportunity.objects.get(id=opportunity_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(campaign=campaign, target_opportunity=opportunity).exists():
                        CampaignTarget.objects.create(
                            campaign=campaign,
                            target_opportunity=opportunity,
                            client_id=client_id  
                        )
                        targets_created += 1
                            
                except Opportunity.DoesNotExist:
                    continue
        
        return targets_created