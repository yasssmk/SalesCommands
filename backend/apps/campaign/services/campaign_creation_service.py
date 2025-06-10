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
                                    target_opportunities: List[int] = None) -> Dict:
        """
        Create a new campaign and generate all activities with optimized queries
        
        Args:
            campaign_data: Dictionary with campaign fields (name, description, etc.)
            target_accounts: List of account IDs to target
            target_contacts: Optional list of specific contact IDs
            target_leads: Optional list of specific lead IDs
            target_opportunities: Optional list of specific opportunity IDs
            
        Returns:
            Dictionary with campaign creation results
        """
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
        
        # Get the initial active activities
        playlist_data = CampaignQueueService.get_active_activities_for_campaign(campaign, limit=20)
        
        # Serialize activities for JSON response
        ready_activities = []
        for activity in playlist_data.get('ready_activities', []):
            ready_activities.append({
                'id': activity.id,
                'title': activity.title,
                'activity_type': activity.activity_type,
                'activity_type_display': activity.get_activity_type_display(),
                'account_id': activity.account_id,
                'account_name': activity.account.company_name if hasattr(activity, 'account') else None,
                'scheduled_start': activity.scheduled_start,
                'status': activity.status,
                'contacts': [
                    {'id': c.id, 'name': c.full_name} 
                    for c in activity.contacts.all()
                ] if hasattr(activity, 'contacts') else []
            })
        
        playlist_data['ready_activities'] = ready_activities
        
        return {
            'success': True,
            'campaign_id': campaign.id,
            'campaign_status': campaign.status,
            'playlist': playlist_data
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
        from apps.activities.models import Activity
        
        # Clear pause dates from all activities
        activities_resumed = 0
        
        for activity in Activity.objects.filter(campaign_info__campaign=campaign):
            if hasattr(activity, 'sequence_info') and activity.sequence_info.sequence_paused_until:
                activity.sequence_info.sequence_paused_until = None
                activity.sequence_info.save()
                activities_resumed += 1
        
        # Import here to avoid circular imports
        from .campaign_execution_service import CampaignExecutionService
        
        # Get updated playlist
        updated_playlist = CampaignExecutionService.get_campaign_playlist(campaign)
        
        return {
            'success': True,
            'action': 'campaign_resumed',
            'message': f'Campaign resumed. {activities_resumed} activities available',
            'active_activities': updated_playlist['total_items']
        }
    
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