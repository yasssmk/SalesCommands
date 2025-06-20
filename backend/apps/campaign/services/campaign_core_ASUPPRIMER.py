# apps/campaign/services/campaign_core.py
from typing import List, Dict, Optional
from django.db import transaction
from rest_framework.response import Response
from apps.activities.models import Activity
from apps.campaign.models import Campaign
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages
from apps.campaign.config.variables import DEFAULT_PLAYLIST_LIMIT
from apps.accounts.models import Account, Contact


class CampaignCoreService:
    """
    Service central pour éviter les imports circulaires entre services Campaign.
    Contient les méthodes de base utilisées par plusieurs services.
    """
    
    @staticmethod
    def get_campaign_playlist_internal(campaign: Campaign, limit: int = None, 
                                     current_activity_type: str = None) -> Response:
        """
        Méthode centrale pour récupérer la playlist d'une campagne.
        Évite l'import circulaire entre CampaignManager et CampaignExecutionService.
        
        Args:
            campaign: Campaign instance
            limit: Nombre d'items à retourner
            current_activity_type: Type d'activité courante pour batching
            
        Returns:
            Response: Standardized response with playlist data
        """
        try:
            if limit is None:
                limit = DEFAULT_PLAYLIST_LIMIT
            
            # Import local pour éviter la circularité
            from .campaign_queue_service import CampaignQueueService
            
            if campaign.sequence_type:
                # Pour campagnes avec séquence : queue d'activités
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
    
    @staticmethod
    def complete_activity_internal(activity: Activity, result: str, 
                                 notes: str = None, **kwargs) -> Response:
        """
        Méthode centrale pour compléter une activité.
        Évite l'import circulaire entre CampaignManager et CampaignResultService.
        
        Args:
            activity: Activity à compléter
            result: Résultat de l'activité
            notes: Notes optionnelles
            **kwargs: Données additionnelles (callback_date, meeting_date, etc.)
            
        Returns:
            Response: Standardized response with completion result
        """
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
            
            # Récupérer les prochaines activités sans import circulaire
            next_activities = []
            if hasattr(activity, 'campaign_info') and activity.campaign_info:
                campaign = activity.campaign_info.campaign
                try:
                    # Utiliser la méthode interne pour éviter la circularité
                    playlist_response = CampaignCoreService.get_campaign_playlist_internal(
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
        
    @staticmethod
    def remove_contact_from_campaign_internal(campaign: Campaign, contact: Contact, 
                                            notes: str = None) -> Response:
        """Méthode centrale pour supprimer un contact d'une campagne"""
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
                
                status_update_result = {'status_updated': False}
                if campaign_target:
                    # Import de la méthode centralisée
                    from apps.campaign.services.campaign_result_service import CampaignResultService
                    status_update_result = CampaignResultService.update_campaign_target_status_for_business_result(
                        campaign_target, 'not_interested'  # Suppression manuelle = pas intéressé
                    )
                
                # Import local pour les messages
                from apps.campaign.config.variables import OPERATION_MESSAGES
                
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'contact_id': contact.id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'activities_cancelled': activities_count,
                    'action': 'contact_removed',
                    'target_status_updated': status_update_result.get('status_updated', False),
                    'old_target_status': status_update_result.get('old_status'),
                    'new_target_status': status_update_result.get('new_status')
                }
                
                meta = {
                    'operation': 'contact_removal',
                    'activities_affected': activities_count,
                    'target_updated': bool(campaign_target),
                    'status_update_method': 'centralized'
                }
                
                return StandardizedSuccessResponse.success(
                    message=OPERATION_MESSAGES['CONTACT_REMOVED'],
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_CONTACT_MAPPING_FAILED
            )

    @staticmethod
    def remove_account_from_campaign_internal(campaign: Campaign, account: Account, 
                                            notes: str = None) -> Response:
        """Méthode centrale pour supprimer un compte d'une campagne"""
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
                
                # Import local pour éviter circularité
                from apps.campaign.models import CampaignTarget
                campaign_target = CampaignTarget.objects.filter(
                    campaign=campaign, account=account
                ).first()
                
                if campaign_target:
                    campaign_target.status = CampaignTarget.Status.STOPPED
                    campaign_target.save()
                
                # Import local pour les messages
                from apps.campaign.config.variables import OPERATION_MESSAGES
                
                data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'account_id': account.id,
                    'account_name': account.company_name,
                    'activities_cancelled': activities_count,
                    'action': 'account_removed'
                }
                
                meta = {
                    'operation': 'account_removal',
                    'activities_affected': activities_count,
                    'target_updated': bool(campaign_target)
                }
                
                return StandardizedSuccessResponse.success(
                    message=OPERATION_MESSAGES['ACCOUNT_REMOVED'],
                    data=data,
                    meta=meta
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
            )

    @staticmethod
    def get_campaign_contacts_with_responses_internal(campaign: Campaign) -> Response:
        """Méthode centrale pour récupérer les contacts avec réponses"""
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