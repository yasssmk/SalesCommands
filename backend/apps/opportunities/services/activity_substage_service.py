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
                    substage = PipelineSubStage.objects.get(
                        id=substage_id, 
                        client_id=client_id
                    )
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
                
                if not create_serializer.is_valid():
                    raise StandardizedValidationError(
                        CoreErrorMessages.VALIDATION_ERROR.format(
                            errors=create_serializer.errors
                        )
                    )
                
                # Créer la liaison avec le serializer principal
                from ..serializers.substage_activity_serializer import SubStageActivitySerializer
                
                link_data = {
                    'substage': substage.id,
                    'activity': activity.id
                }
                
                link_serializer = SubStageActivitySerializer(
                    data=link_data,
                    context={'client_id': client_id}
                )
                
                if link_serializer.is_valid():
                    link = link_serializer.save(
                        created_by=user,
                        client_id=client_id
                    )
                    return link
                else:
                    raise StandardizedValidationError(
                        CoreErrorMessages.VALIDATION_ERROR.format(
                            errors=link_serializer.errors
                        )
                    )
                    
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
                
                opportunity = substage.stage.opportunity_pipeline.opportunity
                
                # Valider les données d'activité
                from ..serializers.substage_activity_serializer import SubStageActivityWithNewActivitySerializer
                
                activity_serializer = SubStageActivityWithNewActivitySerializer(
                    data=activity_data,
                    context={'client_id': client_id}
                )
                
                if not activity_serializer.is_valid():
                    raise StandardizedValidationError(
                        CoreErrorMessages.VALIDATION_ERROR.format(
                            errors=activity_serializer.errors
                        )
                    )
                
                validated_data = activity_serializer.validated_data
                
                # Créer l'activité
                from apps.activities.serializers import ActivitySerializer
                
                activity_create_data = {
                    'title': validated_data['title'],
                    'description': validated_data.get('description', ''),
                    'activity_type': validated_data['activity_type'],
                    'scheduled_start': validated_data.get('scheduled_start'),
                    'scheduled_end': validated_data.get('scheduled_end'),
                    'opportunity': opportunity.id,
                    'owner': validated_data.get('owner_id', user.id)
                }
                
                activity_serializer = ActivitySerializer(
                    data=activity_create_data,
                    context={'client_id': client_id}
                )
                
                if activity_serializer.is_valid():
                    activity = activity_serializer.save(
                        created_by=user,
                        client_id=client_id
                    )
                else:
                    raise StandardizedValidationError(
                        CoreErrorMessages.VALIDATION_ERROR.format(
                            errors=activity_serializer.errors
                        )
                    )
                
                # Créer la liaison automatiquement
                link = cls.link_existing_activity(
                    substage_id=substage_id,
                    activity_id=activity.id,
                    user=user,
                    client_id=client_id
                )
                
                return {
                    'activity': activity,
                    'link': link
                }
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.ACTIVITY_LINK_FAILED.format(reason=str(e))
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
                    link = SubStageActivity.objects.get(
                        substage_id=substage_id,
                        activity_id=activity_id,
                        client_id=client_id
                    )
                except SubStageActivity.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.ACTIVITY_NOT_IN_PIPELINE
                    )
                
                # Supprimer la liaison
                link.delete()
                return True
                
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
            
            # Construire la timeline avec métadonnées
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
                'activities_count': activity_links.count(),
                'timeline_summary': {
                    'earliest_activity': None,
                    'latest_activity': None,
                    'activities_before_substage': 0,
                    'activities_within_substage': 0,
                    'activities_after_substage': 0,
                    'activities_without_date': 0
                }
            }
            
            # Calculer les statistiques de timeline
            if activity_links.exists():
                activities_with_dates = [
                    link.activity for link in activity_links 
                    if link.activity.scheduled_start
                ]
                
                if activities_with_dates:
                    timeline_data['timeline_summary']['earliest_activity'] = min(
                        activities_with_dates, 
                        key=lambda a: a.scheduled_start
                    ).scheduled_start
                    timeline_data['timeline_summary']['latest_activity'] = max(
                        activities_with_dates, 
                        key=lambda a: a.scheduled_start
                    ).scheduled_start
                
                # Compter les positions temporelles
                for link in activity_links:
                    position = link.timeline_position
                    if position == 'before_substage':
                        timeline_data['timeline_summary']['activities_before_substage'] += 1
                    elif position == 'within_substage':
                        timeline_data['timeline_summary']['activities_within_substage'] += 1
                    elif position == 'after_substage':
                        timeline_data['timeline_summary']['activities_after_substage'] += 1
                    else:
                        timeline_data['timeline_summary']['activities_without_date'] += 1
            
            return timeline_data
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get substage timeline: {str(e)}"
                )
            )