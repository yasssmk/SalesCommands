# apps/campaign/services/campaign_result_service.py
from typing import List, Dict, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework.response import Response
from apps.activities.models import Activity, ActivitySequence
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact
from apps.sequence.sequences.chasing_sequence import ChasingSequence
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages, CoreErrorMessages

# Import configuration variables
from apps.campaign.config.variables import (
    TIER_MAX_ATTEMPTS, 
    TIER_PRIORITY_SCORES,
    FIELD_NAMES,
    CALL_RESULTS,
    EMAIL_LINKEDIN_RESULTS,
    OPERATION_MESSAGES
)


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
        MODIFIÉ : Ajout de la synchronisation automatique du statut CampaignTarget
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
            is_sequence_campaign = False
            if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign.sequence_type:
                is_sequence_campaign = True
            
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
            
            # NOUVEAU : Synchronisation automatique du statut CampaignTarget
            cls._sync_campaign_target_status(activity)
            
            return response
                
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # Convert unexpected errors to validation errors
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    def _sync_campaign_target_status(cls, activity: Activity):
        """
        Hook pour synchroniser automatiquement le statut du CampaignTarget
        après traitement d'un résultat d'activité
        
        Args:
            activity: Activity qui vient d'être traitée
        """
        try:
            # Obtenir le CampaignTarget associé
            if hasattr(activity, 'campaign_info') and activity.campaign_info:
                campaign_target = activity.campaign_info.campaign_target
                
                if campaign_target:
                    # Synchroniser le statut automatiquement
                    sync_result = campaign_target.auto_update_status_if_needed()
                    
                    # Log pour debugging en cas de changement de statut
                    if sync_result.get('action_taken') == 'status_updated':
                        # En production, ceci pourrait être loggé proprement
                        pass  # MVP : pas de logging complexe
                        
        except Exception:
            # En cas d'erreur de synchronisation, ne pas faire crasher le processus principal
            # MVP : Synchronisation best-effort, pas critique
            pass

    
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
        if result not in CALL_RESULTS:
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
                    **{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign},
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
                f"{FIELD_NAMES['CONTACT']}_id": contact.id if contact else None,
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
                    **{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign},
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
                f"{FIELD_NAMES['CONTACT']}_id": contact.id if contact else None,
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
        SÉCURISÉ : Transaction atomique pour création + linking
        """
        try:
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
            remaining_steps = len(sequence_dict) - start_from_step + 1
            
            # Get the last completed activity to link properly (en dehors de la transaction)
            last_completed = Activity.objects.filter(
                campaign_info__campaign=campaign,
                contacts=contact,
                status=Activity.Status.COMPLETED,
                sequence_info__isnull=False
            ).order_by('-sequence_info__sequence_position').first()
            
            new_activities = []
            
            # AJOUTER : Transaction atomique pour toute la création + linking
            with transaction.atomic():
                previous_activity=last_completed if not new_activities else new_activities[-1]
                
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
                        previous_activity=previous_activity
                    )
                    
                    new_activities.append(activity)
                    
                    # Link to previous activity (dans la transaction)
                    if previous_activity:
                        # Update previous activity to point to this one
                        previous_activity.next_activity = activity
                        previous_activity.save()
                        
                        # Update current activity to point back to previous
                        activity.previous_activity = previous_activity
                        activity.save()
                    
                    # Current activity becomes previous for next iteration
                    previous_activity = activity
            
            # APRÈS la transaction : Retourner les activités créées
            return new_activities
            
        except Exception as e:
            # En cas d'erreur, les nouvelles activités seront rollback automatiquement
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )

    
    @classmethod
    def _create_regenerated_activity(cls, campaign: Campaign, campaign_target: CampaignTarget,
                                   contact: Contact, step_number: int, step_config: Dict,
                                   previous_activity: Activity = None) -> Activity:
        """
        Create a single regenerated activity
        """
        # Create the base activity
        activity = Activity.objects.create(
            title=f"Step {step_number}: {step_config['description']}",
            activity_type=step_config['type'],
            description=step_config['description'],
            account=campaign_target.account,
            owner=campaign.owner,
            status=Activity.Status.PLANNED,
            client_id=campaign.client_id
        )
        
        # Add contact relationship
        activity.contacts.set([contact])
        
        # Create campaign relationship
        from apps.activities.models import ActivityCampaign, ActivitySequence
        ActivityCampaign.objects.create(
            activity=activity,
            campaign=campaign,
            campaign_target=campaign_target,
            client_id=campaign.client_id
        )
        
        # Create sequence relationship with day-counting
        ActivitySequence.objects.create(
            activity=activity,
            source_type=ActivitySequence.SourceType.CAMPAIGN,
            sequence_position=step_number,
            call_attempts=0,
            min_delay_days=step_config['min_delay'],
            client_id=campaign.client_id
        )
        
        return activity
    
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
                tier_max_attempts = TIER_MAX_ATTEMPTS.get(account_tier, 2)
                
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
        Handle callback request - pause sequence or prioritize contact for non-sequence campaigns
        MODIFIER : Éviter les imports circulaires en supprimant les références aux autres services
        """
        try:
            callback_date = kwargs.get('callback_date')
            callback_type = kwargs.get('callback_type', activity.activity_type)
            
            if not callback_date:
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_CALLBACK_DATE_REQUIRED
                )
            
            # AJOUTER : Validation que la date de callback est cohérente
            if callback_date < date.today():
                raise StandardizedValidationError(
                    "Callback date cannot be in the past"
                )
            
            # AJOUTER : Validation que la date est avant la fin de campagne
            if hasattr(activity, 'campaign_info') and activity.campaign_info:
                campaign = activity.campaign_info.campaign
                if callback_date > campaign.end_date:
                    raise StandardizedValidationError(
                        f"Callback date must be before campaign end date ({campaign.end_date})"
                    )
            
            with transaction.atomic():
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
            
            # APRÈS la transaction : Préparer la réponse (pas de modification DB)
            data = {
                'activity_id': activity.id,
                'action': 'callback_scheduled',
                'callback_date': callback_date,
                'callback_type': callback_type,
                'is_sequence_campaign': is_sequence_campaign
            }
            
            meta = {
                'operation': 'callback_handling',
                'callback_date': callback_date.isoformat(),
                'sequence_paused': is_sequence_campaign
            }
            
            return CampaignResponseBuilder.activity_completed(
                result_action='callback_scheduled',
                activity_id=activity.id,
                additional_info={
                    'callback_date': callback_date,
                    'callback_type': callback_type
                }
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
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
    # def _handle_successful_call(cls, activity: Activity, sequence_info: ActivitySequence,
    #                     notes: str, is_sequence_campaign: bool = True, **kwargs) -> Response:
    #     """
    #     Handle successful call - create meeting and manage campaign target appropriately
    #     MODIFIÉ : Ajout de la mise à jour explicite du statut pour les meetings
    #     """
    #     try:
    #         meeting_date = kwargs.get('meeting_date')
            
    #         # Transaction atomique pour toutes les modifications DB
    #         with transaction.atomic():
    #             # Complete current activity
    #             activity.complete(outcome_notes=f"Successfully scheduled meeting. {notes}" if notes else "Successfully scheduled meeting")
                
    #             # Get campaign information
    #             campaign = None
    #             campaign_target = None
    #             if hasattr(activity, 'campaign_info'):
    #                 campaign_info = activity.campaign_info
    #                 campaign = campaign_info.campaign
    #                 campaign_target = campaign_info.campaign_target
                
    #             # Update campaign info
    #             if hasattr(activity, 'campaign_info'):
    #                 campaign_info = activity.campaign_info
    #                 campaign_info.meeting_scheduled = True
    #                 campaign_info.save()
                    
    #                 # NOUVEAU : Mise à jour explicite du statut pour meeting sécurisé
    #                 if campaign_target:
    #                     campaign_target.update_status(
    #                         campaign_target.Status.MEETING_SECURED, 
    #                         save=True, 
    #                         validate_consistency=False  # On force ce statut car on sait qu'un meeting est sécurisé
    #                     )
                
    #             # Create meeting activity if date provided
    #             meeting_activity_id = None
    #             if meeting_date:
    #                 meeting_activity = cls._create_meeting_activity(activity, meeting_date, notes)
    #                 meeting_activity_id = meeting_activity.id
                
    #             # For sequence campaigns, end the sequence
    #             if is_sequence_campaign:
    #                 cancelled_count = cls._complete_contact_sequence(activity)
    #             else:
    #                 # For non-sequence campaigns, remove contact from queue
    #                 if campaign_target:
    #                     # Mark as completed so it doesn't appear in contact list
    #                     campaign_target.status = campaign_target.Status.COMPLETED
    #                     campaign_target.save()
                
    #             # Update campaign objectives
    #             cls._update_campaign_objectives(activity, 'meeting_scheduled')
                
    #             # Determine which AE should receive this opportunity if it's converted later
    #             assigned_ae = None
    #             if campaign:
    #                 from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
    #                 receivers = campaign.get_receivers()
                    
    #                 if receivers.exists():
    #                     assigned_ae = receivers.first()
            
    #         # Préparer la réponse (après la transaction)
    #         data = {
    #             'activity_id': activity.id,
    #             'action': 'meeting_scheduled',
    #             'meeting_date': meeting_date,
    #             'meeting_activity_id': meeting_activity_id,
    #             'assigned_ae': assigned_ae.id if assigned_ae else None,
    #             'is_sequence_campaign': is_sequence_campaign
    #         }
            
    #         meta = {
    #             'operation': 'successful_call_handling',
    #             'meeting_created': bool(meeting_activity_id),
    #             'sequence_completed': is_sequence_campaign
    #         }
            
    #         return CampaignResponseBuilder.activity_completed(
    #             result_action='meeting_scheduled',
    #             activity_id=activity.id,
    #             additional_info={
    #                 'meeting_date': meeting_date,
    #                 'meeting_activity_id': meeting_activity_id,
    #                 'assigned_ae': assigned_ae.id if assigned_ae else None
    #             }
    #         )
            
    #     except StandardizedValidationError:
    #         # Re-raise validation errors
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
    #         )


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
                
                # Dans tous les cas, marquer le target comme COMPLETED
                # Car l'objectif de la campagne est atteint (next step secured)
                if campaign_target:
                    campaign_target.status = campaign_target.Status.COMPLETED
                    campaign_target.save()
            
            # Préparer la réponse (après la transaction)
            data = {
                'activity_id': activity.id,
                'action': 'successful_needs_next_step',
                'campaign_id': campaign.id if campaign else None,
                'campaign_target_id': campaign_target.id if campaign_target else None,
                'is_sequence_campaign': is_sequence_campaign
            }
            
            meta = {
                'operation': 'successful_call_handling',
                'sequence_completed': is_sequence_campaign,
                'target_completed': True,
                'needs_next_step_selection': True
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
        MODIFIÉ : Ajout de la mise à jour explicite du statut pour disqualification
        """
        try:
            disqualify_account = kwargs.get('disqualify_account', False)
            
            # Complete current activity
            activity.complete(outcome_notes=f"Not interested. {notes}" if notes else "Not interested")
            
            if disqualify_account:
                # Cancel all activities for this account in this campaign
                cancelled_count = cls._cancel_account_sequence(activity)
                
                # NOUVEAU : Mettre à jour le statut de tous les targets de ce compte
                if hasattr(activity, 'campaign_info') and activity.campaign_info:
                    campaign = activity.campaign_info.campaign
                    account = activity.account
                    
                    # Mettre à jour tous les campaign targets pour ce compte
                    from apps.campaign.models.campaign_target import CampaignTarget
                    account_targets = CampaignTarget.objects.filter(
                        campaign=campaign,
                        account=account
                    )
                    
                    for target in account_targets:
                        target.update_status(
                            target.Status.STOPPED, 
                            save=True,
                            validate_consistency=False  # Force le statut car disqualification manuelle
                        )
                
                data = {
                    'activity_id': activity.id,
                    'action': 'account_disqualified',
                    'activities_cancelled': cancelled_count
                }
                
                message = 'Account removed from campaign (not interested)'
                
            else:
                # Cancel remaining activities for just this contact
                cancelled_count = cls._cancel_contact_sequence(activity)
                
                # NOUVEAU : Mettre à jour le statut du target de ce contact
                if hasattr(activity, 'campaign_info') and activity.campaign_info.campaign_target:
                    campaign_target = activity.campaign_info.campaign_target
                    campaign_target.update_status(
                        campaign_target.Status.STOPPED, 
                        save=True,
                        validate_consistency=False  # Force le statut car disqualification manuelle
                    )
                
                data = {
                    'activity_id': activity.id,
                    'action': 'contact_disqualified',
                    'activities_cancelled': cancelled_count
                }
                
                message = 'Contact removed from sequence (not interested)'
            
            meta = {
                'operation': 'not_interested_handling',
                'account_disqualified': disqualify_account,
                'activities_cancelled': cancelled_count
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
            if result not in EMAIL_LINKEDIN_RESULTS:
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
                
                message = OPERATION_MESSAGES['ACTIVITY_COMPLETED']
            
            elif result == 'BOUNCED':
                return cls._handle_email_bounced(activity, sequence_info, notes, is_sequence_campaign, **kwargs)
                
            else:
                # Invalid result for email/LinkedIn
                raise StandardizedValidationError(
                    CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=result)
                )
            
            meta = {
                'operation': 'email_linkedin_handling',
                FIELD_NAMES['RESULT']: result,
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
                **{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign},
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
                    f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign,
                    FIELD_NAMES['ACCOUNT']: account
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
    def _create_meeting_activity(cls, activity: Activity, meeting_date: date, notes: str):
        """
        Create a meeting activity from successful sequence
        """

        if meeting_date <= date.today():
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field="Meeting date (must be in the future)"
                )
            )
        
        
        # Create meeting activity
        meeting_activity = Activity.objects.create(
            title=f"Meeting with {activity.account.company_name}",
            activity_type=Activity.ActivityType.MEETING,
            description=f"Meeting scheduled from {activity.title}. {notes}" if notes else f"Meeting scheduled from {activity.title}",
            **{FIELD_NAMES['ACCOUNT']: activity.account},
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
        
        return meeting_activity
    
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
    
    