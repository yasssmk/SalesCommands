# apps/campaign/services/campaign_queue_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, F, Subquery, OuterRef
from django.core.exceptions import ObjectDoesNotExist
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.campaign.config.variables import (
    TIER_PRIORITY_SCORES, 
    ACTIVITY_TYPE_PRIORITIES,
    OVERDUE_PENALTY_PER_DAY,
    CALLBACK_PRIORITY_BOOST,
    SEQUENCE_STEP_PRIORITY_BONUS,
    WORKING_DAYS,
    BUYING_AUTHORITY_PRIORITY_BOOST
)


class CampaignQueueService:
    """
    Service for managing campaign activity queues and determining which activities are ready
    """
    
    @classmethod
    def get_active_activities_for_campaign(cls, campaign: Campaign, limit: int = 50, 
                                            prefetch_relations: bool = False,
                                            current_activity_type: str = None) -> Dict:
            """
            Get activities that are ready to be worked on for a campaign
            
            Args:
                campaign: The campaign to get activities for
                limit: Maximum number of activities to return
                prefetch_relations: Whether to prefetch related objects for serialization
                current_activity_type: The type of activity the user is currently working on
                                    (used for batching similar activities)
                
            Returns:
                Dictionary with ready activities and queue information
            """
            # Build base queryset (same as before)
            query = Activity.objects.filter(
                campaign_info__campaign=campaign,
                status__in=[Activity.Status.PLANNED]
            )
            
            # Add select_related and prefetch_related (same as before)
            query = query.select_related('account', 'campaign_info__campaign_target')
            if prefetch_relations:
                query = query.prefetch_related(
                    'contacts',
                    'sequence_info'
                )
            
            # Execute the query
            campaign_activities = query.all()
            
            ready_activities = []
            
            for activity in campaign_activities:
                if cls._is_activity_ready(activity):
                    # Calculate standard priority score
                    priority_score = cls._calculate_priority_score(activity)
                    
                    # Add batching information
                    activity_data = {
                        'activity': activity,
                        'priority_score': priority_score,
                        'delay_status': cls._get_delay_status(activity),
                        'activity_type': activity.activity_type
                    }
                    
                    ready_activities.append(activity_data)
            
            # First sort by priority score (descending)
            ready_activities.sort(key=lambda x: -x['priority_score'])
            
            # Then apply activity type batching if a current type is specified
            if current_activity_type:
                # First re-order to prioritize the current activity type
                batched_activities = cls._apply_activity_batching(ready_activities, current_activity_type)
                ready_activities = batched_activities
            
            # Format response - only include Activity objects, not nested dicts with activity inside
            activities_list = [item['activity'] for item in ready_activities[:limit]]
            
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'ready_activities': activities_list,
                'total_ready': len(ready_activities),
                'total_pending': campaign_activities.count(),
                'queue_info': cls._get_queue_info(campaign, ready_activities),
                'activity_types_breakdown': cls._get_activity_type_breakdown(ready_activities)
            }

    @classmethod
    def _apply_activity_batching(cls, activities: List[Dict], current_type: str) -> List[Dict]:
        """
        Apply activity type batching to improve user productivity
        
        Args:
            activities: List of activity data dictionaries
            current_type: The activity type currently being worked on
            
        Returns:
            Reordered list with activity batching applied
        """
        # Group activities by type
        activity_groups = {}
        for activity_data in activities:
            activity_type = activity_data['activity_type']
            if activity_type not in activity_groups:
                activity_groups[activity_type] = []
            activity_groups[activity_type].append(activity_data)
        
        # Start with current activity type
        result = []
        if current_type in activity_groups:
            result.extend(activity_groups[current_type])
            del activity_groups[current_type]
        
        # Then add groups in a productive order:
        # 1. Calls (require focus and are synchronous)
        # 2. Emails (can be batched efficiently)
        # 3. LinkedIn messages (similar to emails)
        # 4. Meetings (usually scheduled, not immediate)
        # 5. Other tasks
        
        activity_type_order = [
            Activity.ActivityType.CALL,
            Activity.ActivityType.EMAIL,
            Activity.ActivityType.LINKEDIN,
            Activity.ActivityType.MEETING,
            Activity.ActivityType.TASK,
            Activity.ActivityType.CUSTOM
        ]
        
        for activity_type in activity_type_order:
            if activity_type in activity_groups:
                result.extend(activity_groups[activity_type])
                del activity_groups[activity_type]
        
        # Add any remaining activity types
        for remaining_activities in activity_groups.values():
            result.extend(remaining_activities)
        
        return result

    @classmethod
    def _get_activity_type_breakdown(cls, activities: List[Dict]) -> Dict:
        """
        Get a breakdown of activity counts by type
        
        Args:
            activities: List of activity data dictionaries
            
        Returns:
            Dictionary with counts by activity type
        """
        counts = {}
        for activity_data in activities:
            activity_type = activity_data['activity_type']
            counts[activity_type] = counts.get(activity_type, 0) + 1
        
        return counts
            
    @classmethod
    def _calculate_working_days_between(cls, start_date: date, end_date: date) -> int:
        """
        Calculate the number of working days between two dates (excluding weekends)
        """
        if start_date >= end_date:
            return 0
        
        current_date = start_date
        working_days = 0
        
        while current_date < end_date:
            # Monday = 0, Sunday = 6
            # Monday to Friday (0-4) are working days
            if current_date.weekday() < 5:
                working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    # @classmethod
    # def _add_working_days(cls, start_date: date, working_days: int) -> date:
    #     """
    #     Add working days to a date (skipping weekends)
    #     """
    #     current_date = start_date
    #     days_added = 0
        
    #     while days_added < working_days:
    #         current_date += timedelta(days=1)
    #         # If it's a working day (Mon-Fri), count it
    #         if current_date.weekday() < 5:
    #             days_added += 1
        
    #     return current_date
    
    # @classmethod
    # def _is_activity_ready(cls, activity: Activity) -> bool:
    #     """
    #     Check if an activity is ready to be worked on based on working day-counting logic
    #     """
    #     if not hasattr(activity, 'sequence_info'):
    #         return True  # Non-sequence activities are always ready
        
    #     sequence_info = activity.sequence_info
        
    #     # Check if sequence is paused
    #     if sequence_info.sequence_paused_until and sequence_info.sequence_paused_until > date.today():
    #         return False
        
    #     # First activity in sequence is always ready
    #     if sequence_info.sequence_position == 1:
    #         return True
        
    #     # Find the previous completed activity in the sequence
    #     previous_activity = activity.previous_activity
    #     if not previous_activity:
    #         return True
        
    #     # Check if previous activity is completed
    #     if previous_activity.status != Activity.Status.COMPLETED:
    #         return False
        
    #     # Calculate working days since last completed activity
    #     if previous_activity.completed_at:
    #         completed_date = previous_activity.completed_at.date()
    #         working_days_passed = cls._calculate_working_days_between(completed_date, date.today())
    #         return working_days_passed >= sequence_info.min_delay_days
        
    #     return False

    @classmethod
    def _is_activity_ready(cls, activity: Activity) -> bool:
        """
        Check if an activity is ready to be worked on based on working day-counting logic
        """
        from core.utils.business_days import BusinessDayCalculator
        
        if not hasattr(activity, 'sequence_info'):
            return True  # Non-sequence activities are always ready
        
        sequence_info = activity.sequence_info
        
        # Check if sequence is paused
        if sequence_info.sequence_paused_until and sequence_info.sequence_paused_until > date.today():
            return False
        
        # First activity in sequence is always ready
        if sequence_info.sequence_position == 1:
            return True
        
        # Find the previous completed activity in the sequence
        previous_activity = activity.previous_activity
        if not previous_activity:
            return True
        
        # Check if previous activity is completed
        if previous_activity.status != Activity.Status.COMPLETED:
            return False
        
        # Calculate business days since last completed activity
        if previous_activity.completed_at:
            completed_date = previous_activity.completed_at.date()
            business_days_passed = BusinessDayCalculator.get_business_days_between(
                completed_date, date.today())
            return business_days_passed >= sequence_info.min_delay_days
        
        return False
    
    @classmethod
    def _get_delay_status(cls, activity: Activity) -> Dict:
        """
        Get delay status information for an activity (using working days)
        """
        if not hasattr(activity, 'sequence_info') or not activity.previous_activity:
            return {'status': 'ready', 'days_waiting': 0}
        
        sequence_info = activity.sequence_info
        
        if activity.previous_activity.completed_at:
            completed_date = activity.previous_activity.completed_at.date()
            
            # Calculate working days passed since completion
            working_days_passed = cls._calculate_working_days_between(completed_date, date.today())
            
            # Calculate how many working days we're ahead/behind the minimum
            working_days_waiting = working_days_passed - sequence_info.min_delay_days
            
            if working_days_waiting < 0:
                # Still waiting - calculate when it will be ready
                target_date = cls._add_working_days(completed_date, sequence_info.min_delay_days)
                ready_in_days = cls._calculate_working_days_between(date.today(), target_date)
                
                return {
                    'status': 'waiting',
                    'working_days_waiting': working_days_waiting,
                    'ready_in_working_days': ready_in_days,
                    'ready_date': target_date
                }
            elif working_days_waiting == 0:
                return {
                    'status': 'ready', 
                    'working_days_waiting': 0,
                    'ready_date': date.today()
                }
            else:
                return {
                    'status': 'overdue',
                    'working_days_waiting': working_days_waiting,
                    'working_days_overdue': working_days_waiting
                }
        
        return {'status': 'pending_previous', 'working_days_waiting': 0}
    
    @classmethod
    def _get_delay_status(cls, activity: Activity) -> Dict:
        """
        Get delay status information for an activity (using business days)
        
        Args:
            activity: The activity to check
            
        Returns:
            Dict with status information about business day delays
        """
        from core.utils.business_days import BusinessDayCalculator
        
        if not hasattr(activity, 'sequence_info') or not activity.previous_activity:
            return {'status': 'ready', 'days_waiting': 0}
        
        sequence_info = activity.sequence_info
        
        if activity.previous_activity.completed_at:
            completed_date = activity.previous_activity.completed_at.date()
            today = date.today()
            
            # Calculate business days passed since completion
            business_days_passed = BusinessDayCalculator.get_business_days_between(
                completed_date, today)
            
            # Calculate how many business days we're ahead/behind the minimum
            business_days_waiting = business_days_passed - sequence_info.min_delay_days
            
            if business_days_waiting < 0:
                # Still waiting - calculate when it will be ready
                target_date = BusinessDayCalculator.add_business_days(
                    completed_date, sequence_info.min_delay_days)
                
                ready_in_days = BusinessDayCalculator.get_business_days_between(
                    today, target_date)
                
                return {
                    'status': 'waiting',
                    'business_days_waiting': business_days_waiting,
                    'ready_in_business_days': ready_in_days,
                    'ready_date': target_date
                }
            elif business_days_waiting == 0:
                return {
                    'status': 'ready', 
                    'business_days_waiting': 0,
                    'ready_date': today
                }
            else:
                return {
                    'status': 'overdue',
                    'business_days_waiting': business_days_waiting,
                    'business_days_overdue': business_days_waiting
                }
        
        return {'status': 'pending_previous', 'business_days_waiting': 0}

    @classmethod
    def _calculate_priority_score(cls, activity: Activity) -> float:
        """
        Calculate priority score for an activity based on various factors
        
        Args:
            activity: The activity to score
            
        Returns:
            float: Priority score (higher = higher priority)
        """
        from core.utils.business_days import BusinessDayCalculator
        
        score = 0.0
        
        # Account tier priority (A=100, B=50, C=10)
        account_tier = getattr(activity.account, 'tier', 'C')
        score += TIER_PRIORITY_SCORES.get(account_tier, 10)

        contact_buying_authority_bonus = 0
        contacts = list(activity.contacts.all())
        if contacts:
            for contact in contacts:
                if getattr(contact, 'has_buying_authority', False):
                    contact_buying_authority_bonus = BUYING_AUTHORITY_PRIORITY_BOOST
                    break
        
        score += contact_buying_authority_bonus
        
        # Sequence position bonus (earlier steps get priority)
        if hasattr(activity, 'sequence_info'):
            sequence_info = activity.sequence_info
            
            # Higher bonus for earlier steps
            step_bonus = max(0, 11 - sequence_info.sequence_position) * SEQUENCE_STEP_PRIORITY_BONUS
            score += step_bonus
            
            # Calculate delay bonus using business days
            if activity.previous_activity and activity.previous_activity.completed_at:
                completed_date = activity.previous_activity.completed_at.date()
                
                business_days_passed = BusinessDayCalculator.get_business_days_between(
                    completed_date, date.today())
                    
                business_days_overdue = business_days_passed - sequence_info.min_delay_days
                
                # Add bonus for overdue activities (business days)
                if business_days_overdue > 0:
                    score += business_days_overdue * OVERDUE_PENALTY_PER_DAY
            
            # Callback requested priority boost
            if sequence_info.callback_requested_date:
                if sequence_info.callback_requested_date <= date.today():
                    score += CALLBACK_PRIORITY_BOOST

        score += ACTIVITY_TYPE_PRIORITIES.get(activity.activity_type, 0)
        
        return score
    
    # @classmethod
    # def _calculate_priority_score(cls, activity: Activity) -> float:
    #     """
    #     Calculate priority score for an activity based on various factors (updated for working days)
    #     """
    #     score = 0.0
        
    #     # Account tier priority (A=100, B=50, C=10)
    #     account_tier = getattr(activity.account, 'tier', 'C')
    #     score += TIER_PRIORITY_SCORES.get(account_tier, 10)

    #     contact_buying_authority_bonus = 0
    #     contacts = list(activity.contacts.all())
    #     if contacts:
    #         for contact in contacts:
    #             if getattr(contact, 'has_buying_authority', False):
    #                 contact_buying_authority_bonus = BUYING_AUTHORITY_PRIORITY_BOOST
    #                 break
        
    #     score += contact_buying_authority_bonus
        
    #     # Sequence position bonus (earlier steps get priority)
    #     if hasattr(activity, 'sequence_info'):
    #         sequence_info = activity.sequence_info
            
    #         # Higher bonus for earlier steps
    #         step_bonus = max(0, 11 - sequence_info.sequence_position) * SEQUENCE_STEP_PRIORITY_BONUS
    #         score += step_bonus
            
    #         # Calculate delay bonus using working days
    #         if activity.previous_activity and activity.previous_activity.completed_at:
    #             completed_date = activity.previous_activity.completed_at.date()
    #             working_days_passed = cls._calculate_working_days_between(completed_date, date.today())
    #             working_days_overdue = working_days_passed - sequence_info.min_delay_days
                
    #             # Add bonus for overdue activities (working days)
    #             if working_days_overdue > 0:
    #                 score += working_days_overdue * OVERDUE_PENALTY_PER_DAY
            
    #         # Callback requested priority boost
    #         if sequence_info.callback_requested_date:
    #             if sequence_info.callback_requested_date <= date.today():
    #                 score += CALLBACK_PRIORITY_BOOST
        

    #     score += ACTIVITY_TYPE_PRIORITIES.get(activity.activity_type,  0)
        
    #     return score

    @classmethod
    def get_prioritized_contacts_for_campaign(cls, campaign: Campaign, limit: int = 50) -> Dict:
        """
        Get a prioritized list of contacts for a non-sequence campaign
        
        Args:
            campaign: The campaign to get contacts for
            limit: Maximum number of contacts to return
            
        Returns:
            Dictionary with prioritized contacts and queue information
        """
        # Verify this is a non-sequence campaign
        if campaign.sequence_type:
            return {
                'success': False,
                'error': 'This method is only for campaigns without sequences',
                'is_sequence': True
            }
        
        # First, update any expired callbacks to IN_PROGRESS
        today = date.today()
        callback_targets = CampaignTarget.objects.filter(
            campaign=campaign,
            status=CampaignTarget.Status.CALLBACK_PENDING,
            callback_date__lte=today  # Callback date is today or in the past
        )
        updated_count = callback_targets.update(status=CampaignTarget.Status.IN_PROGRESS)
        
        # Use the activity service to extract contacts
        from apps.campaign.services.campaign_activity_service import CampaignActivityService
        extraction_result = CampaignActivityService._extract_contacts_from_targets(campaign)
        valid_contacts = extraction_result['valid_contacts']
        skipped_contacts = extraction_result['skipped_contacts']
        contact_to_target_map = extraction_result['contact_to_target_map']
        
        # Get all campaign targets for this campaign
        campaign_targets = CampaignTarget.objects.filter(
            campaign=campaign
        ).select_related(
            'account', 
            'contact',
            'lead',
            'target_opportunity'
        )
        
        # Create a map of contact_id to campaign_target for efficient lookup
        target_by_contact_id = {}
        for target in campaign_targets:
            if target.contact_id:
                target_by_contact_id[target.contact_id] = target
        
        # Calculate priority score for each contact
        contacts_with_score = []
        
        for contact_info in valid_contacts:
            contact = contact_info['contact']
            
            # Skip contacts that have already been processed (completed or stopped)
            target = target_by_contact_id.get(contact.id) or contact_to_target_map.get(contact.id)
            if not target or target.status in [CampaignTarget.Status.COMPLETED, CampaignTarget.Status.STOPPED]:
                continue
            
            # Get associated target and account
            account = contact.account
            
            if not account:
                continue
            
            # Calculate base priority score
            score = 0.0
            
            # Account tier priority (A=100, B=50, C=10)
            account_tier = getattr(account, 'tier', 'C')
            score += TIER_PRIORITY_SCORES.get(account_tier, 10)
            
            # Buying authority bonus
            if getattr(contact, 'has_buying_authority', False):
                score += BUYING_AUTHORITY_PRIORITY_BOOST
            
            # Job level priority (if available)
            job_level = getattr(contact, 'job_level', 0)
            score += job_level * 5  # 5 points per job level
            
            # Decision maker bonus
            if getattr(contact, 'is_decision_maker', False):
                score += 25
            
            # Communication channels bonus - more channels = higher priority
            channels_count = sum([
                contact_info['has_phone'],
                contact_info['has_email'],
                contact_info['has_linkedin']
            ])
            score += channels_count * 5
            
            # Target type priority adjustment
            target_type = target.get_target_type()
            type_priorities = {
                'opportunity': 30,  # Highest priority for opportunity targets
                'lead': 20,         # High priority for leads
                'contact': 15,      # Medium priority for direct contacts
                'account': 10       # Base priority for account targets
            }
            score += type_priorities.get(target_type, 0)
            
            # Status adjustment
            if target.status == CampaignTarget.Status.IN_PROGRESS:
                score += 15  # Bonus for targets already in progress
            
            # Callback priority - massive boost for callbacks due today or in the past
            if hasattr(target, 'callback_date') and target.callback_date:
                # If callback is due today or in the past
                if target.callback_date <= today:
                    score += CALLBACK_PRIORITY_BOOST  # Very high boost
                else:
                    # Calculate days until callback
                    days_until_callback = (target.callback_date - today).days
                    # Reduce priority more for further dates
                    score -= days_until_callback * 10
            
            # Special status for CALLBACK_PENDING
            if target.status == CampaignTarget.Status.CALLBACK_PENDING:
                score += CALLBACK_PRIORITY_BOOST // 2  # Half the boost of an actual callback date
            
            # Add the contact with its score to the list
            contacts_with_score.append({
                'contact': contact,
                'contact_id': contact.id,
                'contact_name': f"{contact.first_name} {contact.last_name}",
                'email': contact.email,
                'phone': contact.phone,
                'account': account,
                'account_name': account.company_name,
                'target_type': target_type,
                'target_id': target.id,
                'has_phone': contact_info['has_phone'],
                'has_email': contact_info['has_email'],
                'has_linkedin': contact_info['has_linkedin'],
                'priority_score': score,
                'callback_date': target.callback_date if hasattr(target, 'callback_date') else None,
                'status': target.status
            })
        
        # Sort by priority score (descending)
        contacts_with_score.sort(key=lambda x: -x['priority_score'])
        
        # Apply limit
        contacts_with_score = contacts_with_score[:limit]
        
        # Calculate totals and stats
        contact_counts = {
            'total': len(valid_contacts),
            'skipped': len(skipped_contacts),
            'prioritized': len(contacts_with_score),
            'callbacks_updated': updated_count
        }
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'contacts': contacts_with_score,
            'counts': contact_counts,
            'skipped_contacts': skipped_contacts,
            'is_sequence': False,
            'success': True
        }
    
    @classmethod
    def _get_queue_info(cls, campaign: Campaign, ready_activities: List) -> Dict:
        """
        Get summary information about the campaign queue
        """
        # Count activities by status
        all_activities = Activity.objects.filter(campaign_info__campaign=campaign)
        
        status_counts = {
            'planned': all_activities.filter(status=Activity.Status.PLANNED).count(),
            'completed': all_activities.filter(status=Activity.Status.COMPLETED).count(),
            'cancelled': all_activities.filter(status=Activity.Status.CANCELLED).count(),
        }
        
        # Count by delay status
        delay_status_counts = {'ready': 0, 'waiting': 0, 'overdue': 0}
        for item in ready_activities:
            delay_status = item['delay_status']['status']
            if delay_status in delay_status_counts:
                delay_status_counts[delay_status] += 1
        
        # Calculate progress
        total_activities = sum(status_counts.values())
        progress_percentage = (status_counts['completed'] / total_activities * 100) if total_activities > 0 else 0
        
        return {
            'status_counts': status_counts,
            'delay_status_counts': delay_status_counts,
            'progress_percentage': round(progress_percentage, 1),
            'total_activities': total_activities
        }
    
    @classmethod
    def activate_campaign(cls, campaign: Campaign) -> Dict:
        """
        Activate a campaign and prepare the first batch of activities
        """
        # Mark campaign as started (you might want to add a field for this)
        # campaign.started_at = timezone.now()
        # campaign.save()
        
        # Get the initial set of ready activities
        return cls.get_active_activities_for_campaign(campaign, limit=50)