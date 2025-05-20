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
    def create_activities_for_campaign(cls, campaign: Campaign, target_contacts: List[int] = None) -> Dict:
        """
        Create activities for all targets in a campaign with optimized queries
        
        Args:
            campaign: The campaign to create activities for
            target_contacts: Optional list of specific contact IDs to target
            
        Returns:
            Dictionary with creation summary
        """
        created_count = 0
        skipped_contacts = []
        
        with transaction.atomic():
            # Get all campaign targets in a single query with account prefetched
            campaign_targets = CampaignTarget.objects.filter(
                campaign=campaign
            ).select_related('account')
            
            # If we have specific contact IDs, get them all at once with prefetched data
            if target_contacts:
                # Get only contacts that belong to the accounts in our campaign targets
                account_ids = [target.account_id for target in campaign_targets]
                all_contacts = Contact.objects.filter(
                    id__in=target_contacts,
                    account_id__in=account_ids
                ).select_related('standard_department')
                
                # Create a lookup dict for faster access
                contacts_by_account = {}
                for contact in all_contacts:
                    if contact.account_id not in contacts_by_account:
                        contacts_by_account[contact.account_id] = []
                    contacts_by_account[contact.account_id].append(contact)
            
            # Process each campaign target
            for campaign_target in campaign_targets:
                account = campaign_target.account
                
                # Get the appropriate contacts for this target
                if target_contacts:
                    # Use our pre-fetched contacts
                    contacts = contacts_by_account.get(account.id, [])
                else:
                    # Query all contacts for this account - removed is_active filter
                    contacts = Contact.objects.filter(
                        account=account
                    ).select_related('standard_department')
                
                # Process each contact
                for contact in contacts:
                    # Check if the contact should be excluded due to opt-out status
                    if hasattr(contact, 'opted_out') and contact.opted_out:
                        skipped_contacts.append({
                            'contact_id': contact.id,
                            'contact': contact.full_name,
                            'account': account.company_name,
                            'reason': 'Contact has opted out of communications'
                        })
                        continue
                        
                    # Check for communication channels
                    has_phone = bool(contact.phone)
                    has_email = bool(contact.email)  
                    has_linkedin = bool(contact.linkedin)
                    
                    # Skip if no communication channels
                    if not (has_phone or has_email or has_linkedin):
                        skipped_contacts.append({
                            'contact_id': contact.id,
                            'contact': contact.full_name,
                            'account': account.company_name,
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
                    
                    # Mark the target as having sequences created
                    if not campaign_target.sequence_created and activities_created:
                        campaign_target.mark_sequence_created()
        
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
        
        # Bulk prepare activity instances
        activity_instances = []
        campaign_info_instances = []
        sequence_info_instances = []
        
        # Create activities for each step in the sequence
        for step_number, step_config in sequence_dict.items():
            # Create the base activity - NO SCHEDULED DATE
            activity = Activity(
                title=f"Step {step_number}: {step_config['description']}",
                activity_type=step_config['type'],
                description=step_config['description'],
                account=campaign_target.account,
                owner=campaign.owner,
                status=Activity.Status.PLANNED,
                client_id=campaign.client_id  # Set client_id from campaign
            )
            
            activity_instances.append(activity)
            
            # We'll handle the sequence and campaign relationships after bulk create
            campaign_info_instances.append({
                'step_number': step_number,
                'step_config': step_config,
                'previous_activity': previous_activity
            })
            
            previous_activity = activity
        
        # Bulk create activities
        created_activities = Activity.objects.bulk_create(activity_instances)
        
        # Now set up contact relationships, campaign links and sequence info
        for i, activity in enumerate(created_activities):
            # Add contact relationship
            activity.contacts.add(contact)
            
            # Create campaign relationship
            campaign_info = ActivityCampaign.objects.create(
                activity=activity,
                campaign=campaign,
                campaign_target=campaign_target,
                client_id=campaign.client_id
            )
            
            # Get previous step info
            info = campaign_info_instances[i]
            step_number = info['step_number']
            step_config = info['step_config']
            
            # Create sequence relationship with day-counting
            sequence_info = ActivitySequence.objects.create(
                activity=activity,
                source_type=ActivitySequence.SourceType.CAMPAIGN,
                sequence_position=step_number,
                call_attempts=0,
                min_delay_days=step_config['min_delay'],
                client_id=campaign.client_id
            )
            
            # Link activities (previous/next)
            prev_activity_index = i - 1
            if prev_activity_index >= 0:
                prev_activity = created_activities[prev_activity_index]
                
                # Use direct database update for sequence instead of instance save
                from django.db.models import F
                ActivitySequence.objects.filter(activity=prev_activity).update(
                    next_sequence_activity=activity
                )
                
                # Use direct updates for activity links too
                Activity.objects.filter(id=prev_activity.id).update(
                    next_activity=activity
                )
                
                Activity.objects.filter(id=activity.id).update(
                    previous_activity=prev_activity
                )
        
        return created_activities
        
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