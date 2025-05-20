# apps/campaign/services/campaign_manager.py
from typing import Dict, List, Optional
from datetime import date
from django.utils import timezone
from django.db import transaction
from apps.campaign.models import Campaign, CampaignTarget
from apps.activities.models import Activity
from .campaign_activity_service import CampaignActivityService
from .campaign_queue_service import CampaignQueueService
from .campaign_result_service import CampaignResultService
from apps.campaign.config.variables import DEFAULT_PLAYLIST_LIMIT, DEFAULT_SUMMARY_ACTIVITIES


class CampaignManager:
    """
    Main service for managing campaigns - provides the primary interface
    for all campaign operations
    """
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, target_accounts: List[int],
                                    target_contacts: List[int] = None) -> Dict:
        """
        Create a new campaign and generate all activities with optimized queries
        
        Args:
            campaign_data: Dictionary with campaign fields (name, description, etc.)
            target_accounts: List of account IDs to target
            target_contacts: Optional list of specific contact IDs
            
        Returns:
            Dictionary with campaign creation results
        """
        with transaction.atomic():
            # Ensure client_id is preserved if provided in campaign_data
            client_id = campaign_data.get('client_id')
            print(f"Creating campaign with client_id: {client_id}")

            if not client_id:
                raise ValueError("client_id is required when creating a new record")
            
            # Create the campaign
            campaign = Campaign.objects.create(**campaign_data)
            
            print('troue ba dour')
            # Create campaign targets
            targets_created = cls._create_campaign_targets(
                campaign, target_accounts, target_contacts
            )
            print('troue ba dour2')
            # Generate activities for all targets
            activity_result = CampaignActivityService.create_activities_for_campaign(
                campaign, target_contacts=target_contacts
            )
            print('troue ba dour3')
            
            return {
                'success': True,
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'targets_created': targets_created,
                'activities_created': activity_result['total_activities_created'],
                'skipped_contacts': activity_result['skipped_contacts'],
            }
    
    @classmethod
    def start_campaign(cls, campaign: Campaign) -> Dict:
        """
        Start/activate a campaign - ONE TIME ACTION
        - Mark campaign as active
        - Initialize campaign state
        - Return initial playlist
        """
        # Check if already started
        if campaign.status == 'ACTIVE':
            return {'error': 'Campaign already started'}
        
        # Mark campaign as started
        campaign.status = 'ACTIVE'
        campaign.started_at = timezone.now()
        campaign.save()
        
        # Get the initial active activities
        return CampaignQueueService.get_active_activities_for_campaign(campaign, limit=20)
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None) -> Dict:
        """
        Get current playlist with configurable limit
        """
        if limit is None:
            limit = DEFAULT_PLAYLIST_LIMIT
            
        return CampaignQueueService.get_active_activities_for_campaign(campaign, limit)
    
    @classmethod
    def complete_activity(cls, activity: Activity, result: str, 
                         notes: str = None, **kwargs) -> Dict:
        """
        Complete an activity and process the result
        
        Args:
            activity: The activity to complete
            result: The result of the activity
            notes: Optional notes
            **kwargs: Additional result data (callback_date, meeting_date, etc.)
            
        Returns:
            Dictionary with result processing information
        """
        # Process the result
        result_info = CampaignResultService.process_activity_result(
            activity, result, notes, **kwargs
        )
        
        # Get updated campaign playlist
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        if campaign:
            updated_playlist = cls.get_campaign_playlist(campaign, limit=10)
            result_info['updated_playlist'] = updated_playlist['ready_activities']
        
        
        return result_info
    
    @classmethod
    def get_campaign_summary(cls, campaign: Campaign) -> Dict:
        """
        Get a comprehensive summary of campaign progress
        
        Args:
            campaign: The campaign to summarize
            
        Returns:
            Dictionary with campaign summary data
        """
        # Get all activities for this campaign
        all_activities = Activity.objects.filter(campaign_info__campaign=campaign)
        
        # Status counts
        status_counts = {
            'planned': all_activities.filter(status=Activity.Status.PLANNED).count(),
            'completed': all_activities.filter(status=Activity.Status.COMPLETED).count(),
            'cancelled': all_activities.filter(status=Activity.Status.CANCELLED).count(),
        }
        
        # Activity type breakdown
        type_counts = {}
        for activity_type in Activity.ActivityType:
            type_counts[activity_type.value] = all_activities.filter(
                activity_type=activity_type.value
            ).count()
        
        # Sequence outcomes
        outcomes = {}
        completed_activities = all_activities.filter(
            status=Activity.Status.COMPLETED,
            sequence_info__sequence_outcome__isnull=False
        )
        
        for activity in completed_activities:
            outcome = activity.sequence_info.sequence_outcome
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        # Progress calculation
        total_activities = sum(status_counts.values())
        progress_percentage = (status_counts['completed'] / total_activities * 100) if total_activities > 0 else 0
        
        # Campaign targets summary
        targets = campaign.targets.all()
        target_summary = {
            'total_targets': targets.count(),
            'targets_by_status': {}
        }
        
        for target in targets:
            status = target.status
            target_summary['targets_by_status'][status] = target_summary['targets_by_status'].get(status, 0) + 1
        
        # Get current active activities
        active_info = CampaignQueueService.get_active_activities_for_campaign(campaign, limit=5)
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'start_date': campaign.start_date,
            'end_date': campaign.end_date,
            'progress_percentage': round(progress_percentage, 1),
            'status_counts': status_counts,
            'type_counts': type_counts,
            'outcomes': outcomes,
            'target_summary': target_summary,
            'active_activities_count': active_info['total_ready'],
            'next_activities': [
                {
                    'id': act.id,
                    'title': act.title,
                    'type': act.activity_type,
                    'account': act.account.company_name,
                    'contacts': [c.full_name for c in act.contacts.all()]
                } for act in active_info['ready_activities'][:5]
            ]
        }
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Dict:
        """
        Pause a campaign (pause all active activities)
        
        Args:
            campaign: The campaign to pause
            pause_until: Optional date to pause until
            
        Returns:
            Dictionary with pause result
        """
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
        
        return {
            'success': True,
            'action': 'campaign_paused',
            'message': f'Campaign paused. {activities_paused} activities affected',
            'pause_until': pause_until
        }
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign) -> Dict:
        """
        Resume a paused campaign
        
        Args:
            campaign: The campaign to resume
            
        Returns:
            Dictionary with resume result
        """
        # Clear pause dates from all activities
        activities_resumed = 0
        
        for activity in Activity.objects.filter(campaign_info__campaign=campaign):
            if hasattr(activity, 'sequence_info') and activity.sequence_info.sequence_paused_until:
                activity.sequence_info.sequence_paused_until = None
                activity.sequence_info.save()
                activities_resumed += 1
        
        # Get updated playlist
        updated_playlist = cls.get_campaign_playlist(campaign)
        
        return {
            'success': True,
            'action': 'campaign_resumed',
            'message': f'Campaign resumed. {activities_resumed} activities available',
            'active_activities': updated_playlist['total_ready']
        }
    
    @classmethod
    def _create_campaign_targets(cls, campaign: Campaign, target_accounts: List[int],
                            target_contacts: List[int] = None) -> int:
        """
        Create campaign targets for the specified accounts/contacts
        """
        from apps.accounts.models import Account
        
        targets_created = 0
        
        # Get client_id from the campaign
        client_id = campaign.client_id
        
        for account_id in target_accounts:
            try:
                account = Account.objects.get(id=account_id)
                
                # Check if target already exists
                if not CampaignTarget.objects.filter(campaign=campaign, account=account).exists():
                    # Create new target with client_id
                    CampaignTarget.objects.create(
                        campaign=campaign,
                        account=account,
                        client_id=client_id  
                    )
                    targets_created += 1
                        
            except Account.DoesNotExist:
                continue
        
        return targets_created
            
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