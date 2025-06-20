# apps/campaign/services/campaign_creation_service.py
from typing import Dict, List, Optional
from datetime import date
from django.utils import timezone
from django.db import transaction
from apps.campaign.models import Campaign, CampaignTarget
from apps.accounts.models import Contact, Account
from .campaign_activity_service import CampaignActivityService
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from rest_framework.response import Response
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)

# Import configuration variables
from apps.campaign.config.variables import (
    FIELD_NAMES,
    OPERATION_MESSAGES,
    CAMPAIGN_STATUSES,
    DEFAULT_PLAYLIST_LIMIT
)


class CampaignCreationService:
    """
    Service specialized in campaign creation and configuration
    Handles creation, state management, and initial setup
    """
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, 
                                    target_accounts: List[int] = None,
                                    target_contacts: List[int] = None,
                                    target_leads: List[int] = None,
                                    target_opportunities: List[int] = None,
                                    targeting_stats: Dict = None,
                                    objective_data: Dict = None) -> Response:  
        """
        Create a new campaign with optional objective and generate all activities
        
        Args:
            campaign_data: Dictionary with campaign fields (name, description, etc.)
            target_accounts: List of account IDs to target
            target_contacts: Optional list of specific contact IDs
            target_leads: Optional list of specific lead IDs
            target_opportunities: Optional list of specific opportunity IDs
            targeting_stats: Optional targeting statistics from preparation
            objective_data: Optional objective data to create with campaign  
            
        Returns:
            Response: Standardized API response with campaign creation results
        """
        try:
            with transaction.atomic():
                # Validate required client_id
                client_id = campaign_data.get('client_id')
                if not client_id:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
                
                # ✅ REMPLACER : Utiliser le serializer au lieu de création directe
                # Préparer le payload pour le serializer
                serializer_data = campaign_data.copy()
                
                # Ajouter les données d'objectif si fournies
                if objective_data:
                    serializer_data['objective'] = objective_data
                
                # Importer et utiliser le serializer
                from apps.campaign.serializers.campaign_serializer import CampaignSerializer
                
                # Créer un contexte minimal pour le serializer
                context = {'request': None}  # MVP : contexte minimal
                
                # Valider et créer via le serializer
                serializer = CampaignSerializer(data=serializer_data, context=context)
                
                if not serializer.is_valid():
                    # Convertir les erreurs du serializer en StandardizedValidationError
                    error_messages = []
                    for field, errors in serializer.errors.items():
                        if isinstance(errors, list):
                            error_messages.extend([f"{field}: {error}" for error in errors])
                        else:
                            error_messages.append(f"{field}: {errors}")
                    raise StandardizedValidationError('; '.join(error_messages))
                
                # Créer la campagne (+ objectif si fourni)
                campaign = serializer.save()
                
                # Create campaign targets (garder logique existante)
                targets_created = cls._create_campaign_targets(
                    campaign, 
                    target_accounts, 
                    target_contacts,
                    target_leads,
                    target_opportunities
                )

                # Generate activities for all targets (garder logique existante)
                activity_result = CampaignActivityService.create_activities_for_campaign(
                    campaign, target_contacts=target_contacts
                )
                
                # ✅ AJOUTER : Inclure info sur l'objectif créé dans la réponse
                objective_created = objective_data is not None
                objective_info = None
                
                if objective_created:
                    # Récupérer l'objectif créé pour la réponse
                    created_objective = campaign.objectives.first()
                    if created_objective:
                        objective_info = {
                            'id': created_objective.id,
                            'name': created_objective.name,
                            'type': created_objective.objective_type,
                            'target_value': float(created_objective.target_value),
                            'is_primary': created_objective.is_primary
                        }
                
                # Utiliser le response builder existant avec info objectif
                response_data = {
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'targets_created': targets_created,
                    'activities_created': activity_result.get('total_activities_created', 0),
                    'skipped_contacts': activity_result.get('skipped_contacts', []),
                    'targeting_stats': targeting_stats,
                    'objective_created': objective_created,  
                    'objective_info': objective_info  
                }
                
                return StandardizedSuccessResponse.success(
                    message=f"Campaign '{campaign.name}' created successfully" + 
                           (" with objective" if objective_created else ""),
                    data=response_data,
                    meta={
                        'operation': 'campaign_creation_with_activities',
                        'objective_created': objective_created,
                        'targets_created': targets_created,
                        'activities_created': activity_result.get('total_activities_created', 0)
                    }
                )
                
        except StandardizedValidationError:
            # Re-raise validation errors (they're already properly formatted)
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    
    @classmethod
    def start_campaign(cls, campaign: Campaign) -> Response:
        """
        Start/activate a campaign - ONE TIME ACTION
        - Mark campaign as active
        - Initialize campaign state
        - Return initial playlist
        """
        try:
            # Get status values from CAMPAIGN_STATUSES
            active_status = next(status[0] for status in CAMPAIGN_STATUSES if status[1] == 'Active')
            completed_status = next(status[0] for status in CAMPAIGN_STATUSES if status[1] == 'Completed')
            cancelled_status = next(status[0] for status in CAMPAIGN_STATUSES if status[1] == 'Cancelled')
            
            # Validate campaign can be started
            if campaign.status == active_status:
                raise StandardizedValidationError(CampaignErrorMessages.CAMPAIGN_ALREADY_STARTED)
            
            if campaign.status in [completed_status, cancelled_status]:
                raise StandardizedValidationError(
                    CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=campaign.status)
                )
            
            # Mark campaign as started
            campaign.status = active_status
            campaign.started_at = timezone.now()
            campaign.save()
            
            # MODIFIER : Utiliser CampaignCoreService au lieu de CampaignQueueService
            from .campaign_core_service import CampaignCoreService
            
            # Get the initial active activities using CampaignCoreService
            try:
                playlist_response = CampaignCoreService.get_campaign_playlist_internal(
                    campaign=campaign,
                    limit=DEFAULT_PLAYLIST_LIMIT
                )
                
                # Extract data from the standardized Response object
                if hasattr(playlist_response, 'data') and 'data' in playlist_response.data:
                    playlist_data = playlist_response.data['data']
                    items = playlist_data.get('items', [])
                    
                    # Create enhanced response with campaign started info
                    additional_data = {
                        'total_pending': playlist_data.get('total_pending', 0),
                        'queue_info': playlist_data.get('queue_info', {}),
                        'campaign_started': True,
                        'started_at': campaign.started_at.isoformat(),
                        'activity_types_breakdown': playlist_data.get('activity_types_breakdown', {})
                    }
                    
                    return CampaignResponseBuilder.campaign_playlist(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        items=items,
                        queue_type=playlist_data.get('queue_type', 'activity'),
                        is_sequence=playlist_data.get('is_sequence', bool(campaign.sequence_type)),
                        total_items=len(items),
                        additional_data=additional_data
                    )
                else:
                    # Fallback si le format de réponse est inattendu
                    raise StandardizedValidationError(
                        CampaignErrorMessages.QUEUE_OPTIMIZATION_FAILED
                    )
                    
            except StandardizedValidationError:
                # Re-raise validation errors
                raise
            except Exception as e:
                # Fallback response si playlist échoue
                return StandardizedSuccessResponse.success(
                    message=f"Campaign {campaign.name} started successfully",
                    data={
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'campaign_started': True,
                        'started_at': campaign.started_at.isoformat(),
                        'playlist_error': str(e)
                    },
                    meta={
                        'operation': 'campaign_start',
                        'playlist_generated': False
                    }
                )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"start failed: {str(e)}")
            )
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Response:
        """
        Pause a campaign (pause all active activities)
        
        Args:
            campaign: The campaign to pause
            pause_until: Optional date to pause until
            
        Returns:
            Response: Standardized API response with pause result
        """
        try:
            from apps.activities.models import Activity
            
            # Get paused status from CAMPAIGN_STATUSES
            paused_status = next(status[0] for status in CAMPAIGN_STATUSES if status[1] == 'Paused')
            
            # Update all planned activities to set pause date
            activities_paused = 0
            
            for activity in Activity.objects.filter(
                **{f"campaign_info__{FIELD_NAMES['CAMPAIGN']}": campaign},
                status=Activity.Status.PLANNED
            ):
                if hasattr(activity, 'sequence_info'):
                    activity.sequence_info.sequence_paused_until = pause_until
                    activity.sequence_info.save()
                    activities_paused += 1
            
            # Update campaign status
            campaign.status = paused_status
            campaign.save()
            
            # Use operation message from config
            message = OPERATION_MESSAGES['CAMPAIGN_PAUSED'].format(name=campaign.name)
            if pause_until:
                message += f" until {pause_until}"
            
            data = {
                f"{FIELD_NAMES['CAMPAIGN']}_id": campaign.id,
                f"{FIELD_NAMES['CAMPAIGN']}_name": campaign.name,
                'activities_paused': activities_paused,
                'pause_until': pause_until.isoformat() if pause_until else None,
                'paused_at': timezone.now().isoformat()
            }
            
            meta = {
                'operation': 'campaign_pause',
                'activities_affected': activities_paused,
                'pause_until': pause_until.isoformat() if pause_until else None
            }
            
            return StandardizedSuccessResponse.success(
                message=message,
                data=data,
                meta=meta
            )
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"pause failed: {str(e)}")
            )
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign) -> Response:
        """
        Resume a paused campaign
        
        Args:
            campaign: The campaign to resume
            
        Returns:
            Response: Standardized API response with resume result
        """
        try:
            from apps.activities.models import Activity
            
            # Get active status from CAMPAIGN_STATUSES
            active_status = next(status[0] for status in CAMPAIGN_STATUSES if status[1] == 'Active')
            
            # Clear pause dates from all activities
            activities_resumed = 0
            
            for activity in Activity.objects.filter(campaign_info__campaign=campaign):
                if hasattr(activity, 'sequence_info') and activity.sequence_info.sequence_paused_until:
                    activity.sequence_info.sequence_paused_until = None
                    activity.sequence_info.save()
                    activities_resumed += 1
            
            # Update campaign status
            campaign.status = active_status
            campaign.save()
            
            # MODIFIER : Utiliser CampaignCoreService au lieu de CampaignExecutionService
            from .campaign_core_service import CampaignCoreService
            
            # Get updated playlist using CampaignCoreService
            try:
                updated_playlist_response = CampaignCoreService.get_campaign_playlist_internal(
                    campaign=campaign,
                    limit=DEFAULT_PLAYLIST_LIMIT
                )
                
                # Extract active activities count from the standardized Response
                active_activities_count = 0
                if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
                    playlist_data = updated_playlist_response.data['data']
                    items = playlist_data.get('items', [])
                    active_activities_count = len(items)
                    
            except Exception:
                # Si la récupération de playlist échoue, continuer sans (non-critique)
                active_activities_count = 0
            
            data = {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'activities_resumed': activities_resumed,
                'active_activities': active_activities_count,
                'resumed_at': timezone.now().isoformat()
            }
            
            meta = {
                'operation': 'campaign_resume',
                'activities_affected': activities_resumed,
                'active_activities_available': active_activities_count
            }
            
            # Use operation message from config
            message = OPERATION_MESSAGES['CAMPAIGN_RESUMED'].format(name=campaign.name)
            
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
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"resume failed: {str(e)}")
            )
    
    @classmethod
    def _create_campaign_targets(cls, campaign: Campaign, 
                                target_accounts: List[int] = None,
                                target_contacts: List[int] = None,
                                target_leads: List[int] = None,
                                target_opportunities: List[int] = None) -> int:
        """
        Create campaign targets for the specified accounts/contacts/leads/opportunities
        All targets will eventually generate activities for their associated contacts
        
        Args:
            campaign: Campaign to create targets for
            target_accounts: List of account IDs
            target_contacts: List of contact IDs
            target_leads: List of lead IDs
            target_opportunities: List of opportunity IDs
            
        Returns:
            int: Number of targets created
        """
        from apps.accounts.models import Account, Contact
        from apps.leads.models import Lead
        from apps.opportunities.models import Opportunity
        
        targets_created = 0
        client_id = campaign.client_id
        
        # Create account targets
        if target_accounts:
            for account_id in target_accounts:
                try:
                    account = Account.objects.get(id=account_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(
                        **{FIELD_NAMES['CAMPAIGN']: campaign, FIELD_NAMES['ACCOUNT']: account}
                    ).exists():
                        CampaignTarget.objects.create(
                            **{
                                FIELD_NAMES['CAMPAIGN']: campaign,
                                FIELD_NAMES['ACCOUNT']: account,
                                'client_id': client_id
                            }
                        )
                        targets_created += 1
                            
                except Account.DoesNotExist:
                    continue
        
        # Create contact targets
        if target_contacts:
            for contact_id in target_contacts:
                try:
                    contact = Contact.objects.get(id=contact_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(
                        **{FIELD_NAMES['CAMPAIGN']: campaign, FIELD_NAMES['CONTACT']: contact}
                    ).exists():
                        CampaignTarget.objects.create(
                            **{
                                FIELD_NAMES['CAMPAIGN']: campaign,
                                FIELD_NAMES['CONTACT']: contact,
                                'client_id': client_id
                            }
                        )
                        targets_created += 1
                            
                except Contact.DoesNotExist:
                    continue
        
        # Create lead targets
        if target_leads:
            for lead_id in target_leads:
                try:
                    lead = Lead.objects.get(id=lead_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(
                        **{FIELD_NAMES['CAMPAIGN']: campaign, FIELD_NAMES['LEAD']: lead}
                    ).exists():
                        CampaignTarget.objects.create(
                            **{
                                FIELD_NAMES['CAMPAIGN']: campaign,
                                FIELD_NAMES['LEAD']: lead,
                                'client_id': client_id
                            }
                        )
                        targets_created += 1
                            
                except Lead.DoesNotExist:
                    continue
        
        # Create opportunity targets
        if target_opportunities:
            for opportunity_id in target_opportunities:
                try:
                    opportunity = Opportunity.objects.get(id=opportunity_id)
                    
                    # Check if target already exists
                    if not CampaignTarget.objects.filter(
                        **{FIELD_NAMES['CAMPAIGN']: campaign, FIELD_NAMES['TARGET_OPPORTUNITY']: opportunity}
                    ).exists():
                        CampaignTarget.objects.create(
                            **{
                                FIELD_NAMES['CAMPAIGN']: campaign,
                                FIELD_NAMES['TARGET_OPPORTUNITY']: opportunity,
                                'client_id': client_id
                            }
                        )
                        targets_created += 1
                            
                except Opportunity.DoesNotExist:
                    continue
        
        return targets_created

    @classmethod
    def create_campaign_with_objective(cls, campaign_data: Dict, objective_data: Dict = None) -> Campaign:
        """
        Create campaign with optional objective
        Extracted from CampaignSerializer to separate business logic from validation
        
        Args:
            campaign_data: Validated campaign data
            objective_data: Optional objective data to create with campaign
            
        Returns:
            Campaign: Created campaign instance
        """
        try:
            with transaction.atomic():
                # Create campaign entity
                campaign = cls._create_campaign_entity(campaign_data)
                
                # Create primary objective if provided
                if objective_data:
                    objective = cls._create_primary_objective(campaign, objective_data)
                    
                return campaign
                
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(
                    reason=f"Campaign creation failed: {str(e)}"
                )
            )

    @classmethod
    def _create_campaign_entity(cls, campaign_data: Dict) -> Campaign:
        """Create the campaign entity with validated data"""
        try:
            # Import local pour éviter circularité
            from apps.campaign.models import Campaign
            
            campaign = Campaign.objects.create(**campaign_data)
            return campaign
            
        except Exception as e:
            raise StandardizedValidationError(
                f"Failed to create campaign: {str(e)}"
            )

    @classmethod  
    def _create_primary_objective(cls, campaign: Campaign, objective_data: Dict):
        """Create primary objective for campaign"""
        try:
            # Import local pour éviter circularité
            from apps.campaign.models.campaign_objective import CampaignObjective
            
            # Set as primary and link to campaign
            objective_data['campaign'] = campaign
            objective_data['is_primary'] = True
            objective_data['client_id'] = campaign.client_id
            
            objective = CampaignObjective.objects.create(**objective_data)
            return objective
            
        except Exception as e:
            raise StandardizedValidationError(
                f"Failed to create campaign objective: {str(e)}"
            )