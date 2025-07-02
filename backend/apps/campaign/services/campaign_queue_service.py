# apps/campaign/services/campaign_queue_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q, F, Subquery, OuterRef
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.response import Response
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.campaign.config.settings import CONFIG
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
        🔧 MODIFIÉ : Utilise CampaignAnalyticsService pour les métriques cohérentes
        
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
                **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                status__in=[Activity.Status.PLANNED]
            )
            
            # CRITICAL: Always prefetch relations needed for priority calculation
            # This prevents N+1 queries in _calculate_priority_score()
            query = query.select_related(
                CONFIG.fields.account,  
                f"campaign_info__{CONFIG.fields.campaign}_target",  # Campaign relationship
                'sequence_info',  # For sequence-based scoring
                # ✅ AJOUT : Préchargement des activités précédentes/suivantes pour le serializer
                'previous_activity',
                'previous_activity__sequence_info',  # Pour get_previous_activity_info()
                'next_activity', 
                'next_activity__sequence_info'  # Pour get_next_activity_info()
            )
            
            # Always prefetch contacts for priority calculation (buying authority check)
            query = query.prefetch_related('contacts')
            
            # Execute the query ONCE with all optimizations
            campaign_activities = query.all() 

            try:
                update_result = cls._calculate_and_update_scheduled_dates(
                    campaign, 
                    update_missing_only=True  # Ne met à jour que les dates manquantes
                )
                
                # Log optionnel des mises à jour pour debugging
                if update_result['updated_count'] > 0:
                    print(f"Updated {update_result['updated_count']} missing scheduled_start dates for campaign {campaign.id}")
                    
            except Exception as e:
                # Si le calcul des dates échoue, on continue avec les données existantes
                print(f"Warning: Failed to update scheduled dates for campaign {campaign.id}: {str(e)}")
                update_result = {'updated_count': 0, 'errors': []}
            
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
                # Import du serializer
                from apps.activities.serializers.activity_serializer import ActivitySerializer
                
                # Utiliser le serializer avec le contexte approprié
                serializer = ActivitySerializer(activities_list, many=True, context={
                    'request': None,  # Pas de request dans un service
                    'include_relations': True  # Flag pour inclure toutes les relations
                })
                
                items_for_response = serializer.data
            else:
                # Return raw Activity objects for internal service calls
                items_for_response = activities_list
            
            # 🔧 MODIFIÉ : Utiliser la nouvelle méthode optimisée
            queue_info = cls._get_queue_info(campaign, ready_activities, campaign_activities)
            activity_types_breakdown = cls._get_activity_type_breakdown(ready_activities)

            additional_data = {
                'total_pending': len(campaign_activities),
                'queue_info': queue_info,
                'activity_types_breakdown': activity_types_breakdown,
                'scheduled_dates_update': {
                    'updated_count': update_result.get('updated_count', 0),
                    'errors_count': len(update_result.get('errors', [])),
                    'integration_enabled': True
                }
            }
            
            # Use CampaignResponseBuilder for standardized playlist response
            return CampaignResponseBuilder.campaign_playlist(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                items=items_for_response,
                queue_type='activity',
                is_sequence=True,
                activities_created=len(ready_activities),
                total_items=len(ready_activities),
                additional_data=additional_data
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
            )
    
    @classmethod
    def _update_following_scheduled_dates(cls, completed_activity: Activity) -> Dict:
        """
        Met à jour les dates planifiées des activités suivantes après completion d'une activité
        À intégrer dans CampaignResultService.complete_activity()
        
        Args:
            completed_activity: L'activité qui vient d'être complétée
            
        Returns:
            Dict: Résumé des mises à jour effectuées
        """
        try:
            # Vérifier si l'activité fait partie d'une séquence
            if not hasattr(completed_activity, 'sequence_info') or not completed_activity.sequence_info:
                return {
                    'updated_count': 0,
                    'reason': 'Activity is not part of a sequence',
                    'activities_updated': []
                }
            
            # Récupérer la campagne
            campaign = getattr(completed_activity, f"campaign_info__{CONFIG.fields.campaign}", None)
            if not campaign:
                return {
                    'updated_count': 0,
                    'reason': 'Campaign not found',
                    'activities_updated': []
                }
            
            # Trouver la prochaine activité dans la séquence
            next_activity = None
            try:
                next_activity = Activity.objects.filter(
                    **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                    sequence_info__sequence_position=completed_activity.sequence_info.sequence_position + 1,
                    status=Activity.Status.PLANNED
                ).select_related('sequence_info').first()
            except Exception as e:
                print(f"Error finding next activity: {str(e)}")
            
            if not next_activity:
                return {
                    'updated_count': 0,
                    'reason': 'No next activity found in sequence',
                    'activities_updated': []
                }
            
            # Utiliser la méthode existante pour mettre à jour à partir de la prochaine activité
            update_result = cls._calculate_and_update_scheduled_dates(
                campaign,
                update_missing_only=False,  # Forcer la mise à jour même si dates existent
                start_from_activity=next_activity,
                force_update=True  # Forcer la recalculation basée sur la nouvelle completion
            )
            
            # Ajouter des informations spécifiques à cette opération
            update_result['trigger_activity_id'] = completed_activity.id
            update_result['trigger_activity_position'] = completed_activity.sequence_info.sequence_position
            update_result['next_activity_id'] = next_activity.id if next_activity else None
            update_result['operation'] = 'post_completion_update'
            
            return update_result
            
        except Exception as e:
            return {
                'updated_count': 0,
                'reason': f'Error updating following dates: {str(e)}',
                'activities_updated': [],
                'error': str(e)
            }

    @classmethod
    def _calculate_and_update_scheduled_dates(cls, campaign: Campaign, 
                                        update_missing_only: bool = False,
                                        start_from_activity: Activity = None,
                                        force_update: bool = False) -> Dict:
        """
        Calculate and update scheduled_start dates for sequence activities
        
        Args:
            campaign: Campaign to update activities for
            update_missing_only: Only update activities with scheduled_start = None
            start_from_activity: Start updating from this activity (inclusive)
            force_update: Update even if calculated date matches current date
            
        Returns:
            Dict: Summary of updated activities and any errors
        """
        try:
            from core.utils.business_days import BusinessDayCalculator
            from django.db import transaction
            
            # Get sequence activities ordered by position
            sequence_activities = Activity.objects.filter(
                campaign_info__campaign=campaign,
                sequence_info__isnull=False,
                status__in=[Activity.Status.PLANNED, Activity.Status.COMPLETED]
            ).select_related(
                'sequence_info', 'previous_activity'
            ).order_by('sequence_info__sequence_position')
            
            if not sequence_activities.exists():
                return {'updated_count': 0, 'activities_updated': [], 'errors': []}
            
            # Find starting point if start_from_activity specified
            start_index = 0
            if start_from_activity:
                for i, activity in enumerate(sequence_activities):
                    if activity.id == start_from_activity.id:
                        start_index = i
                        break
            
            updated_activities = []
            errors = []
            
            with transaction.atomic():
                for i, activity in enumerate(sequence_activities[start_index:], start_index):
                    try:
                        # Skip if update_missing_only and scheduled_start exists
                        if update_missing_only and activity.scheduled_start is not None:
                            continue
                        
                        # Calculate new scheduled_start
                        new_scheduled_start = cls._calculate_activity_scheduled_start(
                            activity, campaign, sequence_activities[:i]
                        )
                        
                        # Update if different or force_update
                        if (force_update or 
                            activity.scheduled_start is None or 
                            activity.scheduled_start.date() != new_scheduled_start.date()):
                            
                            activity.scheduled_start = new_scheduled_start
                            activity.save(update_fields=['scheduled_start'])
                            
                            updated_activities.append({
                                'activity_id': activity.id,
                                'sequence_position': activity.sequence_info.sequence_position,
                                'old_date': activity.scheduled_start,
                                'new_date': new_scheduled_start
                            })
                    
                    except Exception as e:
                        errors.append({
                            'activity_id': activity.id,
                            'error': str(e)
                        })
            
            return {
                'updated_count': len(updated_activities),
                'activities_updated': updated_activities,
                'errors': errors,
                'campaign_id': campaign.id
            }
            
        except Exception as e:
            return {
                'updated_count': 0,
                'activities_updated': [],
                'errors': [{'general_error': str(e)}],
                'campaign_id': campaign.id
            }

    @classmethod
    def _calculate_activity_scheduled_start(cls, activity: Activity, campaign: Campaign, 
                                        previous_activities: List[Activity]) -> timezone.datetime:
        """
        Calculate scheduled_start for a single activity
        
        Args:
            activity: Activity to calculate date for
            campaign: Campaign context
            previous_activities: List of activities before this one in sequence
            
        Returns:
            datetime: Calculated scheduled_start
        """
        try:
            from core.utils.business_days import BusinessDayCalculator
            
            sequence_info = activity.sequence_info
            
            # First activity in sequence
            if sequence_info.sequence_position == 1:
                # Use campaign start_date at default hour (9 AM)
                base_date = campaign.start_date
                return timezone.datetime.combine(
                    base_date, 
                    timezone.datetime.min.time().replace(hour=CONFIG.time.default_call_start_hour)
                ).replace(tzinfo=timezone.get_current_timezone())
            
            # Find the previous activity
            previous_activity = None
            for prev_act in reversed(previous_activities):
                if (prev_act.sequence_info and 
                    prev_act.sequence_info.sequence_position == sequence_info.sequence_position - 1):
                    previous_activity = prev_act
                    break
            
            if not previous_activity:
                # Fallback: use campaign start_date + estimated days
                estimated_days = (sequence_info.sequence_position - 1) * sequence_info.min_delay_days
                base_date = BusinessDayCalculator.add_business_days(
                    campaign.start_date, estimated_days
                )
                return timezone.datetime.combine(
                    base_date,
                    timezone.datetime.min.time().replace(hour=CONFIG.time.default_call_start_hour)
                ).replace(tzinfo=timezone.get_current_timezone())
            
            # Calculate based on previous activity
            if previous_activity.completed_at:
                # Previous completed: add min_delay_days
                start_date = previous_activity.completed_at.date()
                target_date = BusinessDayCalculator.add_business_days(
                    start_date, sequence_info.min_delay_days
                )
            else:
                # Previous not completed: estimate from its scheduled_start
                if previous_activity.scheduled_start:
                    estimated_completion = previous_activity.scheduled_start.date()
                    target_date = BusinessDayCalculator.add_business_days(
                        estimated_completion, sequence_info.min_delay_days
                    )
                else:
                    # Last resort: use today + min_delay
                    target_date = BusinessDayCalculator.add_business_days(
                        timezone.now().date(), sequence_info.min_delay_days
                    )
            
            # Set appropriate hour based on activity type
            hour = CONFIG.time.default_call_start_hour
            if activity.activity_type == Activity.ActivityType.EMAIL:
                hour = CONFIG.time.default_email_start_hour
            elif activity.activity_type == Activity.ActivityType.MEETING:
                hour = CONFIG.time.default_meeting_start_hour
            
            return timezone.datetime.combine(
                target_date,
                timezone.datetime.min.time().replace(hour=hour)
            ).replace(tzinfo=timezone.get_current_timezone())
            
        except Exception as e:
            # Fallback: return current time + 2 day
            print(f"Error calculating scheduled_start for activity {activity.id}: {str(e)}")
            return timezone.now() + timezone.timedelta(days=2)
    
    @classmethod
    def integrate_into_complete_activity(cls, activity: Activity, completion_result: Dict) -> Dict:
        """
        Méthode d'intégration à appeler dans CampaignResultService.complete_activity()
        
        Usage dans CampaignResultService.complete_activity():
        
        # Après activity.complete(), avant construction de la réponse finale
        if activity.next_activity or (hasattr(activity, 'sequence_info') and activity.sequence_info):
            from apps.campaign.services.campaign_queue_service import CampaignQueueService
            schedule_update = CampaignQueueService.integrate_into_complete_activity(activity, completion_result)
            completion_result['scheduled_dates_update'] = schedule_update
        
        Args:
            activity: L'activité complétée
            completion_result: Le dictionnaire de résultat de completion existant
            
        Returns:
            Dict: Informations sur la mise à jour des dates planifiées
        """
        try:
            # Mettre à jour les dates des activités suivantes
            update_result = cls._update_following_scheduled_dates(activity)
            
            # Enrichir le résultat avec des métadonnées
            update_result['integration_timestamp'] = timezone.now().isoformat()
            update_result['completed_activity_id'] = activity.id
            
            # Log optionnel pour debugging
            if update_result['updated_count'] > 0:
                print(f"Completion of activity {activity.id} triggered update of {update_result['updated_count']} following activities")
            
            return update_result
            
        except Exception as e:
            return {
                'updated_count': 0,
                'error': str(e),
                'integration_timestamp': timezone.now().isoformat(),
                'completed_activity_id': activity.id
            }


    @classmethod
    def get_prioritized_contacts_for_campaign(cls, campaign: Campaign, limit: int = 50) -> Response:
        """
        Get a prioritized list of contacts for a non-sequence campaign
        UPDATED: Uses State Machine for callback expiration
        
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
            
            
            
            # 🔧 MODIFIED: Use State Machine for expired callbacks instead of direct update
            today = date.today()
            expired_callback_targets = CampaignTarget.objects.filter(
                **{CONFIG.fields.campaign: campaign},
                status=CampaignTarget.Status.CALLBACK_PENDING,
                callback_date__lte=today  # Callback date is today or in the past
            )
            
            # Process expired callbacks with State Machine
            updated_count = 0
            for target in expired_callback_targets:
                try:
                    # 🔧 NEW: Use State Machine business trigger instead of direct update
                    expiry_result = target.expire_callback(
                        notes=f"Callback expired (was due: {target.callback_date})",
                        user=None  # System operation
                    )
                    
                    if expiry_result.get('status_updated'):
                        updated_count += 1
                        
                except Exception as e:
                    # Log error but continue processing other targets
                    print(f"Failed to expire callback for target {target.id}: {str(e)}")
            # 🔧 END MODIFICATION
            
            # Use the activity service to extract contacts
            from apps.campaign.services.campaign_activity_service import CampaignActivityService
            extraction_result = CampaignActivityService._extract_contacts_from_targets(campaign)
            valid_contacts = extraction_result['valid_contacts']
            skipped_contacts = extraction_result['skipped_contacts']
            contact_to_target_map = extraction_result['contact_to_target_map']
            
            # Get all campaign targets for this campaign
            campaign_targets = CampaignTarget.objects.filter(
                **{CONFIG.fields.campaign: campaign}
            ).select_related(
                CONFIG.fields.account, 
                CONFIG.fields.contact,
                CONFIG.fields.lead,
                CONFIG.fields.target_opportunity
            )
            
            # Create a map of contact_id to campaign_target for efficient lookup
            target_by_contact_id = {}
            for target in campaign_targets:
                if target.contact_id:
                    target_by_contact_id[target.contact_id] = target
            
            # Calculate priority score for each contact
            contacts_with_score = []
            
            for contact_info in valid_contacts:
                contact = contact_info[CONFIG.fields.contact]
                
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
                score += CONFIG.tiers.priority_scores.get(account_tier, 10)
                
                # Buying authority bonus
                if getattr(contact, 'has_buying_authority', False):
                    score += CONFIG.priorities.buying_authority_priority_boost
                
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
                    CONFIG.fields.contact: 15,      
                    CONFIG.fields.account: 10       # Base priority for account targets
                }
                score += type_priorities.get(target_type, 0)
                
                # Status adjustment
                if target.status == CampaignTarget.Status.IN_PROGRESS:
                    score += 15  # Bonus for targets already in progress
                
                # Callback priority - massive boost for callbacks due today or in the past
                if hasattr(target, 'callback_date') and target.callback_date:
                    # If callback is due today or in the past
                    if target.callback_date <= today:
                        score += CONFIG.priorities.callback_priority_boost    # Very high boost
                    else:
                        # Calculate days until callback
                        days_until_callback = (target.callback_date - today).days
                        # Reduce priority more for further dates
                        score -= days_until_callback * 10
                
                # Special status for CALLBACK_PENDING
                if target.status == CampaignTarget.Status.CALLBACK_PENDING:
                    score += CONFIG.priorities.callback_priority_boost // 2  # Half the boost of an actual callback date
                
                # Add the contact with its score to the list
                contacts_with_score.append({
                    f"{CONFIG.fields.contact}_id": contact.id,
                    f"{CONFIG.fields.contact}_name": f"{contact.first_name} {contact.last_name}",
                    'contact_first_name': contact.first_name,
                    'contact_last_name': contact.last_name,
                    'email': contact.email,
                    'phone': contact.phone,
                    'linkedin': getattr(contact, 'linkedin', None),
                    f"{CONFIG.fields.account}_id": account.id,
                    f"{CONFIG.fields.account}_name": account.company_name,
                    'target_type': target_type,
                    'target_id': target.id,
                    'has_phone': contact_info['has_phone'],
                    'has_email': contact_info['has_email'],
                    'has_linkedin': contact_info['has_linkedin'],
                    'priority_score': score,
                    'callback_date': target.callback_date.isoformat() if (hasattr(target, 'callback_date') and target.callback_date) else None,
                    'status': target.status,
                    'status_display': target.get_status_display() if hasattr(target, 'get_status_display') else target.status
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
                'callbacks_updated': updated_count  # 🔧 ENHANCED: Now includes State Machine updates
            }
            
            # Use CampaignResponseBuilder for standardized contact queue response
            return CampaignResponseBuilder.campaign_playlist(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                items=contacts_with_score,
                queue_type=CONFIG.fields.contact,
                is_sequence=False,
                activities_created=0,
                total_items=contact_counts['prioritized'],
                additional_data={
                    'total_pending': contact_counts['total'],
                    'skipped_contacts': skipped_contacts,
                    'counts': contact_counts,
                    'state_machine_integration': True,
                    'callbacks_expired_with_state_machine': updated_count
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
                    f"{CONFIG.fields.campaign}_id": campaign.id,
                    f"{CONFIG.fields.campaign}_name": campaign.name,
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
                message = CONFIG.messages.campaign_started.format(name=campaign.name)
                
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
            print(sequence_info)
            
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
                print(f"activity {activity} completed at {completed_date}")
                business_days_passed = BusinessDayCalculator.get_business_days_between(
                    completed_date, date.today())
                print(sequence_info.min_delay_days)
                return business_days_passed >= sequence_info.min_delay_days
            
            return False
        except Exception as e:
            print("Error calculating activity readiness:", str(e))
            # If calculation fails, default to not ready for safety
            return False
    
    @classmethod
    def _get_delay_status(cls, activity: Activity) -> Dict:
        """Get delay status information for an activity (using business days)"""
        try:
            from core.utils.business_days import BusinessDayCalculator
            
            if not hasattr(activity, 'sequence_info') or not activity.previous_activity:
                return {CONFIG.fields.status: 'ready', 'days_waiting': 0}
            
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
                        CONFIG.fields.status: 'waiting',
                        'business_days_waiting': business_days_waiting,
                        'ready_in_business_days': ready_in_days,
                        'ready_date': target_date
                    }
                elif business_days_waiting == 0:
                    return {
                        CONFIG.fields.status: 'ready', 
                        'business_days_waiting': 0,
                        'ready_date': today
                    }
                else:
                    return {
                        CONFIG.fields.status: 'overdue',
                        'business_days_waiting': business_days_waiting,
                        'business_days_overdue': business_days_waiting
                    }
            
            return {CONFIG.fields.status: 'pending_previous', 'business_days_waiting': 0}
        except Exception:
            # If calculation fails, default to ready status
            return {CONFIG.fields.status: 'ready', 'days_waiting': 0}

    @classmethod
    def _calculate_priority_score(cls, activity: Activity) -> float:
        """Calculate priority score for an activity based on various factors"""
        try:
            from core.utils.business_days import BusinessDayCalculator
            
            score = 0.0
            
            # Account tier priority (A=100, B=50, C=10)
            account_tier = getattr(activity.account, 'tier', 'C')
            score += CONFIG.tiers.priority_scores.get(account_tier, 10)

            # Contact buying authority bonus - OPTIMIZED: no additional query
            contact_buying_authority_bonus = 0
            
            try:
                # Access prefetched contacts
                prefetched_contacts = activity.contacts.all()
                
                # Check if any contact has buying authority
                for contact in prefetched_contacts:
                    if getattr(contact, 'has_buying_authority', False):
                        contact_buying_authority_bonus = CONFIG.priorities.buying_authority_priority_boost
                        break
                        
            except AttributeError:
                # Fallback if contacts not prefetched
                pass
            
            score += contact_buying_authority_bonus
            
            # Sequence position bonus (earlier steps get priority)
            sequence_info = getattr(activity, 'sequence_info', None)
            if sequence_info:
                # Higher bonus for earlier steps
                step_bonus = max(0, 11 - sequence_info.sequence_position) * CONFIG.priorities.sequence_step_priority_bonus
                score += step_bonus
                
                # Calculate delay bonus using business days
                if activity.previous_activity and activity.previous_activity.completed_at:
                    completed_date = activity.previous_activity.completed_at.date()
                    
                    business_days_passed = BusinessDayCalculator.get_business_days_between(
                        completed_date, date.today())
                        
                    business_days_overdue = business_days_passed - sequence_info.min_delay_days
                    
                    # Add bonus for overdue activities (business days)
                    if business_days_overdue > 0:
                        score += business_days_overdue * CONFIG.priorities.overdue_penalty_per_day
                
                # Callback requested priority boost
                if sequence_info.callback_requested_date:
                    if sequence_info.callback_requested_date <= date.today():
                        score += CONFIG.priorities.callback_priority_boost

            # Activity type priority
            score += CONFIG.priorities.activity_type_priorities.get(activity.activity_type, 0)
            
            return score
        except Exception:
            # If calculation fails, return base score
            return 10.0
    
    @classmethod
    def _get_queue_info(cls, campaign: Campaign, ready_activities: List, 
                all_campaign_activities: List = None) -> Dict:
        """
        Get summary information about the campaign queue
        🔧 MODIFIÉ : Utilise CampaignAnalyticsService pour éviter la duplication
        """
        try:
            # 🔧 NOUVEAU : Utiliser CampaignAnalyticsService pour les calculs de base
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            
            # Obtenir les métriques d'activités optimisées du service analytics
            activities_progress = CampaignAnalyticsService._calculate_activities_progress(campaign)
            
            # 🔧 SPÉCIFIQUE QUEUE : Calculer seulement les delay_status_counts (unique à la queue)
            delay_status_counts = {'ready': 0, 'waiting': 0, 'overdue': 0, 'pending_previous': 0}
            
            for item in ready_activities:
                delay_status = item['delay_status'][CONFIG.fields.status]
                if delay_status in delay_status_counts:
                    delay_status_counts[delay_status] += 1
            
            # 🔧 RÉUTILISER : Combiner les données du service analytics avec les données spécifiques à la queue
            return {
                # Réutiliser les calculs optimisés du service analytics
                'status_counts': {
                    'planned': activities_progress['planned_activities'],
                    'completed': activities_progress['completed_activities'],
                    'cancelled': activities_progress['cancelled_activities']
                },
                # Ajouter les calculs spécifiques à la queue
                'delay_status_counts': delay_status_counts,
                # Réutiliser le calcul de progression (completion_rate est déjà calculé)
                'progress_percentage': activities_progress['completion_rate'],
                'total_activities': activities_progress['total_activities'],
                # 🔧 BONUS : Ajouter les breakdown par type d'activité
                'type_breakdown': activities_progress.get('type_breakdown', {})
            }
            
        except Exception as e:
            # 🔧 FALLBACK : Si le service analytics échoue, utiliser calculs minimaux
            print(f"Warning: Failed to get analytics data for queue info, using fallback: {str(e)}")
            
            # Fallback simple sans duplication
            total_ready = len(ready_activities)
            delay_status_counts = {'ready': 0, 'waiting': 0, 'overdue': 0, 'pending_previous': 0}
            
            for item in ready_activities:
                delay_status = item['delay_status'][CONFIG.fields.status]
                if delay_status in delay_status_counts:
                    delay_status_counts[delay_status] += 1
            
            return {
                'status_counts': {'planned': total_ready, 'completed': 0, 'cancelled': 0},
                'delay_status_counts': delay_status_counts,
                'progress_percentage': 0,
                'total_activities': total_ready,
                'error': f'Analytics service unavailable: {str(e)}'
            }
