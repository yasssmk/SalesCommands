# backend/apps/opportunities/services/opportunity_pipeline_service.py

from django.db import transaction
from rest_framework.response import Response
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class OpportunityPipelineService:
    """
    Service pour l'orchestration des pipelines d'opportunité.
    Centralise toute la logique métier et les calculs de pipeline.
    """


    @classmethod
    def create_opportunity_pipeline(cls, template, request):
        """
        Crée un OpportunityPipeline à partir d'un template créé
        
        Args:
            template: Le PipelineTemplate déjà créé avec ses stages
            request: Request pour user et context
            
        Returns:
            OpportunityPipeline: Le pipeline créé et initialisé
        """
        try:
            # Import différé pour éviter les imports circulaires
            from ..serializers.opportunity_pipeline_serializer import OpportunityPipelineSerializer
            
            with transaction.atomic():
                # Préparer les données pour le pipeline
                pipeline_data = {
                    'opportunity': template.opportunity.id,
                    'status': 'ACTIVE'
                }
                
                # Créer le pipeline via le serializer
                serializer = OpportunityPipelineSerializer(
                    data=pipeline_data,
                    context={'request': request}
                )
                
                serializer.is_valid(raise_exception=True)
                pipeline = serializer.save()
                
                # Initialiser current_stage au premier stage du template
                first_stage = template.stages.filter(is_active=True).order_by('order').first()
                if first_stage:
                    pipeline.current_stage = first_stage
                    
                    # Initialiser current_substage au premier substage du premier stage
                    first_substage = first_stage.substages.filter(is_active=True).order_by('order').first()
                    if first_substage:
                        pipeline.current_substage = first_substage
                    
                    pipeline.save(update_fields=['current_stage', 'current_substage'])
                
                return pipeline
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
            )
        
    # @classmethod
    # def get_complete_pipeline_overview(cls, opportunity_id: int, client_id: str) -> Response:
    #         """
    #         Récupère une vue d'ensemble complète du pipeline avec toutes les métadonnées
            
    #         Args:
    #             opportunity_id: ID de l'opportunité
    #             client_id: ID du client
                
    #         Returns:
    #             Response: Vue d'ensemble complète du pipeline
    #         """
    #         try:
    #             # Import différé pour éviter les imports circulaires
    #             from ..serializers.opportunity_pipeline_serializer import OpportunityPipelineSerializer
                
    #             # Récupérer le pipeline avec optimisations
    #             pipeline = cls._get_pipeline_optimized(opportunity_id, client_id)
                
    #             # Sérialiser le pipeline avec tous les calculs
    #             pipeline_serializer = OpportunityPipelineSerializer(pipeline)
                
    #             # Récupérer toutes les substages avec métadonnées
    #             all_substages = pipeline.get_all_substages_with_metadata()
                
    #             # Récupérer le résumé du pipeline
    #             pipeline_summary = pipeline.get_pipeline_summary()
                
    #             return Response({
    #                 'success': True,
    #                 'data': {
    #                     'pipeline': pipeline_serializer.data,
    #                     'all_substages': all_substages,
    #                     'summary': pipeline_summary,
    #                     'total_substages': len(all_substages),
    #                     'substages_by_stage': cls._group_substages_by_stage(all_substages)
    #                 }
    #             })
                
    #         except StandardizedValidationError:
    #             raise
    #         except Exception as e:
    #             raise StandardizedValidationError(
    #                 OpportunityErrorMessages.PIPELINE_OVERVIEW_FAILED.format(reason=str(e))
    #             )

    # @classmethod
    # def get_pipeline_metrics(cls, opportunity_id: int, client_id: str) -> Response:
    #     """
    #     Récupère les métriques détaillées du pipeline
        
    #     Args:
    #         opportunity_id: ID de l'opportunité
    #         client_id: ID du client
            
    #     Returns:
    #         Response: Métriques complètes du pipeline
    #     """
    #     try:
    #         pipeline = cls._get_pipeline(opportunity_id, client_id)
            
    #         # Calculs des métriques
    #         metrics = {
    #             'progress': {
    #                 'percentage': float(pipeline.progress_percentage),
    #                 'completed_stages': pipeline.get_completed_stages_count(),
    #                 'total_stages': pipeline.get_total_stages_count(),
    #                 'completed_substages': pipeline.get_completed_substages_count(),
    #                 'total_substages': pipeline.get_total_substages_count()
    #             },
    #             'timeline': {
    #                 'days_since_started': pipeline.days_since_started,
    #                 'expected_close_date': pipeline.expected_close_date,
    #                 'days_until_close': pipeline.days_until_expected_close,
    #                 'actual_duration_days': pipeline.actual_duration_days
    #             },
    #             'health': {
    #                 'is_overdue': pipeline.is_pipeline_overdue(),
    #                 'overdue_summary': pipeline.get_overdue_summary(),
    #                 'status': pipeline.status,
    #                 'is_customized': pipeline.is_customized
    #             },
    #             'position': {
    #                 'current_position': pipeline.get_current_position(),
    #                 'last_updated': pipeline.last_updated
    #             }
    #         }
            
    #         return Response({
    #             'success': True,
    #             'data': {
    #                 'opportunity_id': opportunity_id,
    #                 'pipeline_id': pipeline.id,
    #                 'metrics': metrics
    #             }
    #         })
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.METRICS_CALCULATION_FAILED.format(reason=str(e))
    #         )

    # @classmethod
    # def update_pipeline_position(cls, opportunity_id: int, stage_id: int = None, 
    #                            substage_id: int = None, client_id: str = None, user=None) -> Response:
    #     """
    #     Met à jour manuellement la position du pipeline
        
    #     Args:
    #         opportunity_id: ID de l'opportunité
    #         stage_id: ID du stage (optionnel si substage_id fourni)
    #         substage_id: ID du substage (optionnel)
    #         client_id: ID du client
    #         user: Utilisateur effectuant l'action
            
    #     Returns:
    #         Response: Confirmation de la mise à jour
    #     """
    #     try:
    #         with transaction.atomic():
    #             # Import différé pour éviter les imports circulaires
    #             from ..serializers.opportunity_pipeline_serializer import OpportunityPipelineSerializer
                
    #             pipeline = cls._get_pipeline(opportunity_id, client_id)
                
    #             # Préparer les données de mise à jour
    #             update_data = {}
                
    #             if substage_id:
    #                 # Récupérer et valider le substage
    #                 substage = cls._get_substage(substage_id, pipeline, client_id)
    #                 update_data['current_substage'] = substage_id
    #                 update_data['current_stage'] = substage.stage.id
    #                 action_description = f"substage '{substage.name}'"
                    
    #             elif stage_id:
    #                 # Récupérer et valider le stage
    #                 stage = cls._get_stage(stage_id, pipeline, client_id)
    #                 update_data['current_stage'] = stage_id
    #                 # Garder le substage si elle appartient au même stage
    #                 if pipeline.current_substage and pipeline.current_substage.stage.id != stage_id:
    #                     update_data['current_substage'] = None
    #                 action_description = f"stage '{stage.name}'"
    #             else:
    #                 raise StandardizedValidationError(
    #                     CoreErrorMessages.INVALID_FIELD.format(field='Either stage_id or substage_id must be provided')
    #                 )
                
    #             # Mettre à jour via le serializer
    #             serializer = OpportunityPipelineSerializer(
    #                 pipeline, 
    #                 data=update_data, 
    #                 partial=True,
    #                 context={'request': type('Request', (), {'user': user})()}
    #             )
                
    #             if not serializer.is_valid():
    #                 raise StandardizedValidationError(serializer.errors)
                
    #             updated_pipeline = serializer.save()
                
    #             return Response({
    #                 'success': True,
    #                 'message': f'Pipeline position updated to {action_description}',
    #                 'data': {
    #                     'pipeline_id': updated_pipeline.id,
    #                     'current_stage': {
    #                         'id': updated_pipeline.current_stage.id if updated_pipeline.current_stage else None,
    #                         'name': updated_pipeline.current_stage.name if updated_pipeline.current_stage else None
    #                     },
    #                     'current_substage': {
    #                         'id': updated_pipeline.current_substage.id if updated_pipeline.current_substage else None,
    #                         'name': updated_pipeline.current_substage.name if updated_pipeline.current_substage else None
    #                     },
    #                     'progress_percentage': float(updated_pipeline.progress_percentage),
    #                     'last_updated': updated_pipeline.last_updated
    #                 }
    #             })
                
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.PIPELINE_UPDATE_FAILED.format(reason=str(e))
    #         )

    @classmethod
    def get_substages_with_metadata(cls, opportunity_id: int, client_id: str) -> Response:
        """
        Récupère toutes les substages avec leurs métadonnées complètes
        
        Args:
            opportunity_id: ID de l'opportunité
            client_id: ID du client
            
        Returns:
            Response: Liste complète des substages avec métadonnées
        """
        try:
            pipeline = cls._get_pipeline(opportunity_id, client_id)
            
            # Récupérer toutes les substages avec métadonnées
            all_substages = pipeline.get_all_substages_with_metadata()
            
            # Grouper par stages pour une meilleure lisibilité
            substages_by_stage = cls._group_substages_by_stage(all_substages)
            
            # Statistiques
            stats = {
                'total_substages': len(all_substages),
                'substages_by_type': cls._count_substages_by_type(all_substages),
                'substages_with_activities': sum(1 for s in all_substages if s['activity_count'] > 0),
                'substages_with_metadata': sum(1 for s in all_substages if any(s['metadata'].values()))
            }
            
            return Response({
                'success': True,
                'data': {
                    'pipeline_id': pipeline.id,
                    'opportunity_id': opportunity_id,
                    'all_substages': all_substages,
                    'substages_by_stage': substages_by_stage,
                    'statistics': stats
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGES_RETRIEVAL_FAILED.format(reason=str(e))
            )

    # @classmethod
    # def detect_position_from_activities(cls, opportunity_id: int, client_id: str) -> Response:
    #     """
    #     Détecte la position courante basée sur les activités IN_PROGRESS
        
    #     Args:
    #         opportunity_id: ID de l'opportunité
    #         client_id: ID du client
            
    #     Returns:
    #         Response: Position détectée et recommandations
    #     """
    #     try:
    #         pipeline = cls._get_pipeline(opportunity_id, client_id)
            
    #         # Détection de position
    #         current_position = pipeline.get_current_position()
            
    #         # Comparaison avec la position enregistrée
    #         position_analysis = {
    #             'recorded_position': {
    #                 'stage_name': pipeline.current_stage.name if pipeline.current_stage else None,
    #                 'substage_name': pipeline.current_substage.name if pipeline.current_substage else None
    #             },
    #             'detected_position': current_position,
    #             'needs_update': False,
    #             'recommendation': None
    #         }
            
    #         # Analyser si une mise à jour est recommandée
    #         if current_position['detected_from_activities']:
    #             detected_substage = current_position.get('detected_substage')
    #             current_substage = position_analysis['recorded_position']['substage_name']
                
    #             if detected_substage and detected_substage != current_substage:
    #                 position_analysis['needs_update'] = True
    #                 position_analysis['recommendation'] = f"Consider updating position to: {detected_substage}"
            
    #         return Response({
    #             'success': True,
    #             'data': {
    #                 'pipeline_id': pipeline.id,
    #                 'opportunity_id': opportunity_id,
    #                 'position_analysis': position_analysis,
    #                 'last_updated': pipeline.last_updated
    #             }
    #         })
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.POSITION_DETECTION_FAILED.format(reason=str(e))
    #         )
    
    @classmethod
    def _detect_pipeline_position(cls, pipeline) -> dict:
        """
        Détecte la position courante d'un pipeline (même pattern que _is_substage_overdue)
        
        Args:
            pipeline: Instance OpportunityPipeline
            
        Returns:
            dict: {activity_id, substage_id, stage_id} ou None si pas trouvé
        """
        try:
            # Import différé pour éviter les imports circulaires
            from apps.activities.models import Activity
            
            template = pipeline.get_pipeline_template()
            if not template:
                return {'activity_id': None, 'substage_id': None, 'stage_id': None}

            # ===== PRIORITÉ 1 : ACTIVITÉS IN_PROGRESS =====
            in_progress_activities = Activity.objects.filter(
                opportunity=pipeline.opportunity,
                status=Activity.Status.IN_PROGRESS,
                pipeline_substage__isnull=False
            ).select_related(
                'pipeline_substage', 
                'pipeline_substage__stage'
            ).order_by(
                'pipeline_substage__stage__order',  # Stage le plus avancé
                'pipeline_substage__order'           # Substage le plus avancé
            )

            if in_progress_activities.exists():
                # Prendre la plus avancée dans le processus
                most_advanced_activity = in_progress_activities.last()
                substage = most_advanced_activity.pipeline_substage
                stage = substage.stage
                
                return {
                    'activity_id': most_advanced_activity.id,
                    'substage_id': substage.id,
                    'stage_id': stage.id
                }

            # ===== PRIORITÉ 2 : DERNIÈRE COMPLETED + NEXT STEP =====
            last_completed_activity = Activity.objects.filter(
                opportunity=pipeline.opportunity,
                status=Activity.Status.COMPLETED,
                pipeline_substage__isnull=False
            ).select_related(
                'pipeline_substage', 
                'pipeline_substage__stage'
            ).order_by('-completed_at').first()

            if last_completed_activity:
                completed_substage = last_completed_activity.pipeline_substage
                
                # Chercher le next substage
                next_substage = cls._find_next_substage_in_template(completed_substage, template)
                
                if next_substage:
                    return {
                        'activity_id': None,  # Pas d'activité spécifique
                        'substage_id': next_substage.id,
                        'stage_id': next_substage.stage.id
                    }

            # ===== FALLBACK : PREMIÈRE ÉTAPE DU TEMPLATE =====
            first_stage = template.stages.filter(is_active=True).order_by('order').first()
            if first_stage:
                first_substage = first_stage.substages.filter(is_active=True).order_by('order').first()
                
                return {
                    'activity_id': None,
                    'substage_id': first_substage.id if first_substage else None,
                    'stage_id': first_stage.id
                }

            return {'activity_id': None, 'substage_id': None, 'stage_id': None}
            
        except Exception:
            return {'activity_id': None, 'substage_id': None, 'stage_id': None}


    @classmethod
    def _find_next_substage_in_template(cls, current_substage, template):
        """
        Trouve le prochain substage selon l'ordre du template
        
        Args:
            current_substage: SubStage actuel
            template: PipelineTemplate
            
        Returns:
            PipelineSubStage: Prochain substage ou None
        """
        try:
            # 1. Chercher next substage dans le même stage
            next_in_same_stage = current_substage.stage.substages.filter(
                is_active=True,
                order__gt=current_substage.order
            ).order_by('order').first()
            
            if next_in_same_stage:
                return next_in_same_stage
            
            # 2. Sinon, chercher premier substage du stage suivant
            current_stage = current_substage.stage
            
            next_stage = template.stages.filter(
                is_active=True,
                order__gt=current_stage.order
            ).order_by('order').first()
            
            if next_stage:
                return next_stage.substages.filter(
                    is_active=True
                ).order_by('order').first()
            
            return None
            
        except Exception:
            return None

    # @classmethod
    # def create_pipeline_from_opportunity(cls, opportunity_id: int, client_id: str, user=None) -> Response:
    #     """
    #     Crée un nouveau pipeline pour une opportunité
        
    #     Args:
    #         opportunity_id: ID de l'opportunité
    #         client_id: ID du client
    #         user: Utilisateur créant le pipeline
            
    #     Returns:
    #         Response: Pipeline créé avec initialisation
    #     """
    #     try:
    #         # Import différé pour éviter les imports circulaires
    #         from ..models import Opportunity
    #         from ..serializers.opportunity_pipeline_serializer import OpportunityPipelineSerializer
            
    #         # Récupérer l'opportunité
    #         try:
    #             opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
    #         except Opportunity.DoesNotExist:
    #             raise StandardizedValidationError(
    #                 OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
    #             )
            
    #         # Vérifier qu'un template existe
    #         if not opportunity.pipeline_templates.exists():
    #             raise StandardizedValidationError(
    #                 OpportunityErrorMessages.NO_TEMPLATE_FOUND
    #             )
            
    #         # Créer le pipeline via le serializer
    #         pipeline_data = {
    #             'opportunity': opportunity_id,
    #             'status': 'ACTIVE'
    #         }
            
    #         serializer = OpportunityPipelineSerializer(
    #             data=pipeline_data,
    #             context={'request': type('Request', (), {'user': user})()}
    #         )
            
    #         if not serializer.is_valid():
    #             raise StandardizedValidationError(serializer.errors)
            
    #         pipeline = serializer.save()
            
    #         return Response({
    #             'success': True,
    #             'message': f'Pipeline created for opportunity "{opportunity.title}"',
    #             'data': {
    #                 'pipeline_id': pipeline.id,
    #                 'opportunity_id': opportunity_id,
    #                 'current_stage': {
    #                     'id': pipeline.current_stage.id if pipeline.current_stage else None,
    #                     'name': pipeline.current_stage.name if pipeline.current_stage else None
    #                 },
    #                 'current_substage': {
    #                     'id': pipeline.current_substage.id if pipeline.current_substage else None,
    #                     'name': pipeline.current_substage.name if pipeline.current_substage else None
    #                 },
    #                 'status': pipeline.status,
    #                 'created_at': pipeline.created_at
    #             }
    #         })
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
    #         )

    @classmethod
    def get_pipeline_status(cls, opportunity_id: int, client_id: str) -> dict:
        """
        ✅ MÉTHODE UNIQUE - Remplace get_pipeline_metrics + get_pipeline_status
        
        Retourne TOUTES les informations importantes du pipeline :
        - Métriques complètes (progress, timeline, health, position)  
        - Navigation (previous/next steps)
        - Actions suggérées
        - Executive summary
        - Format optimisé pour frontend
        
        Args:
            opportunity_id: ID de l'opportunité
            client_id: ID du client
            
        Returns:
            dict: Données complètes du statut du pipeline
        """
        try:
            pipeline = cls._get_pipeline(opportunity_id, client_id)
            
            # ===== MÉTRIQUES COMPLÈTES (ex get_pipeline_metrics) =====
            metrics = {
                'progress': {
                    'percentage': float(pipeline.progress_percentage),
                    'completed_stages': pipeline.get_completed_stages_count(),
                    'total_stages': pipeline.get_total_stages_count(),
                    'completed_substages': pipeline.get_completed_substages_count(),
                    'total_substages': pipeline.get_total_substages_count()
                },
                'timeline': {
                    'days_since_started': pipeline.days_since_started,
                    'expected_close_date': pipeline.expected_close_date,
                    'days_until_close': pipeline.days_until_expected_close,
                    'actual_duration_days': pipeline.actual_duration_days
                },
                'health': {
                    'is_overdue': pipeline.is_pipeline_overdue(),
                    'overdue_summary': pipeline.get_overdue_summary(),
                    'status': pipeline.status,
                    'is_customized': pipeline.is_customized
                },
                'position': {
                    'current_position': pipeline.get_current_position(),
                    'last_updated': pipeline.last_updated
                }
            }
            
            # ===== INFORMATIONS COMPLÉMENTAIRES =====
            navigation_data = cls._build_navigation_data(pipeline)
            actions_data = cls._build_suggested_actions(pipeline, metrics)
            executive_summary = cls._build_executive_summary(metrics, navigation_data, actions_data)
            
            return {
                'opportunity_id': opportunity_id,
                'pipeline_id': pipeline.id,
                
                # Position actuelle enrichie
                'current_position': {
                    'current_stage': {
                        'id': pipeline.current_stage.id if pipeline.current_stage else None,
                        'name': pipeline.current_stage.name if pipeline.current_stage else None,
                        'order': pipeline.current_stage.order if pipeline.current_stage else None
                    },
                    'current_substage': {
                        'id': pipeline.current_substage.id if pipeline.current_substage else None,
                        'name': pipeline.current_substage.name if pipeline.current_substage else None,
                        'order': pipeline.current_substage.order if pipeline.current_substage else None
                    },
                    'detected_position': metrics['position']['current_position']
                },
                
                # Toutes les métriques
                'metrics': metrics,
                
                # Nouvelles fonctionnalités
                'navigation': navigation_data,
                'suggested_actions': actions_data,
                'executive_summary': executive_summary
            }
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get pipeline status: {str(e)}"
                )
            )

    # ===== MÉTHODES PRIVÉES =====

    @classmethod
    def _get_pipeline(cls, opportunity_id: int, client_id: str):
        """
        Récupère le pipeline d'une opportunité avec validation
        """
        try:
            from ..models import Opportunity
            
            opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
            
            if not hasattr(opportunity, 'pipeline') or not opportunity.pipeline:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.PIPELINE_NOT_FOUND
                )
            
            return opportunity.pipeline
            
        except Opportunity.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )

    @classmethod
    def _build_navigation_data(cls, pipeline):
        """
        Construit les données de navigation (previous/next steps)
        """
        navigation = {
            'previous_steps': [],
            'next_steps': [],
            'available_stages': []
        }
        
        if not pipeline.current_stage:
            return navigation
        
        template = pipeline.get_pipeline_template()
        if not template:
            return navigation
        
        # Récupérer tous les stages ordonnés
        all_stages = list(template.stages.filter(is_active=True).order_by('order'))
        current_stage_index = None
        
        for i, stage in enumerate(all_stages):
            if stage.id == pipeline.current_stage.id:
                current_stage_index = i
                break
        
        if current_stage_index is not None:
            # Previous stage
            if current_stage_index > 0:
                prev_stage = all_stages[current_stage_index - 1]
                navigation['previous_steps'].append({
                    'type': 'stage',
                    'id': prev_stage.id,
                    'name': prev_stage.name,
                    'order': prev_stage.order
                })
            
            # Next stage
            if current_stage_index < len(all_stages) - 1:
                next_stage = all_stages[current_stage_index + 1]
                navigation['next_steps'].append({
                    'type': 'stage',
                    'id': next_stage.id,
                    'name': next_stage.name,
                    'order': next_stage.order
                })
        
        # Navigation substages dans le stage actuel
        if pipeline.current_substage:
            current_substages = list(
                pipeline.current_stage.substages.filter(is_active=True).order_by('order')
            )
            current_substage_index = None
            
            for i, substage in enumerate(current_substages):
                if substage.id == pipeline.current_substage.id:
                    current_substage_index = i
                    break
            
            if current_substage_index is not None:
                # Previous substage
                if current_substage_index > 0:
                    prev_substage = current_substages[current_substage_index - 1]
                    navigation['previous_steps'].insert(0, {
                        'type': 'substage',
                        'id': prev_substage.id,
                        'name': prev_substage.name,
                        'order': prev_substage.order,
                        'stage_name': pipeline.current_stage.name
                    })
                
                # Next substage
                if current_substage_index < len(current_substages) - 1:
                    next_substage = current_substages[current_substage_index + 1]
                    navigation['next_steps'].insert(0, {
                        'type': 'substage',
                        'id': next_substage.id,
                        'name': next_substage.name,
                        'order': next_substage.order,
                        'stage_name': pipeline.current_stage.name
                    })
        
        # Liste de tous les stages pour navigation rapide
        navigation['available_stages'] = [
            {
                'id': stage.id,
                'name': stage.name,
                'order': stage.order,
                'is_current': stage.id == (pipeline.current_stage.id if pipeline.current_stage else None)
            }
            for stage in all_stages
        ]
        
        return navigation

    @classmethod  
    def _build_suggested_actions(cls, pipeline, metrics):
        """
        ✅ MÉTHODE MODIFIÉE - Utilise metrics au lieu de existing_metrics
        
        Construit les actions suggérées basées sur l'état actuel
        """
        actions = []
        alerts = []
        
        # Alertes basées sur les métriques
        health = metrics['health']
        timeline = metrics['timeline']
        
        # Alerte de retard
        if health['is_overdue']:
            alerts.append({
                'type': 'overdue',
                'severity': 'high',
                'message': f"Pipeline en retard - {health['overdue_summary']['overdue_count']} étapes concernées"
            })
            
            actions.append({
                'type': 'resolve_overdue',
                'priority': 'high',
                'description': "Résoudre les étapes en retard",
                'count': health['overdue_summary']['overdue_count']
            })
        
        # Alerte de stagnation  
        if timeline['days_since_started'] > 30:
            alerts.append({
                'type': 'stagnation',
                'severity': 'medium',
                'message': f"Aucune progression depuis {timeline['days_since_started']} jours"
            })
            
            actions.append({
                'type': 'advance_pipeline',
                'priority': 'medium',
                'description': "Faire progresser le pipeline"
            })
        
        # Actions basées sur la position courante
        if pipeline.current_substage:
            actions.append({
                'type': 'complete_current',
                'priority': 'high',
                'description': f"Compléter: {pipeline.current_substage.name}",
                'substage_id': pipeline.current_substage.id
            })
        
        return {
            'alerts': alerts,
            'actions': actions,
            'summary': {
                'total_alerts': len(alerts),
                'high_priority_alerts': len([a for a in alerts if a.get('severity') == 'high']),
                'total_actions': len(actions),
                'high_priority_actions': len([a for a in actions if a.get('priority') == 'high'])
            }
        }

    @classmethod
    def _build_executive_summary(cls, metrics, navigation_data, actions_data):
        """
        ✅ MÉTHODE MODIFIÉE - Utilise metrics au lieu de existing_metrics
        
        Construit le résumé exécutif pour dashboard
        """
        progress = metrics['progress']
        health = metrics['health']
        timeline = metrics['timeline']
        
        # Statut global
        overall_status = 'on_track'
        if actions_data['summary']['high_priority_alerts'] > 0:
            overall_status = 'at_risk'
        elif health['is_overdue']:
            overall_status = 'overdue'
        elif progress['percentage'] > 75:
            overall_status = 'near_completion'
        
        # Score de santé  
        health_score = 100
        health_score -= actions_data['summary']['high_priority_alerts'] * 20
        health_score -= actions_data['summary']['total_alerts'] * 10
        health_score = max(0, health_score)
        
        return {
            'overall_status': overall_status,
            'health_score': health_score,
            'progress_percentage': progress['percentage'],
            'days_in_pipeline': timeline['days_since_started'],
            'critical_alerts_count': actions_data['summary']['high_priority_alerts'],
            'next_milestone': cls._get_next_milestone(progress, navigation_data),
            'key_metrics': {
                'stages_completed': f"{progress['completed_stages']}/{progress['total_stages']}",
                'substages_completed': f"{progress['completed_substages']}/{progress['total_substages']}",  
                'days_remaining': timeline.get('days_until_close', 'N/A')
            }
        }

    @classmethod
    def _get_next_milestone(cls, progress, navigation_data):
        """
        Détermine le prochain milestone
        """
        if progress['completed_stages'] == 0:
            return "Compléter le premier stage"
        elif len(navigation_data['next_steps']) > 0:
            next_step = navigation_data['next_steps'][0]
            return f"Prochaine étape: {next_step['name']}"
        elif progress['total_stages'] - progress['completed_stages'] == 1:
            return "Stage final en cours"
        else:
            remaining = progress['total_stages'] - progress['completed_stages']
            return f"Compléter {remaining} stages restants"