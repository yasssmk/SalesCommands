# apps/opportunities/services/substage_followup_service.py
# VERSION REFACTORISÉE - Coordinateur ultra-léger

from django.db import transaction
from rest_framework.response import Response
from typing import List
from datetime import date, timedelta

from apps.opportunities.models import PipelineSubStage
from core.exceptions import StandardizedValidationError
from core.error_messages import OpportunityErrorMessages
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse


class SubStageFollowUpService:
    """
    Service coordinateur léger pour gérer l'intégration substages ↔ campaigns follow-up
    
    RESPONSABILITÉS LÉGITIMES (app opportunities) :
    - Validation des substages
    - Récupération des stakeholders
    - Formatage des réponses pour l'API opportunities
    
    DÉLÉGATIONS (app campaign) :
    - Création/gestion des campaigns → CampaignCreationService
    - Gestion des targets → CampaignTargetService  
    - Actions sur séquences → CampaignResultService
    """
    
    FOLLOWUP_CAMPAIGN_NAME = "Client Follow-up Campaign"
    
    @classmethod
    def add_substage_to_followup(cls, substage_id: int, user, client_id: str) -> Response:
        """
        Ajoute un substage à la campaign follow-up unique du client
        COORDINATEUR LÉGER : Valide + délègue + formate
        """
        try:
            with transaction.atomic():
                # 1. ✅ RESPONSABILITÉ LÉGITIME : Valider le substage
                substage = cls._get_validated_substage(substage_id, client_id)
                
                # 2. ✅ RESPONSABILITÉ LÉGITIME : Vérifier qu'il n'est pas déjà en follow-up
                if cls._is_substage_in_followup(substage):
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' is already in a follow-up campaign"
                    )
                
                # 3. ✅ RESPONSABILITÉ LÉGITIME : Récupérer les stakeholders
                stakeholders = cls._get_substage_stakeholders(substage)
                if not stakeholders:
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' has no stakeholders. Add stakeholders before adding to follow-up."
                    )
                
                # 4. ✅ DÉLÉGATION : Utiliser CampaignCreationService pour gérer la campaign
                from apps.campaign.services.campaign_creation_service import CampaignCreationService
                
                campaign_data = {
                    'name': cls.FOLLOWUP_CAMPAIGN_NAME,
                    'description': 'Automatic follow-up campaign for pipeline substages',
                    'sequence_type': 'FOLLOW_UP',
                    'start_date': date.today(),
                    'end_date': date.today() + timedelta(days=365),
                    'status': 'ACTIVE',
                    'client_id': client_id
                }
                
                # Utiliser la logique existante dans create_campaign_with_activities 
                # qui gère déjà l'unicité des follow-up campaigns
                target_contacts = [contact.id for contact in stakeholders]
                
                campaign_response = CampaignCreationService.create_campaign_with_activities(
                    campaign_data=campaign_data,
                    target_accounts=[],
                    target_contacts=target_contacts,
                    target_leads=[],
                    target_opportunities=[],
                    targeting_stats=None,
                    request=None
                )
                
                # 5. ✅ DÉLÉGATION : Ajouter le contexte substage aux targets créés
                if hasattr(campaign_response, 'data') and 'data' in campaign_response.data:
                    campaign_id = campaign_response.data['data']['campaign_id']
                    cls._add_substage_context_to_targets(campaign_id, substage, stakeholders)
                
                # 6. ✅ RESPONSABILITÉ LÉGITIME : Formater la réponse pour l'API opportunities
                return cls._format_add_response(campaign_response, substage, len(stakeholders))
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to add substage to follow-up: {str(e)}")
    
    @classmethod
    def remove_substage_from_followup(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Supprime un substage de la campaign follow-up
        COORDINATEUR LÉGER : Valide + délègue + formate
        """
        try:
            # 1. ✅ RESPONSABILITÉ LÉGITIME : Valider le substage
            substage = cls._get_validated_substage(substage_id, client_id)
            
            # 2. ✅ RESPONSABILITÉ LÉGITIME : Vérifier qu'il est bien en follow-up
            if not cls._is_substage_in_followup(substage):
                raise StandardizedValidationError(
                    f"SubStage '{substage.name}' is not in any follow-up campaign"
                )
            
            # 3. ✅ DÉLÉGATION : Utiliser CampaignResultService pour annuler les targets
            from apps.campaign.services.campaign_result_service import CampaignResultService
            
            cancel_response = CampaignResultService.cancel_substage_targets(
                substage_id=substage_id,
                client_id=client_id,
                user=user,
                notes=notes
            )
            
            # 4. ✅ DÉLÉGATION : Supprimer les targets du substage
            cls._remove_substage_targets(substage_id, client_id)
            
            # 5. ✅ RESPONSABILITÉ LÉGITIME : Formater la réponse pour l'API opportunities
            return cls._format_remove_response(cancel_response, substage)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to remove substage from follow-up: {str(e)}")
    
    @classmethod
    def complete_substage_sequence(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Marque la séquence follow-up d'un substage comme completed
        COORDINATEUR LÉGER : Valide + délègue + formate
        """
        try:
            # 1. ✅ RESPONSABILITÉ LÉGITIME : Valider le substage
            substage = cls._get_validated_substage(substage_id, client_id)
            
            # 2. ✅ RESPONSABILITÉ LÉGITIME : Vérifier qu'il est bien en follow-up
            if not cls._is_substage_in_followup(substage):
                raise StandardizedValidationError(
                    f"SubStage '{substage.name}' is not in any follow-up campaign"
                )
            
            # 3. ✅ DÉLÉGATION : Utiliser CampaignResultService pour compléter les targets
            from apps.campaign.services.campaign_result_service import CampaignResultService
            
            complete_response = CampaignResultService.complete_substage_targets(
                substage_id=substage_id,
                client_id=client_id,
                user=user,
                notes=notes
            )
            
            # 4. ✅ RESPONSABILITÉ LÉGITIME : Formater la réponse pour l'API opportunities
            return cls._format_complete_response(complete_response, substage)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to complete substage sequence: {str(e)}")
    
    @classmethod
    def cancel_substage_sequence(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Annule la séquence follow-up d'un substage
        COORDINATEUR LÉGER : Valide + délègue + formate
        """
        try:
            # 1. ✅ RESPONSABILITÉ LÉGITIME : Valider le substage
            substage = cls._get_validated_substage(substage_id, client_id)
            
            # 2. ✅ RESPONSABILITÉ LÉGITIME : Vérifier qu'il est bien en follow-up
            if not cls._is_substage_in_followup(substage):
                raise StandardizedValidationError(
                    f"SubStage '{substage.name}' is not in any follow-up campaign"
                )
            
            # 3. ✅ DÉLÉGATION : Utiliser CampaignResultService pour annuler les targets
            from apps.campaign.services.campaign_result_service import CampaignResultService
            
            cancel_response = CampaignResultService.cancel_substage_targets(
                substage_id=substage_id,
                client_id=client_id,
                user=user,
                notes=notes
            )
            
            # 4. ✅ RESPONSABILITÉ LÉGITIME : Formater la réponse pour l'API opportunities
            return cls._format_cancel_response(cancel_response, substage)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to cancel substage sequence: {str(e)}")
    
    @classmethod
    def get_substage_followup_status(cls, substage_id: int, client_id: str) -> Response:
        """
        Récupère le statut détaillé du substage dans la campaign follow-up
        COORDINATEUR LÉGER : Valide + délègue + formate
        """
        try:
            # 1. ✅ RESPONSABILITÉ LÉGITIME : Valider le substage
            substage = cls._get_validated_substage(substage_id, client_id)
            
            # 2. ✅ DÉLÉGATION : Utiliser CampaignResultService pour récupérer la progression
            from apps.campaign.services.campaign_result_service import CampaignResultService
            
            progress_response = CampaignResultService.get_target_followup_progress(
                target_type='substage',
                target_id=substage_id,
                client_id=client_id
            )
            
            # 3. ✅ RESPONSABILITÉ LÉGITIME : Formater la réponse pour l'API opportunities
            return cls._format_status_response(progress_response, substage)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to get substage follow-up status: {str(e)}")
    
    # ===== MÉTHODES PRIVÉES - RESPONSABILITÉS LÉGITIMES =====
    
    @classmethod
    def _get_validated_substage(cls, substage_id: int, client_id: str) -> PipelineSubStage:
        """✅ RESPONSABILITÉ LÉGITIME : Validation des substages"""
        try:
            return PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(OpportunityErrorMessages.SUBSTAGE_NOT_FOUND)
    
    @classmethod
    def _is_substage_in_followup(cls, substage: PipelineSubStage) -> bool:
        """✅ RESPONSABILITÉ LÉGITIME : Vérification statut substage"""
        from apps.campaign.models import CampaignTarget, Campaign
        return CampaignTarget.objects.filter(
            substage=substage,
            campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
            client_id=substage.client_id
        ).exists()
    
    @classmethod
    def _get_substage_stakeholders(cls, substage: PipelineSubStage) -> List:
        """✅ RESPONSABILITÉ LÉGITIME : Récupération des stakeholders du substage"""
        # Logique spécifique à l'app opportunities pour récupérer les stakeholders
        # Cette méthode doit être implémentée selon votre modèle de données
        stakeholders = []
        
        # EXEMPLE : Si les stakeholders sont stockés dans le substage
        if hasattr(substage, 'stakeholders') and substage.stakeholders.exists():
            stakeholders = list(substage.stakeholders.all())
        
        # EXEMPLE : Si les stakeholders viennent de l'opportunity
        elif hasattr(substage, 'stage') and hasattr(substage.stage, 'opportunity'):
            opportunity = substage.stage.opportunity
            if hasattr(opportunity, 'contacts') and opportunity.contacts.exists():
                stakeholders = list(opportunity.contacts.all())
        
        return stakeholders
    
    @classmethod
    def _add_substage_context_to_targets(cls, campaign_id: int, substage: PipelineSubStage, stakeholders: List):
        """✅ DÉLÉGATION LÉGÈRE : Ajouter le contexte substage aux targets créés"""
        from apps.campaign.models import CampaignTarget
        
        # Mettre à jour les targets pour ajouter le contexte substage
        substage_context = {
            'substage_id': substage.id,
            'objective': substage.objective if hasattr(substage, 'objective') else None,
            'stakeholders_count': len(stakeholders)
        }
        
        CampaignTarget.objects.filter(
            campaign_id=campaign_id,
            contact__in=stakeholders
        ).update(
            substage=substage,
            substage_objective=substage_context.get('objective'),
            substage_context=substage_context
        )
    
    @classmethod
    def _remove_substage_targets(cls, substage_id: int, client_id: str):
        """✅ DÉLÉGATION LÉGÈRE : Supprimer les targets liés au substage"""
        from apps.campaign.models import CampaignTarget, Campaign
        
        CampaignTarget.objects.filter(
            substage_id=substage_id,
            campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
            client_id=client_id
        ).delete()
    
    # ===== MÉTHODES DE FORMATAGE - RESPONSABILITÉS LÉGITIMES =====
    
    @classmethod
    def _format_add_response(cls, campaign_response: Response, substage: PipelineSubStage, stakeholders_count: int) -> Response:
        """✅ RESPONSABILITÉ LÉGITIME : Formatage pour l'API opportunities"""
        original_data = campaign_response.data.get('data', {})
        
        return StandardizedSuccessResponse.success(
            message=f"SubStage '{substage.name}' added to follow-up campaign successfully",
            data={
                'substage_id': substage.id,
                'substage_name': substage.name,
                'campaign_id': original_data.get('campaign_id'),
                'campaign_name': original_data.get('campaign_name'),
                'targets_created': original_data.get('targets_created', 0),
                'stakeholders_count': stakeholders_count,
                'action': 'substage_added_to_followup'
            }
        )
    
    @classmethod
    def _format_remove_response(cls, cancel_response: Response, substage: PipelineSubStage) -> Response:
        """✅ RESPONSABILITÉ LÉGITIME : Formatage pour l'API opportunities"""
        original_data = cancel_response.data.get('data', {})
        
        return StandardizedSuccessResponse.success(
            message=f"SubStage '{substage.name}' removed from follow-up campaign successfully",
            data={
                'substage_id': substage.id,
                'substage_name': substage.name,
                'action': 'substage_removed_from_followup',
                'targets_processed': original_data.get('targets_processed', 0),
                'activities_cancelled': original_data.get('total_activities_cancelled', 0)
            }
        )
    
    @classmethod
    def _format_complete_response(cls, complete_response: Response, substage: PipelineSubStage) -> Response:
        """✅ RESPONSABILITÉ LÉGITIME : Formatage pour l'API opportunities"""
        original_data = complete_response.data.get('data', {})
        
        return StandardizedSuccessResponse.success(
            message=f"SubStage '{substage.name}' sequence completed successfully",
            data={
                'substage_id': substage.id,
                'substage_name': substage.name,
                'action': 'substage_sequence_completed',
                'targets_processed': original_data.get('targets_processed', 0),
                'activities_cancelled': original_data.get('total_activities_cancelled', 0)
            }
        )
    
    @classmethod
    def _format_cancel_response(cls, cancel_response: Response, substage: PipelineSubStage) -> Response:
        """✅ RESPONSABILITÉ LÉGITIME : Formatage pour l'API opportunities"""
        original_data = cancel_response.data.get('data', {})
        
        return StandardizedSuccessResponse.success(
            message=f"SubStage '{substage.name}' sequence cancelled successfully",
            data={
                'substage_id': substage.id,
                'substage_name': substage.name,
                'action': 'substage_sequence_cancelled',
                'targets_processed': original_data.get('targets_processed', 0),
                'activities_cancelled': original_data.get('total_activities_cancelled', 0)
            }
        )
    
    @classmethod
    def _format_status_response(cls, progress_response: Response, substage: PipelineSubStage) -> Response:
        """✅ RESPONSABILITÉ LÉGITIME : Formatage pour l'API opportunities"""
        original_data = progress_response.data.get('data', {})
        
        return StandardizedSuccessResponse.success(
            message=f"SubStage '{substage.name}' follow-up status retrieved successfully",
            data={
                'substage_id': substage.id,
                'substage_name': substage.name,
                'in_followup_campaign': original_data.get('in_followup_campaign', False),
                'campaign_id': original_data.get('campaign_id'),
                'campaign_name': original_data.get('campaign_name'),
                'progress_percentage': original_data.get('progress_percentage', 0),
                'targets_count': original_data.get('targets_count', 0),
                'targets': original_data.get('targets', [])
            }
        )