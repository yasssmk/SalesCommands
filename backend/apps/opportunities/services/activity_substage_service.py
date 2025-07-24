# backend/apps/opportunities/services/activity_substage_service.py

from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from rest_framework.response import Response
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages, ActivityErrorMessages
from apps.opportunities.models import SubStageActivity, PipelineSubStage
from apps.activities.models import Activity


class ActivitySubStageService:
    """
    Service centralisé MVP pour gérer les liaisons Activity ↔ SubStage.
    
    REMPLACE ActivityPipelineService (qui sera supprimé).
    
    RÈGLES MVP :
    - Validation unique dans SubStageActivitySerializer
    - Helper centralisé get_substage_opportunity()
    - Méthodes simples et DRY
    - Gestion d'erreurs standardisée
    - Compatible avec buying_process_view.py existant
    """

    # ===== HELPER CENTRAL (utilisé par le serializer) =====
    
    @classmethod
    def get_substage_opportunity(cls, substage):
        """
        Helper central pour récupérer l'opportunity d'un substage.
        
        Cette méthode remplace _get_substage_opportunity() du modèle Activity.
        Utilisée par SubStageActivitySerializer pour validation.
        
        Args:
            substage: Instance PipelineSubStage
            
        Returns:
            Opportunity instance ou None
        """
        try:
            if not substage or not substage.stage:
                return None
                
            stage = substage.stage
            
            # Cas 1: Stage d'instance (lié à un pipeline d'opportunité)
            if hasattr(stage, 'opportunity_pipeline') and stage.opportunity_pipeline:
                return stage.opportunity_pipeline.opportunity
            
            # Cas 2: Stage de template (lié à un template d'opportunité)
            elif hasattr(stage, 'template') and stage.template and hasattr(stage.template, 'opportunity'):
                return stage.template.opportunity
            
            return None
        
        except Exception:
            return None

    # ===== MÉTHODES PRINCIPALES (utilisées par buying_process_view.py) =====
    
    @classmethod
    def link_existing_activity(cls, substage_id: int, activity_id: int, 
                             user, client_id: str) -> SubStageActivity:
        """
        Lie une activité existante à un substage.
        
        La validation Activity.opportunity = SubStage.opportunity
        est faite dans SubStageActivitySerializer.validate()
        
        Args:
            substage_id: ID du substage
            activity_id: ID de l'activité existante
            user: Utilisateur qui effectue l'action
            client_id: ID du client
            
        Returns:
            SubStageActivity: La liaison créée
            
        Raises:
            StandardizedValidationError: Si validation échoue
        """

        with transaction.atomic():
            # Import différé pour éviter l'import circulaire
            from ..serializers.substage_activity_serializer import SubStageActivitySerializer
            
            # Valider et créer via le serializer (qui fait la validation)
            data = {
                'substage': substage_id,
                'activity': activity_id
            }
            
            serializer = SubStageActivitySerializer(
            data=data,
                context={'client_id': client_id}
            )
            serializer.is_valid(raise_exception=True)
            
            # Créer la liaison (le serializer gère Activity.pipeline_substage)
            substage_activity = serializer.save()

            if substage_activity.substage:
                substage_activity.substage.update_stakeholders()
            
            return substage_activity
            
    
    @classmethod
    def unlink_activity(cls, substage_id: int, activity_id: int, client_id: str):
        """
        Supprime la liaison entre un substage et une activité.
        
        Args:
            substage_id: ID du substage
            activity_id: ID de l'activité
            client_id: ID du client
            
        Returns:
            dict: Informations sur la déliaison
        """
        try:
            with transaction.atomic():
                # Récupérer la liaison
                try:
                    substage_activity = SubStageActivity.objects.get(
                        substage_id=substage_id,
                        activity_id=activity_id,
                        client_id=client_id
                    )
                except SubStageActivity.DoesNotExist:
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
                # Récupérer l'activité pour nettoyer la liaison directe
                activity = substage_activity.activity
                substage = substage_activity.substage
                
                # Supprimer la liaison SubStageActivity
                substage_activity.delete()
                
                # Nettoyer la liaison directe dans Activity
                if activity.pipeline_substage and activity.pipeline_substage.id == substage_id:
                    activity.pipeline_substage = None
                    activity.save(update_fields=['pipeline_substage'])
                
                if substage:
                    substage.update_stakeholders()
                
                return {
                    'activity_id': activity.id,
                    'activity_title': activity.title,
                    'substage_id': substage_id,
                    'unlinked': True
                }
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(e))
            )
    
    @classmethod
    def create_activity_for_substage(cls, substage_id: int, activity_data: dict, 
                                   user, client_id: str) -> dict:
        """
        Crée une nouvelle activité et la lie automatiquement au substage.
        
        Args:
            substage_id: ID du substage
            activity_data: Données de l'activité à créer
            user: Utilisateur qui crée l'activité
            client_id: ID du client
            
        Returns:
            dict: {'activity': Activity, 'link': SubStageActivity, 'substage': PipelineSubStage}
        """
        try:
            with transaction.atomic():
                # Récupérer le substage
                try:
                    substage = PipelineSubStage.objects.select_related('stage').get(
                        id=substage_id, 
                        client_id=client_id
                    )
                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                    )
                
                # Récupérer l'opportunity du substage
                opportunity = cls.get_substage_opportunity(substage)
                if not opportunity:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_OPPORTUNITY_NOT_FOUND
                    )
                
                # Préparer les données de l'activité
                activity_data_clean = {
                    key: value for key, value in activity_data.items() 
                    if hasattr(Activity, key) and key not in ['id', 'created_at', 'updated_at']
                }

                if 'account' in activity_data_clean:
                    from apps.accounts.models import Account
                    try:
                        account_id = activity_data_clean['account']
                        account = Account.objects.get(id=account_id, client_id=client_id)
                        activity_data_clean['account'] = account
                    except Account.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.OBJECT_NOT_FOUND.format(object_name='Account')
                        )
                
                substage_context = cls._build_substage_context(substage, opportunity)

                activity_data_clean.update({
                    'opportunity': opportunity,
                    'pipeline_substage': substage,
                    'owner': user,
                    'client_id': client_id,
                    'substage_name': substage.name,
                    'objectives': substage_context['objectives'],
                    'context_info': substage_context['context_info'],
                    'call_to_action': substage_context['call_to_action']
                })

                # Créer l'activité
                from apps.activities.serializers.activity_serializer import ActivitySerializer
                activity_serializer = ActivitySerializer(
                    data={
                        **activity_data,
                        'opportunity': opportunity.id, 
                        'pipeline_substage': substage.id
                    },
                    context={'client_id': client_id}
                )
                activity_serializer.is_valid(raise_exception=True)  
                activity = Activity.objects.create(**activity_data_clean)
                
                # Créer la liaison SubStageActivity
                substage_activity = SubStageActivity.objects.create(
                    substage=substage,
                    activity=activity,
                    client_id=client_id,
                    created_by=user
                )
                
                return {
                    'activity': activity,
                    'link': substage_activity,
                    'substage': substage
                }
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def get_substage_timeline(cls, substage_id: int, client_id: str) -> dict:
        """
        Récupère la timeline des activités liées à un substage.
        
        Args:
            substage_id: ID du substage
            client_id: ID du client
            
        Returns:
            dict: Timeline data avec activités et statistiques
        """
        try:
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Récupérer toutes les activités liées
            activities = Activity.objects.filter(
                pipeline_substage=substage,
                client_id=client_id
            ).select_related('owner', 'opportunity').order_by('scheduled_start')
            
            # Organiser en timeline
            timeline_data = {
                'substage_id': substage.id,
                'substage_name': substage.name,
                'substage_status': substage.status,
                'activities': [
                    {
                        'id': activity.id,
                        'title': activity.title,
                        'activity_type': activity.activity_type,
                        'status': activity.status,
                        'scheduled_start': activity.scheduled_start,
                        'scheduled_end': activity.scheduled_end,
                        'completed_at': activity.completed_at,
                        'owner_name': activity.owner.get_full_name() if activity.owner else None,
                        'outcome_notes': activity.outcome_notes
                    }
                    for activity in activities
                ],
                'stats': {
                    'total_activities': activities.count(),
                    'completed_activities': activities.filter(status='COMPLETED').count(),
                    'pending_activities': activities.filter(status='PLANNED').count(),
                    'in_progress_activities': activities.filter(status='IN_PROGRESS').count()
                }
            }
            
            return timeline_data
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(e))
            )
    
    # ===== MÉTHODES DE CONSULTATION =====
    
    @classmethod
    def get_substage_activities(cls, substage_id: int, client_id: str) -> list:
        """
        Récupère toutes les activités liées à une sous-étape.
        
        Args:
            substage_id: ID du substage
            client_id: ID du client
            
        Returns:
            list: Liste des activités avec informations essentielles
        """
        try:
            substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            
            activities = Activity.objects.filter(
                pipeline_substage=substage,
                client_id=client_id
            ).select_related('owner', 'opportunity').order_by('scheduled_start')
            
            return [
                {
                    'id': activity.id,
                    'title': activity.title,
                    'activity_type': activity.activity_type,
                    'status': activity.status,
                    'scheduled_start': activity.scheduled_start,
                    'scheduled_end': activity.scheduled_end,
                    'owner_name': activity.owner.get_full_name() if activity.owner else None,
                    'opportunity_id': activity.opportunity.id if activity.opportunity else None
                }
                for activity in activities
            ]
            
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(e))
            )
    
    @classmethod
    def get_activity_substage_info(cls, activity_id: int, client_id: str) -> Optional[dict]:
        """
        Récupère les informations de la sous-étape liée à une activité.
        
        Args:
            activity_id: ID de l'activité
            client_id: ID du client
            
        Returns:
            dict ou None: Informations du substage lié
        """
        try:
            activity = Activity.objects.select_related(
                'pipeline_substage__stage'
            ).get(id=activity_id, client_id=client_id)
            
            if not activity.pipeline_substage:
                return None
            
            substage = activity.pipeline_substage
            
            return {
                'substage_id': substage.id,
                'substage_name': substage.name,
                'substage_status': substage.status,
                'stage_id': substage.stage.id,
                'stage_name': substage.stage.name,
                'opportunity_id': cls.get_substage_opportunity(substage).id if cls.get_substage_opportunity(substage) else None
            }
            
        except Activity.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND
            )
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=str(e))
            )
        

    @classmethod
    def _build_substage_context(cls, substage, opportunity):
        """
        Construit le contexte d'un substage pour une activité.
        
        Reproduit la logique de Activity.set_substage_context() 
        mais retourne les données au lieu de modifier l'instance.
        
        Args:
            substage: Instance PipelineSubStage
            opportunity: Instance Opportunity
            
        Returns:
            dict: Données de contexte
        """
        try:
            # Construire les objectifs
            objectives_parts = []
            if hasattr(substage, 'metadata') and substage.metadata and substage.metadata.objective:
                objectives_parts.append(f"SubStage Goal: {substage.metadata.objective}")
            
            # Ajouter contexte stage
            if substage.stage:
                objectives_parts.append(f"Stage: {substage.stage.name}")
                
            # Ajouter contexte opportunity
            if opportunity:
                objectives_parts.append(f"Opportunity: {opportunity.title}")
            
            objectives = " | ".join(objectives_parts) if objectives_parts else ""
            
            # Construire context_info
            context_info = {
                'substage_id': substage.id,
                'substage_type': getattr(substage, 'substage_type', 'UNKNOWN'),
                'stage_name': substage.stage.name if substage.stage else None
            }
            
            # Ajouter métadonnées si disponibles
            if hasattr(substage, 'metadata') and substage.metadata:
                metadata = substage.metadata
                context_info.update({
                    'validation_criteria': metadata.validation_criteria or [],
                    'process_notes': metadata.process_notes,
                    'stakeholders': []
                })
                
                # Ajouter stakeholders
                try:
                    for stakeholder in metadata.stakeholders.all():
                        context_info['stakeholders'].append({
                            'id': stakeholder.id,
                            'name': f"{stakeholder.first_name} {stakeholder.last_name}",
                            'email': stakeholder.email,
                            'title': getattr(stakeholder, 'title', '')
                        })
                except Exception:
                    pass
            
            # Construire call_to_action
            stage_name = substage.stage.name if substage.stage else "process"
            substage_name = substage.name
            substage_type = getattr(substage, 'substage_type', 'UNKNOWN')
            
            if substage_type == 'INTERACTION_CLIENT':
                call_to_action = f"Schedule meeting to discuss {substage_name} for {stage_name}"
            elif substage_type == 'PROCESS_INTERNE_CLIENT':
                call_to_action = f"Follow up on {substage_name} status - ask for timeline update"
            elif substage_type == 'ACTION_INTERNE':
                call_to_action = f"Update client on progress of {substage_name}"
            else:
                call_to_action = f"Follow up on {substage_name} for {stage_name}"
            
            return {
                'objectives': objectives,
                'context_info': context_info,
                'call_to_action': call_to_action
            }
            
        except Exception:
            # Retourner contexte par défaut en cas d'erreur
            return {
                'objectives': f"SubStage: {substage.name}",
                'context_info': {
                    'substage_id': substage.id,
                    'substage_type': 'UNKNOWN',
                    'stage_name': substage.stage.name if substage.stage else None
                },
                'call_to_action': f"Follow up on {substage.name}"
            }
    
