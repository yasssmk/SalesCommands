# apps/campaign/services/campaign_core_service.py
from typing import List, Dict, Optional
from datetime import date
from django.db import transaction
from rest_framework.response import Response
from apps.activities.models import Activity
from apps.campaign.models import Campaign
from apps.accounts.models import Contact, Account
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages
from apps.campaign.config.settings import CONFIG


class CampaignCoreService:
    """
    Service unifié pour toutes les opérations de campagne
    Remplace CampaignManager + CampaignCoreService pour éliminer la délégation inutile
    """
    
    # ===== CAMPAIGN CREATION & LIFECYCLE =====
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, 
                                    target_accounts: List[int] = None,
                                    target_contacts: List[int] = None,
                                    target_leads: List[int] = None,
                                    target_opportunities: List[int] = None,
                                    targeting_stats: Dict = None,
                                    request=None) -> Response:
        """Create campaign with activities - délègue au service spécialisé"""
        try:
            # Import local pour éviter circularité
            from .campaign_creation_service import CampaignCreationService

            return CampaignCreationService.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_accounts,
                target_contacts=target_contacts,
                target_leads=target_leads,
                target_opportunities=target_opportunities,
                targeting_stats=targeting_stats,
                request=request
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def start_campaign(cls, campaign: Campaign, user=None) -> Response:
        """Start campaign - délègue au service spécialisé"""
        try:
            from .campaign_creation_service import CampaignCreationService

            return CampaignCreationService.start_campaign(campaign)


        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"start failed: {str(e)}")
            )
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None, user=None) -> Response:
        """Pause campaign - délègue au service spécialisé"""
        try:
            from .campaign_creation_service import CampaignCreationService
            return CampaignCreationService.pause_campaign(campaign, pause_until)
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"pause failed: {str(e)}")
            )
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign, user=None) -> Response:
        """Resume campaign - délègue au service spécialisé"""
        try:
            from .campaign_creation_service import CampaignCreationService
            return CampaignCreationService.resume_campaign(campaign)
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"resume failed: {str(e)}")
            )
    
    # ===== CAMPAIGN EXECUTION =====
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, 
                             current_activity_type: str = None) -> Response:
        """Get campaign playlist - logique centralisée sans circularité"""
        try:
            if limit is None:
                limit = CONFIG.limits.playlist_limit
            
            # Import local pour éviter la circularité
            from .campaign_queue_service import CampaignQueueService
            if campaign.sequence_type:
                # Pour campagnes avec séquence : queue d'activités
                print(f"Fetching playlist for campaign {campaign.id} with limit {limit} and activity type {current_activity_type}")
                return CampaignQueueService.get_active_activities_for_campaign(
                    campaign=campaign,
                    limit=limit,
                    prefetch_relations=True,
                    current_activity_type=current_activity_type
                )
            else:
                # Pour campagnes sans séquence : queue de contacts
                return CampaignQueueService.get_prioritized_contacts_for_campaign(
                    campaign=campaign,
                    limit=limit
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
            )
    
    @classmethod
    def complete_activity(cls, activity: Activity, result: str, 
                         notes: str = None, **kwargs) -> Response:
        """Complete activity and get next playlist"""
        try:
            # Import local pour éviter la circularité
            from .campaign_result_service import CampaignResultService
            
            # Traiter le résultat
            result_response = CampaignResultService.process_activity_result(
                activity=activity,
                result=result,
                notes=notes,
                **kwargs
            )
            
            # Récupérer les prochaines activités
            next_activities = []
            if hasattr(activity, 'campaign_info') and activity.campaign_info:
                campaign = activity.campaign_info.campaign
                try:
                    playlist_response = cls.get_campaign_playlist(
                        campaign=campaign, 
                        limit=10
                    )
                    
                    # Extraire les données de la réponse
                    if hasattr(playlist_response, 'data') and 'data' in playlist_response.data:
                        playlist_data = playlist_response.data['data']
                        next_activities = playlist_data.get('items', [])
                        
                except Exception:
                    # Si récupération playlist échoue, continuer sans (non-critique)
                    pass
            
            # Extraire les données du résultat
            result_info = {}
            if hasattr(result_response, 'data') and 'data' in result_response.data:
                result_info = result_response.data['data']
            
            # Construire la réponse finale
            return CampaignResponseBuilder.activity_completed(
                result_action=result_info.get('action', 'completed'),
                activity_id=activity.id,
                next_activities=next_activities,
                additional_info=result_info
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, 
                               notes: str = None) -> Response:
        """Remove contact from campaign - UPDATED: Uses State Machine business triggers"""
        try:
            with transaction.atomic():
                activities = Activity.objects.filter(
                    campaign_info__campaign=campaign,
                    contacts=contact,
                    status=Activity.Status.PLANNED
                )
                
                activities_count = activities.count()
                activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes=f"Manually removed from campaign: {notes}" if notes else "Manually removed from campaign"
                )
                
                # Import local pour éviter circularité
                from apps.campaign.models import CampaignTarget
                campaign_target = CampaignTarget.objects.filter(
                    campaign=campaign, contact=contact
                ).first()
                
                # Use State Machine business trigger instead of centralized method
                status_update_result = {'status_updated': False}
                if campaign_target:
                    status_update_result = campaign_target.mark_as_stopped(
                        reason='manual_stop',
                        notes=f"Contact manually removed from campaign: {notes}" if notes else "Contact manually removed from campaign",
                        user=None  
                    )

                
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'activities_cancelled': activities_count,
                    'action': 'contact_removed',
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'old_target_status': status_update_result.get('old_status'),
                    'new_target_status': status_update_result.get('new_status'),
                    'state_machine_used': status_update_result.get('state_machine_used', False),
                    'business_trigger': status_update_result.get('trigger')
                }
                
                meta = {
                    'operation': 'contact_removal',
                    'activities_affected': activities_count,
                    'target_updated': bool(campaign_target),
                    'status_update_method': 'state_machine_business_trigger',  
                    'state_machine_integration': True 
                }
                
                return StandardizedSuccessResponse.success(
                    message=CONFIG.messages.contact_removed,
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_CONTACT_MAPPING_FAILED
            )


    @classmethod
    def remove_account_from_campaign(cls, campaign: Campaign, account: Account, 
                               notes: str = None) -> Response:
        """Remove account from campaign - UPDATED: Uses State Machine business triggers"""
        try:
            with transaction.atomic():
                activities = Activity.objects.filter(
                    campaign_info__campaign=campaign,
                    account=account,
                    status=Activity.Status.PLANNED
                )
                
                activities_count = activities.count()
                activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes=f"Account removed from campaign: {notes}" if notes else "Account removed from campaign"
                )
                
                # Use State Machine business triggers for all account targets
                from apps.campaign.models import CampaignTarget
                account_targets = CampaignTarget.objects.filter(
                    campaign=campaign, account=account
                )
                
                targets_updated = []
                for campaign_target in account_targets:
                    update_result = campaign_target.mark_as_stopped(
                        reason='manual_stop',
                        notes=f"Account manually removed from campaign: {notes}" if notes else "Account manually removed from campaign",
                        user=None  # Could be enhanced to accept user parameter
                    )
                    targets_updated.append(update_result)

                
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities_cancelled': activities_count,
                    'action': 'account_removed',
                    'targets_updated': len(targets_updated),
                    'state_machine_updates': targets_updated
                }
                
                meta = {
                    'operation': 'account_removal',
                    'activities_affected': activities_count,
                    'targets_updated': len(targets_updated),
                    'status_update_method': 'state_machine_business_trigger',  
                    'state_machine_integration': True  
                }
                
                return StandardizedSuccessResponse.success(
                    message=CONFIG.messages.account_removed,
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
            )
    
    @classmethod
    def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> Response:
        """Get contacts with potential responses"""
        try:
            email_linkedin_activities = Activity.objects.filter(
                campaign_info__campaign=campaign,
                activity_type__in=[Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN],
                status=Activity.Status.COMPLETED
            ).select_related('account').prefetch_related('contacts')
            
            contacts_with_activities = {}
            
            for activity in email_linkedin_activities:
                for contact in activity.contacts.all():
                    contact_key = contact.id
                    
                    if contact_key not in contacts_with_activities:
                        contacts_with_activities[contact_key] = {
                            'contact': contact,
                            'account': activity.account,
                            'activities': []
                        }
                    
                    contacts_with_activities[contact_key]['activities'].append({
                        'id': activity.id,
                        'type': activity.activity_type,
                        'title': activity.title,
                        'completed_at': activity.completed_at,
                        'outcome_notes': activity.outcome_notes,
                        'can_add_response': True
                    })
            
            formatted_contacts = []
            for item in contacts_with_activities.values():
                contact = item['contact']
                account = item['account']
                
                formatted_contacts.append({
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'contact_email': contact.email,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities': item['activities']
                })
            
            data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'contacts': formatted_contacts
            }
            
            meta = {
                'operation': 'contacts_with_responses',
                'contacts_count': len(formatted_contacts),
                'total_activities_processed': email_linkedin_activities.count()
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Retrieved {len(formatted_contacts)} contacts with potential responses",
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    # ===== ANALYTICS & REPORTING =====
    
    @classmethod
    def get_campaign_summary(cls, campaign: Campaign) -> Response:
        """Get campaign summary - délègue au service spécialisé"""
        try:
            from .campaign_analytics_service import CampaignAnalyticsService
            return CampaignAnalyticsService.get_campaign_summary(campaign)
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    @classmethod
    def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Response:
        """Get campaign activities - délègue au service spécialisé"""
        try:
            from .campaign_analytics_service import CampaignAnalyticsService
            return CampaignAnalyticsService.get_campaign_activities(
                campaign=campaign,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    @classmethod
    def get_account_activities_in_campaign(cls, campaign: Campaign, account: Account, 
                                        status_filter: List[str] = None) -> Response:
        """Get account activities - délègue au service spécialisé"""
        try:
            from .campaign_analytics_service import CampaignAnalyticsService
            return CampaignAnalyticsService.get_account_activities_in_campaign(
                campaign=campaign,
                account=account,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    @classmethod
    def get_contact_activities_in_campaign(cls, campaign: Campaign, contact: Contact, 
                                        status_filter: List[str] = None) -> Response:
        """Get contact activities - délègue au service spécialisé"""
        try:
            from .campaign_analytics_service import CampaignAnalyticsService
            return CampaignAnalyticsService.get_contact_activities_in_campaign(
                campaign=campaign,
                contact=contact,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    @classmethod
    def get_campaign_performance_metrics(cls, campaign: Campaign) -> Response:
        """Get performance metrics - délègue au service spécialisé"""
        try:
            from .campaign_analytics_service import CampaignAnalyticsService
            return CampaignAnalyticsService.get_campaign_performance_metrics(campaign)
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    # ===== CONVENIENCE METHODS =====
    
    @classmethod
    def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
                                      activity_type: str, result: str, notes: str = None, 
                                      user=None, **kwargs) -> Response:
        """Add manual activity for non-sequence campaigns"""
        try:
            # Verify this is a non-sequence campaign
            if campaign.sequence_type:
                raise StandardizedValidationError(
                    "This operation is only for campaigns without sequences"
                )
            
            # Validate activity type
            valid_types = [choice[0] for choice in Activity.ActivityType.choices]
            if activity_type not in valid_types:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=activity_type)
                )
            
            # Get the campaign target for this contact
            target = None
            for t in campaign.targets.all():
                if (t.contact_id == contact.id or 
                    (t.account_id == contact.account_id) or
                    (t.lead and t.lead.account_id == contact.account_id) or
                    (t.target_opportunity and t.target_opportunity.account_id == contact.account_id)):
                    target = t
                    break
            
            if not target:
                raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
            from django.utils import timezone
            from apps.activities.models import ActivityCampaign, ActivitySequence
            
            # Create activity in transaction
            with transaction.atomic():
                # Create activity
                activity = Activity.objects.create(
                    title=f"{Activity.ActivityType(activity_type).label} with {contact.first_name} {contact.last_name}",
                    activity_type=activity_type,
                    description=notes or '',
                    account=contact.account,
                    owner=user,
                    status=Activity.Status.COMPLETED,
                    scheduled_start=timezone.now(),
                    completed_at=timezone.now(),
                    outcome_notes=notes or '',
                    client_id=campaign.client_id
                )
                
                # Add contact relationship
                activity.contacts.add(contact)
                
                # Create campaign relationship
                ActivityCampaign.objects.create(
                    activity=activity,
                    campaign=campaign,
                    campaign_target=target,
                    client_id=campaign.client_id
                )
                
                # Add sequence info for consistent tracking
                ActivitySequence.objects.create(
                    activity=activity,
                    source_type=ActivitySequence.SourceType.MANUAL,
                    sequence_position=1,
                    min_delay_days=0,
                    client_id=campaign.client_id
                )
                
                # Process result using unified method
                result_response = cls.complete_activity(
                    activity=activity,
                    result=result,
                    notes=notes,
                    **kwargs
                )
                
                # Extract result info from the standardized response
                result_info = {}
                if hasattr(result_response, 'data') and 'data' in result_response.data:
                    result_info = result_response.data['data']
            
            # Get updated playlist
            next_activities = []
            try:
                updated_playlist_response = cls.get_campaign_playlist(
                    campaign=campaign, 
                    limit=CONFIG.limits.playlist_limit
                )
                if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
                    playlist_data = updated_playlist_response.data['data']
                    next_activities = playlist_data.get('items', [])
            except Exception:
                pass
            
            # Enhance the response with playlist data
            enhanced_data = result_info.copy()
            enhanced_data['next_activities'] = next_activities
            
            meta = {
                'operation': 'manual_activity_creation',
                'activity_type': activity_type,
                'playlist_updated': len(next_activities) > 0
            }

            return StandardizedSuccessResponse.success(
                message=CONFIG.messages.activity_completed,
                data=enhanced_data,
                meta=meta
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(current_state=f"creation failed: {str(e)}")
            )
    
    # ===== BULK OPERATIONS =====
    
    @classmethod
    def bulk_remove_contacts(cls, campaign: Campaign, contact_ids: List[int], 
                           notes: str = None) -> Response:
        """Bulk remove multiple contacts from campaign"""
        try:
            from apps.accounts.models import Contact
            
            successful = []
            failed = []
            total_activities_cancelled = 0
            
            for contact_id in contact_ids:
                try:
                    contact = Contact.objects.get(id=contact_id)
                    result_response = cls.remove_contact_from_campaign(campaign, contact, notes)
                    
                    # Extract data from the standardized response
                    if hasattr(result_response, 'data') and 'data' in result_response.data:
                        response_data = result_response.data['data']
                        activities_cancelled = response_data.get('activities_cancelled', 0)
                        
                        successful.append({
                            f"{CONFIG.fields.contact}_id": contact_id,
                            f"{CONFIG.fields.contact}_name": f"{contact.first_name} {contact.last_name}",
                            'activities_cancelled': activities_cancelled
                        })
                        total_activities_cancelled += activities_cancelled
                    
                except Contact.DoesNotExist:
                    failed.append({
                        f"{CONFIG.fields.contact}_id": contact_id,
                        'error': 'Contact not found'
                    })
                except Exception as e:
                    failed.append({
                        f"{CONFIG.fields.contact}_id": contact_id,
                        'error': str(e)
                    })
            
            # Use bulk operation response
            message = CONFIG.messages.bulk_operation_completed.format(
                successful=len(successful),
                total=len(contact_ids)
            )
            
            return CampaignResponseBuilder.bulk_operation(
                operation_type='contact_removal',
                successful_items=successful,
                failed_items=failed,
                custom_message=message
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="contact removal")
            )