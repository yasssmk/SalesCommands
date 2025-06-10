# apps/campaign/services/campaign_manager.py
from typing import Dict, List, Optional
from datetime import date
from django.utils import timezone
from django.db import transaction
from apps.campaign.models import Campaign, CampaignTarget
from apps.activities.models import Activity
from apps.accounts.models import Contact, Account
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
            # Ensure client_id is preserved if provided in campaign_data
            client_id = campaign_data.get('client_id')

            if not client_id:
                raise ValueError("campaign_manager.py: client_id is required when creating a new record")
            
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
        # Check if already started
        if campaign.status == 'ACTIVE':
            return {'error': 'Campaign already started'}
        
        # Mark campaign as started
        campaign.status = 'ACTIVE'
        campaign.started_at = timezone.now()
        campaign.save()
        
        # Get the initial active activities
        playlist_data = CampaignQueueService.get_active_activities_for_campaign(campaign, limit=20)
        
        # Make sure activities are serialized to dictionaries, not model instances
        if 'ready_activities' in playlist_data:
            # Replace activity instances with simple dictionary representations
            ready_activities = []
            for activity in playlist_data['ready_activities']:
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
                # Transform Activity objects into dictionaries - contacts and sequence_info are now prefetched
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
        
        # Get client_id from the campaign
        client_id = campaign.client_id
        
        # Create account targets
        if target_accounts:
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
        
        # Create contact targets
        if target_contacts:
            for contact_id in target_contacts:
                try:
                    contact = Contact.objects.get(id=contact_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(campaign=campaign, contact=contact).exists():
                        # Create new target with client_id
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
                        # Create new target with client_id
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
                        # Create new target with client_id
                        CampaignTarget.objects.create(
                            campaign=campaign,
                            target_opportunity=opportunity,
                            client_id=client_id  
                        )
                        targets_created += 1
                            
                except Opportunity.DoesNotExist:
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
                campaign_target.update_status(CampaignTarget.Status.STOPPED)
            
            return {
                'success': True,
                'action': 'account_removed',
                'message': f'Account removed from campaign - {activities_count} activities cancelled',
                'activities_cancelled': activities_count
            }
        
    @classmethod
    def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Dict:
        """
        Get all activities for a campaign with optional status filtering
        OPTIMIZED: Prefetch all relations needed for formatting
        """
        # Build query with OPTIMIZED prefetching
        activities_query = Activity.objects.filter(
            campaign_info__campaign=campaign
        ).select_related(
            'account',                        # For activity formatting
            'campaign_info__campaign_target', # For campaign relationship
            'sequence_info'                   # For sequence information
        ).prefetch_related(
            'contacts'                        # CRITICAL: For formatting without N+1
        )
        
        # Apply status filter if provided
        if status_filter:
            activities_query = activities_query.filter(status__in=status_filter)
        
        # Execute query with optimizations
        activities = activities_query.order_by('sequence_info__sequence_position', 'scheduled_start')
        
        # Count by status using already fetched data when possible
        status_counts = {}
        for status_choice in Activity.Status.choices:
            status_code = status_choice[0]
            status_counts[status_code] = activities_query.filter(status=status_code).count()
        
        # Format activities - NO additional queries thanks to prefetching
        activities_data = cls._format_activities_for_response(activities)
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'total_activities': activities.count(),
            'status_counts': status_counts,
            'activities': activities_data
        }

    @classmethod
    def get_account_activities_in_campaign(cls, campaign: Campaign, account: Account, 
                                        status_filter: List[str] = None) -> Dict:
        """
        Get all activities for a specific account in a campaign
        OPTIMIZED: Prefetch all relations needed for formatting
        """
        # Build query with OPTIMIZED prefetching
        activities_query = Activity.objects.filter(
            campaign_info__campaign=campaign,
            account=account
        ).select_related(
            'account',                        # Already filtered by account, but needed for formatting
            'campaign_info__campaign_target', 
            'sequence_info'                   
        ).prefetch_related(
            'contacts'                        # CRITICAL: Prevent N+1 in formatting
        )
        
        # Apply status filter if provided
        if status_filter:
            activities_query = activities_query.filter(status__in=status_filter)
        
        # Execute query
        activities = activities_query.order_by('sequence_info__sequence_position', 'scheduled_start')
        
        # Count by status
        status_counts = {}
        for status_choice in Activity.Status.choices:
            status_code = status_choice[0]
            status_counts[status_code] = activities_query.filter(status=status_code).count()
        
        # Format activities - NO additional queries thanks to prefetching
        activities_data = cls._format_activities_for_response(activities)
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'account_id': account.id,
            'account_name': account.company_name,
            'total_activities': activities.count(),
            'status_counts': status_counts,
            'activities': activities_data
        }

    @classmethod
    def get_contact_activities_in_campaign(cls, campaign: Campaign, contact: Contact, 
                                        status_filter: List[str] = None) -> Dict:
        """
        Get all activities for a specific contact in a campaign
        OPTIMIZED: Prefetch all relations needed for formatting
        """
        # Build query with OPTIMIZED prefetching
        activities_query = Activity.objects.filter(
            campaign_info__campaign=campaign,
            contacts=contact
        ).select_related(
            'account',                        
            'campaign_info__campaign_target', 
            'sequence_info'                   
        ).prefetch_related(
            'contacts'                        # CRITICAL: Prevent N+1 in formatting
        )
        
        # Apply status filter if provided
        if status_filter:
            activities_query = activities_query.filter(status__in=status_filter)
        
        # Execute query
        activities = activities_query.order_by('sequence_info__sequence_position', 'scheduled_start')
        
        # Count by status
        status_counts = {}
        for status_choice in Activity.Status.choices:
            status_code = status_choice[0]
            status_counts[status_code] = activities_query.filter(status=status_code).count()
        
        # Format activities - NO additional queries thanks to prefetching
        activities_data = cls._format_activities_for_response(activities)
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'contact_id': contact.id,
            'contact_name': f"{contact.first_name} {contact.last_name}",
            'account_id': contact.account_id,
            'account_name': getattr(contact.account, 'company_name', 'Unknown'),
            'total_activities': activities.count(),
            'status_counts': status_counts,
            'activities': activities_data
        }

    @classmethod
    def _format_activities_for_response(cls, activities):
        """
        Format activities for API response
        
        Args:
            activities: QuerySet or list of Activity objects
                    MUST have prefetched 'contacts' and select_related 'account', 'sequence_info'
        
        Returns:
            List of formatted activity dictionaries
            
        Note:
            This method expects optimized activities with prefetched relations.
            Calling methods MUST ensure proper prefetching to avoid N+1 queries.
        """
        activities_data = []
        
        for activity in activities:
            # Format contacts - OPTIMIZED: Use prefetched contacts (no additional DB query)
            contacts_data = []
            
            try:
                # Access prefetched contacts - if not prefetched, this could cause N+1
                prefetched_contacts = activity.contacts.all()
                
                for contact in prefetched_contacts:
                    contacts_data.append({
                        'id': contact.id,
                        'name': f"{contact.first_name} {contact.last_name}",
                        'email': contact.email,
                        'phone': getattr(contact, 'phone', None)
                    })
                    
            except Exception:
                # Fallback if contacts not properly prefetched
                # In production, this should log a warning
                contacts_data = [{'id': None, 'name': 'Contacts not loaded', 'email': None, 'phone': None}]
            
            # Format activity data - account should be select_related from calling method
            activity_data = {
                'id': activity.id,
                'title': activity.title,
                'activity_type': activity.activity_type,
                'activity_type_display': activity.get_activity_type_display(),
                'status': activity.status,
                'status_display': activity.get_status_display(),
                'scheduled_start': activity.scheduled_start,
                'completed_at': activity.completed_at,
                'account_id': activity.account_id,
                'account_name': getattr(activity.account, 'company_name', 'Unknown'),
                'contacts': contacts_data,
            }
            
            # Add sequence info if available - should be select_related from calling method
            sequence_info = getattr(activity, 'sequence_info', None)
            if sequence_info:
                activity_data['sequence_info'] = {
                    'position': sequence_info.sequence_position,
                    'call_attempts': sequence_info.call_attempts,
                    'min_delay_days': sequence_info.min_delay_days
                }
            
            activities_data.append(activity_data)
        
        return activities_data