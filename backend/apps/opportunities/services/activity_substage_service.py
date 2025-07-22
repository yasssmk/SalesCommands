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
    Service simplifié pour gérer les liaisons entre activités et substages.
    
    Fonctionnalités principales :
    - Lier une activité existante à un substage
    - Créer une activité et la lier automatiquement au substage
    - Délier une activité d'un substage
    - Récupérer la timeline des activités d'un substage
    """

    @classmethod
    def _get_substage_opportunity(cls, substage):
        """Helper pour récupérer l'opportunity d'un substage - UNIFIÉ"""
        try:
            if not substage or not substage.stage:
                return None
                
            stage = substage.stage
            
            # Cas 1: Stage d'instance (opportunity_pipeline)
            if hasattr(stage, 'opportunity_pipeline') and stage.opportunity_pipeline:
                return stage.opportunity_pipeline.opportunity
            
            # Cas 2: Stage de template
            elif hasattr(stage, 'template') and stage.template and hasattr(stage.template, 'opportunity'):
                return stage.template.opportunity
            
            return None
        
        except:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )
    
    @classmethod
    def link_existing_activity(cls, substage_id: int, activity_id: int, 
                             user, client_id: str) -> SubStageActivity:
        """
        Lie une activité existante à un substage
        
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
        try:
            with transaction.atomic():
                # ✅ Import différé pour éviter l'import circulaire
                from ..serializers.substage_activity_serializer import SubStageActivityCreateSerializer
                
                # Récupérer le substage
                try:
                    substage = PipelineSubStage.objects.select_related(
                        'stage__template__opportunity'
                    ).get(id=substage_id, client_id=client_id)
                    

                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                    )
                
                # Récupérer l'activité 
                try:
                    activity = Activity.objects.get(
                        id=activity_id,
                        client_id=client_id
                    )
                except Activity.DoesNotExist:
                    raise StandardizedValidationError(
                        ActivityErrorMessages.ACTIVITY_NOT_FOUND
                    )
                
                # Créer la liaison via le serializer
                create_serializer = SubStageActivityCreateSerializer(
                    data={'activity_id': activity_id},
                    context={'client_id': client_id}
                )
                

                substage_opportunity = cls._get_substage_opportunity(substage)
                if not substage_opportunity:
                    raise StandardizedValidationError(
                        "Cannot determine opportunity for substage"
                    )
                
                # Validation : même opportunity
                if activity.opportunity and activity.opportunity != substage_opportunity:
                    raise StandardizedValidationError(
                        f'Activity belongs to "{activity.opportunity.title}" but substage belongs to "{substage_opportunity.title}"'
                    )
                
                # Validation : même account
                if activity.account != substage_opportunity.account:
                    raise StandardizedValidationError(
                        "Activity account must match substage opportunity account"
                    )
                
                # ✅ NOUVEAU: Auto-set opportunity si pas définie
                if not activity.opportunity:
                    activity.opportunity = substage_opportunity
                    activity.save(update_fields=['opportunity'])
                
                #  Utiliser la méthode du modèle Activity (plus propre)
                activity.link_to_substage(substage)
                
                # Récupérer la liaison créée
                link = SubStageActivity.objects.get(
                    substage=substage,
                    activity=activity,
                    client_id=client_id
                )
                
                return link
    
                    
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
            )

    @classmethod 
    def create_activity_for_substage(cls, substage_id: int, activity_data: dict, 
                                   user, client_id: str) -> Dict:
        """
        Crée une nouvelle activité et la lie automatiquement au substage
        
        Args:
            substage_id: ID du substage
            activity_data: Données pour créer l'activité
            user: Utilisateur qui effectue l'action
            client_id: ID du client
            
        Returns:
            Dict: {'activity': Activity, 'link': SubStageActivity}
            
        Raises:
            StandardizedValidationError: Si création/liaison échoue
        """
        try:
            with transaction.atomic():
                # Récupérer le substage et l'opportunity associée
                try:
                    substage = PipelineSubStage.objects.select_related(
                        'stage__opportunity_pipeline__opportunity'
                    ).get(id=substage_id, client_id=client_id)
                except PipelineSubStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                    )
                
                opportunity = cls._get_substage_opportunity(substage)
                
                activity_data_clean = {
                    'title': activity_data.get('title'),
                    'activity_type': activity_data.get('activity_type'),
                    'description': activity_data.get('description', ''),
                    'account': opportunity.account,
                    'owner': user,
                    'opportunity': opportunity,  
                    'pipeline_substage': substage, 
                    'scheduled_start': activity_data.get('scheduled_start'),
                    'scheduled_end': activity_data.get('scheduled_end'),
                    'objectives': activity_data.get('objectives', ''),
                    'context_info': activity_data.get('context_info', {}),
                }
                

                from apps.activities.serializers import ActivitySerializer
                
                activity_serializer = ActivitySerializer(
                    data=activity_data_clean,
                    context={'client_id': client_id, 'request': type('Request', (), {'user': user})()}
                )
                
                
                # Créer l'activité (le save() auto-gérera opportunity et pipeline_substage)
                activity = activity_serializer.save()
                
                # ✅ NOUVEAU: Enrichir le contexte avec substage
                activity.set_substage_context(substage)
                activity.save()
                
                # ✅ SIMPLIFIÉ: Utiliser la méthode du modèle (plus robuste)
                activity.link_to_substage(substage)
                
                # Récupérer la liaison créée
                link = SubStageActivity.objects.get(
                    substage=substage,
                    activity=activity,
                    client_id=client_id
                )
                
                # ✅ NOUVEAU: Gérer les contacts
                contact_ids = activity_data.get('contact_ids', [])
                if contact_ids:
                    from apps.accounts.models import Contact
                    contacts = Contact.objects.filter(
                        id__in=contact_ids,
                        account=opportunity.account,
                        client_id=client_id
                    )
                    activity.contacts.set(contacts)
                elif opportunity.contact:
                    # Fallback: contact principal de l'opportunité
                    activity.contacts.add(opportunity.contact)
                
                return {
                    'activity': activity,
                    'link': link
                }
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to create activity for substage: {str(e)}"
                )
            )

    @classmethod
    def unlink_activity(cls, substage_id: int, activity_id: int, client_id: str) -> bool:
        """
        Supprime la liaison entre un substage et une activité
        
        Args:
            substage_id: ID du substage
            activity_id: ID de l'activité
            client_id: ID du client
            
        Returns:
            bool: True si suppression réussie
            
        Raises:
            StandardizedValidationError: Si liaison n'existe pas ou erreur
        """
        try:
            with transaction.atomic():
                # Rechercher la liaison
                try:
                    activity = Activity.objects.get(
                        id=activity_id,
                        client_id=client_id
                    )
                except Activity.DoesNotExist:
                    raise StandardizedValidationError(
                        ActivityErrorMessages.ACTIVITY_NOT_FOUND
                    )
                
                # Supprimer la liaison
                activity.unlink_from_substage()
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to unlink activity: {str(e)}"
                )
            )

    @classmethod
    def get_substage_timeline(cls, substage_id: int, client_id: str) -> Dict:
        """
        Récupère la timeline des activités liées à un substage avec métadonnées
        
        Args:
            substage_id: ID du substage
            client_id: ID du client
            
        Returns:
            Dict: Timeline avec activités ordonnées et métadonnées
            
        Raises:
            StandardizedValidationError: Si substage n'existe pas
        """
        try:
            # Récupérer le substage avec ses informations
            try:
                substage = PipelineSubStage.objects.select_related(
                    'stage'
                ).get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Récupérer toutes les activités liées avec optimisations
            activity_links = SubStageActivity.objects.filter(
                substage_id=substage_id,
                client_id=client_id
            ).select_related(
                'activity',
                'activity__owner'
            ).order_by('activity__scheduled_start', 'created_at')
            
            # Sérialiser les liaisons
            from ..serializers.substage_activity_serializer import SubStageActivitySerializer
            
            links_serializer = SubStageActivitySerializer(
                activity_links, 
                many=True,
                context={'client_id': client_id}
            )
            
            timeline_data = {
                'substage': {
                    'id': substage.id,
                    'name': substage.name,
                    'status': substage.status,
                    'start_date': substage.start_date,
                    'end_date': substage.end_date,
                    'estimated_duration_days': substage.estimated_duration_days
                },
                'activities_links': links_serializer.data,
                'activities_count': len(links_serializer.data),
                'timeline_generated_at': timezone.now().isoformat()
            }
            
            return timeline_data
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get substage timeline: {str(e)}"
                )
            )