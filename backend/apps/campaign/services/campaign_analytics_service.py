# apps/campaign/services/campaign_analytics_service.py
from typing import Dict, List, Optional
from apps.campaign.models import Campaign
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity
from .campaign_queue_service import CampaignQueueService


class CampaignAnalyticsService:
    """
    Service specialized in campaign analytics, reporting and data formatting
    Handles summaries, activity listings, and data presentation
    """
    
    @classmethod
    def get_campaign_summary(cls, campaign: Campaign) -> Dict:
        """
        Get a comprehensive summary of campaign progress
        
        Args:
            campaign: The campaign to summarize
            
        Returns:
            Dictionary with campaign summary data
        """
        # Get all activities for this campaign with optimized query
        all_activities = Activity.objects.filter(
            campaign_info__campaign=campaign
        ).select_related('account').prefetch_related('contacts')
        
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
            if hasattr(activity, 'sequence_info') and activity.sequence_info:
                outcome = activity.sequence_info.sequence_outcome
                if outcome:
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
        
        # Get current active activities (limited to avoid performance issues)
        active_info = CampaignQueueService.get_active_activities_for_campaign(campaign, limit=5)
        
        # Format next activities
        next_activities = []
        for activity in active_info.get('ready_activities', [])[:5]:
            next_activities.append({
                'id': activity.id,
                'title': activity.title,
                'type': activity.activity_type,
                'account': activity.account.company_name,
                'contacts': [c.full_name for c in activity.contacts.all()]
            })
        
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
            'active_activities_count': active_info.get('total_ready', 0),
            'next_activities': next_activities
        }
    
    @classmethod
    def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Dict:
        """
        Get all activities for a campaign with optional status filtering
        OPTIMIZED: Prefetch all relations needed for formatting
        
        Args:
            campaign: The campaign to get activities for
            status_filter: Optional list of activity status values to filter by
            
        Returns:
            Dictionary with activities and summary information
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
        
        Args:
            campaign: The campaign to get activities for
            account: The account to filter by
            status_filter: Optional list of activity status values to filter by
            
        Returns:
            Dictionary with activities and summary information
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
        
        Args:
            campaign: The campaign to get activities for
            contact: The contact to filter by
            status_filter: Optional list of activity status values to filter by
            
        Returns:
            Dictionary with activities and summary information
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
    
    @classmethod
    def get_campaign_performance_metrics(cls, campaign: Campaign) -> Dict:
        """
        Get detailed performance metrics for a campaign
        
        Args:
            campaign: The campaign to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        # Get all activities with optimized query
        activities = Activity.objects.filter(
            campaign_info__campaign=campaign
        ).select_related('sequence_info')
        
        # Calculate key metrics
        total_activities = activities.count()
        completed_activities = activities.filter(status=Activity.Status.COMPLETED).count()
        
        # Response rates by activity type
        response_rates = {}
        for activity_type in Activity.ActivityType:
            type_activities = activities.filter(activity_type=activity_type.value)
            type_completed = type_activities.filter(status=Activity.Status.COMPLETED).count()
            type_total = type_activities.count()
            
            if type_total > 0:
                response_rates[activity_type.value] = {
                    'completed': type_completed,
                    'total': type_total,
                    'rate': round((type_completed / type_total) * 100, 1)
                }
        
        # Sequence step performance (for sequence campaigns)
        step_performance = {}
        if campaign.sequence_type:
            sequence_activities = activities.filter(sequence_info__isnull=False)
            for activity in sequence_activities:
                if hasattr(activity, 'sequence_info') and activity.sequence_info:
                    step = activity.sequence_info.sequence_position
                    if step not in step_performance:
                        step_performance[step] = {'total': 0, 'completed': 0}
                    
                    step_performance[step]['total'] += 1
                    if activity.status == Activity.Status.COMPLETED:
                        step_performance[step]['completed'] += 1
            
            # Calculate completion rates for each step
            for step in step_performance:
                total = step_performance[step]['total']
                completed = step_performance[step]['completed']
                step_performance[step]['completion_rate'] = round((completed / total) * 100, 1) if total > 0 else 0
        
        return {
            'campaign_id': campaign.id,
            'total_activities': total_activities,
            'completed_activities': completed_activities,
            'overall_completion_rate': round((completed_activities / total_activities) * 100, 1) if total_activities > 0 else 0,
            'response_rates_by_type': response_rates,
            'step_performance': step_performance,
            'targets_count': campaign.targets.count()
        }