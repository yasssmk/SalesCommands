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

        if not campaign.sequence_type:
            return {
                'total_activities_created': 0,
                'skipped_contacts': [],
                'success': True,
                'message': 'Campaign has no sequence - no activities pre-generated'
            }
            
        with transaction.atomic():
            # Get all campaign targets in a single query with related entities prefetched
            campaign_targets = CampaignTarget.objects.filter(
                campaign=campaign
            ).select_related(
                'account', 
                'contact',
                'lead',
                'target_opportunity'
            )
            
            # Collect all relevant accounts for further processing
            # Accounts can come from different sources: direct account targets, 
            # contact targets, lead targets, or opportunity targets
            account_ids = set()
            direct_contact_ids = set()
            
            for target in campaign_targets:
                # For direct account targets
                if target.account:
                    account_ids.add(target.account.id)
                
                # For direct contact targets
                if target.contact:
                    direct_contact_ids.add(target.contact.id)
                    if target.contact.account_id:
                        account_ids.add(target.contact.account_id)
                
                # For lead targets (get associated account)
                if target.lead and target.lead.account_id:
                    account_ids.add(target.lead.account_id)
                
                # For opportunity targets (get associated account)
                if target.target_opportunity and target.target_opportunity.account_id:
                    account_ids.add(target.target_opportunity.account_id)
            
            # If we have specific contact IDs provided, filter by them
            if target_contacts:
                all_contacts = Contact.objects.filter(
                    id__in=target_contacts,
                    account_id__in=account_ids
                ).select_related('standard_department')
            else:
                # Get all contacts for the collected accounts
                all_contacts = Contact.objects.filter(
                    account_id__in=account_ids
                ).select_related('standard_department')
                
                # Add directly targeted contacts even if their account was not included
                if direct_contact_ids:
                    direct_contacts = Contact.objects.filter(
                        id__in=direct_contact_ids
                    ).exclude(account_id__in=account_ids).select_related('standard_department')
                    
                    # Combine QuerySets
                    all_contacts = (all_contacts | direct_contacts).distinct()
            
            # Organize contacts by account for easier access
            contacts_by_account = {}
            for contact in all_contacts:
                if contact.account_id not in contacts_by_account:
                    contacts_by_account[contact.account_id] = []
                contacts_by_account[contact.account_id].append(contact)
            
            # Process each campaign target
            for campaign_target in campaign_targets:
                account = campaign_target.get_target_account()
                
                if not account:
                    continue  # Skip targets without an associated account
                
                # Get the appropriate contacts for this target
                contacts = contacts_by_account.get(account.id, [])
                
                # For direct contact targets, ensure we're only targeting that specific contact
                if campaign_target.contact:
                    contacts = [c for c in contacts if c.id == campaign_target.contact.id]
                
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
                    
                    # Mark the target as having activities generated
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
        Create sequence activities for a specific contact with stakeholder-based assignment
        """

        if not campaign.sequence_type:
            return []
        
        # Get sequence type from campaign, default to CHASING if not set
        from apps.sequence.sequences.sequence_dispatcher import SequenceDisptacher
        sequence_type = getattr(campaign, 'sequence_type', SequenceDisptacher.CHASING)
        
        # Get the sequence dictionary from the dispatcher
        sequence_dict = SequenceDisptacher.get_sequence(
            sequence_type=sequence_type,
            has_phone=has_phone,
            has_email=has_email,
            has_linkedin=has_linkedin
        )
        
        # Determine activity owner based on stakeholder roles
        from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
        
        # First try to find EXECUTOR stakeholders
        executors = campaign.get_executors()
        
        if executors.exists():
            # For simplicity in MVP, assign to first executor
            # More advanced implementation could rotate or balance load
            activity_owner = executors.first()
        else:
            # Fall back to campaign owner
            activity_owner = campaign.owner
        
        activities = []
        previous_activity = None
        
        # Bulk prepare activity instances
        activity_instances = []
        campaign_info_instances = []
        
        # Create activities for each step in the sequence
        for step_number, step_config in sequence_dict.items():
            # Create the base activity - NO SCHEDULED DATE
            activity = Activity(
                title=f"Step {step_number}: {step_config['description']}",
                activity_type=step_config['type'],
                description=step_config['description'],
                account=campaign_target.account,
                owner=activity_owner,  # Use stakeholder-based owner
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