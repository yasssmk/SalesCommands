# backend/apps/opportunities/services/opportunity_pipeline_service.py

from django.db import transaction
from rest_framework.response import Response
from apps.opportunities.models import (
    OpportunityPipeline, 
    PipelineTemplate, 
    PipelineStage, 
    PipelineSubStage,
    Opportunity
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class OpportunityPipelineService:
    """
    Service pour la gestion des pipelines d'opportunité.
    Gère l'initialisation, personnalisation et navigation dans les pipelines.
    """
    
    @classmethod
    def initialize_pipeline_from_template(cls, opportunity_id: int, template_id: int, 
                                        client_id: str, user=None) -> Response:
        """
        Initialise un pipeline d'opportunité à partir d'un template
        
        Args:
            opportunity_id: ID de l'opportunité
            template_id: ID du template à utiliser
            client_id: ID du client
            user: Utilisateur créateur
        """
        try:
            with transaction.atomic():
                # Vérifier que l'opportunité existe et n'a pas déjà de pipeline
                try:
                    opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
                except Opportunity.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
                    )
                
                # Vérifier qu'il n'y a pas déjà un pipeline
                if hasattr(opportunity, 'pipeline'):
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.PIPELINE_ALREADY_EXISTS
                    )
                
                # Récupérer le template
                try:
                    template = PipelineTemplate.objects.get(id=template_id, client_id=client_id)
                except PipelineTemplate.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.TEMPLATE_NOT_FOUND
                    )
                
                # Créer le pipeline à partir du template
                pipeline = OpportunityPipeline.create_from_template(
                    opportunity=opportunity,
                    template=template,
                    user=user
                )
                
                return Response({
                    'success': True,
                    'message': f'Pipeline initialized from template "{template.name}"',
                    'data': {
                        'pipeline_id': pipeline.id,
                        'opportunity_id': opportunity.id,
                        'template_id': template.id,
                        'template_name': template.name,
                        'total_stages': pipeline.total_stages,
                        'current_stage': {
                            'id': pipeline.current_stage.id if pipeline.current_stage else None,
                            'name': pipeline.current_stage.name if pipeline.current_stage else None
                        } if pipeline.current_stage else None
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def get_pipeline_with_details(cls, opportunity_id: int, client_id: str) -> Response:
        """
        Récupère un pipeline avec tous ses détails (étapes et sous-étapes)
        """
        try:
            # Récupérer l'opportunité et son pipeline
            pipeline = cls._get_pipeline(opportunity_id, client_id)
            opportunity = pipeline.opportunity
            
            # Récupérer les étapes avec sous-étapes
            stages = pipeline.get_all_stages()
            stages_data = []
            
            for stage in stages:
                substages = stage.substages.filter(is_active=True).order_by('order')
                substages_data = []
                
                for substage in substages:
                    # Calculer les métriques simplifiées
                    is_overdue = False
                    days_remaining = None
                    
                    if substage.end_date:
                        from django.utils import timezone
                        delta = substage.end_date.date() - timezone.now().date()
                        days_remaining = delta.days
                        is_overdue = days_remaining < 0
                    
                    substages_data.append({
                        'id': substage.id,
                        'name': substage.name,
                        'description': substage.description,
                        'order': substage.order,
                        'substage_type': substage.substage_type,
                        'status': substage.status,
                        'estimated_duration_days': substage.estimated_duration_days,
                        'start_date': substage.start_date,
                        'end_date': substage.end_date,
                        'is_overdue': is_overdue,
                        'days_remaining': days_remaining
                    })
                
                stages_data.append({
                    'id': stage.id,
                    'name': stage.name,
                    'description': stage.description,
                    'order': stage.order,
                    'status': stage.status,
                    'started_at': stage.started_at,
                    'completed_at': stage.completed_at,
                    'estimated_duration': stage.estimated_duration,
                    'substages': substages_data,
                    'substages_count': len(substages_data)
                })
            
            return Response({
                'success': True,
                'data': {
                    'pipeline': {
                        'id': pipeline.id,
                        'opportunity_id': opportunity.id,
                        'opportunity_title': opportunity.title,
                        'template_id': pipeline.template.id,
                        'template_name': pipeline.template.name,
                        'status': pipeline.status,
                        'started_at': pipeline.started_at,
                        'completed_at': pipeline.completed_at,
                        'progress_percentage': pipeline.progress_percentage,
                        'total_stages': pipeline.total_stages,
                        'completed_stages': pipeline.completed_stages,
                        'days_since_started': pipeline.days_since_started,
                        'is_customized': pipeline.is_customized
                    },
                    'current_stage': {
                        'id': pipeline.current_stage.id if pipeline.current_stage else None,
                        'name': pipeline.current_stage.name if pipeline.current_stage else None,
                        'order': pipeline.current_stage.order if pipeline.current_stage else None
                    } if pipeline.current_stage else None,
                    'stages': stages_data
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Pipeline retrieval failed: {str(e)}")
            )
    
    @classmethod
    def move_to_next_stage(cls, opportunity_id: int, client_id: str, user=None) -> Response:
        """
        Fait avancer le pipeline à l'étape suivante
        """
        try:
            with transaction.atomic():
                # Récupérer le pipeline
                pipeline = cls._get_pipeline(opportunity_id, client_id)
                
                # Vérifier que le pipeline est actif
                if not pipeline.is_active:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.PIPELINE_INVALID_STATE.format(
                            current_state=pipeline.status
                        )
                    )
                
                # Avancer à l'étape suivante
                next_stage = pipeline.move_to_next_stage()
                
                if next_stage:
                    return Response({
                        'success': True,
                        'message': f'Pipeline advanced to stage "{next_stage.name}"',
                        'data': {
                            'pipeline_id': pipeline.id,
                            'current_stage': {
                                'id': next_stage.id,
                                'name': next_stage.name,
                                'order': next_stage.order
                            },
                            'progress_percentage': pipeline.progress_percentage,
                            'completed_stages': pipeline.completed_stages
                        }
                    })
                else:
                    return Response({
                        'success': True,
                        'message': 'Pipeline completed successfully',
                        'data': {
                            'pipeline_id': pipeline.id,
                            'status': pipeline.status,
                            'completed_at': pipeline.completed_at,
                            'progress_percentage': pipeline.progress_percentage
                        }
                    })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_COMPLETION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def move_to_previous_stage(cls, opportunity_id: int, client_id: str, user=None) -> Response:
        """
        Revient à l'étape précédente du pipeline
        """
        try:
            with transaction.atomic():
                # Récupérer le pipeline
                pipeline = cls._get_pipeline(opportunity_id, client_id)
                
                # Revenir à l'étape précédente
                previous_stage = pipeline.move_to_previous_stage()
                
                if previous_stage:
                    return Response({
                        'success': True,
                        'message': f'Pipeline moved back to stage "{previous_stage.name}"',
                        'data': {
                            'pipeline_id': pipeline.id,
                            'current_stage': {
                                'id': previous_stage.id,
                                'name': previous_stage.name,
                                'order': previous_stage.order
                            },
                            'progress_percentage': pipeline.progress_percentage,
                            'completed_stages': pipeline.completed_stages
                        }
                    })
                else:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.NAVIGATION_NO_PREVIOUS_STAGE
                    )
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Pipeline navigation failed: {str(e)}")
            )
    
    @classmethod
    def add_custom_stage(cls, opportunity_id: int, stage_name: str, stage_description: str,
                        insert_after_order: int, client_id: str, user=None) -> Response:
        """
        Ajoute une étape personnalisée au pipeline
        """
        try:
            with transaction.atomic():
                # Récupérer le pipeline
                pipeline = cls._get_pipeline(opportunity_id, client_id)
                
                # Marquer comme personnalisé
                pipeline.mark_as_customized(f"Added custom stage: {stage_name}")
                
                # Créer la nouvelle étape
                new_stage = PipelineStage.objects.create(
                    opportunity_pipeline=pipeline,
                    name=stage_name,
                    description=stage_description,
                    order=insert_after_order + 1,  # Le modèle gère automatiquement le décalage
                    status=PipelineStage.StageStatus.ACTIVE,
                    is_active=True,
                    client_id=client_id,
                    user=user
                )
                
                # Mettre à jour les métriques du pipeline (méthode simplifiée)
                pipeline.refresh_from_db()
                pipeline.save()
                
                return Response({
                    'success': True,
                    'message': f'Custom stage "{stage_name}" added successfully',
                    'data': {
                        'pipeline_id': pipeline.id,
                        'new_stage': {
                            'id': new_stage.id,
                            'name': new_stage.name,
                            'description': new_stage.description,
                            'order': new_stage.order
                        },
                        'total_stages': pipeline.total_stages,
                        'is_customized': pipeline.is_customized
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CUSTOMIZATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def add_substage(cls, stage_id: int, substage_data: dict, client_id: str, user=None) -> Response:
        """
        Ajoute une sous-étape à une étape du pipeline
        """
        try:
            with transaction.atomic():
                # Récupérer l'étape
                try:
                    stage = PipelineStage.objects.get(
                        id=stage_id,
                        client_id=client_id,
                        opportunity_pipeline__isnull=False  # S'assurer que c'est une étape d'opportunité
                    )
                except PipelineStage.DoesNotExist:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.STAGE_NOT_FOUND
                    )
                
                # Créer la sous-étape
                substage = PipelineSubStage.objects.create(
                    stage=stage,
                    name=substage_data.get('name'),
                    description=substage_data.get('description', ''),
                    order=substage_data.get('order', 1),
                    substage_type=substage_data.get('substage_type', 'INTERACTION_CLIENT'),
                    estimated_duration_days=substage_data.get('estimated_duration_days'),
                    start_date=substage_data.get('start_date'),
                    end_date=substage_data.get('end_date'),
                    notes=substage_data.get('notes', ''),
                    client_id=client_id,
                    user=user
                )
                
                # Marquer le pipeline comme personnalisé
                stage.opportunity_pipeline.mark_as_customized(f"Added substage: {substage.name}")
                
                return Response({
                    'success': True,
                    'message': f'Substage "{substage.name}" added successfully',
                    'data': {
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'stage_id': stage.id,
                        'stage_name': stage.name,
                        'pipeline_id': stage.opportunity_pipeline.id
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CUSTOMIZATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def update_substage_status(cls, substage_id: int, new_status: str, client_id: str, 
                             user=None) -> Response:
        """
        Met à jour le statut d'une sous-étape
        """
        try:
            # Récupérer la sous-étape
            try:
                substage = PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Mettre à jour le statut selon le nouveau statut
            if new_status == 'IN_PROGRESS':
                substage.mark_as_started()
            elif new_status == 'COMPLETED':
                substage.mark_as_completed()
            elif new_status == 'BLOCKED':
                substage.mark_as_blocked()
            elif new_status == 'NOT_STARTED':
                substage.mark_as_not_started()
            else:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_TYPE_INVALID.format(substage_type=new_status)
                )
            
            return Response({
                'success': True,
                'message': f'Substage "{substage.name}" status updated to {new_status}',
                'data': {
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'new_status': substage.status,
                    'actual_start_date': substage.actual_start_date,
                    'actual_end_date': substage.actual_end_date
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Substage status update failed: {str(e)}")
            )
    
    @classmethod
    def get_pipeline_progress(cls, opportunity_id: int, client_id: str) -> Response:
        """
        Récupère les métriques de progression du pipeline
        Version simplifiée pour MVP
        """
        try:
            # Récupérer le pipeline
            pipeline = cls._get_pipeline(opportunity_id, client_id)
            
            # Calculer les métriques de base
            stages = pipeline.get_all_stages()
            overdue_substages = []
            
            for stage in stages:
                substages = stage.substages.filter(is_active=True)
                for substage in substages:
                    # Calcul simplifié du retard
                    if substage.end_date:
                        from django.utils import timezone
                        delta = substage.end_date.date() - timezone.now().date()
                        if delta.days < 0:  # En retard
                            overdue_substages.append({
                                'id': substage.id,
                                'name': substage.name,
                                'stage_name': stage.name,
                                'days_overdue': abs(delta.days)
                            })
            
            return Response({
                'success': True,
                'data': {
                    'pipeline_id': pipeline.id,
                    'opportunity_title': pipeline.opportunity.title,
                    'progress_percentage': pipeline.progress_percentage,
                    'total_stages': pipeline.total_stages,
                    'completed_stages': pipeline.completed_stages,
                    'days_since_started': pipeline.days_since_started,
                    'current_stage': {
                        'id': pipeline.current_stage.id if pipeline.current_stage else None,
                        'name': pipeline.current_stage.name if pipeline.current_stage else None,
                        'order': pipeline.current_stage.order if pipeline.current_stage else None
                    } if pipeline.current_stage else None,
                    'overdue_substages': overdue_substages,
                    'overdue_count': len(overdue_substages),
                    'status': pipeline.status,
                    'is_customized': pipeline.is_customized
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.METRICS_CALCULATION_FAILED.format(reason=str(e))
            )
    
    # ===== MÉTHODES PRIVÉES =====
    
    @classmethod
    def _get_pipeline(cls, opportunity_id: int, client_id: str) -> OpportunityPipeline:
        """
        Récupère le pipeline d'une opportunité avec validation
        """
        try:
            opportunity = Opportunity.objects.get(id=opportunity_id, client_id=client_id)
            return opportunity.pipeline
        except Opportunity.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )
        except AttributeError:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_NOT_FOUND
            )