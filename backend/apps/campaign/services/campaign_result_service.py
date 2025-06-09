# apps/campaign/services/campaign_result_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact
from apps.sequence.sequences.chasing_sequence import ChasingSequence
from apps.campaign.config.variables import TIER_MAX_ATTEMPTS, TIER_PRIORITY_SCORES


class CampaignResultService:
    """
    Service for handling campaign activity results and managing sequence progression
    """
    
    @classmethod
    def process_activity_result(cls, activity: Activity, result: str, 
                               notes: str = None, **kwargs) -> Dict:
        """
        Process the result of an activity and handle appropriate actions
        Works for both sequence and non-sequence campaigns
        
        Args:
            activity: The completed activity
            result: The outcome ('NO_ANSWER', 'NOT_INTERESTED', 'CALLBACK_REQUESTED', 'SUCCESSFUL', etc.)
            notes: Optional notes about the result
            **kwargs: Additional data like callback_date, meeting_date
            
        Returns:
            Dictionary with the result processing information
        """
        with transaction.atomic():
            # Check if this is a sequence or non-sequence activity
            is_sequence_campaign = False
            if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign.sequence_type:
                is_sequence_campaign = True
            
            # For call activities
            if activity.activity_type == Activity.ActivityType.CALL:
                return cls._handle_call_result(activity, result, notes, is_sequence_campaign, **kwargs)
            else:
                return cls._handle_email_linkedin_result(activity, result, notes, is_sequence_campaign, **kwargs)

    
    @classmethod
    def _handle_call_result(cls, activity: Activity, result: str, 
                       notes: str = None, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle call activity results with unified logic for sequence and non-sequence campaigns
        """
        sequence_info = getattr(activity, 'sequence_info', None)
        campaign_info = getattr(activity, 'campaign_info', None)
        
        if result == 'INVALID_PHONE_NUMBER':
            return cls._handle_invalid_phone_number(activity, sequence_info, notes, is_sequence_campaign)
        
        elif result == 'NO_ANSWER':
            return cls._handle_no_answer_call(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
        
        elif result == 'NOT_RIGHT_CONTACT':
            return cls._handle_wrong_contact(activity, sequence_info, notes, is_sequence_campaign)
        
        elif result == 'CALLBACK_REQUESTED':
            return cls._handle_callback_requested(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
        
        elif result == 'CONTACT_NOT_AVAILABLE':
            return cls._handle_contact_not_available(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
        
        elif result == 'NOT_INTERESTED':
            return cls._handle_not_interested(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
        
        elif result == 'SUCCESSFUL':
            return cls._handle_successful_call(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
        
        else:
            return {'success': False, 'error': f'Unknown result: {result}'}
        
    @classmethod
    def _handle_invalid_phone_number(cls, activity: Activity, sequence_info: ActivitySequence,
                                    notes: str, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle invalid phone number - regenerate sequence without phone
        """
        contact = activity.contacts.first()
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
        
        # Complete current activity
        activity.complete(outcome_notes=f"Invalid phone number. {notes}" if notes else "Invalid phone number")
        
        # Mark contact as having no valid phone
        if contact:
            contact.phone_is_valid = False
            contact.save()
        
        # Cancel all remaining activities for this contact in this campaign
        if is_sequence_campaign: 
            remaining_activities = Activity.objects.filter(
                campaign_info__campaign=campaign,
                contacts=contact,
                status=Activity.Status.PLANNED
            )
            remaining_activities.update(status=Activity.Status.CANCELLED, outcome_notes="Cancelled due to invalid phone - sequence regenerated")
        
            # Regenerate sequence without phone
            new_activities = cls._regenerate_sequence_without_phone(
                campaign, campaign_target, contact, sequence_info.sequence_position
            )
        
            return {
                'success': True,
                'action': 'sequence_regenerated',
                'message': f'Invalid phone number. Regenerated sequence without phone calls',
                'new_activities_count': len(new_activities)
            }
        
        return {
                'success': True,
                'message': f'Invalid phone number.',
            }

    
    @classmethod
    def _handle_email_bounced(cls, activity: Activity, sequence_info: ActivitySequence,
                             notes: str, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle bounced email - regenerate sequence without email
        """
        contact = activity.contacts.first()
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
        
        # Complete current activity
        activity.complete(outcome_notes=f"Email bounced. {notes}" if notes else "Email bounced")
        
        # Mark contact as having invalid email
        if contact:
            contact.email_is_valid = False
            contact.save()
        
        if is_sequence_campaign:
            # Cancel all remaining activities for this contact in this campaign
            remaining_activities = Activity.objects.filter(
                campaign_info__campaign=campaign,
                contacts=contact,
                status=Activity.Status.PLANNED
            )
            remaining_activities.update(status=Activity.Status.CANCELLED, outcome_notes="Cancelled due to bounced email - sequence regenerated")
            
            # Regenerate sequence without email
            has_phone = bool(contact.phone and getattr(contact, 'phone_is_valid', True))
            has_linkedin = bool(contact.linkedin)
            
            new_activities = cls._regenerate_sequence_for_contact(
                campaign, campaign_target, contact, sequence_info.sequence_position,
                has_phone=has_phone, has_email=False, has_linkedin=has_linkedin
            )
            
            return {
                'success': True,
                'action': 'sequence_regenerated',
                'message': f'Email bounced. Regenerated sequence without emails',
                'new_activities_count': len(new_activities)
            }
    
        return {
            'success': True,
            'message': f'Email bounced.',
        }
    
    @classmethod
    def _regenerate_sequence_without_phone(cls, campaign: Campaign, campaign_target: CampaignTarget,
                                         contact: Contact, current_step: int) -> List[Activity]:
        """
        Regenerate sequence starting from current step, without phone calls
        """
        has_email = bool(contact.email and getattr(contact, 'email_is_valid', True))
        has_linkedin = bool(contact.linkedin)
        
        return cls._regenerate_sequence_for_contact(
            campaign, campaign_target, contact, current_step,
            has_phone=False, has_email=has_email, has_linkedin=has_linkedin
        )
    
    @classmethod
    def _regenerate_sequence_for_contact(cls, campaign: Campaign, campaign_target: CampaignTarget,
                                       contact: Contact, start_from_step: int,
                                       has_phone: bool, has_email: bool, has_linkedin: bool) -> List[Activity]:
        """
        Regenerate sequence for a contact starting from a specific step
        """
        # Get the appropriate sequence based on available channels
        if has_phone and has_email:
            sequence_dict = ChasingSequence.get_standard_sequence()
        elif not has_phone and has_email and has_linkedin:
            sequence_dict = ChasingSequence.get_sequence_without_phone()
        elif has_phone and not has_email and has_linkedin:
            sequence_dict = ChasingSequence.get_sequence_without_email()
        elif has_phone and not (has_email or has_linkedin):
            sequence_dict = ChasingSequence.get_sequence_phone_only()
        else:
            # If no valid channels, return empty list
            return []
        
        # Calculate which steps to create based on current progress
        # Map the current step to the new sequence
        steps_to_create = []
        
        # For simplicity, let's continue with remaining steps in new sequence
        # Starting from next logical step
        remaining_steps = len(sequence_dict) - start_from_step + 1
        
        new_activities = []
        previous_activity = None
        
        # Get the last completed activity to link properly
        last_completed = Activity.objects.filter(
            campaign_info__campaign=campaign,
            contacts=contact,
            status=Activity.Status.COMPLETED,
            sequence_info__isnull=False
        ).order_by('-sequence_info__sequence_position').first()
        
        # Create activities starting from the next logical step
        for i, (step_num, step_config) in enumerate(sequence_dict.items(), 1):
            if i <= start_from_step:
                continue  # Skip already completed/current steps
            
            # Create the activity
            activity = cls._create_regenerated_activity(
                campaign=campaign,
                campaign_target=campaign_target,
                contact=contact,
                step_number=step_num,
                step_config=step_config,
                previous_activity=last_completed if not new_activities else new_activities[-1]
            )
            
            new_activities.append(activity)
            
            # Link to previous activity
            if last_completed and not previous_activity:
                last_completed.next_activity = activity
                activity.previous_activity = last_completed
                last_completed.save()
                activity.save()
            
            previous_activity = activity
        
        return new_activities
    
    @classmethod
    def _create_regenerated_activity(cls, campaign: Campaign, campaign_target: CampaignTarget,
                                   contact: Contact, step_number: int, step_config: Dict,
                                   previous_activity: Activity = None) -> Activity:
        """
        Create a single regenerated activity
        """
        # Import here to avoid circular imports
        from apps.campaign.services.campaign_activity_service import CampaignActivityService
        
        # Use the same logic as the original activity creation
        return CampaignActivityService._create_single_activity(
            campaign=campaign,
            campaign_target=campaign_target,
            contact=contact,
            step_number=step_number,
            step_config=step_config,
            previous_activity=previous_activity
        )
    
    @classmethod
    def _handle_no_answer_call(cls, activity: Activity, sequence_info: ActivitySequence,
                              notes: str = None, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle no answer for calls - increment attempts based on tier
        """
        if is_sequence_campaign:
            # Get tier-based max attempts
            account_tier = getattr(activity.account, 'tier', 'C')
            tier_max_attempts = TIER_MAX_ATTEMPTS.get(account_tier, 2)
            
            # Increment call attempts
            if sequence_info:
                sequence_info.call_attempts += 1
                sequence_info.save()
            
            # Check if we've reached max attempts for this tier
            if sequence_info and sequence_info.call_attempts >= tier_max_attempts:
                # Mark activity as completed and move to next step
                activity.complete(outcome_notes=f"No answer after {sequence_info.call_attempts} attempts")
                
                # Make next activity ready if it exists
                cls._activate_next_activity(activity)
                
                return {
                    'success': True,
                    'action': 'activity_completed',
                    'message': f'Call completed after {sequence_info.call_attempts} attempts',
                    'attempts_made': sequence_info.call_attempts,
                    'max_attempts': tier_max_attempts
                }
            else:
                # Activity stays active for another attempt
                activity.outcome_notes = f"No answer - attempt {sequence_info.call_attempts}/{tier_max_attempts}"
                if notes:
                    activity.outcome_notes += f". {notes}"
                activity.save()
                
                return {
                    'success': True,
                    'action': 'retry_needed',
                    'message': f'Attempt {sequence_info.call_attempts}/{tier_max_attempts} - try again',
                    'attempts_made': sequence_info.call_attempts,
                    'max_attempts': tier_max_attempts
                }
        else:
            """
            Handle no answer for calls in non-sequence campaigns
            """
            # Complete the activity but leave contact in the queue
            activity.complete(outcome_notes=f"No answer. {notes}" if notes else "No answer")
            
            # We could increment a counter in the campaign target if needed
            # campaign_target.no_answer_count = (campaign_target.no_answer_count or 0) + 1
            # campaign_target.save()
            
            return {
                'success': True,
                'action': 'completed_no_change',
                'message': 'Activity completed but contact remains in queue',
                'is_sequence_campaign': False
            }

    
    @classmethod
    def _handle_wrong_contact(cls, activity: Activity, sequence_info: ActivitySequence,
                             notes: str, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle wrong contact - remove this contact from sequence
        """
        # Complete current activity
        activity.complete(outcome_notes=f"Wrong contact. {notes}" if notes else "Wrong contact")


        # Cancel remaining activities for this contact in this campaign
        cls._cancel_contact_sequence(activity)
        
        return {
            'success': True,
            'action': 'contact_removed',
            'message': 'Contact removed from sequence (wrong contact)'
        }
    
    @classmethod
    def _handle_callback_requested(cls, activity: Activity, sequence_info: ActivitySequence,
                              notes: str, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle callback request - pause sequence or prioritize contact for non-sequence campaigns
        """
        callback_date = kwargs.get('callback_date')
        callback_type = kwargs.get('callback_type', activity.activity_type)
        
        if not callback_date:
            return {'success': False, 'error': 'Callback date is required'}
        
        # Complete current activity
        activity.complete(outcome_notes=f"Callback requested for {callback_date}. {notes}" if notes else f"Callback requested for {callback_date}")
        
        # Common behavior: update campaign target status
        if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign_target:
            campaign_target = activity.campaign_info.campaign_target
            # Mark campaign target with a special status or field for callback tracking
            campaign_target.callback_date = callback_date  # This field would need to be added to the CampaignTarget model
            campaign_target.save()
        
        # Sequence-specific behavior
        if is_sequence_campaign and sequence_info:
            sequence_info.callback_requested_date = callback_date
            sequence_info.sequence_paused_until = callback_date
            sequence_info.save()
            
            # Update next activity if it exists
            next_activity = activity.next_activity
            if next_activity:
                # Update next activity type if specified
                if callback_type != next_activity.activity_type:
                    next_activity.activity_type = callback_type
                    next_activity.title = f"Callback: {next_activity.title}"
                    next_activity.save()
        
        # Non-sequence specific behavior
        else:
            # For non-sequence campaigns, we need to ensure this contact is prioritized when the callback date comes
            contact = activity.contacts.first()
            if contact:
                # We could add a special field to track callbacks for non-sequence campaigns
                # For example, by adding a contact_status field to CampaignTarget
                if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign_target:
                    campaign_target = activity.campaign_info.campaign_target
                    campaign_target.status = 'CALLBACK_PENDING'  # Custom status for non-sequence targets
                    campaign_target.save()
        
        return {
            'success': True,
            'action': 'callback_scheduled',
            'message': f'Contact will be called back on {callback_date}',
            'callback_date': callback_date,
            'callback_type': callback_type,
            'is_sequence_campaign': is_sequence_campaign
        }
    
    @classmethod
    def _handle_successful_call(cls, activity: Activity, sequence_info: ActivitySequence,
                            notes: str, is_sequence_campaign: bool = True, **kwargs) -> Dict:
        """
        Handle successful call - create meeting and manage campaign target appropriately
        Works for both sequence and non-sequence campaigns
        """
        meeting_date = kwargs.get('meeting_date')
        
        # Complete current activity
        activity.complete(outcome_notes=f"Successfully scheduled meeting. {notes}" if notes else "Successfully scheduled meeting")
        
        # Get campaign information
        campaign = None
        campaign_target = None
        if hasattr(activity, 'campaign_info'):
            campaign_info = activity.campaign_info
            campaign = campaign_info.campaign
            campaign_target = campaign_info.campaign_target
        
        # Update campaign info
        if hasattr(activity, 'campaign_info'):
            campaign_info = activity.campaign_info
            campaign_info.meeting_scheduled = True
            campaign_info.save()
            
            # Update campaign target status
            if campaign_target:
                campaign_target.update_status(CampaignTarget.Status.MEETING_SECURED)
        
        # Create meeting activity if date provided
        if meeting_date:
            cls._create_meeting_activity(activity, meeting_date, notes)
        
        # For sequence campaigns, end the sequence
        if is_sequence_campaign:
            cls._complete_contact_sequence(activity)
        else:
            # For non-sequence campaigns, remove contact from queue
            if campaign_target:
                # Mark as completed so it doesn't appear in contact list
                campaign_target.status = CampaignTarget.Status.COMPLETED
                campaign_target.save()
        
        # Update campaign objectives
        cls._update_campaign_objectives(activity, 'meeting_scheduled')
        
        # Determine which AE should receive this opportunity if it's converted later
        assigned_ae = None
        if campaign:
            from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
            receivers = campaign.get_receivers()
            
            if receivers.exists():
                assigned_ae = receivers.first()
        
        return {
            'success': True,
            'action': 'meeting_scheduled',
            'message': 'Meeting scheduled successfully',
            'meeting_date': meeting_date,
            'assigned_ae': assigned_ae.id if assigned_ae else None,
            'is_sequence_campaign': is_sequence_campaign
        }
    
    @classmethod
    def _handle_not_interested(cls, activity: Activity, sequence_info: ActivitySequence,
                              notes: str, **kwargs) -> Dict:
        """
        Handle not interested - option to disqualify contact or whole account
        """
        disqualify_account = kwargs.get('disqualify_account', False)
        
        # Complete current activity
        activity.complete(outcome_notes=f"Not interested. {notes}" if notes else "Not interested")
        
        if disqualify_account:
            # Cancel all activities for this account in this campaign
            cls._cancel_account_sequence(activity)
            return {
                'success': True,
                'action': 'account_disqualified',
                'message': 'Account removed from campaign (not interested)'
            }
        else:
            # Cancel remaining activities for just this contact
            cls._cancel_contact_sequence(activity)
            return {
                'success': True,
                'action': 'contact_disqualified',
                'message': 'Contact removed from sequence (not interested)'
            }
    
    
    @classmethod
    def _handle_email_linkedin_result(cls, activity: Activity, result: str,
                                     notes: str = None, **kwargs) -> Dict:
        """
        Handle email/LinkedIn activity results
        """
        sequence_info = getattr(activity, 'sequence_info', None)
        
        # For emails/LinkedIn, typically we just complete and move to next
        # unless there's a specific response
        
        if result == 'NO_RESPONSE':
            # Wait for min_delay, then auto-progress to next step
            activity.complete(outcome_notes=f"No response. {notes}" if notes else "No response")
            cls._activate_next_activity(activity)
            
            return {
                'success': True,
                'action': 'completed_moving_next',
                'message': 'Email/LinkedIn sent, moving to next step'
            }
        
        elif result == 'POSITIVE_RESPONSE':
            return cls._handle_successful_call(activity, sequence_info, notes, **kwargs)
        
        elif result == 'UNSUBSCRIBE_OPTOUT':
            activity.complete(outcome_notes=f"Unsubscribed/Opted out. {notes}" if notes else "Unsubscribed/Opted out")
            cls._cancel_contact_sequence(activity)
            
            return {
                'success': True,
                'action': 'contact_removed',
                'message': 'Contact removed from sequence (unsubscribed)'
            }
        
        else:
            # Default: complete and move to next
            activity.complete(outcome_notes=notes)
            cls._activate_next_activity(activity)
            
            return {
                'success': True,
                'action': 'completed',
                'message': 'Activity completed'
            }
    
    @classmethod
    def _activate_next_activity(cls, current_activity: Activity):
        """
        Activate the next activity in the sequence
        """
        next_activity = current_activity.next_activity
        if next_activity and next_activity.status == Activity.Status.PLANNED:
            # The queue service will handle when it becomes ready based on working days
            pass
    
    @classmethod
    def _cancel_contact_sequence(cls, activity: Activity):
        """
        Cancel remaining activities for this contact in this campaign
        For non-sequence campaigns, update the campaign target status
        """
        contact = activity.contacts.first()
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
        
        # Cancel planned activities for this contact
        if contact and campaign:
            Activity.objects.filter(
                campaign_info__campaign=campaign,
                contacts=contact,
                status=Activity.Status.PLANNED
            ).update(status=Activity.Status.CANCELLED)
        
        # For non-sequence campaigns, update the target status
        if campaign and campaign.sequence_type is None and campaign_target:
            campaign_target.status = CampaignTarget.Status.STOPPED
            campaign_target.save()
    
    @classmethod
    def _cancel_account_sequence(cls, activity: Activity):
        """
        Cancel remaining activities for this account in this campaign
        """
        account = activity.account
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        
        if account and campaign:
            Activity.objects.filter(
                campaign_info__campaign=campaign,
                account=account,
                status=Activity.Status.PLANNED
            ).update(status=Activity.Status.CANCELLED)
    
    @classmethod
    def _complete_contact_sequence(cls, activity: Activity):
        """
        Mark sequence as completed for this contact
        """
        cls._cancel_contact_sequence(activity)
    
    @classmethod
    def _create_meeting_activity(cls, activity: Activity, meeting_date: date, notes: str):
        """
        Create a meeting activity from successful sequence
        """
        # Create meeting activity
        meeting_activity = Activity.objects.create(
            title=f"Meeting with {activity.account.company_name}",
            activity_type=Activity.ActivityType.MEETING,
            description=f"Meeting scheduled from {activity.title}. {notes}" if notes else f"Meeting scheduled from {activity.title}",
            account=activity.account,
            owner=activity.owner,
            scheduled_start=timezone.make_aware(timezone.datetime.combine(meeting_date, timezone.datetime.min.time().replace(hour=10))),
            status=Activity.Status.PLANNED
        )
        
        # Link contacts
        meeting_activity.contacts.set(activity.contacts.all())
        
        # Link to campaign if applicable
        if hasattr(activity, 'campaign_info'):
            from apps.activities.models import ActivityCampaign
            ActivityCampaign.objects.create(
                activity=meeting_activity,
                campaign=activity.campaign_info.campaign,
                campaign_target=activity.campaign_info.campaign_target
            )
    
    @classmethod
    def _update_campaign_objectives(cls, activity: Activity, objective_type: str):
        """
        Update campaign objectives based on activity results
        """
        if not hasattr(activity, 'campaign_info'):
            return
        
        campaign = activity.campaign_info.campaign
        
        # Update relevant objectives
        from apps.campaign.models.campaign_objective import CampaignObjective
        
        if objective_type == 'meeting_scheduled':
            meeting_objectives = campaign.objectives.filter(
                objective_type=CampaignObjective.ObjectiveType.MEETINGS
            )
            for objective in meeting_objectives:
                objective.update_progress(1, increment=True)