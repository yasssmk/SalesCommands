# apps/opportunities/services/substage_followup_service.py

from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from typing import Dict, List, Optional
from datetime import date, timedelta

from apps.campaign.models import Campaign, CampaignTarget
from apps.campaign.services.campaign_core_service import CampaignCoreService
from apps.campaign.services.campaign_result_service import CampaignResultService
from apps.opportunities.models import PipelineSubStage
from apps.activities.models import Activity
from core.exceptions import StandardizedValidationError
from core.error_messages import OpportunityErrorMessages
from apps.campaign.utils.standardized_responses import StandardizedSuccessResponse


class SubStageFollowUpService:
    """
    Service pour gérer l'ajout/suppression de substages dans les campaigns follow-up
    REFACTORISÉ : Utilise uniquement les méthodes existantes de CampaignResultService
    """
    
    FOLLOWUP_CAMPAIGN_NAME = "Client Follow-up Campaign"
    
    @classmethod
    def add_substage_to_followup(cls, substage_id: int, user, client_id: str) -> Response:
        """
        Ajoute un substage à la campaign follow-up unique du client
        """
        try:
            with transaction.atomic():
                # 1. Récupérer et valider le substage
                substage = cls._get_validated_substage(substage_id, client_id)
                
                # 2. Vérifier qu'il n'est pas déjà dans une follow-up
                if cls._is_substage_in_followup(substage):
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' is already in a follow-up campaign"
                    )
                
                # 3. Récupérer les stakeholders du substage
                stakeholders = cls._get_substage_stakeholders(substage)
                
                if not stakeholders:
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' has no stakeholders. Add stakeholders before adding to follow-up."
                    )
                
                # 4. Utiliser CampaignCoreService pour créer/récupérer campaign follow-up
                campaign = cls._get_or_create_followup_campaign_via_service(client_id, stakeholders, user)
                
                # 5. Créer les CampaignTarget pour ce substage spécifiquement
                targets_created = cls._create_substage_targets(campaign, substage, stakeholders, user)
                
                # 6. Retourner le résultat
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' added to follow-up campaign successfully",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'targets_created': targets_created,
                        'stakeholders_count': len(stakeholders)
                    }
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to add substage to follow-up: {str(e)}")
    
    @classmethod
    def remove_substage_from_followup(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Supprime un substage de la campaign follow-up
        Utilise CampaignResultService._cancel_contact_sequence existant
        """
        try:
            with transaction.atomic():
                # 1. Valider le substage existe
                substage = cls._get_validated_substage(substage_id, client_id)
                
                # 2. Trouver tous les CampaignTarget liés à ce substage
                targets = CampaignTarget.objects.filter(
                    substage=substage,
                    campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                    client_id=client_id
                ).select_related('campaign', 'contact')
                
                if not targets.exists():
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' is not in any follow-up campaign"
                    )
                
                total_cancelled = 0
                campaign_name = targets.first().campaign.name
                target_results = []
                
                # 3. Pour chaque target, utiliser CampaignResultService pour annuler la séquence
                for target in targets:
                    # Trouver une activité de ce target pour utiliser _cancel_contact_sequence
                    activity = Activity.objects.filter(
                        campaign_info__campaign_target=target,
                        status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS]
                    ).first()
                    
                    cancelled_count = 0
                    if activity:
                        # Utiliser la méthode existante de CampaignResultService
                        cancelled_count = CampaignResultService._cancel_contact_sequence(activity)
                    else:
                        # Fallback : annuler directement les activités plannées
                        cancelled_activities = Activity.objects.filter(
                            campaign_info__campaign_target=target,
                            status=Activity.Status.PLANNED
                        )
                        cancelled_count = cancelled_activities.count()
                        cancelled_activities.update(status=Activity.Status.CANCELLED)
                    
                    total_cancelled += cancelled_count
                    
                    target_results.append({
                        'target_id': target.id,
                        'contact_name': f"{target.contact.first_name} {target.contact.last_name}" if target.contact else "Unknown",
                        'activities_cancelled': cancelled_count
                    })
                
                # 4. Supprimer tous les targets liés à ce substage
                targets_count = targets.count()
                targets.delete()
                
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' removed from follow-up campaign successfully. {targets_count} contacts removed.",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'action': 'substage_removed_from_followup',
                        'campaign_name': campaign_name,
                        'targets_removed': targets_count,
                        'total_activities_cancelled': total_cancelled,
                        'target_results': target_results
                    }
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to remove substage from follow-up: {str(e)}")
    
    @classmethod
    def complete_substage_sequence(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Marque la séquence follow-up d'un substage comme completed
        Utilise CampaignResultService._complete_contact_sequence existant
        """
        try:
            with transaction.atomic():
                # 1. Valider le substage existe
                substage = cls._get_validated_substage(substage_id, client_id)
                
                # 2. Trouver tous les CampaignTarget liés à ce substage
                targets = CampaignTarget.objects.filter(
                    substage=substage,
                    campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                    client_id=client_id
                ).select_related('campaign', 'contact')
                
                if not targets.exists():
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' is not in any follow-up campaign"
                    )
                
                total_cancelled = 0
                targets_updated = 0
                target_results = []
                
                # 3. Pour chaque target, utiliser CampaignResultService pour compléter la séquence
                for target in targets:
                    # Trouver une activité de ce target pour utiliser _complete_contact_sequence
                    activity = Activity.objects.filter(
                        campaign_info__campaign_target=target,
                        status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS]
                    ).first()
                    
                    cancelled_count = 0
                    if activity:
                        # Utiliser la méthode existante de CampaignResultService
                        cancelled_count = CampaignResultService._complete_contact_sequence(activity)
                    else:
                        # Fallback : annuler directement les activités plannées restantes
                        cancelled_activities = Activity.objects.filter(
                            campaign_info__campaign_target=target,
                            status=Activity.Status.PLANNED
                        )
                        cancelled_count = cancelled_activities.count()
                        cancelled_activities.update(status=Activity.Status.CANCELLED)
                    
                    total_cancelled += cancelled_count
                    
                    # Marquer le target comme completed
                    target_update_result = target.mark_as_completed(
                        reason='substage_completed',
                        notes=f"SubStage sequence completed: {notes}" if notes else "SubStage sequence completed",
                        user=user
                    )
                    
                    if target_update_result.get('status_updated'):
                        targets_updated += 1
                    
                    target_results.append({
                        'target_id': target.id,
                        'contact_name': f"{target.contact.first_name} {target.contact.last_name}" if target.contact else "Unknown",
                        'activities_cancelled': cancelled_count,
                        'target_status_updated': target_update_result.get('status_updated', False),
                        'old_status': target_update_result.get('old_status'),
                        'new_status': target_update_result.get('new_status')
                    })
                
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' sequence completed successfully for {len(targets)} contacts",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'action': 'substage_sequence_completed',
                        'total_targets': len(targets),
                        'targets_updated': targets_updated,
                        'total_activities_cancelled': total_cancelled,
                        'target_results': target_results
                    }
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to complete substage sequence: {str(e)}")
    
    @classmethod
    def cancel_substage_sequence(cls, substage_id: int, client_id: str, user=None, notes: str = None) -> Response:
        """
        Annule la séquence follow-up d'un substage
        Utilise CampaignResultService._cancel_contact_sequence existant
        """
        try:
            with transaction.atomic():
                # 1. Valider le substage existe
                substage = cls._get_validated_substage(substage_id, client_id)
                
                # 2. Trouver tous les CampaignTarget liés à ce substage
                targets = CampaignTarget.objects.filter(
                    substage=substage,
                    campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                    client_id=client_id
                ).select_related('campaign', 'contact')
                
                if not targets.exists():
                    raise StandardizedValidationError(
                        f"SubStage '{substage.name}' is not in any follow-up campaign"
                    )
                
                total_cancelled = 0
                targets_updated = 0
                target_results = []
                
                # 3. Pour chaque target, utiliser CampaignResultService pour annuler la séquence
                for target in targets:
                    # Trouver une activité de ce target pour utiliser _cancel_contact_sequence
                    activity = Activity.objects.filter(
                        campaign_info__campaign_target=target,
                        status__in=[Activity.Status.PLANNED, Activity.Status.IN_PROGRESS]
                    ).first()
                    
                    cancelled_count = 0
                    if activity:
                        # Utiliser la méthode existante de CampaignResultService
                        cancelled_count = CampaignResultService._cancel_contact_sequence(activity)
                    else:
                        # Fallback : annuler directement les activités plannées
                        cancelled_activities = Activity.objects.filter(
                            campaign_info__campaign_target=target,
                            status=Activity.Status.PLANNED
                        )
                        cancelled_count = cancelled_activities.count()
                        cancelled_activities.update(status=Activity.Status.CANCELLED)
                    
                    total_cancelled += cancelled_count
                    
                    # Marquer le target comme stopped
                    target_update_result = target.mark_as_stopped(
                        reason='substage_cancelled',
                        notes=f"SubStage sequence cancelled: {notes}" if notes else "SubStage sequence cancelled",
                        user=user
                    )
                    
                    if target_update_result.get('status_updated'):
                        targets_updated += 1
                    
                    target_results.append({
                        'target_id': target.id,
                        'contact_name': f"{target.contact.first_name} {target.contact.last_name}" if target.contact else "Unknown",
                        'activities_cancelled': cancelled_count,
                        'target_status_updated': target_update_result.get('status_updated', False),
                        'old_status': target_update_result.get('old_status'),
                        'new_status': target_update_result.get('new_status')
                    })
                
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' sequence cancelled successfully for {len(targets)} contacts",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'action': 'substage_sequence_cancelled',
                        'total_targets': len(targets),
                        'targets_updated': targets_updated,
                        'total_activities_cancelled': total_cancelled,
                        'target_results': target_results
                    }
                )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to cancel substage sequence: {str(e)}")
    
    @classmethod
    def get_substage_followup_status(cls, substage_id: int, client_id: str) -> Response:
        """
        Récupère le statut détaillé du substage dans la campaign follow-up
        Avec % d'avancement de la séquence
        """
        try:
            # 1. Récupérer et valider le substage
            substage = cls._get_validated_substage(substage_id, client_id)
            
            # 2. Vérifier s'il est dans une follow-up campaign
            targets = CampaignTarget.objects.filter(
                substage=substage,
                campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                client_id=client_id
            ).select_related('campaign', 'contact')
            
            if not targets.exists():
                return StandardizedSuccessResponse.success(
                    message=f"SubStage '{substage.name}' is not in any follow-up campaign",
                    data={
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'in_followup_campaign': False,
                        'progress_percentage': 0,
                        'targets': []
                    }
                )
            
            # 3. Calculer le statut et progression pour chaque target
            campaign = targets.first().campaign
            targets_status = []
            total_progress = 0
            
            for target in targets:
                target_progress = cls._calculate_target_progress(target)
                total_progress += target_progress['progress_percentage']
                
                targets_status.append({
                    'target_id': target.id,
                    'contact_name': f"{target.contact.first_name} {target.contact.last_name}" if target.contact else "Unknown",
                    'contact_email': target.contact.email if target.contact else None,
                    'target_status': target.status,
                    'progress_percentage': target_progress['progress_percentage'],
                    'current_sequence_step': target_progress['current_step'],
                    'total_sequence_steps': target_progress['total_steps'],
                    'next_activity': target_progress['next_activity'],
                    'last_activity': target_progress['last_activity']
                })
            
            # 4. Calculer la progression moyenne
            average_progress = total_progress / len(targets) if targets else 0
            
            return StandardizedSuccessResponse.success(
                message=f"SubStage '{substage.name}' follow-up status retrieved successfully",
                data={
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'in_followup_campaign': True,
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'progress_percentage': round(average_progress, 1),
                    'targets_count': len(targets),
                    'targets': targets_status
                }
            )
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(f"Failed to get substage follow-up status: {str(e)}")
    
    # ===== MÉTHODES PRIVÉES =====
    
    @classmethod
    def _get_validated_substage(cls, substage_id: int, client_id: str) -> PipelineSubStage:
        """Récupère et valide un substage"""
        try:
            return PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(OpportunityErrorMessages.SUBSTAGE_NOT_FOUND)
    
    @classmethod
    def _is_substage_in_followup(cls, substage: PipelineSubStage) -> bool:
        """Vérifie si un substage est déjà dans une follow-up campaign"""
        return CampaignTarget.objects.filter(
            substage=substage,
            campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
            client_id=substage.client_id
        ).exists()
    
    @classmethod
    def _get_or_create_followup_campaign_via_service(cls, client_id: str, stakeholders: List, user) -> Campaign:
        """
        Utilise CampaignCoreService pour créer/récupérer campaign follow-up
        Avec la logique d'unicité intégrée dans CampaignCreationService
        """
        # Préparer les données de campaign
        campaign_data = {
            'name': cls.FOLLOWUP_CAMPAIGN_NAME,
            'description': 'Automatic follow-up campaign for pipeline substages',
            'campaign_type': Campaign.CampaignType.FOLLOW_UP,
            'sequence_type': 'FOLLOW_UP',
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=365),  # 1 an
            'status': 'ACTIVE',
            'client_id': client_id
        }
        
        # Extraire les IDs des contacts
        target_contacts = [contact.id for contact in stakeholders]
        
        # Utiliser CampaignCoreService - la logique d'unicité est gérée automatiquement
        response = CampaignCoreService.create_campaign_with_activities(
            campaign_data=campaign_data,
            target_accounts=[],
            target_contacts=target_contacts,  # Passer les stakeholders
            target_leads=[],
            target_opportunities=[],
            request=None
        )
        
        # Extraire la campaign du response
        if hasattr(response, 'data') and 'data' in response.data:
            campaign_id = response.data['data']['campaign_id']
            return Campaign.objects.get(id=campaign_id)
        else:
            raise StandardizedValidationError("Failed to create/retrieve follow-up campaign")
    
    @classmethod
    def _get_substage_stakeholders(cls, substage: PipelineSubStage) -> List:
        """Récupère les stakeholders du substage via ses metadata"""
        if hasattr(substage, 'metadata') and substage.metadata:
            return list(substage.metadata.stakeholders.all())
        return []
    
    @classmethod
    def _create_substage_targets(cls, campaign: Campaign, substage: PipelineSubStage, stakeholders: List, user) -> int:
        """
        Crée les CampaignTarget pour chaque stakeholder du substage
        IMPORTANT : Ajoute la référence substage_id pour traçabilité
        """
        targets_created = 0
        
        for stakeholder in stakeholders:
            # Vérifier si le target existe déjà pour CE substage spécifiquement
            existing_target = CampaignTarget.objects.filter(
                campaign=campaign,
                contact=stakeholder,
                substage=substage  # Important : vérifier le substage aussi
            ).first()
            
            if not existing_target:
                # Créer le target avec référence au substage
                target = CampaignTarget.objects.create(
                    campaign=campaign,
                    contact=stakeholder,
                    substage=substage,  # IMPORTANT : référence au substage
                    client_id=campaign.client_id,
                    user=user
                )
                
                # Copier le contexte du substage (méthode existante)
                target.copy_substage_context()
                target.save()
                
                targets_created += 1
        
        return targets_created
    
    @classmethod
    def _calculate_target_progress(cls, target: CampaignTarget) -> Dict:
        """
        Calcule la progression d'un target dans sa séquence follow-up
        """
        # Récupérer toutes les activités de ce target
        activities = Activity.objects.filter(
            campaign_info__campaign_target=target
        ).select_related('sequence_info').order_by('sequence_info__sequence_position')
        
        if not activities.exists():
            return {
                'progress_percentage': 0,
                'current_step': 0,
                'total_steps': 5,  # FollowUpSequence a 5 étapes
                'next_activity': None,
                'last_activity': None
            }
        
        # Compter les activités completed vs total
        total_activities = activities.count()
        completed_activities = activities.filter(status=Activity.Status.COMPLETED).count()
        
        progress_percentage = (completed_activities / total_activities * 100) if total_activities > 0 else 0
        
        # Trouver la prochaine activité et la dernière
        next_activity = activities.filter(status=Activity.Status.PLANNED).first()
        last_activity = activities.filter(status=Activity.Status.COMPLETED).last()
        
        return {
            'progress_percentage': round(progress_percentage, 1),
            'current_step': completed_activities + 1,
            'total_steps': total_activities,
            'next_activity': {
                'id': next_activity.id,
                'type': next_activity.activity_type,
                'scheduled_date': next_activity.scheduled_start.date() if next_activity and next_activity.scheduled_start else None
            } if next_activity else None,
            'last_activity': {
                'id': last_activity.id,
                'type': last_activity.activity_type,
                'completed_date': last_activity.completed_at.date() if last_activity and last_activity.completed_at else None
            } if last_activity else None
        }