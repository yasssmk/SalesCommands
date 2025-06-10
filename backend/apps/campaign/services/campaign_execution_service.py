# apps/campaign/services/campaign_execution_service.py
from typing import Dict, List, Optional
from datetime import date
from django.db import transaction
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity
from .campaign_queue_service import CampaignQueueService
from apps.campaign.config.variables import DEFAULT_PLAYLIST_LIMIT
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages


class CampaignExecutionService:
    """
    Service specialized in campaign execution and operational management
    Handles playlists, contact/account management, and execution workflows
    """
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, current_activity_type: str = None) -> Dict:
        """
        Get current playlist with configurable limit
        Works for both sequence and non-sequence campaigns
        
        Args:
            campaign: The campaign to get queue for
            limit: Number of items to return (default: campaign config or 20)
            current_activity_type: Optional current activity type for batching similar activities
            
        Returns:
            Dictionary with queue data (activities or contacts) and queue information
        """
        if limit is None:
            limit = DEFAULT_PLAYLIST_LIMIT
        
        # Check if this is a campaign with or without sequence
        if campaign.sequence_type:
            # For sequence campaigns, get activity queue
            playlist_data = CampaignQueueService.get_active_activities_for_campaign(
                campaign, 
                limit,
                prefetch_relations=True,
                current_activity_type=current_activity_type
            )
            
            # Serialize activity objects for JSON response
            if 'ready_activities' in playlist_data:
                serialized_activities = []
                for activity in playlist_data['ready_activities']:
                    # Basic activity data
                    activity_data = {
                        'id': activity.id,
                        'title': activity.title,
                        'activity_type': activity.activity_type,
                        'activity_type_display': activity.get_activity_type_display(),
                        'account_id': activity.account_id,
                        'account_name': activity.account.company_name,  # Now safely accessed due to select_related
                        'scheduled_start': activity.scheduled_start,
                        'status': activity.status,
                    }
                    
                    # Add contacts - now efficiently prefetched
                    activity_data['contacts'] = [
                        {'id': c.id, 'name': c.full_name} 
                        for c in activity.contacts.all()  # No additional queries due to prefetch
                    ]
                    
                    # Add sequence info if available - also prefetched
                    if hasattr(activity, 'sequence_info') and activity.sequence_info:
                        activity_data['sequence_info'] = {
                            'position': activity.sequence_info.sequence_position,
                            'source_type': activity.sequence_info.source_type,
                            'call_attempts': activity.sequence_info.call_attempts,
                        }
                    
                    serialized_activities.append(activity_data)
                
                # Replace activities with serialized version
                playlist_data['ready_activities'] = serialized_activities
                
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'is_sequence': True,
                'queue_type': 'activity',
                'items': playlist_data.get('ready_activities', []),
                'total_items': playlist_data.get('total_ready', 0),
                'total_pending': playlist_data.get('total_pending', 0),
                'queue_info': playlist_data.get('queue_info', {}),
                'activity_types_breakdown': playlist_data.get('activity_types_breakdown', {})
            }
        else:
            # For non-sequence campaigns, get contact queue
            contact_data = CampaignQueueService.get_prioritized_contacts_for_campaign(
                campaign,
                limit
            )
            
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'is_sequence': False,
                'queue_type': 'contact',
                'items': contact_data.get('contacts', []),
                'total_items': contact_data.get('counts', {}).get('prioritized', 0),
                'total_pending': contact_data.get('counts', {}).get('total', 0),
                'skipped_contacts': contact_data.get('skipped_contacts', [])
            }
    
    @classmethod
    def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, notes: str = None) -> Dict:
        """
        Remove a contact from a campaign by canceling all their activities
        
        Args:
            campaign: The campaign to remove the contact from
            contact: The contact to remove
            notes: Optional notes about the removal reason
            
        Returns:
            Dictionary with removal information
        """
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
            
            return {
                'success': True,
                'action': 'contact_removed',
                'message': f'Contact removed from campaign - {activities_count} activities cancelled',
                'activities_cancelled': activities_count
            }
        
    @classmethod
    def remove_account_from_campaign(cls, campaign: Campaign, account: Account, notes: str = None) -> Dict:
        """
        Remove an account from a campaign by canceling all related activities
        
        Args:
            campaign: The campaign to remove the account from
            account: The account to remove
            notes: Optional notes about the removal reason
            
        Returns:
            Dictionary with removal information
        """
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
            
            return {
                'success': True,
                'action': 'account_removed',
                'message': f'Account removed from campaign - {activities_count} activities cancelled',
                'activities_cancelled': activities_count
            }
    
    @classmethod
    def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> List[Dict]:
        """
        Get all contacts in campaign with their email/LinkedIn activities that might have responses
        
        Args:
            campaign: The campaign to check
            
        Returns:
            List of contacts with their email/LinkedIn activities
        """
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
        
        return list(contacts_with_activities.values())
    
    @classmethod
    def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
                                      activity_type: str, result: str, notes: str = None, 
                                      user=None, **kwargs) -> Dict:
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
            Dictionary with activity creation and result processing information
        """
        # Verify this is a non-sequence campaign
        if campaign.sequence_type:
            raise StandardizedValidationError(
                "This operation is only for campaigns without sequences"
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
            result_info = CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
        
        return {
            'success': True,
            'activity_id': activity.id,
            'result': result_info
        }