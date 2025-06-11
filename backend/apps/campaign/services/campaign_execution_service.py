# apps/campaign/services/campaign_execution_service.py
from typing import Dict, List, Optional
from datetime import date
from django.db import transaction
from rest_framework.response import Response
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity
from .campaign_queue_service import CampaignQueueService
from apps.campaign.config.variables import DEFAULT_PLAYLIST_LIMIT
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages


class CampaignExecutionService:
    """
    Service specialized in campaign execution and operational management
    Handles playlists, contact/account management, and execution workflows
    Now returns standardized Response objects
    """
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, current_activity_type: str = None) -> Response:
        """
        Get current playlist with configurable limit
        Works for both sequence and non-sequence campaigns
        
        Args:
            campaign: The campaign to get queue for
            limit: Number of items to return (default: campaign config or 20)
            current_activity_type: Optional current activity type for batching similar activities
            
        Returns:
            Response: Standardized response with queue data (activities or contacts) and queue information
        """
        try:
            if limit is None:
                limit = DEFAULT_PLAYLIST_LIMIT
            
            # Check if this is a campaign with or without sequence
            if campaign.sequence_type:
                # For sequence campaigns, get activity queue with serialization enabled
                queue_response = CampaignQueueService.get_active_activities_for_campaign(
                    campaign, 
                    limit,
                    prefetch_relations=True,  # Enable serialization for API response
                    current_activity_type=current_activity_type
                )
                
                # Extract data from the standardized Response to verify and enhance if needed
                if hasattr(queue_response, 'data') and 'data' in queue_response.data:
                    response_data = queue_response.data['data']
                    items = response_data.get('items', [])
                    
                    # Return the response directly with any additional execution-specific data
                    return CampaignResponseBuilder.campaign_playlist(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        items=items,
                        queue_type='activity',
                        is_sequence=True,
                        total_items=response_data.get('total_items', len(items)),
                        additional_data={
                            'total_pending': response_data.get('total_pending', 0),
                            'queue_info': response_data.get('queue_info', {}),
                            'activity_types_breakdown': response_data.get('activity_types_breakdown', {}),
                            'execution_context': 'playlist_request'
                        }
                    )
                else:
                    # If response format is unexpected, raise error
                    raise StandardizedValidationError(
                        CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
                    )
                
            else:
                # For non-sequence campaigns, get contact queue
                contact_response = CampaignQueueService.get_prioritized_contacts_for_campaign(
                    campaign,
                    limit
                )
                
                # Extract data from the standardized Response
                if hasattr(contact_response, 'data') and 'data' in contact_response.data:
                    response_data = contact_response.data['data']
                    items = response_data.get('items', [])
                    
                    # Return enhanced contact playlist response
                    return CampaignResponseBuilder.campaign_playlist(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        items=items,
                        queue_type='contact',
                        is_sequence=False,
                        total_items=response_data.get('total_items', len(items)),
                        additional_data={
                            'total_pending': response_data.get('total_pending', 0),
                            'skipped_contacts': response_data.get('skipped_contacts', []),
                            'counts': response_data.get('counts', {}),
                            'execution_context': 'contact_queue_request'
                        }
                    )
                else:
                    # If response format is unexpected, raise error
                    raise StandardizedValidationError(
                        CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
                    )
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.PLAYLIST_EMPTY
            )
    
    @classmethod
    def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, notes: str = None) -> Response:
        """
        Remove a contact from a campaign by canceling all their activities
        
        Args:
            campaign: The campaign to remove the contact from
            contact: The contact to remove
            notes: Optional notes about the removal reason
            
        Returns:
            Response: Standardized response with removal information
        """
        try:
            with transaction.atomic():
                # Find all planned activities for this contact in this campaign
                activities = Activity.objects.filter(
                    campaign_info__campaign=campaign,
                    contacts=contact,
                    status=Activity.Status.PLANNED
                )
                
                # Get count before cancellation
                activities_count = activities.count()
                
                # Cancel all activities
                activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes=f"Manually removed from campaign: {notes}" if notes else "Manually removed from campaign"
                )
                
                # Update campaign target status if this is a direct contact target
                campaign_target = CampaignTarget.objects.filter(
                    campaign=campaign,
                    contact=contact
                ).first()
                
                if campaign_target:
                    campaign_target.status = CampaignTarget.Status.STOPPED
                    campaign_target.save()
                
                # Prepare response data
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'activities_cancelled': activities_count,
                    'action': 'contact_removed'
                }
                
                meta = {
                    'operation': 'contact_removal',
                    'activities_affected': activities_count,
                    'target_updated': bool(campaign_target)
                }
                
                return StandardizedSuccessResponse.success(
                    message=CampaignSuccessMessages.CONTACT_REMOVED,
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_CONTACT_MAPPING_FAILED
            )
        
    @classmethod
    def remove_account_from_campaign(cls, campaign: Campaign, account: Account, notes: str = None) -> Response:
        """
        Remove an account from a campaign by canceling all related activities
        
        Args:
            campaign: The campaign to remove the account from
            account: The account to remove
            notes: Optional notes about the removal reason
            
        Returns:
            Response: Standardized response with removal information
        """
        try:
            with transaction.atomic():
                # Find all planned activities for this account in this campaign
                activities = Activity.objects.filter(
                    campaign_info__campaign=campaign,
                    account=account,
                    status=Activity.Status.PLANNED
                )
                
                # Get count before cancellation
                activities_count = activities.count()
                
                # Cancel all activities
                activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes=f"Account removed from campaign: {notes}" if notes else "Account removed from campaign"
                )
                
                # Update campaign target status
                campaign_target = CampaignTarget.objects.filter(
                    campaign=campaign,
                    account=account
                ).first()
                
                if campaign_target:
                    campaign_target.status = CampaignTarget.Status.STOPPED
                    campaign_target.save()
                
                # Prepare response data
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities_cancelled': activities_count,
                    'action': 'account_removed'
                }
                
                meta = {
                    'operation': 'account_removal',
                    'activities_affected': activities_count,
                    'target_updated': bool(campaign_target)
                }
                
                return StandardizedSuccessResponse.success(
                    message=CampaignSuccessMessages.ACCOUNT_REMOVED,
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
            )
    
    @classmethod
    def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> Response:
        """
        Get all contacts in campaign with their email/LinkedIn activities that might have responses
        
        Args:
            campaign: The campaign to check
            
        Returns:
            Response: Standardized response with contacts and their email/LinkedIn activities
        """
        try:
            # Get all completed email/LinkedIn activities for this campaign
            email_linkedin_activities = Activity.objects.filter(
                campaign_info__campaign=campaign,
                activity_type__in=[Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN],
                status=Activity.Status.COMPLETED
            ).select_related('account').prefetch_related('contacts')
            
            contacts_with_activities = {}
            
            for activity in email_linkedin_activities:
                for contact in activity.contacts.all():
                    contact_key = contact.id
                    
                    if contact_key not in contacts_with_activities:
                        contacts_with_activities[contact_key] = {
                            'contact': contact,
                            'account': activity.account,
                            'activities': []
                        }
                    
                    contacts_with_activities[contact_key]['activities'].append({
                        'id': activity.id,
                        'type': activity.activity_type,
                        'title': activity.title,
                        'completed_at': activity.completed_at,
                        'outcome_notes': activity.outcome_notes,
                        'can_add_response': True  # All completed email/LinkedIn can have responses added
                    })
            
            # Format for standardized response
            formatted_contacts = []
            for item in contacts_with_activities.values():
                contact = item['contact']
                account = item['account']
                
                formatted_contacts.append({
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'contact_email': contact.email,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities': item['activities']
                })
            
            data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'contacts': formatted_contacts
            }
            
            meta = {
                'operation': 'contacts_with_responses',
                'contacts_count': len(formatted_contacts),
                'total_activities_processed': email_linkedin_activities.count()
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Retrieved {len(formatted_contacts)} contacts with potential responses",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    @classmethod
    def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
                                      activity_type: str, result: str, notes: str = None, 
                                      user=None, **kwargs) -> Response:
        """
        Add a manual activity for a contact in a non-sequence campaign
        
        Args:
            campaign: The campaign (must be non-sequence)
            contact: The contact
            activity_type: Type of activity (CALL, EMAIL, etc.)
            result: Activity result
            notes: Optional notes
            user: User creating the activity
            **kwargs: Additional data (meeting_date, callback_date, etc.)
            
        Returns:
            Response: Standardized response with activity creation and result processing information
        """
        try:
            # Verify this is a non-sequence campaign
            if campaign.sequence_type:
                raise StandardizedValidationError(
                    CampaignErrorMessages.CAMPAIGN_NO_SEQUENCE_TYPE
                )
            
            # Validate activity type
            valid_types = [choice[0] for choice in Activity.ActivityType.choices]
            if activity_type not in valid_types:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=activity_type)
                )
            
            # Get the campaign target for this contact
            target = None
            for t in campaign.targets.all():
                if (t.contact_id == contact.id or 
                    (t.account_id == contact.account_id) or
                    (t.lead and t.lead.account_id == contact.account_id) or
                    (t.target_opportunity and t.target_opportunity.account_id == contact.account_id)):
                    target = t
                    break
            
            if not target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            from django.utils import timezone
            from apps.activities.models import ActivityCampaign, ActivitySequence
            
            # Create activity in transaction
            with transaction.atomic():
                # Create activity
                activity = Activity.objects.create(
                    title=f"{Activity.ActivityType(activity_type).label} with {contact.first_name} {contact.last_name}",
                    activity_type=activity_type,
                    description=notes or '',
                    account=contact.account,
                    owner=user,
                    status=Activity.Status.COMPLETED,
                    scheduled_start=timezone.now(),
                    completed_at=timezone.now(),
                    outcome_notes=notes or '',
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
                from .campaign_result_service import CampaignResultService
                result_response = CampaignResultService.process_activity_result(
                    activity=activity,
                    result=result,
                    notes=notes,
                    **kwargs
                )
                
                # Extract result info from the standardized response
                result_info = {}
                if hasattr(result_response, 'data') and 'data' in result_response.data:
                    result_info = result_response.data['data']
            
            # Prepare response data
            data = {
                'activity_id': activity.id,
                'campaign_id': campaign.id,
                'contact_id': contact.id,
                'activity_type': activity_type,
                'result': result_info
            }
            
            meta = {
                'operation': 'manual_activity_creation',
                'activity_type': activity_type,
                'result_processed': True
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Manual {activity_type.lower()} activity added and processed successfully",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(current_state=f"creation failed: {str(e)}")
            )