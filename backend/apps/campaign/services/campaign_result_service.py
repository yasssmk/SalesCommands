# apps/campaign/services/campaign_result_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework.response import Response
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages
from apps.campaign.services.campaign_queue_service import CampaignQueueService

# Import configuration variables
from apps.campaign.config.settings import CONFIG


class CampaignResultService:
    """
    Service for handling campaign activity results and managing sequence progression
    Now returns standardized Response objects
    """
    
    @classmethod
    def process_activity_result(cls, activity: Activity, result: str, 
                        notes: str = None, **kwargs) -> Response:
        """
        Process the result of an activity and handle appropriate actions
        Works for both sequence and non-sequence campaigns
        ✅ UPDATED: Uses specific triggers for target synchronization
        """
        try:
            # Validate activity exists and is accessible
            if not activity:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            # Validate result is provided
            if not result:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Activity result")
                )
            
            # Check if this is a sequence or non-sequence activity
            campaign = activity.campaign_info.campaign
            is_sequence_campaign = campaign.sequence_type is not None

            # ✅ Auto-activation de campagne si nécessaire (inclut maintenant sync targets automatique)
            cls._ensure_campaign_is_active(activity)

            
            # Route to appropriate handler based on activity type
            if activity.activity_type == Activity.ActivityType.CALL:
                response = cls._handle_call_result(activity, result, notes, is_sequence_campaign, **kwargs)
            elif activity.activity_type in [Activity.ActivityType.EMAIL, Activity.ActivityType.LINKEDIN]:
                response = cls._handle_email_linkedin_result(activity, result, notes, is_sequence_campaign, **kwargs)
            else:
                # Unsupported activity type
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(
                        current_state=f"Unsupported activity type: {activity.activity_type}"
                    )
                )
        
            try:
                # Vérifier si l'activité a été complétée (pour éviter les appels inutiles)
                if activity.status == Activity.Status.COMPLETED:
                    schedule_update = CampaignQueueService.integrate_into_complete_activity(activity, {})
                    
                    # Ajouter les informations de mise à jour des dates à la réponse
                    if hasattr(response, 'data') and 'data' in response.data:
                        response.data['data']['scheduled_dates_update'] = schedule_update
                        
                        # Ajouter aussi dans les métadonnées
                        if 'meta' not in response.data:
                            response.data['meta'] = {}
                        response.data['meta']['dates_updated'] = schedule_update.get('updated_count', 0)
                        response.data['meta']['schedule_integration'] = True
                        
            except Exception as schedule_error:
                # En cas d'erreur de mise à jour des dates, ne pas faire crasher le processus principal
                print(f"WARNING: Failed to update scheduled dates after activity result: {str(schedule_error)}")
                # Ajouter une indication d'erreur dans la réponse si possible
                if hasattr(response, 'data') and 'data' in response.data:
                    response.data['data']['scheduled_dates_update'] = {
                        'updated_count': 0,
                        'error': str(schedule_error)
                    }
            
            # ✅ CONSERVÉ: Sync basé sur le résultat d'activité avec trigger spécifique
            cls._sync_target_using_centralized_method(activity, "after result processing")
            
            return response
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Convert unexpected errors to validation errors
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )

    @classmethod
    def _sync_target_using_centralized_method(cls, activity: Activity, context: str = ""):
        """
        ✅ SIMPLIFIÉ: Synchronisation avec trigger 'activity_result' spécifique
        Utilise la nouvelle logique simplifiée d'auto_update_status_if_needed
        
        Args:
            activity: Activity qui vient d'être traitée
            context: Contexte pour le logging (optionnel)
        """
        try:
            # Obtenir le CampaignTarget associé
            if not (hasattr(activity, 'campaign_info') and activity.campaign_info):
                return
                
            campaign_target = activity.campaign_info.campaign_target
            
            if not campaign_target:
                return
            
            # Récupérer l'utilisateur depuis l'activité
            user = getattr(activity, 'owner', None)
            
            # ✅ UTILISER LE NOUVEAU TRIGGER SPÉCIFIQUE 'activity_result'
            update_result = campaign_target.auto_update_status_if_needed(
                user=user,
                trigger_type='activity_result'
            )
            
            # Logging pour debugging si nécessaire
            if update_result.get('action_taken') == 'status_updated':
                print(f"TARGET_SYNC: {context} - Target {campaign_target.id} updated from {update_result.get('old_status')} to {update_result.get('new_status')} via activity_result trigger")
            elif update_result.get('action_taken') != 'no_change_needed':
                print(f"TARGET_SYNC: {context} - Target {campaign_target.id} action: {update_result.get('action_taken')} via activity_result trigger")
                            
        except Exception as e:
            # En cas d'erreur de synchronisation, ne pas faire crasher le processus principal
            print(f"TARGET_SYNC_ERROR: {context} - Failed to sync target for activity {getattr(activity, 'id', 'unknown')} via activity_result trigger: {str(e)}")
            pass
    
    @classmethod
    def _ensure_campaign_is_active(cls, activity: Activity):
        """
        ✅ ENHANCED: S'assure que la campagne est ACTIVE et synchronise les targets
        Auto-active la campagne si elle n'est pas dans un état interdit
        + Déclenche la synchronisation de TOUS les targets après activation
        
        Args:
            activity: L'activité en cours de traitement
        """
        try:
            if not (hasattr(activity, 'campaign_info') and activity.campaign_info):
                return
                
            campaign = activity.campaign_info.campaign
            if not campaign:
                return
            
            current_status = campaign.status
            
            # Si déjà ACTIVE, rien à faire
            if current_status == 'ACTIVE':
                return
            
            # ✅ Utiliser la configuration existante pour les états interdits
            if current_status in CONFIG.validation.forbidden_states:
                raise StandardizedValidationError(
                    f"Cannot process activity result: Campaign is {current_status}"
                )
            
            # ✅ NOUVEAU: Récupérer l'utilisateur de l'activité pour audit
            user = getattr(activity, 'owner', None)
            old_status = current_status
            
            # Auto-activation : Passer en ACTIVE
            with transaction.atomic():
                campaign.status = 'ACTIVE'
                campaign.started_at = timezone.now()
                campaign.save()
                
                print(f"AUTO-ACTIVATION: Campaign {campaign.id} {old_status} → ACTIVE (triggered by activity result)")
            
            # ✅ NOUVEAU: Déclencher la synchronisation de TOUS les targets après activation
            try:
                from apps.campaign.models.campaign_target import CampaignTarget
                
                targets_sync_result = CampaignTarget.sync_all_targets_with_campaign_status(
                    campaign=campaign,
                    new_campaign_status='ACTIVE',
                    old_campaign_status=old_status,
                    user=user,
                    notes="Auto-activated due to activity result processing"
                )
                
                print(f"AUTO-SYNC TARGETS: {targets_sync_result.get('targets_updated', 0)}/{targets_sync_result.get('targets_processed', 0)} targets synchronized after campaign auto-activation")
                
            except Exception as sync_error:
                # Log l'erreur mais ne pas faire crasher le processus principal
                print(f"WARNING: Failed to sync targets after campaign auto-activation: {str(sync_error)}")
                # Continuer le traitement de l'activité même si la sync des targets échoue
                pass
            
        except StandardizedValidationError:
            # Re-raise les erreurs de validation
            raise
        except Exception as e:
            # Ne pas faire crasher le processus principal pour auto-activation
            raise StandardizedValidationError(
                f"Failed to auto-activate campaign: {str(e)}"
            )

    @classmethod
    def _ensure_campaign_is_active(cls, activity: Activity):
        """
        ✅ ENHANCED: S'assure que la campagne est ACTIVE et synchronise les targets
        Auto-active la campagne si elle n'est pas dans un état interdit
        + Déclenche la synchronisation de TOUS les targets après activation
        
        Args:
            activity: L'activité en cours de traitement
        """
        try:
            if not (hasattr(activity, 'campaign_info') and activity.campaign_info):
                return
                
            campaign = activity.campaign_info.campaign
            if not campaign:
                return
            
            current_status = campaign.status
            
            # Si déjà ACTIVE, rien à faire
            if current_status == 'ACTIVE':
                return
            
            # ✅ Utiliser la configuration existante pour les états interdits
            if current_status in CONFIG.validation.forbidden_states:
                raise StandardizedValidationError(
                    f"Cannot process activity result: Campaign is {current_status}"
                )
            
            # ✅ NOUVEAU: Récupérer l'utilisateur de l'activité pour audit
            user = getattr(activity, 'owner', None)
            old_status = current_status
            
            # Auto-activation : Passer en ACTIVE
            with transaction.atomic():
                campaign.status = 'ACTIVE'
                campaign.started_at = timezone.now()
                campaign.save()
                
                print(f"AUTO-ACTIVATION: Campaign {campaign.id} {old_status} → ACTIVE (triggered by activity result)")
            
            # ✅ NOUVEAU: Déclencher la synchronisation de TOUS les targets après activation
            try:
                from apps.campaign.models.campaign_target import CampaignTarget
                
                targets_sync_result = CampaignTarget.sync_all_targets_with_campaign_status(
                    campaign=campaign,
                    new_campaign_status='ACTIVE',
                    old_campaign_status=old_status,
                    user=user,
                    notes="Auto-activated due to activity result processing"
                )
                
                print(f"AUTO-SYNC TARGETS: {targets_sync_result.get('targets_updated', 0)}/{targets_sync_result.get('targets_processed', 0)} targets synchronized after campaign auto-activation")
                
            except Exception as sync_error:
                # Log l'erreur mais ne pas faire crasher le processus principal
                print(f"WARNING: Failed to sync targets after campaign auto-activation: {str(sync_error)}")
                # Continuer le traitement de l'activité même si la sync des targets échoue
                pass
            
        except StandardizedValidationError:
            # Re-raise les erreurs de validation
            raise
        except Exception as e:
            # Ne pas faire crasher le processus principal pour auto-activation
            raise StandardizedValidationError(
                f"Failed to auto-activate campaign: {str(e)}"
            )
    
    
    @classmethod
    def _handle_call_result(cls, activity: Activity, result: str, 
                       notes: str = None, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle call activity results with unified logic for sequence and non-sequence campaigns
        
        Args:
            activity: The call activity
            result: The result code
            notes: Optional notes
            is_sequence_campaign: Whether this is part of a sequence campaign
            **kwargs: Additional data
            
        Returns:
            Response: Standardized response with call result processing
        """
        # Validate result is in allowed call results
        if result not in CONFIG.validation.call_results:
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=result)
            )
        
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
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=result)
            )
        
    @classmethod
    def _handle_invalid_phone_number(cls, activity: Activity, sequence_info: ActivitySequence,
                                    notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle invalid phone number - regenerate sequence without phone
        
        Returns:
            Response: Standardized response with sequence regeneration info
        """
        try:
            contact = activity.contacts.first()
            campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
            campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
            
            # Complete current activity
            activity.complete(outcome_notes=f"Invalid phone number. {notes}" if notes else "Invalid phone number")
            
            # Mark contact as having no valid phone
            if contact:
                contact.phone_is_valid = False
                contact.save()
            
            new_activities_count = 0
            
            # Cancel all remaining activities for this contact in this campaign
            if is_sequence_campaign and campaign: 
                remaining_activities = Activity.objects.filter(
                    **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                    contacts=contact,
                    status=Activity.Status.PLANNED
                )
                cancelled_count = remaining_activities.count()
                remaining_activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes="Cancelled due to invalid phone - sequence regenerated"
                )
            
                # Regenerate sequence without phone
                new_activities = cls._regenerate_sequence_without_phone(
                    campaign, campaign_target, contact, sequence_info.sequence_position
                )
                new_activities_count = len(new_activities)
            
            # Prepare response data
            data = {
                'activity_id': activity.id,
                'action': 'sequence_regenerated' if is_sequence_campaign else 'completed',
                f"{CONFIG.fields.contact}_id": contact.id if contact else None,
                'phone_marked_invalid': True,
                'new_activities_count': new_activities_count
            }
            
            if is_sequence_campaign:
                message = f'Invalid phone number. Regenerated sequence without phone calls ({new_activities_count} new activities)'
            else:
                message = 'Invalid phone number recorded'
            
            meta = {
                'operation': 'invalid_phone_handling',
                'sequence_regenerated': is_sequence_campaign,
                'activities_created': new_activities_count
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )

    
    @classmethod
    def _handle_email_bounced(cls, activity: Activity, sequence_info: ActivitySequence,
                             notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle bounced email - regenerate sequence without email
        
        Returns:
            Response: Standardized response with sequence regeneration info
        """
        try:
            contact = activity.contacts.first()
            campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
            campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
            
            # Complete current activity
            activity.complete(outcome_notes=f"Email bounced. {notes}" if notes else "Email bounced")
            
            # Mark contact as having invalid email
            if contact:
                contact.email_is_valid = False
                contact.save()
            
            new_activities_count = 0
            
            if is_sequence_campaign and campaign:
                # Cancel all remaining activities for this contact in this campaign
                remaining_activities = Activity.objects.filter(
                    **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                    contacts=contact,
                    status=Activity.Status.PLANNED
                )
                remaining_activities.update(
                    status=Activity.Status.CANCELLED, 
                    outcome_notes="Cancelled due to bounced email - sequence regenerated"
                )
                
                # Regenerate sequence without email
                has_phone = bool(contact.phone and getattr(contact, 'phone_is_valid', True))
                has_linkedin = bool(contact.linkedin)
                
                new_activities = cls._regenerate_sequence_for_contact(
                    campaign, campaign_target, contact, sequence_info.sequence_position,
                    has_phone=has_phone, has_email=False, has_linkedin=has_linkedin
                )
                new_activities_count = len(new_activities)
            
            # Prepare response data
            data = {
                'activity_id': activity.id,
                'action': 'sequence_regenerated' if is_sequence_campaign else 'completed',
                f"{CONFIG.fields.contact}_id": contact.id if contact else None,
                'email_marked_invalid': True,
                'new_activities_count': new_activities_count
            }
            
            if is_sequence_campaign:
                message = f'Email bounced. Regenerated sequence without emails ({new_activities_count} new activities)'
            else:
                message = 'Email bounce recorded'
            
            meta = {
                'operation': 'email_bounce_handling',
                'sequence_regenerated': is_sequence_campaign,
                'activities_created': new_activities_count
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
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
        CORRIGÉ : Résout le problème de violation de contrainte d'unicité sur previous_activity_id
        """
        try:
            
            from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher

            cleaned_count = cls._clean_sequence_links_for_contact(campaign, contact)
        
            # Get the appropriate sequence based on campaign sequence type and available channels
            sequence_dict, sequence_variant = SequenceDispatcher.get_sequence_with_variant(
                sequence_type=campaign.sequence_type, 
                has_phone=has_phone,
                has_email=has_email,
                has_linkedin=has_linkedin
            )
            
            # Si aucune séquence disponible, retourner liste vide
            if not sequence_dict:
                return []
            
            # Calculate which steps to create based on current progress
            remaining_steps = len(sequence_dict) - start_from_step + 1
            
            # Get the last completed activity to link properly (en dehors de la transaction)
            last_completed = Activity.objects.filter(
                campaign_info__campaign=campaign,
                contacts=contact,
                status=Activity.Status.COMPLETED,
                sequence_info__isnull=False
            ).order_by('-sequence_info__sequence_position').first()
            
            new_activities = []
            
            # CORRECTION : Transaction atomique avec chaînage correct
            with transaction.atomic():
                # IMPORTANT : Initialiser previous_activity avec la dernière activité complétée
                previous_activity = last_completed
                
                # Create activities starting from the next logical step
                for i, (step_num, step_config) in enumerate(sequence_dict.items(), 1):
                    if i <= start_from_step:
                        continue  # Skip already completed/current steps

                    from apps.campaign.services.campaign_activity_service import CampaignActivityService
                    
                    # Create the activity SANS définir previous_activity 
                    activity = CampaignActivityService._create_single_activity(
                        campaign=campaign,
                        campaign_target=campaign_target,
                        contact=contact,
                        step_number=step_num,
                        step_config=step_config,
                        previous_activity=previous_activity,
                        sequence_type=campaign.sequence_type,  # ✅ AJOUTÉ
                        sequence_variant=sequence_variant      # ✅ AJOUTÉ
                    )
                    
                    new_activities.append(activity)
                    
                    # CORRECTION : Link to previous activity correctly
                    if previous_activity:
                        # Update previous activity to point to this one
                        previous_activity.next_activity = activity
                        previous_activity.save()
                        
                        # Update current activity to point back to previous
                        activity.previous_activity = previous_activity
                        activity.save()
                    
                    # CRITIQUE : Current activity becomes previous for next iteration
                    previous_activity = activity  
            
            # APRÈS la transaction : Retourner les activités créées
            return new_activities
            
        except StandardizedValidationError:
            # Re-raise validation errors (including those from cleaning)
            raise
        except Exception as e:
            # En cas d'erreur, les nouvelles activités seront rollback automatiquement
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
            
    @classmethod
    def _clean_sequence_links_for_contact(cls, campaign: Campaign, contact: Contact) -> int:
        """
        Nettoie les liens de séquence pour un contact dans une campagne
        - Nettoie les next_activity de TOUTES les activités
        - Nettoie les previous_activity des activités NON-COMPLÉTÉES uniquement
        - PRÉSERVE les previous_activity des activités COMPLÉTÉES pour l'historique
        
        Args:
            campaign: Campagne concernée
            contact: Contact pour lequel nettoyer les liens
            
        Returns:
            int: Nombre total de liens nettoyés
            
        Raises:
            StandardizedValidationError: Si le nettoyage échoue
        """
        try:
            with transaction.atomic():
                # 1. Nettoyer TOUS les next_activity (même pour les activités complétées)
                forward_cleaned = Activity.objects.filter(
                    **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                    contacts=contact,
                    next_activity__isnull=False
                ).update(next_activity=None)
                
                # 2. Nettoyer les previous_activity SEULEMENT pour les activités NON-COMPLÉTÉES
                backward_cleaned = Activity.objects.filter(
                    **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                    contacts=contact,
                    status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS, Activity.Status.CANCELLED],  # Pas COMPLETED
                    previous_activity__isnull=False
                ).update(previous_activity=None)
                
                total_cleaned = forward_cleaned + backward_cleaned
                
                return total_cleaned
                
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(
                    reason=f"Failed to clean sequence links for contact {contact.id}: {str(e)}"
                )
            )
        
    
    @classmethod
    def _handle_no_answer_call(cls, activity: Activity, sequence_info: ActivitySequence,
                              notes: str = None, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle no answer for calls - increment attempts based on tier
        
        Returns:
            Response: Standardized response with attempt tracking
        """
        try:
            if is_sequence_campaign and sequence_info:
                # Get tier-based max attempts
                account_tier = getattr(activity.account, 'tier', 'C')
                tier_max_attempts = CONFIG.tiers.max_attempts.get(account_tier, 2)
                
                # Increment call attempts
                sequence_info.call_attempts += 1
                sequence_info.save()
                
                # Check if we've reached max attempts for this tier
                if sequence_info.call_attempts >= tier_max_attempts:
                    # Mark activity as completed and move to next step
                    activity.complete(outcome_notes=f"No answer after {sequence_info.call_attempts} attempts")
                    
                    # Make next activity ready if it exists
                    cls._activate_next_activity(activity)
                    
                    data = {
                        'activity_id': activity.id,
                        'action': 'activity_completed',
                        'attempts_made': sequence_info.call_attempts,
                        'max_attempts': tier_max_attempts,
                        'sequence_progressed': True
                    }
                    
                    message = f'Call completed after {sequence_info.call_attempts} attempts'
                    
                else:
                    # Activity stays active for another attempt
                    activity.outcome_notes = f"No answer - attempt {sequence_info.call_attempts}/{tier_max_attempts}"
                    if notes:
                        activity.outcome_notes += f". {notes}"
                    activity.save()
                    
                    data = {
                        'activity_id': activity.id,
                        'action': 'retry_needed',
                        'attempts_made': sequence_info.call_attempts,
                        'max_attempts': tier_max_attempts,
                        'sequence_progressed': False
                    }
                    
                    message = f'Attempt {sequence_info.call_attempts}/{tier_max_attempts} - try again'
                
                meta = {
                    'operation': 'no_answer_handling',
                    'tier': account_tier,
                    'max_attempts_for_tier': tier_max_attempts
                }
                
            else:
                # Non-sequence campaign handling
                activity.complete(outcome_notes=f"No answer. {notes}" if notes else "No answer")
                
                data = {
                    'activity_id': activity.id,
                    'action': 'completed_no_change',
                    'is_sequence_campaign': False
                }
                
                message = 'Activity completed but contact remains in queue'
                meta = {
                    'operation': 'no_answer_handling',
                    'sequence_campaign': False
                }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )

    
    @classmethod
    def _handle_wrong_contact(cls, activity: Activity, sequence_info: ActivitySequence,
                             notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle wrong contact - remove this contact from sequence
        
        Returns:
            Response: Standardized response with contact removal info
        """
        try:
            # Complete current activity
            activity.complete(outcome_notes=f"Wrong contact. {notes}" if notes else "Wrong contact")

            # Cancel remaining activities for this contact in this campaign
            cancelled_count = cls._cancel_contact_sequence(activity)
            
            data = {
                'activity_id': activity.id,
                'action': 'contact_removed',
                'activities_cancelled': cancelled_count
            }
            
            meta = {
                'operation': 'wrong_contact_handling',
                'activities_cancelled': cancelled_count
            }
            
            return StandardizedSuccessResponse.success(
                message='Contact removed from sequence (wrong contact)',
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def _handle_callback_requested(cls, activity: Activity, sequence_info: ActivitySequence,
                            notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle callback request - UPDATED to use State Machine business triggers
        """
        try:
            callback_date = kwargs.get('callback_date')
            callback_type = kwargs.get('callback_type', activity.activity_type)
            
            if not callback_date:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_CALLBACK_DATE_REQUIRED
                )
            
            # Validation que la date de callback est cohérente
            if callback_date < date.today():
                raise StandardizedValidationError(
                    "Callback date cannot be in the past"
                )
            
            with transaction.atomic():
                # Complete current activity
                activity.complete(outcome_notes=f"Callback requested for {callback_date}. {notes}" if notes else f"Callback requested for {callback_date}")
                
                # 🔧 NEW: Use State Machine business trigger
                target_update_result = {}
                if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign_target:
                    campaign_target = activity.campaign_info.campaign_target
                    target_update_result = campaign_target.request_callback(
                        callback_date=callback_date,
                        notes=f"Callback requested: {notes}" if notes else "Callback requested",
                        user=getattr(activity, 'owner', None)
                    )
                
                # Sequence-specific behavior (existing logic)
                if is_sequence_campaign and sequence_info:
                    sequence_info.callback_requested_date = callback_date
                    sequence_info.sequence_paused_until = callback_date
                    sequence_info.save()
                    
                    # Update next activity if it exists
                    next_activity = activity.next_activity
                    if next_activity:
                        if callback_type != next_activity.activity_type:
                            next_activity.activity_type = callback_type
                            next_activity.title = f"Callback: {next_activity.title}"
                            next_activity.save()
            
            # Préparer la réponse avec info State Machine
            data = {
                'activity_id': activity.id,
                'action': 'callback_scheduled',
                'callback_date': callback_date,
                'callback_type': callback_type,
                'is_sequence_campaign': is_sequence_campaign,
                'target_status_updated': target_update_result.get('status_updated', False),
                'new_target_status': target_update_result.get('new_status'),
                'state_machine_used': target_update_result.get('state_machine_used', False)
            }
            
            meta = {
                'operation': 'callback_handling',
                'callback_date': callback_date.isoformat(),
                'sequence_paused': is_sequence_campaign,
                'state_machine_integration': True
            }
            
            return CampaignResponseBuilder.activity_completed(
                result_action='callback_scheduled',
                activity_id=activity.id,
                additional_info=data
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
            
    @classmethod
    def _handle_contact_not_available(cls, activity: Activity, sequence_info: ActivitySequence,
                                    notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle contact not available - similar to no answer but different tracking
        
        Returns:
            Response: Standardized response
        """
        # For now, handle the same as no answer
        return cls._handle_no_answer_call(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
    

    @classmethod
    def _handle_successful_call(cls, activity: Activity, sequence_info: ActivitySequence,
                        notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle successful call - complete sequence and mark target as completed
        MODIFIÉ : Target COMPLETED car objectif campagne atteint (next step secured)
        """
        try:
            # Transaction atomique pour toutes les modifications DB
            with transaction.atomic():
                # Complete current activity
                activity.complete(outcome_notes=f"Activity successful. {notes}" if notes else "Activity successful")
                
                # Get campaign information
                campaign = None
                campaign_target = None
                if hasattr(activity, 'campaign_info'):
                    campaign_info = activity.campaign_info
                    campaign = campaign_info.campaign
                    campaign_target = campaign_info.campaign_target
                
                # For sequence campaigns, end the sequence
                if is_sequence_campaign:
                    cancelled_count = cls._complete_contact_sequence(activity)
                
                # Use State Machine business trigger instead of direct status change
                target_update_result = {}
                if campaign_target:
                    target_update_result = campaign_target.mark_as_completed(
                        reason='successful_activity',
                        notes=f"Successful call activity: {notes}" if notes else "Successful call activity",
                        user=getattr(activity, 'owner', None)
                    )
            
            # Préparer la réponse (après la transaction)
            data = {
                'activity_id': activity.id,
                'action': 'successful_needs_next_step',
                'campaign_id': campaign.id if campaign else None,
                'campaign_target_id': campaign_target.id if campaign_target else None,
                'is_sequence_campaign': is_sequence_campaign,
                'target_status_updated': target_update_result.get('status_updated', False),
                'new_target_status': target_update_result.get('new_status')
            }
            
            meta = {
                'operation': 'successful_call_handling',
                'sequence_completed': is_sequence_campaign,
                'target_completed': True,
                'needs_next_step_selection': True,
                'state_machine_used': target_update_result.get('state_machine_used', False)
            }
            
            return CampaignResponseBuilder.activity_completed(
                result_action='successful_needs_next_step',
                activity_id=activity.id,
                additional_info={
                    'campaign_id': campaign.id if campaign else None,
                    'campaign_target_id': campaign_target.id if campaign_target else None,
                    'next_step_required': True,
                    'target_completed': True
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def _handle_not_interested(cls, activity: Activity, sequence_info: ActivitySequence,
                          notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle not interested - option to disqualify contact or whole account
        MODIFIÉ : Utilise la méthode centralisée pour mise à jour du statut
        """
        try:
            disqualify_account = kwargs.get('disqualify_account', False)
            
            # Complete current activity
            activity.complete(outcome_notes=f"Not interested. {notes}" if notes else "Not interested")
            
            if disqualify_account:
                # Cancel all activities for this account in this campaign
                cancelled_count = cls._cancel_account_sequence(activity)
                
                # ✅ REMPLACER : Utiliser la méthode centralisée pour tous les targets du compte
                if hasattr(activity, 'campaign_info') and activity.campaign_info:
                    campaign = activity.campaign_info.campaign
                    account = activity.account
                    
                    # Mettre à jour tous les campaign targets pour ce compte avec la méthode centralisée
                    from apps.campaign.models.campaign_target import CampaignTarget
                    account_targets = CampaignTarget.objects.filter(
                        campaign=campaign,
                        account=account
                    )
                    
                    targets_updated = []
                    for target in account_targets:
                        update_result = target.mark_as_stopped(
                            reason='not_interested',
                            notes=f"Account-wide not interested: {notes}" if notes else "Account-wide not interested",
                            user=getattr(activity, 'owner', None)
                        )
                        targets_updated.append(update_result)
                
                data = {
                    'activity_id': activity.id,
                    'action': 'account_disqualified',
                    'activities_cancelled': cancelled_count,
                    'targets_updated': len(targets_updated) if 'targets_updated' in locals() else 0,
                    'status_updates': targets_updated if 'targets_updated' in locals() else []
                }
                
                message = 'Account removed from campaign (not interested)'
                
            else:
                # Cancel remaining activities for just this contact
                cancelled_count = cls._cancel_contact_sequence(activity)
                
                #  Use State Machine business trigger
                target_update_result = {'status_updated': False}
                if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign_target:
                    campaign_target = activity.campaign_info.campaign_target
                    target_update_result = campaign_target.mark_as_stopped(
                        reason='not_interested',
                        notes=f"Contact not interested: {notes}" if notes else "Contact not interested",
                        user=getattr(activity, 'owner', None)
                    )
                
                data = {
                    'activity_id': activity.id,
                    'action': 'contact_disqualified',
                    'activities_cancelled': cancelled_count,
                    'target_status_updated': target_update_result.get('status_updated', False),
                    'old_target_status': target_update_result.get('old_status'),
                    'new_target_status': target_update_result.get('new_status'),
                    'state_machine_used': target_update_result.get('state_machine_used', False)
                }
                
                message = 'Contact removed from sequence (not interested)'
            
            meta = {
                'operation': 'not_interested_handling',
                'account_disqualified': disqualify_account,
                'activities_cancelled': cancelled_count,
                'state_machine_integration': True
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def _handle_email_linkedin_result(cls, activity: Activity, result: str,
                                     notes: str = None, is_sequence_campaign: bool = True, **kwargs) -> Response:
        """
        Handle email/LinkedIn activity results
        
        Returns:
            Response: Standardized response with email/LinkedIn result processing
        """
        try:
            # Validate result is in allowed email/LinkedIn results
            if result not in CONFIG.validation.email_linkedin_results:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=result)
                )
            
            sequence_info = getattr(activity, 'sequence_info', None)
            
            # For emails/LinkedIn, typically we just complete and move to next
            # unless there's a specific response
            
            if result == 'NO_RESPONSE':
                # Wait for min_delay, then auto-progress to next step
                activity.complete(outcome_notes=f"No response. {notes}" if notes else "No response")
                cls._activate_next_activity(activity)
                
                data = {
                    'activity_id': activity.id,
                    'action': 'completed_moving_next'
                }
                
                message = 'Email/LinkedIn sent, moving to next step'
                
            elif result == 'POSITIVE_RESPONSE':
                return cls._handle_successful_call(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
            
            elif result == 'UNSUBSCRIBE_OPTOUT':
                activity.complete(outcome_notes=f"Unsubscribed/Opted out. {notes}" if notes else "Unsubscribed/Opted out")
                cancelled_count = cls._cancel_contact_sequence(activity)
                
                data = {
                    'activity_id': activity.id,
                    'action': 'contact_removed',
                    'activities_cancelled': cancelled_count
                }
                
                message = 'Contact removed from sequence (unsubscribed)'
                
            elif result in ['SENT', 'DELIVERED', 'OPENED', 'CLICKED']:
                # Standard email/LinkedIn metrics - complete and move to next
                activity.complete(outcome_notes=notes)
                cls._activate_next_activity(activity)
                
                data = {
                    'activity_id': activity.id,
                    'action': 'completed'
                }
                
                message = CONFIG.messages.activity_completed
            
            elif result == 'BOUNCED':
                return cls._handle_email_bounced(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
                
            else:
                # Invalid result for email/LinkedIn
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=result)
                )
            
            meta = {
                'operation': 'email_linkedin_handling',
                CONFIG.fields.result: result,
                'sequence_progressed': result in ['NO_RESPONSE', 'SENT', 'DELIVERED', 'OPENED', 'CLICKED']
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )

    
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
    def _cancel_contact_sequence(cls, activity: Activity) -> int:
        """
        Cancel remaining activities for this contact in this campaign
        For non-sequence campaigns, update the campaign target status
        
        Returns:
            int: Number of activities cancelled
        """
        contact = activity.contacts.first()
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        campaign_target = activity.campaign_info.campaign_target if hasattr(activity, 'campaign_info') else None
        
        cancelled_count = 0
        
        # Cancel planned activities for this contact
        if contact and campaign:
            cancelled_activities = Activity.objects.filter(
                **{f"campaign_info__{CONFIG.fields.campaign}": campaign},
                contacts=contact,
                status=Activity.Status.PLANNED
            )
            cancelled_count = cancelled_activities.count()
            cancelled_activities.update(status=Activity.Status.CANCELLED)
        
        # For non-sequence campaigns, update the target status
        if campaign and campaign.sequence_type is None and campaign_target:
            campaign_target.status = CampaignTarget.Status.STOPPED
            campaign_target.save()
        
        return cancelled_count
    
    @classmethod
    def _cancel_account_sequence(cls, activity: Activity) -> int:
        """
        Cancel remaining activities for this account in this campaign
        
        Returns:
            int: Number of activities cancelled
        """
        account = activity.account
        campaign = activity.campaign_info.campaign if hasattr(activity, 'campaign_info') else None
        
        cancelled_count = 0
        
        if account and campaign:
            cancelled_activities = Activity.objects.filter(
                **{
                    f"campaign_info__{CONFIG.fields.campaign}": campaign,
                    CONFIG.fields.account: account
                },
                status=Activity.Status.PLANNED
            )
            cancelled_count = cancelled_activities.count()
            cancelled_activities.update(status=Activity.Status.CANCELLED)
        
        return cancelled_count
    
    @classmethod
    def _complete_contact_sequence(cls, activity: Activity) -> int:
        """
        Mark sequence as completed for this contact
        
        Returns:
            int: Number of activities cancelled
        """
        return cls._cancel_contact_sequence(activity)
    
    
    
    @classmethod
    def update_campaign_target_status_for_business_result(cls, campaign_target: CampaignTarget, 
                                                        business_result_type: str, user=None, 
                                                        notes: str = None, callback_date=None) -> dict:
        """
        ENHANCED: Supports callback_date for callback business results
        """
        try:
            old_status = campaign_target.status
            
            # Enhanced mapping with callback date support
            if business_result_type == 'callback' and callback_date:
                update_result = campaign_target.request_callback(
                    callback_date=callback_date,
                    notes=notes or "Business result: callback scheduled",
                    user=user
                )
                trigger_used = 'callback_requested'
                method_used = 'request_callback'
            else:
                # Use the existing mapping for other business results
                business_result_mapping = {
                    'meeting': ('mark_as_completed', 'meeting_scheduled'),
                    'lead': ('mark_as_completed', 'lead_created'), 
                    'opportunity': ('mark_as_completed', 'opportunity_created'),
                    'not_interested': ('mark_as_stopped', 'not_interested'),
                    'wrong_contact': ('mark_as_stopped', 'wrong_contact'),
                    'invalid_contact_info': ('mark_as_stopped', 'invalid_contact_info'),
                    'unsubscribed': ('mark_as_stopped', 'unsubscribed'),
                    'other': ('mark_as_completed', 'manual_completion')
                }
                
                method_name, reason = business_result_mapping.get(
                    business_result_type, 
                    ('mark_as_completed', 'manual_completion')
                )
                
                # Execute the method
                if method_name == 'mark_as_completed':
                    update_result = campaign_target.mark_as_completed(
                        reason=reason,
                        notes=notes or f"Business result: {business_result_type}",
                        user=user
                    )
                elif method_name == 'mark_as_stopped':
                    update_result = campaign_target.mark_as_stopped(
                        reason=reason,
                        notes=notes or f"Business result: {business_result_type}",
                        user=user
                    )
                
                trigger_used = reason
                method_used = method_name
            
            return {
                'status_updated': update_result.get('status_updated', False),
                'old_status': update_result.get('old_status', old_status),
                'new_status': update_result.get('new_status', campaign_target.status),
                'business_result_type': business_result_type,
                'business_trigger_used': trigger_used,
                'method_used': method_used,
                'state_machine_used': update_result.get('state_machine_used', True),
                'campaign_id': campaign_target.campaign.id,
                'target_id': campaign_target.id,
                'timestamp': update_result.get('timestamp', timezone.now().isoformat()),
                'updated_by': user.id if user else None
            }
            
        except Exception as e:
            return {
                'status_updated': False,
                'error': str(e),
                'business_result_type': business_result_type,
                'timestamp': timezone.now().isoformat()
            }


    @classmethod
    def cancel_substage_targets(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Annule toutes les séquences des targets d'un substage spécifique
        RÉUTILISE _cancel_contact_sequence() existant
        
        Args:
            substage_id: ID du substage à annuler
            client_id: ID du client
            user: Utilisateur effectuant l'action
            notes: Notes optionnelles
            
        Returns:
            Response: Résultat standardisé avec détails des annulations
        """
        try:
            return cls._process_substage_targets(
                substage_id=substage_id,
                client_id=client_id,
                action_type='cancel',
                user=user,
                notes=notes
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )

    @classmethod
    def complete_substage_targets(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Complète toutes les séquences des targets d'un substage spécifique
        RÉUTILISE _cancel_contact_sequence() pour nettoyer les activités restantes
        
        Args:
            substage_id: ID du substage à compléter
            client_id: ID du client
            user: Utilisateur effectuant l'action
            notes: Notes optionnelles
            
        Returns:
            Response: Résultat standardisé avec détails des complétions
        """
        try:
            return cls._process_substage_targets(
                substage_id=substage_id,
                client_id=client_id,
                action_type='complete',
                user=user,
                notes=notes
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )

    @classmethod
    def _process_substage_targets(cls, substage_id: int, client_id: str, action_type: str, 
                                 user=None, notes: str = None) -> Response:
        """
        Méthode privée qui factorise la logique commune entre cancel et complete
        
        Args:
            substage_id: ID du substage
            client_id: ID du client
            action_type: 'cancel' ou 'complete'
            user: Utilisateur effectuant l'action
            notes: Notes optionnelles
            
        Returns:
            Response: Résultat standardisé
        """
        # Import local pour éviter circularité  
        from apps.opportunities.models import PipelineSubStage
        
        with transaction.atomic():
            # 1. Valider que le substage existe
            try:
                substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                )
            
            # 2. Trouver tous les CampaignTarget liés à ce substage
            targets = CampaignTarget.objects.filter(
                substage=substage,
                campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                client_id=client_id
            ).select_related('campaign', 'contact')
            
            if not targets.exists():
                operation_verb = 'cancel' if action_type == 'cancel' else 'complete'
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' has no active follow-up targets to {operation_verb}",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'targets_processed': 0,
                        'total_activities_cancelled': 0,
                        'target_results': []
                    },
                    meta={
                        'operation': f'{action_type}_substage_targets',
                        'targets_found': 0
                    }
                )
            
            # 3. Traiter chaque target
            total_cancelled = 0
            targets_updated = 0
            target_results = []
            target_status = CampaignTarget.Status.STOPPED if action_type == 'cancel' else CampaignTarget.Status.COMPLETED
            
            for target in targets:
                # Trouver une activité active de ce target pour utiliser _cancel_contact_sequence
                activity = Activity.objects.filter(
                    campaign_info__campaign_target=target,
                    status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS]
                ).first()
                
                cancelled_count = 0
                target_processed = False
                
                if activity:
                    # ✅ RÉUTILISER la méthode existante _cancel_contact_sequence
                    cancelled_count = cls._cancel_contact_sequence(activity)
                    target_processed = True
                else:
                    # Fallback : gérer les activités plannées directement
                    planned_activities = Activity.objects.filter(
                        campaign_info__campaign_target=target,
                        status=Activity.Status.PLANNED
                    )
                    cancelled_count = planned_activities.count()
                    if cancelled_count > 0:
                        planned_activities.update(status=Activity.Status.CANCELLED)
                        target_processed = True
                    else:
                        # Pas d'activités à traiter, mais on peut quand même changer le statut
                        target_processed = True
                
                total_cancelled += cancelled_count
                
                # Mettre à jour le statut du target
                target_status_updated = False
                if target_processed:
                    target.status = target_status
                    target.save()
                    targets_updated += 1
                    target_status_updated = True
                
                target_results.append({
                    'target_id': target.id,
                    'contact_name': f"{target.contact.first_name} {target.contact.last_name}" if target.contact else "Unknown",
                    'contact_email': target.contact.email if target.contact else None,
                    'activities_cancelled': cancelled_count,
                    'target_status_updated': target_status_updated,
                    'target_status': target.status
                })
            
            # 4. Construire la réponse selon l'action
            action_verb = 'Cancelled' if action_type == 'cancel' else 'Completed'
            action_past = 'stopped' if action_type == 'cancel' else 'completed'
            
            return StandardizedSuccessResponse.success(
                message=f"{action_verb} substage sequences for '{substage.name}' - {targets_updated} targets {action_past}, {total_cancelled} activities cancelled",
                data={
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'targets_processed': len(targets),
                    'targets_updated': targets_updated,
                    'total_activities_cancelled': total_cancelled,
                    'target_results': target_results
                },
                meta={
                    'operation': f'{action_type}_substage_targets',
                    'targets_found': len(targets),
                    'activities_cancelled': total_cancelled
                }
            )

    @classmethod
    def get_target_followup_progress(cls, target_type: str, target_id: int, client_id: str) -> Response:
        """
        Récupère la progression détaillée d'un target dans les campaigns follow-up
        GÉNÉRALISÉ pour tous types de targets (substage, contact, account, lead, opportunity)
        
        Args:
            target_type: Type de target ('substage', 'contact', 'account', 'lead', 'opportunity')
            target_id: ID du target
            client_id: ID du client
            
        Returns:
            Response: Statut et progression détaillée du target
        """
        try:
            # 1. Valider le type de target
            valid_target_types = ['substage', 'contact', 'account', 'lead', 'opportunity']
            if target_type not in valid_target_types:
                raise StandardizedValidationError(
                    CampaignErrorMessages.TARGET_INVALID_TYPE.format(target_type=target_type)
                )
            
            # 2. Construire le filtre selon le type de target
            filter_kwargs = {
                'campaign__campaign_type': Campaign.CampaignType.FOLLOW_UP,
                'client_id': client_id
            }
            
            target_name = "Unknown"
            
            if target_type == 'substage':
                # Import local pour éviter circularité
                from apps.opportunities.models import PipelineSubStage
                try:
                    substage = PipelineSubStage.objects.get(id=target_id, client_id=client_id)
                    target_name = substage.name
                    filter_kwargs['substage'] = substage
                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                    )
            elif target_type == 'contact':
                from apps.accounts.models import Contact
                try:
                    contact = Contact.objects.get(id=target_id, client_id=client_id)
                    target_name = f"{contact.first_name} {contact.last_name}"
                    filter_kwargs['contact'] = contact
                except Contact.DoesNotExist:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                    )
            elif target_type == 'account':
                from apps.accounts.models import Account
                try:
                    account = Account.objects.get(id=target_id, client_id=client_id)
                    target_name = account.company_name
                    filter_kwargs['account'] = account
                except Account.DoesNotExist:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                    )
            elif target_type == 'lead':
                from apps.leads.models import Lead
                try:
                    lead = Lead.objects.get(id=target_id, client_id=client_id)
                    target_name = f"{lead.first_name} {lead.last_name}"
                    filter_kwargs['lead'] = lead
                except Lead.DoesNotExist:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                    )
            elif target_type == 'opportunity':
                from apps.opportunities.models import Opportunity
                try:
                    opportunity = Opportunity.objects.get(id=target_id, client_id=client_id)
                    target_name = opportunity.title
                    filter_kwargs['target_opportunity'] = opportunity
                except Opportunity.DoesNotExist:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
                    )
            
            # 3. Trouver tous les CampaignTarget correspondants
            targets = CampaignTarget.objects.filter(**filter_kwargs).select_related('campaign', 'contact')
            
            if not targets.exists():
                return StandardizedSuccessResponse.success(
                    message=f"{target_type.title()} '{target_name}' is not in any follow-up campaign",
                    data={
                        'target_type': target_type,
                        'target_id': target_id,
                        'target_name': target_name,
                        'in_followup_campaign': False,
                        'progress_percentage': 0,
                        'targets': []
                    },
                    meta={
                        'operation': 'get_target_followup_progress',
                        'targets_found': 0
                    }
                )
            
            # 4. Calculer la progression pour chaque target
            campaign = targets.first().campaign
            targets_status = []
            total_progress = 0
            
            for target in targets:
                # Compter les activités pour ce target
                all_activities = Activity.objects.filter(campaign_info__campaign_target=target)
                completed_activities = all_activities.filter(status=Activity.Status.COMPLETED)
                planned_activities = all_activities.filter(status=Activity.Status.PLANNED)
                
                # Calculer le pourcentage de progression
                total_activities_count = all_activities.count()
                completed_count = completed_activities.count()
                progress_percentage = (completed_count / total_activities_count * 100) if total_activities_count > 0 else 0
                
                total_progress += progress_percentage
                
                # Prochaine activité et dernière activité
                next_activity = planned_activities.order_by('scheduled_date').first()
                last_activity = completed_activities.order_by('-completed_at').first()
                
                # Déterminer le nom du contact selon le type de target
                contact_name = "Unknown"
                contact_email = None
                if target.contact:
                    contact_name = f"{target.contact.first_name} {target.contact.last_name}"
                    contact_email = target.contact.email
                elif target_type == 'lead' and target.lead:
                    contact_name = f"{target.lead.first_name} {target.lead.last_name}"
                    contact_email = target.lead.email
                
                targets_status.append({
                    'target_id': target.id,
                    'contact_name': contact_name,
                    'contact_email': contact_email,
                    'target_status': target.status,
                    'progress_percentage': round(progress_percentage, 1),
                    'total_activities': total_activities_count,
                    'completed_activities': completed_count,
                    'remaining_activities': planned_activities.count(),
                    'next_activity': {
                        'id': next_activity.id,
                        'type': next_activity.activity_type,
                        'scheduled_date': next_activity.scheduled_date.isoformat() if next_activity.scheduled_date else None
                    } if next_activity else None,
                    'last_activity': {
                        'id': last_activity.id,
                        'type': last_activity.activity_type,
                        'completed_at': last_activity.completed_at.isoformat() if last_activity.completed_at else None
                    } if last_activity else None
                })
            
            # 5. Calculer la progression moyenne
            average_progress = total_progress / len(targets) if targets else 0
            
            return StandardizedSuccessResponse.success(
                message=f"Retrieved {target_type} '{target_name}' follow-up progress",
                data={
                    'target_type': target_type,
                    'target_id': target_id,
                    'target_name': target_name,
                    'in_followup_campaign': True,
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'progress_percentage': round(average_progress, 1),
                    'targets_count': len(targets),
                    'targets': targets_status
                },
                meta={
                    'operation': 'get_target_followup_progress',
                    'targets_found': len(targets),
                    'average_progress': round(average_progress, 1)
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )