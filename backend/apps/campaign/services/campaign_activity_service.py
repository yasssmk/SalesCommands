# apps/campaign/services/campaign_activity_service.py (revised)
from typing import List, Dict
from django.db import transaction
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.sequence.sequences.chasing_sequence import ChasingSequence
from apps.accounts.models import Contact


class CampaignActivityService:
    """
    Service for creating and managing campaign activities based on sequences
    """
    
    @classmethod
    def create_activities_for_campaign(cls, campaign: Campaign) -> Dict:
        """
        Create activities for all targets in a campaign
        
        Returns:
            Dictionary with creation summary
        """
        created_count = 0
        skipped_contacts = []
        
        with transaction.atomic():
            for campaign_target in campaign.targets.all():
                contacts = campaign_target.account.contacts.filter(is_active=True)
                
                for contact in contacts:
                    # Analyze contact channels
                    has_phone = bool(contact.phone)
                    has_email = bool(contact.email)  
                    has_linkedin = bool(contact.linkedin)
                    
                    # Skip if no communication channels
                    if not (has_phone or has_email or has_linkedin):
                        skipped_contacts.append({
                            'contact': contact.full_name,
                            'reason': 'No communication channels available'
                        })
                        continue
                    
                    # Create activities for this contact
                    activities_created = cls._create_activities_for_contact(
                        campaign=campaign,
                        campaign_target=campaign_target,
                        contact=contact,
                        has_phone=has_phone,
                        has_email=has_email,
                        has_linkedin=has_linkedin
                    )
                    
                    created_count += len(activities_created)
        
        return {
            'total_activities_created': created_count,
            'skipped_contacts': skipped_contacts,
            'success': True
        }
    
    @classmethod
    def _create_activities_for_contact(cls, campaign: Campaign, campaign_target: CampaignTarget, 
                                     contact: Contact, has_phone: bool, has_email: bool, 
                                     has_linkedin: bool) -> List[Activity]:
        """
        Create sequence activities for a specific contact (no scheduled dates)
        """
        # Get the appropriate sequence based on available channels
        if has_phone and has_email:
            sequence_dict = ChasingSequence.get_standard_sequence()
        elif not has_phone and has_email:
            sequence_dict = ChasingSequence.get_sequence_without_phone()
        elif has_phone and not has_email and has_linkedin:
            sequence_dict = ChasingSequence.get_sequence_without_email()
        elif has_phone and not (has_email or has_linkedin):
            sequence_dict = ChasingSequence.get_sequence_phone_only()
        else:
            # Fallback case - should rarely happen due to earlier check
            sequence_dict = ChasingSequence.get_sequence_without_phone()
        
        activities = []
        previous_activity = None
        
        # Create activities for each step in the sequence
        for step_number, step_config in sequence_dict.items():
            activity = cls._create_single_activity(
                campaign=campaign,
                campaign_target=campaign_target,
                contact=contact,
                step_number=step_number,
                step_config=step_config,
                previous_activity=previous_activity
            )
            
            activities.append(activity)
            previous_activity = activity
        
        return activities
    
    @classmethod
    def _create_single_activity(cls, campaign: Campaign, campaign_target: CampaignTarget,
                               contact: Contact, step_number: int, step_config: Dict,
                               previous_activity: Activity = None) -> Activity:
        """
        Create a single activity with all necessary relationships (no scheduled date)
        """
        # Create the base activity - NO SCHEDULED DATE
        activity = Activity.objects.create(
            title=f"Step {step_number}: {step_config['description']}",
            activity_type=step_config['type'],
            description=step_config['description'],
            account=campaign_target.account,
            owner=campaign.owner,
            # NO scheduled_start - will be set when campaign is activated
            status=Activity.Status.PLANNED
        )
        
        # Add contact relationship
        activity.contacts.set([contact])
        
        # Create campaign relationship
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target
        )
        
        # Create sequence relationship with day-counting
        sequence_info = ActivitySequence.objects.create(
            activity=activity,
            source_type=ActivitySequence.SourceType.CAMPAIGN,
            sequence_position=step_number,
            call_attempts=0,
            # Store the minimum delay from sequence config
            min_delay_days=step_config['min_delay']
        )
        
        # Set next sequence activity link (for easier navigation)
        if previous_activity and hasattr(previous_activity, 'sequence_info'):
            previous_activity.sequence_info.next_sequence_activity = activity
            previous_activity.sequence_info.save()
        
        # Link to previous activity in sequence
        if previous_activity:
            previous_activity.next_activity = activity
            activity.previous_activity = previous_activity
            activity.save()
            previous_activity.save()
        
        return activity