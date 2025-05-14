# apps/sequence/services/chasing_sequence.py
from typing import List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from apps.activities.models import Activity, ActivitySequence
from apps.accounts.models import Contact
from apps.campaign.models import Campaign, CampaignTarget


class ChasingSequenceService:
    """
    Service to handle chasing sequence creation and management
    """
    
    # Define the 10-step chasing sequence
    SEQUENCE_STEPS = [
        {
            'step': 1,
            'type': Activity.ActivityType.CALL,
            'title': 'Initial Outreach Call',
            'min_delay_days': 0,
            'description': 'First contact attempt - introduce yourself and company'
        },
        {
            'step': 2,
            'type': Activity.ActivityType.EMAIL,
            'title': 'Follow-up Email',
            'min_delay_days': 1,
            'description': 'Send introduction email with company information'
        },
        {
            'step': 3,
            'type': Activity.ActivityType.CALL,
            'title': 'Second Call Attempt',
            'min_delay_days': 2,
            'description': 'Follow up on initial call and email'
        },
        {
            'step': 4,
            'type': Activity.ActivityType.EMAIL,
            'title': 'Value Proposition Email',
            'min_delay_days': 3,
            'description': 'Share specific value proposition and case studies'
        },
        {
            'step': 5,
            'type': Activity.ActivityType.CALL,
            'title': 'Third Call Attempt',
            'min_delay_days': 2,
            'description': 'Discuss potential solutions and pain points'
        },
        {
            'step': 6,
            'type': Activity.ActivityType.EMAIL,
            'title': 'Case Study Email',
            'min_delay_days': 4,
            'description': 'Send relevant case study and success stories'
        },
        {
            'step': 7,
            'type': Activity.ActivityType.CALL,
            'title': 'Fourth Call Attempt',
            'min_delay_days': 3,
            'description': 'Address any concerns and discuss next steps'
        },
        {
            'step': 8,
            'type': Activity.ActivityType.EMAIL,
            'title': 'Last Opportunity Email',
            'min_delay_days': 7,
            'description': 'Final attempt to engage with limited-time offer'
        },
        {
            'step': 9,
            'type': Activity.ActivityType.CALL,
            'title': 'Final Call',
            'min_delay_days': 3,
            'description': 'Last call attempt before closing sequence'
        },
        {
            'step': 10,
            'type': Activity.ActivityType.EMAIL,
            'title': 'Breakup Email',
            'min_delay_days': 7,
            'description': 'Professional breakup email, leave door open for future'
        }
    ]
    
    @classmethod
    def create_sequence_for_target(cls, campaign: Campaign, campaign_target: CampaignTarget) -> List[Activity]:
        """
        Create a complete chasing sequence for a campaign target
        
        Args:
            campaign: The campaign this sequence belongs to
            campaign_target: The target (account) for the sequence
            
        Returns:
            List of created activities
        """
        # Get all active contacts for the account
        contacts = Contact.objects.filter(
            account=campaign_target.account,
            is_active=True
        )
        
        if not contacts.exists():
            raise ValueError(f"No active contacts found for account {campaign_target.account.company_name}")
        
        created_activities = []
        
        # Create sequence for each contact
        for contact in contacts:
            activities = cls.create_sequence_for_contact(campaign, campaign_target, contact)
            created_activities.extend(activities)
        
        # Mark sequence as created for the target
        campaign_target.mark_sequence_created()
        
        return created_activities
    
    @classmethod
    def create_sequence_for_contact(cls, campaign: Campaign, campaign_target: CampaignTarget, contact: Contact) -> List[Activity]:
        """
        Create a chasing sequence for a specific contact
        
        Args:
            campaign: The campaign this sequence belongs to
            campaign_target: The campaign target
            contact: The specific contact for the sequence
            
        Returns:
            List of created activities
        """
        created_activities = []
        current_date = timezone.now().date()
        
        with transaction.atomic():
            previous_activity = None
            
            for step_data in cls.SEQUENCE_STEPS:
                # Calculate scheduled date based on previous activity
                if step_data['step'] == 1:
                    scheduled_date = current_date
                else:
                    scheduled_date = current_date + timedelta(days=step_data['min_delay_days'])
                    current_date = scheduled_date
                
                # Create the activity
                activity = cls._create_sequence_activity(
                    campaign=campaign,
                    campaign_target=campaign_target,
                    contact=contact,
                    step_data=step_data,
                    scheduled_date=scheduled_date,
                    previous_activity=previous_activity
                )
                
                created_activities.append(activity)
                previous_activity = activity
        
        return created_activities
    
    @classmethod
    def _create_sequence_activity(cls, campaign: Campaign, campaign_target: CampaignTarget, 
                                 contact: Contact, step_data: dict, scheduled_date: datetime.date,
                                 previous_activity: Activity = None) -> Activity:
        """
        Create a single sequence activity
        
        Args:
            campaign: The campaign
            campaign_target: The campaign target  
            contact: The contact
            step_data: Step configuration from SEQUENCE_STEPS
            scheduled_date: When the activity is scheduled
            previous_activity: The previous activity in the sequence
            
        Returns:
            Created Activity instance
        """
        # Convert date to datetime (9 AM default for calls, flexible for emails)
        if step_data['type'] == Activity.ActivityType.CALL:
            scheduled_datetime = timezone.make_aware(
                datetime.combine(scheduled_date, datetime.min.time().replace(hour=9))
            )
            # Calls typically last 30 minutes
            scheduled_end = scheduled_datetime + timedelta(minutes=30)
        else:
            # Emails can be scheduled at any time, default to 10 AM
            scheduled_datetime = timezone.make_aware(
                datetime.combine(scheduled_date, datetime.min.time().replace(hour=10))
            )
            scheduled_end = None
        
        # Create the activity
        activity = Activity.objects.create(
            title=step_data['title'],
            activity_type=step_data['type'],
            description=step_data['description'],
            account=campaign_target.account,
            owner=campaign.owner,
            scheduled_start=scheduled_datetime,
            scheduled_end=scheduled_end,
            status=Activity.Status.PLANNED
        )
        
        # Add the contact
        activity.contacts.set([contact])
        
        # Create campaign information
        from apps.activities.models import ActivityCampaign
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target
        )
        
        # Create sequence information
        sequence_info = ActivitySequence.objects.create(
            activity=activity,
            source_type=ActivitySequence.SourceType.CAMPAIGN,
            sequence_position=step_data['step']
        )
        
        # Link to previous activity in sequence
        if previous_activity and hasattr(previous_activity, 'sequence_info'):
            previous_activity.sequence_info.next_sequence_activity = activity
            previous_activity.sequence_info.save()
        
        return activity
    
    @classmethod
    def handle_sequence_progression(cls, completed_activity: Activity, outcome: str) -> Activity:
        """
        Handle what happens when a sequence activity is completed
        
        Args:
            completed_activity: The activity that was just completed
            outcome: The outcome of the activity
            
        Returns:
            Next activity in sequence or None if sequence should end
        """
        if not hasattr(completed_activity, 'sequence_info'):
            return None
        
        sequence_info = completed_activity.sequence_info
        
        # Handle different outcomes
        if outcome == ActivitySequence.SequenceOutcome.NO_ANSWER:
            # Continue to next step if available
            if sequence_info.next_sequence_activity:
                return sequence_info.next_sequence_activity
        
        elif outcome == ActivitySequence.SequenceOutcome.NOT_INTERESTED:
            # End sequence - could implement logic to pause/stop future activities
            cls._end_sequence_for_contact(completed_activity)
            return None
        
        elif outcome == ActivitySequence.SequenceOutcome.MEETING_SCHEDULED:
            # End sequence and update campaign target
            cls._complete_sequence_successfully(completed_activity)
            return None
        
        elif outcome == ActivitySequence.SequenceOutcome.CALLBACK_REQUESTED:
            # Handle callback - reschedule next activity
            if sequence_info.next_sequence_activity:
                return cls._handle_callback_request(completed_activity)
        
        return None
    
    @classmethod
    def _end_sequence_for_contact(cls, activity: Activity):
        """End the sequence for a specific contact (not interested)"""
        if not hasattr(activity, 'sequence_info'):
            return
        
        # Option 1: Just this contact
        # Cancel all future activities for this contact in this campaign
        future_activities = Activity.objects.filter(
            campaign_info__campaign=activity.campaign_info.campaign,
            contacts=activity.contacts.first(),
            status=Activity.Status.PLANNED,
            sequence_info__sequence_position__gt=activity.sequence_info.sequence_position
        )
        
        for future_activity in future_activities:
            future_activity.cancel(reason="Contact not interested")
    
    @classmethod
    def _complete_sequence_successfully(cls, activity: Activity):
        """Complete the sequence successfully (meeting scheduled)"""
        if not hasattr(activity, 'campaign_info'):
            return
        
        # Update campaign target status
        campaign_target = activity.campaign_info.campaign_target
        campaign_target.update_status(CampaignTarget.Status.MEETING_SECURED)
        
        # Cancel remaining sequence activities for this contact
        future_activities = Activity.objects.filter(
            campaign_info__campaign=activity.campaign_info.campaign,
            contacts=activity.contacts.first(),
            status=Activity.Status.PLANNED,
            sequence_info__sequence_position__gt=activity.sequence_info.sequence_position
        )
        
        for future_activity in future_activities:
            future_activity.cancel(reason="Meeting scheduled - sequence completed")
    
    @classmethod
    def _handle_callback_request(cls, activity: Activity) -> Activity:
        """Handle callback request - reschedule next activity"""
        if not hasattr(activity, 'sequence_info') or not activity.sequence_info.next_sequence_activity:
            return None
        
        sequence_info = activity.sequence_info
        next_activity = sequence_info.next_sequence_activity
        callback_date = sequence_info.callback_requested_date
        
        if callback_date:
            # Reschedule next activity to the callback date
            next_activity.scheduled_start = timezone.make_aware(
                datetime.combine(callback_date, next_activity.scheduled_start.time())
            )
            
            # Add note about the callback
            next_activity.description += f"\n\nRescheduled to {callback_date} per contact request"
            next_activity.save()
        
        return next_activity
    
    @classmethod
    def get_sequence_status(cls, campaign: Campaign, contact: Contact = None, account_id: int = None) -> dict:
        """
        Get the current status of a sequence for a campaign
        
        Args:
            campaign: The campaign to check
            contact: Specific contact (optional)
            account_id: Specific account ID (optional)
            
        Returns:
            Dictionary with sequence status information
        """
        # Build query
        activities_query = Activity.objects.filter(
            campaign_info__campaign=campaign,
            sequence_info__isnull=False
        )
        
        if contact:
            activities_query = activities_query.filter(contacts=contact)
        elif account_id:
            activities_query = activities_query.filter(account_id=account_id)
        
        # Get all sequence activities
        activities = activities_query.order_by('sequence_info__sequence_position')
        
        if not activities.exists():
            return {'status': 'not_started', 'activities': []}
        
        # Analyze the sequence status
        status_info = {
            'status': 'in_progress',
            'total_steps': 10,
            'completed_steps': activities.filter(status=Activity.Status.COMPLETED).count(),
            'current_step': None,
            'next_activity': None,
            'activities': []
        }
        
        for activity in activities:
            activity_data = {
                'id': activity.id,
                'step': activity.sequence_info.sequence_position,
                'type': activity.activity_type,
                'title': activity.title,
                'status': activity.status,
                'outcome': activity.sequence_info.sequence_outcome,
                'scheduled_start': activity.scheduled_start
            }
            status_info['activities'].append(activity_data)
            
            # Find current step
            if activity.status == Activity.Status.PLANNED and not status_info['current_step']:
                status_info['current_step'] = activity.sequence_info.sequence_position
                status_info['next_activity'] = activity_data
        
        # Determine overall status
        if status_info['completed_steps'] == 0:
            status_info['status'] = 'not_started'
        elif status_info['completed_steps'] == 10:
            status_info['status'] = 'completed'
        elif not status_info['current_step']:
            # All activities either completed or cancelled
            last_outcome = activities.filter(status=Activity.Status.COMPLETED).last()
            if last_outcome and hasattr(last_outcome, 'sequence_info'):
                outcome = last_outcome.sequence_info.sequence_outcome
                if outcome == ActivitySequence.SequenceOutcome.MEETING_SCHEDULED:
                    status_info['status'] = 'success'
                elif outcome == ActivitySequence.SequenceOutcome.NOT_INTERESTED:
                    status_info['status'] = 'ended'
        
        return status_info