# apps/campaign/services/campaign_activity_service.py (version complète finale)

from typing import List, Dict, Optional, TYPE_CHECKING
from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from apps.activities.models import Activity, ActivityCampaign, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact
from apps.campaign.utils.contact_helpers import ContactSafetyHelper
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from apps.accounts.models import Account

# Import configuration variables
from apps.campaign.config.settings import CONFIG


class CampaignActivityService:
    """
    Service for creating and managing campaign activities based on sequences
    Version sécurisée avec réponses standardisées et gestion des edge cases
    """
    
    @classmethod
    def create_activities_for_campaign(cls, campaign: Campaign, target_contacts: List[int] = None,
                                     for_campaign_creation: bool = True) -> Response:
        """
        Create activities for all targets in a campaign with optimized queries
        For campaigns without sequence, just extract and return contacts without creating activities
        
        Args:
            campaign: The campaign to create activities for
            target_contacts: Optional list of specific contact IDs to target
            for_campaign_creation: True si appelé lors de création de campagne, False pour génération ultérieure
            
        Returns:
            Response: Standardized response with creation summary or contact queue
        """
        try:
            created_count = 0

            print(f"Creating activities for campaign: {campaign.id} - {campaign.name}")
            
            # Extract all relevant contacts regardless of sequence type
            extraction_result = cls._extract_contacts_from_targets(campaign, target_contacts)
            valid_contacts = extraction_result['valid_contacts']
            skipped_contacts = extraction_result['skipped_contacts']
            contact_to_target_map = extraction_result['contact_to_target_map']
            
            print(f"Valid contacts extracted: {len(valid_contacts)}")
            print(f"Skipped contacts: {len(skipped_contacts)}")
            print(f"Contact to target map: {len(contact_to_target_map)} entries")

            # For campaigns without a sequence, return contact queue response
            if not campaign.sequence_type:
                print("Campaign has no sequence type, returning contact queue")
                return CampaignResponseBuilder.campaign_playlist(
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    items=valid_contacts,
                    queue_type='contact',
                    is_sequence=False,
                    total_items=len(valid_contacts),
                    additional_data={
                        'skipped_contacts': skipped_contacts,
                        'contact_to_target_map': contact_to_target_map,
                        'message': 'Campaign has no sequence - contacts extracted for manual activities'
                    }
                )
            
            # Check for empty campaign (no valid contacts for sequence)
            if not valid_contacts:
                print("No valid contacts found for activity generation")
                if for_campaign_creation:
                    return CampaignResponseBuilder.campaign_created_empty(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        targets_created=len(contact_to_target_map),
                        skipped_contacts=skipped_contacts
                    )
                else:
                    return CampaignResponseBuilder.activities_generated(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        activities_created=0,
                        skipped_contacts=skipped_contacts,
                        additional_data={
                            'warning': 'No valid contacts found for activity generation'
                        }
                    )
                
            # For campaigns with sequence, create activities
            with transaction.atomic():
                # Process each valid contact
                for contact_info in valid_contacts:
                    print(f"Processing contact: {contact_info[CONFIG.fields.contact].id}")
                    contact = contact_info[CONFIG.fields.contact]
                    has_phone = contact_info['has_phone']
                    has_email = contact_info['has_email']
                    has_linkedin = contact_info['has_linkedin']
                    
                    # Get the associated target for this contact
                    campaign_target = contact_to_target_map.get(contact.id)
                    if not campaign_target:
                        continue  # Skip if no target mapping found
                    print(f"Found target for contact {contact.id}: {campaign_target.id}")
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
                    print(f"Created {len(activities_created)} activities for contact {contact.id}")
                    
                    # Mark the target as having activities generated
                    if not campaign_target.activities_generated and activities_created:
                        campaign_target.mark_activities_generated()
            print(f"Total activities created for campaign {campaign.id}: {created_count}")
            # Return appropriate response based on context
            if for_campaign_creation:
                # Contexte : création de campagne
                if created_count == 0:
                    return CampaignResponseBuilder.campaign_created_empty(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        targets_created=len(contact_to_target_map),
                        skipped_contacts=skipped_contacts
                    )
                else:
                    return CampaignResponseBuilder.campaign_created(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        targets_created=len(contact_to_target_map),
                        activities_created=created_count,
                        skipped_contacts=skipped_contacts
                    )
            else:
                # Contexte : génération d'activités pour campagne existante
                return CampaignResponseBuilder.activities_generated(
                    campaign_id=campaign.id,
                    campaign_name=campaign.name,
                    activities_created=created_count,
                    skipped_contacts=skipped_contacts,
                    additional_data={
                        'valid_contacts': len(valid_contacts),
                        'targets_processed': len(contact_to_target_map)
                    }
                )
        except StandardizedValidationError as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_GENERATION_FAILED.format(reason=str(e))
            )
        
    @classmethod
    def _get_safe_account_for_activity(cls, campaign_target: CampaignTarget, 
                                     contact: Contact) -> 'Account':
        """
        Safely get account for activity creation from campaign target or contact
        
        Args:
            campaign_target: CampaignTarget instance
            contact: Contact instance as fallback
            
        Returns:
            Account: Valid account instance
            
        Raises:
            StandardizedValidationError: If no valid account can be found
        """
        # Essayer d'abord le campaign_target.account
        if campaign_target and hasattr(campaign_target, 'account') and campaign_target.account:
            return campaign_target.account
        
        # Fallback: essayer contact.account
        contact_account = ContactSafetyHelper.get_account(contact)
        if contact_account:
            return contact_account
        
        # Pas d'account valide trouvé
        target_info = "Unknown Target"
        if campaign_target:
            target_type = getattr(campaign_target, 'get_target_type', lambda: 'unknown')()
            target_info = f"{target_type} target"
        
        contact_info = ContactSafetyHelper.get_contact_display_info(contact)
        
        raise StandardizedValidationError(
            CampaignErrorMessages.CAMPAIGN_ACTIVITY_ORPHANED.format(
                activity=f"Cannot create activity for {target_info} - no valid account found for contact {contact_info['contact_name']}"
            )
        )
    
    @classmethod
    def _create_activities_for_contact(cls, campaign: Campaign, campaign_target: CampaignTarget, 
                                contact: Contact, has_phone: bool, has_email: bool, 
                                has_linkedin: bool) -> List[Activity]:
        """
        Create sequence activities for a specific contact with stakeholder-based assignment
        SÉCURISÉ contre les accounts manquants
        """

        if not campaign.sequence_type:
            return []
        
        # Validation sécurisée de l'account avant création des activités
        try:
            activity_account = cls._get_safe_account_for_activity(campaign_target, contact)
        except StandardizedValidationError:
            # Si pas d'account valide, on ne peut pas créer d'activités
            # Log this situation mais ne fait pas crasher le processus complet
            return []
        
        # Get sequence type from campaign, default to CHASING if not set
        from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
        sequence_type = getattr(campaign, 'sequence_type', SequenceDispatcher.CHASING)
        
        # Get the sequence dictionary from the dispatcher
        sequence_dict = SequenceDispatcher.get_sequence(
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
            # Create the base activity - SÉCURISÉ avec account validé
            activity = Activity(
                title=f"Step {step_number}: {step_config['description']}",
                activity_type=step_config['type'],
                description=step_config['description'],
                account=activity_account,  # ✅ SÉCURISÉ - account validé ci-dessus
                owner=activity_owner,
                status=Activity.Status.PLANNED,
                client_id=campaign.client_id
            )
            
            activity_instances.append(activity)
            
            # We'll handle the sequence and campaign relationships after bulk create
            campaign_info_instances.append({
                'step_number': step_number,
                'step_config': step_config,
                'previous_activity': previous_activity
            })
            
            previous_activity = activity
        
        # Si aucune activité créée (séquence vide), retourner liste vide
        if not activity_instances:
            return []
        
        try:
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
            
        except Exception as e:
            # Si la création des activités échoue, lever une erreur standardisée
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(
                    reason=f"Failed to create activities for contact {contact.id}: {str(e)}"
                )
            )
        
        
    @classmethod
    def _create_single_activity(cls, campaign: Campaign, campaign_target: CampaignTarget,
                               contact: Contact, step_number: int, step_config: Dict,
                               previous_activity: Activity = None) -> Activity:
        """
        Create a single activity with all necessary relationships (no scheduled date)
        SÉCURISÉ contre les accounts manquants
        """
        # Validation sécurisée de l'account
        activity_account = cls._get_safe_account_for_activity(campaign_target, contact)
        
        # Create the base activity - SÉCURISÉ avec account validé
        activity = Activity.objects.create(
            title=f"Step {step_number}: {step_config['description']}",
            activity_type=step_config['type'],
            description=step_config['description'],
            account=activity_account,  # ✅ SÉCURISÉ - account validé
            owner=campaign.owner,
            status=Activity.Status.PLANNED,
            client_id=campaign.client_id
        )
        
        # Add contact relationship
        activity.contacts.set([contact])
        
        # Create campaign relationship
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target,
            client_id=campaign.client_id
        )
        
        # Create sequence relationship with day-counting
        sequence_info = ActivitySequence.objects.create(
            activity=activity,
            source_type=ActivitySequence.SourceType.CAMPAIGN,
            sequence_position=step_number,
            call_attempts=0,
            min_delay_days=step_config['min_delay'],
            client_id=campaign.client_id
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

    @classmethod
    def _extract_contacts_from_targets(cls, campaign: Campaign, target_contacts: List[int] = None):
        """
        Extract all relevant contacts from campaign targets - SÉCURISÉ CONTRE LES CONTACTS SANS ACCOUNT
        
        Args:
            campaign: The campaign to extract contacts for
            target_contacts: Optional list of specific contact IDs to filter by
            
        Returns:
            Dictionary with extracted contacts and account mapping
        """
        campaign_targets = CampaignTarget.objects.filter(**{CONFIG.fields.campaign: campaign}).select_related(
            CONFIG.fields.account, 
            CONFIG.fields.contact,
            CONFIG.fields.lead,
            CONFIG.fields.target_opportunity
        )

        # OPTIMIZATION: Create index dictionaries for O(1) lookups instead of O(n*m) nested loops
        account_ids = set()
        direct_contact_ids = set()
        
        # Build lookup dictionaries - O(m) where m = number of targets
        target_by_contact_id = {}          
        target_by_account_id = {}          
        lead_account_to_target = {}        
        opportunity_account_to_target = {} 

        for target in campaign_targets:
            # For direct account targets - SÉCURISÉ
            if target.account:
                account_ids.add(target.account.id)
                if target.account.id not in target_by_account_id:
                    target_by_account_id[target.account.id] = target
            
            # For direct contact targets - SÉCURISÉ avec validation
            if target.contact:
                # Validation que le contact a un account valide
                if ContactSafetyHelper.validate_contact_has_account(target.contact):
                    direct_contact_ids.add(target.contact.id)
                    target_by_contact_id[target.contact.id] = target
                    account_id = ContactSafetyHelper.get_account_id(target.contact)
                    if account_id:
                        account_ids.add(account_id)
                # Si le contact n'a pas d'account valide, on l'ignore ici
                # Il sera traité dans skipped_contacts plus bas
            
            # For lead targets - SÉCURISÉ
            if target.lead and target.lead.account_id:
                account_ids.add(target.lead.account_id)
                lead_account_to_target[target.lead.account_id] = target
            
            # For opportunity targets - SÉCURISÉ  
            if target.target_opportunity and target.target_opportunity.account_id:
                account_ids.add(target.target_opportunity.account_id)
                opportunity_account_to_target[target.target_opportunity.account_id] = target
        
        # Get contacts with single optimized query - SÉCURISÉ
        if target_contacts:
            all_contacts = Contact.objects.filter(
                id__in=target_contacts,
                account_id__in=account_ids  # Déjà filtré pour avoir des accounts valides
            ).select_related('standard_department', CONFIG.fields.account)
        else:
            # Get all contacts for the collected accounts
            all_contacts = Contact.objects.filter(
                account_id__in=account_ids
            ).select_related('standard_department', CONFIG.fields.account)
            
            # Add directly targeted contacts even if their account was not included
            if direct_contact_ids:
                direct_contacts = Contact.objects.filter(
                    id__in=direct_contact_ids
                ).exclude(account_id__in=account_ids).select_related('standard_department', CONFIG.fields.account)
                
                # Combine QuerySets
                all_contacts = (all_contacts | direct_contacts).distinct()
        
        # Process contacts with O(1) lookups and SÉCURISATION
        contacts_by_account = {}
        skipped_contacts = []
        valid_contacts = []
        contact_to_target_map = {}
        
        for contact in all_contacts:
            # Validation critique - skip si pas d'account valide
            if not ContactSafetyHelper.validate_contact_has_account(contact):
                contact_info = ContactSafetyHelper.get_contact_display_info(contact)
                skipped_contacts.append({
                    'contact_id': contact_info['contact_id'],
                    CONFIG.fields.contact: contact_info['contact_name'],
                    CONFIG.fields.account: contact_info['account_name'],
                    'reason': 'Contact has no valid account association'
                })
                continue
            
            # SÉCURISÉ: Utiliser helper pour obtenir account_id
            account_id = ContactSafetyHelper.get_account_id(contact)
            if not account_id:
                # Double vérification - normalement déjà attrapé au-dessus
                contact_info = ContactSafetyHelper.get_contact_display_info(contact)
                skipped_contacts.append({
                    'contact_id': contact_info['contact_id'],
                    CONFIG.fields.contact: contact_info['contact_name'],
                    CONFIG.fields.account: contact_info['account_name'],
                    'reason': 'Contact account ID is missing'
                })
                continue
            
            if account_id not in contacts_by_account:
                contacts_by_account[account_id] = []
            contacts_by_account[account_id].append(contact)
            
            # Check if the contact should be excluded due to opt-out status
            if hasattr(contact, 'opted_out') and contact.opted_out:
                contact_info = ContactSafetyHelper.get_contact_display_info(contact)
                skipped_contacts.append({
                    'contact_id': contact_info['contact_id'],
                    CONFIG.fields.contact: contact_info['contact_name'],
                    CONFIG.fields.account: contact_info['account_name'],
                    'reason': 'Contact has opted out of communications'
                })
                continue
                
            # Check for communication channels
            has_phone = bool(contact.phone)
            has_email = bool(contact.email)  
            has_linkedin = bool(contact.linkedin)
            
            # Skip if no communication channels
            if not (has_phone or has_email or has_linkedin):
                contact_info = ContactSafetyHelper.get_contact_display_info(contact)
                skipped_contacts.append({
                    'contact_id': contact_info['contact_id'],
                    CONFIG.fields.contact: contact_info['contact_name'],
                    CONFIG.fields.account: contact_info['account_name'],
                    'reason': 'No communication channels available'
                })
                continue
            
            # Valid contact for activities
            valid_contacts.append({
                CONFIG.fields.contact: contact,
                'has_phone': has_phone,
                'has_email': has_email,
                'has_linkedin': has_linkedin
            })
            
            # OPTIMIZED: Find target using O(1) lookups instead of nested loops
            target = cls._find_target_for_contact(
                contact, 
                target_by_contact_id,
                target_by_account_id,
                lead_account_to_target,
                opportunity_account_to_target
            )
            
            if target:
                contact_to_target_map[contact.id] = target
        
        # Vérifier et signaler les contacts directement ciblés sans account valide
        for target in campaign_targets:
            if target.contact and not ContactSafetyHelper.validate_contact_has_account(target.contact):
                contact_info = ContactSafetyHelper.get_contact_display_info(target.contact)
                skipped_contacts.append({
                    'contact_id': contact_info['contact_id'],
                    CONFIG.fields.contact: contact_info['contact_name'],
                    CONFIG.fields.account: contact_info['account_name'],
                    'reason': 'Direct target contact has no valid account association'
                })
        
        return {
            'valid_contacts': valid_contacts,
            'contacts_by_account': contacts_by_account,
            'skipped_contacts': skipped_contacts,
            'contact_to_target_map': contact_to_target_map,
            'all_targets': dict(target_by_account_id)
        }

    @classmethod
    def _find_target_for_contact(cls, contact: Contact, 
                            target_by_contact_id: dict,
                            target_by_account_id: dict,
                            lead_account_to_target: dict,
                            opportunity_account_to_target: dict) -> CampaignTarget:
        """
        Find the appropriate target for a contact using O(1) dictionary lookups
        
        Args:
            contact: The contact to find target for
            target_by_contact_id: Direct contact ID -> target mapping
            target_by_account_id: Account ID -> target mapping  
            lead_account_to_target: Lead account ID -> target mapping
            opportunity_account_to_target: Opportunity account ID -> target mapping
            
        Returns:
            CampaignTarget or None
        """
        # Priority order: direct contact > lead account > opportunity account > general account
        
        # 1. Direct contact target (highest priority)
        if contact.id in target_by_contact_id:
            return target_by_contact_id[contact.id]
        
        # 2. Contact from lead's account
        if contact.account_id in lead_account_to_target:
            return lead_account_to_target[contact.account_id]
        
        # 3. Contact from opportunity's account  
        if contact.account_id in opportunity_account_to_target:
            return opportunity_account_to_target[contact.account_id]
        
        # 4. Contact from general account target (lowest priority)
        if contact.account_id in target_by_account_id:
            return target_by_account_id[contact.account_id]
        
        return None

    @classmethod
    def cleanup_orphaned_activities(cls, campaign: Campaign) -> Dict:
        """
        Nettoie les activités orphelines (sans target valide)
        Méthode utilitaire pour maintenance
        
        Args:
            campaign: Campaign à nettoyer
            
        Returns:
            Dict: Rapport de nettoyage
        """
        from apps.activities.models import Activity
        
        # Trouver les activités de la campagne sans target valide
        campaign_activities = Activity.objects.filter(
            campaign_info__campaign=campaign
        ).select_related('campaign_info__campaign_target')
        
        orphaned_activities = []
        
        for activity in campaign_activities:
            campaign_info = getattr(activity, 'campaign_info', None)
            if not campaign_info or not campaign_info.campaign_target:
                orphaned_activities.append(activity)
        
        # Supprimer les activités orphelines
        orphaned_count = 0
        if orphaned_activities:
            orphaned_ids = [a.id for a in orphaned_activities]
            Activity.objects.filter(id__in=orphaned_ids).delete()
            orphaned_count = len(orphaned_ids)
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'orphaned_activities_found': len(orphaned_activities),
            'orphaned_activities_deleted': orphaned_count,
            'cleanup_successful': True,
            'cleanup_timestamp': timezone.now().isoformat()
        }
    
    @classmethod
    def validate_campaign_integrity(cls, campaign: Campaign) -> Dict:
        """
        Valide l'intégrité d'une campagne (diagnostic)
        
        Args:
            campaign: Campaign à valider
            
        Returns:
            Dict: Rapport de validation
        """
        from apps.activities.models import Activity
        
        # Compter les targets
        total_targets = campaign.targets.count()
        targets_with_activities = campaign.targets.filter(
            activity_campaign__isnull=False
        ).distinct().count()
        
        # Compter les activités
        total_activities = Activity.objects.filter(
            campaign_info__campaign=campaign
        ).count()
        
        orphaned_activities = Activity.objects.filter(
            campaign_info__campaign=campaign,
            campaign_info__campaign_target__isnull=True
        ).count()
        
        # Contacts valides vs skipped
        extraction_result = cls._extract_contacts_from_targets(campaign)
        valid_contacts_count = len(extraction_result['valid_contacts'])
        skipped_contacts_count = len(extraction_result['skipped_contacts'])
        
        # Déterminer l'état
        is_empty = (total_activities == 0 and campaign.sequence_type is not None)
        has_orphans = (orphaned_activities > 0)
        has_issues = (skipped_contacts_count > valid_contacts_count)
        
        integrity_status = 'healthy'
        if is_empty:
            integrity_status = 'empty'
        elif has_orphans or has_issues:
            integrity_status = 'issues_detected'
        
        return {
            'campaign_id': campaign.id,
            'campaign_name': campaign.name,
            'integrity_status': integrity_status,
            'is_empty_campaign': is_empty,
            'targets': {
                'total': total_targets,
                'with_activities': targets_with_activities,
                'without_activities': total_targets - targets_with_activities
            },
            'activities': {
                'total': total_activities,
                'orphaned': orphaned_activities
            },
            'contacts': {
                'valid': valid_contacts_count,
                'skipped': skipped_contacts_count
            },
            'recommendations': cls._get_integrity_recommendations(
                is_empty, has_orphans, has_issues, skipped_contacts_count, valid_contacts_count
            )
        }
    
    @classmethod
    def _get_integrity_recommendations(cls, is_empty: bool, has_orphans: bool, 
                                     has_issues: bool, skipped: int, valid: int) -> List[str]:
        """Helper pour générer des recommandations d'amélioration"""
        recommendations = []
        
        if is_empty:
            recommendations.append("Campaign has no activities - verify target contacts have valid communication channels")
        
        if has_orphans:
            recommendations.append("Orphaned activities detected - run cleanup_orphaned_activities()")
        
        if has_issues and skipped > valid:
            recommendations.append(f"More contacts skipped ({skipped}) than valid ({valid}) - review target selection")
        
        if not recommendations:
            recommendations.append("Campaign integrity is good")
        
        return recommendations