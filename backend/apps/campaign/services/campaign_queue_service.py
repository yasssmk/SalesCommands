# apps/campaign/services/campaign_queue_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, F, Subquery, OuterRef
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.response import Response
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.campaign.config.variables import (
    TIER_PRIORITY_SCORES, 
    ACTIVITY_TYPE_PRIORITIES,
    OVERDUE_PENALTY_PER_DAY,
    CALLBACK_PRIORITY_BOOST,
    SEQUENCE_STEP_PRIORITY_BONUS,
    WORKING_DAYS,
    BUYING_AUTHORITY_PRIORITY_BOOST,
    FIELD_NAMES,
    OPERATION_MESSAGES
)
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages


class CampaignQueueService:
    """
    Service for managing campaign activity queues and determining which activities are ready
    Now returns standardized Response objects with proper error handling
    """
    
    @classmethod
    def get_active_activities_for_campaign(cls, campaign: Campaign, limit: int = 50, 
                                        prefetch_relations: bool = False,
                                        current_activity_type: str = None) -> Response:
        """
        Get activities that are ready to be worked on for a campaign
        
        Args:
            campaign: The campaign to get activities for
            limit: Maximum number of activities to return
            prefetch_relations: Whether to prefetch related objects for serialization
            current_activity_type: The type of activity the user is currently working on
                                (used for batching similar activities)
            
        Returns:
            Response: Standardized response with ready activities and queue information
        """
        try:
            # Build base queryset
            query = Activity.objects.filter(
                **{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign},
                status__in=[Activity.Status.PLANNED]
            )
            
            # CRITICAL: Always prefetch relations needed for priority calculation
            # This prevents N+1 queries in _calculate_priority_score()
            query = query.select_related(
                FIELD_NAMES['ACCOUNT'],  # For tier-based scoring
                f"campaign_info__{FIELD_NAMES['CAMPAIGN']}_target",  # Campaign relationship
                'previous_activity',  # For overdue calculation
                'sequence_info'  # For sequence-based scoring
            )
            
            # Always prefetch contacts for priority calculation (buying authority check)
            query = query.prefetch_related('contacts')
            
            # Execute the query ONCE with all optimizations
            campaign_activities = query.all()
            
            ready_activities = []
            
            # Process each activity - NO additional queries thanks to prefetching
            for activity in campaign_activities:
                if cls._is_activity_ready(activity):
                    # Calculate priority score - all relations are now prefetched
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
                batched_activities = cls._apply_activity_batching(ready_activities, current_activity_type)
                ready_activities = batched_activities
            
            # Format response - only include Activity objects, not nested dicts with activity inside
            activities_list = [item['activity'] for item in ready_activities[:limit]]
            
            # Serialize activities for JSON response if prefetch_relations is True
            if prefetch_relations:
                serialized_activities = []
                for activity in activities_list:
                    # Basic activity data
                    activity_data = {
                        'id': activity.id,
                        'title': activity.title,
                        'activity_type': activity.activity_type,
                        'activity_type_display': activity.get_activity_type_display(),
                        f"{FIELD_NAMES['ACCOUNT']}_id": activity.account_id,
                        f"{FIELD_NAMES['ACCOUNT']}_name": activity.account.company_name,  # Now safely accessed due to select_related
                        'scheduled_start': activity.scheduled_start,
                        FIELD_NAMES['STATUS']: activity.status,
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
                
                items_for_response = serialized_activities
            else:
                # Return raw Activity objects for internal service calls
                items_for_response = activities_list
            
            # Get queue information using already fetched data
            queue_info = cls._get_queue_info(campaign, ready_activities, campaign_activities)
            activity_types_breakdown = cls._get_activity_type_breakdown(ready_activities)
            
            # Use CampaignResponseBuilder for standardized playlist response
            return CampaignResponseBuilder.campaign_playlist(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                items=items_for_response,
                queue_type='activity',
                is_sequence=True,
                total_items=len(ready_activities),
                additional_data={
                    'total_pending': len(campaign_activities),
                    'queue_info': queue_info,
                    'activity_types_breakdown': activity_types_breakdown
                }
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
            )

    @classmethod
    def get_prioritized_contacts_for_campaign(cls, campaign: Campaign, limit: int = 50) -> Response:
        """
        Get a prioritized list of contacts for a non-sequence campaign
        
        Args:
            campaign: The campaign to get contacts for
            limit: Maximum number of contacts to return
            
        Returns:
            Response: Standardized response with prioritized contacts and queue information
        """
        try:
            # Verify this is a non-sequence campaign
            if campaign.sequence_type:
                raise StandardizedValidationError(
                    CampaignErrorMessages.CAMPAIGN_NO_SEQUENCE_TYPE
                )
            
            # First, update any expired callbacks to IN_PROGRESS
            today = date.today()
            callback_targets = CampaignTarget.objects.filter(
                **{FIELD_NAMES['CAMPAIGN']: campaign},
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
                **{FIELD_NAMES['CAMPAIGN']: campaign}
            ).select_related(
                FIELD_NAMES['ACCOUNT'], 
                FIELD_NAMES['CONTACT'],
                FIELD_NAMES['LEAD'],
                FIELD_NAMES['TARGET_OPPORTUNITY']
            )
            
            # Create a map of contact_id to campaign_target for efficient lookup
            target_by_contact_id = {}
            for target in campaign_targets:
                if target.contact_id:
                    target_by_contact_id[target.contact_id] = target
            
            # Calculate priority score for each contact
            contacts_with_score = []
            
            for contact_info in valid_contacts:
                contact = contact_info[FIELD_NAMES['CONTACT']]
                
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
                    FIELD_NAMES['CONTACT']: 15,      # Medium priority for direct contacts
                    FIELD_NAMES['ACCOUNT']: 10       # Base priority for account targets
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
                    FIELD_NAMES['CONTACT']: contact,
                    f"{FIELD_NAMES['CONTACT']}_id": contact.id,
                    f"{FIELD_NAMES['CONTACT']}_name": f"{contact.first_name} {contact.last_name}",
                    'email': contact.email,
                    'phone': contact.phone,
                    FIELD_NAMES['ACCOUNT']: account,
                    f"{FIELD_NAMES['ACCOUNT']}_name": account.company_name,
                    'target_type': target_type,
                    'target_id': target.id,
                    'has_phone': contact_info['has_phone'],
                    'has_email': contact_info['has_email'],
                    'has_linkedin': contact_info['has_linkedin'],
                    'priority_score': score,
                    'callback_date': target.callback_date if hasattr(target, 'callback_date') else None,
                    FIELD_NAMES['STATUS']: target.status
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
            
            # Use CampaignResponseBuilder for standardized contact queue response
            return CampaignResponseBuilder.campaign_playlist(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                items=contacts_with_score,
                queue_type=FIELD_NAMES['CONTACT'],
                is_sequence=False,
                total_items=contact_counts['prioritized'],
                additional_data={
                    'total_pending': contact_counts['total'],
                    'skipped_contacts': skipped_contacts,
                    'counts': contact_counts
                }
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
            )
    
    @classmethod
    def activate_campaign(cls, campaign: Campaign) -> Response:
        """
        Activate a campaign and prepare the first batch of activities
        
        Args:
            campaign: The campaign to activate
            
        Returns:
            Response: Standardized response with campaign activation and initial queue
        """
        try:
            # Mark campaign as started (if there's a started_at field)
            if hasattr(campaign, 'started_at'):
                campaign.started_at = timezone.now()
                campaign.save()
            
            # Get the initial set of ready activities
            playlist_response = cls.get_active_activities_for_campaign(campaign, limit=50)
            
            # Extract data from the response to add activation information
            if hasattr(playlist_response, 'data') and 'data' in playlist_response.data:
                playlist_data = playlist_response.data['data']
                items = playlist_data.get('items', [])
                
                # Add activation-specific data
                activation_data = {
                    f"{FIELD_NAMES['CAMPAIGN']}_id": campaign.id,
                    f"{FIELD_NAMES['CAMPAIGN']}_name": campaign.name,
                    'campaign_activated': True,
                    'activation_time': timezone.now().isoformat(),
                    'initial_queue': items,
                    'initial_queue_size': len(items)
                }
                
                meta = {
                    'operation': 'campaign_activation',
                    'initial_activities_ready': len(items),
                    'activated_at': timezone.now().isoformat()
                }
                
                # Use operation message from config
                message = OPERATION_MESSAGES['CAMPAIGN_STARTED'].format(name=campaign.name)
                
                return StandardizedSuccessResponse.success(
                    message=message,
                    data=activation_data,
                    meta=meta
                )
            else:
                # Fallback if playlist_response format is unexpected
                raise StandardizedValidationError(
                    CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(
                    current_state=f"activation failed: {str(e)}"
                )
            )
    
    # [HELPER METHODS - unchanged but with proper error handling]
    
    @classmethod
    def _apply_activity_batching(cls, activities: List[Dict], current_type: str) -> List[Dict]:
        """Apply activity type batching to improve user productivity"""
        try:
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
            
            # Then add groups in a productive order
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
        except Exception:
            # If batching fails, return original order
            return activities

    @classmethod
    def _get_activity_type_breakdown(cls, activities: List[Dict]) -> Dict:
        """Get a breakdown of activity counts by type"""
        counts = {}
        for activity_data in activities:
            activity_type = activity_data['activity_type']
            counts[activity_type] = counts.get(activity_type, 0) + 1
        return counts
            
    @classmethod
    def _is_activity_ready(cls, activity: Activity) -> bool:
        """Check if an activity is ready to be worked on based on business day-counting logic"""
        try:
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
        except Exception:
            # If calculation fails, default to not ready for safety
            return False
    
    @classmethod
    def _get_delay_status(cls, activity: Activity) -> Dict:
        """Get delay status information for an activity (using business days)"""
        try:
            from core.utils.business_days import BusinessDayCalculator
            
            if not hasattr(activity, 'sequence_info') or not activity.previous_activity:
                return {FIELD_NAMES['STATUS']: 'ready', 'days_waiting': 0}
            
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
                        FIELD_NAMES['STATUS']: 'waiting',
                        'business_days_waiting': business_days_waiting,
                        'ready_in_business_days': ready_in_days,
                        'ready_date': target_date
                    }
                elif business_days_waiting == 0:
                    return {
                        FIELD_NAMES['STATUS']: 'ready', 
                        'business_days_waiting': 0,
                        'ready_date': today
                    }
                else:
                    return {
                        FIELD_NAMES['STATUS']: 'overdue',
                        'business_days_waiting': business_days_waiting,
                        'business_days_overdue': business_days_waiting
                    }
            
            return {FIELD_NAMES['STATUS']: 'pending_previous', 'business_days_waiting': 0}
        except Exception:
            # If calculation fails, default to ready status
            return {FIELD_NAMES['STATUS']: 'ready', 'days_waiting': 0}

    @classmethod
    def _calculate_priority_score(cls, activity: Activity) -> float:
        """Calculate priority score for an activity based on various factors"""
        try:
            from core.utils.business_days import BusinessDayCalculator
            
            score = 0.0
            
            # Account tier priority (A=100, B=50, C=10)
            account_tier = getattr(activity.account, 'tier', 'C')
            score += TIER_PRIORITY_SCORES.get(account_tier, 10)

            # Contact buying authority bonus - OPTIMIZED: no additional query
            contact_buying_authority_bonus = 0
            
            try:
                # Access prefetched contacts
                prefetched_contacts = activity.contacts.all()
                
                # Check if any contact has buying authority
                for contact in prefetched_contacts:
                    if getattr(contact, 'has_buying_authority', False):
                        contact_buying_authority_bonus = BUYING_AUTHORITY_PRIORITY_BOOST
                        break
                        
            except AttributeError:
                # Fallback if contacts not prefetched
                pass
            
            score += contact_buying_authority_bonus
            
            # Sequence position bonus (earlier steps get priority)
            sequence_info = getattr(activity, 'sequence_info', None)
            if sequence_info:
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

            # Activity type priority
            score += ACTIVITY_TYPE_PRIORITIES.get(activity.activity_type, 0)
            
            return score
        except Exception:
            # If calculation fails, return base score
            return 10.0
    
    @classmethod
    def _get_queue_info(cls, campaign: Campaign, ready_activities: List, 
                   all_campaign_activities: List = None) -> Dict:
        """Get summary information about the campaign queue"""
        try:
            # Use provided activities if available, otherwise query (fallback)
            if all_campaign_activities is not None:
                # Count activities by status using already fetched data - NO DB QUERY
                status_counts = {
                    'planned': sum(1 for a in all_campaign_activities if a.status == Activity.Status.PLANNED),
                    'completed': sum(1 for a in all_campaign_activities if a.status == Activity.Status.COMPLETED),
                    'cancelled': sum(1 for a in all_campaign_activities if a.status == Activity.Status.CANCELLED),
                }
                total_activities = len(all_campaign_activities)
            else:
                # Fallback: query database (should be avoided)
                all_activities = Activity.objects.filter(**{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign})
                
                status_counts = {
                    'planned': all_activities.filter(status=Activity.Status.PLANNED).count(),
                    'completed': all_activities.filter(status=Activity.Status.COMPLETED).count(),
                    'cancelled': all_activities.filter(status=Activity.Status.CANCELLED).count(),
                }
                total_activities = sum(status_counts.values())
            
            # Count by delay status using already processed data
            delay_status_counts = {'ready': 0, 'waiting': 0, 'overdue': 0}
            for item in ready_activities:
                delay_status = item['delay_status'][FIELD_NAMES['STATUS']]
                if delay_status in delay_status_counts:
                    delay_status_counts[delay_status] += 1
            
            # Calculate progress
            progress_percentage = (status_counts['completed'] / total_activities * 100) if total_activities > 0 else 0
            
            return {
                'status_counts': status_counts,
                'delay_status_counts': delay_status_counts,
                'progress_percentage': round(progress_percentage, 1),
                'total_activities': total_activities
            }
        except Exception:
            # If calculation fails, return minimal info
            return {
                'status_counts': {'planned': 0, 'completed': 0, 'cancelled': 0},
                'delay_status_counts': {'ready': 0, 'waiting': 0, 'overdue': 0},
                'progress_percentage': 0,
                'total_activities': 0
            }