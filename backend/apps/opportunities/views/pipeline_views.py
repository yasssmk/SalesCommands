# apps/opportunities/views/pipeline_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Prefetch, Max
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.opportunities.models import (
    Opportunity, OpportunityPipeline, PipelineTemplate, 
    PipelineStage, PipelineSubStage, SubStageMetadata
)
from apps.opportunities.serializers import (
    OpportunityPipelineSerializer, PipelineSubStageSerializer,
    PipelineTemplateSerializer, PipelineStageSerializer
)
from apps.opportunities.services.opportunity_pipeline_service import OpportunityPipelineService


class PipelineViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ViewSet):
    """
    API endpoints pour la gestion des pipelines d'opportunité.
    
    Note: Utilise ViewSet (pas ModelViewSet) car les actions sont centrées 
    sur les opportunités plutôt que sur les pipelines directement.
    """
    entity_name = 'pipeline'
    
    def get_opportunity(self, opportunity_id):
        """Récupère une opportunité avec validation du client"""
        try:
            return Opportunity.objects.get(
                id=opportunity_id,
                client_id=self.get_client_id()
            )
        except Opportunity.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )
    
    def get_pipeline(self, opportunity_id):
        """Récupère le pipeline d'une opportunité avec validation"""
        opportunity = self.get_opportunity(opportunity_id)
        
        if not hasattr(opportunity, 'pipeline'):
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_NOT_FOUND
            )
        
        return opportunity.pipeline
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline')
    def retrieve_pipeline(self, request, opportunity_id=None):
        """
        GET /opportunities/{id}/pipeline/
        Récupère le pipeline complet d'une opportunité avec tous ses détails
        """
        try:
            # Utiliser le service existant
            response = OpportunityPipelineService.get_pipeline_with_details(
                opportunity_id=int(opportunity_id),
                client_id=self.get_client_id()
            )
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Opportunity ID")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Pipeline retrieval failed: {str(e)}")
            )
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/initialize')
    def initialize_pipeline(self, request, opportunity_id=None):
        """
        POST /opportunities/{id}/pipeline/initialize/
        Initialise un nouveau pipeline pour une opportunité depuis un template
        
        Body: {
            "template_id": 123,
            "custom_stages": [...] (optionnel)
        }
        """
        try:
            # Validation des données
            template_id = request.data.get('template_id')
            if not template_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="template_id")
                )
            
            # Utiliser le service existant
            response = OpportunityPipelineService.initialize_pipeline_from_template(
                opportunity_id=int(opportunity_id),
                template_id=int(template_id),
                client_id=self.get_client_id(),
                user=request.user
            )
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
            )
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/overview')
    def pipeline_overview(self, request, opportunity_id=None):
        """
        GET /opportunities/{id}/pipeline/overview/
        Vue d'ensemble rapide du pipeline avec métriques
        """
        try:
            # Utiliser le service existant
            response = OpportunityPipelineService.get_pipeline_metrics(
                opportunity_id=int(opportunity_id),
                client_id=self.get_client_id()
            )
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Opportunity ID")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Pipeline overview failed: {str(e)}")
            )
    
    @action(detail=False, methods=['put'], url_path='(?P<opportunity_id>[^/.]+)/pipeline')
    def update_pipeline(self, request, opportunity_id=None):
        """
        PUT /opportunities/{id}/pipeline/
        Met à jour les informations générales du pipeline
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Champs modifiables
            allowed_fields = ['notes', 'estimated_duration_days']
            update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
            
            if not update_data:
                raise StandardizedValidationError(
                    "No valid fields provided for update"
                )
            
            # Appliquer les modifications
            for field, value in update_data.items():
                setattr(pipeline, field, value)
            
            pipeline.save()
            
            # Sérialiser le résultat
            serializer = OpportunityPipelineSerializer(pipeline)
            
            return Response({
                'success': True,
                'message': 'Pipeline updated successfully',
                'data': serializer.data
            })
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Opportunity ID")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_UPDATE_FAILED.format(reason=str(e))
            )
    
    # ===== GESTION DES SUBSTAGES =====
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages')
    def list_substages(self, request, opportunity_id=None):
        """
        GET /opportunities/{id}/pipeline/substages/
        Liste tous les substages du pipeline avec filtres optionnels
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer tous les substages actifs
            substages = PipelineSubStage.objects.filter(
                stage__opportunity_pipeline=pipeline,
                is_active=True,
                client_id=self.get_client_id()
            ).select_related(
                'stage', 'metadata'
            ).prefetch_related(
                'metadata__stakeholders',
                'campaign_targets'
            ).order_by('stage__order', 'order')
            
            # Filtres optionnels
            stage_id = request.query_params.get('stage_id')
            if stage_id:
                substages = substages.filter(stage_id=stage_id)
            
            substage_type = request.query_params.get('type')
            if substage_type:
                substages = substages.filter(substage_type=substage_type)
            
            status_filter = request.query_params.get('status')
            if status_filter:
                substages = substages.filter(status=status_filter)
            
            # Sérialiser
            serializer = PipelineSubStageSerializer(substages, many=True)
            
            # Ajouter des stats
            stats = {
                'total_substages': substages.count(),
                'by_status': {},
                'by_type': {},
                'overdue_count': 0
            }
            
            from django.utils import timezone
            today = timezone.now().date()
            
            for substage in substages:
                # Stats par statut
                status_key = substage.status
                stats['by_status'][status_key] = stats['by_status'].get(status_key, 0) + 1
                
                # Stats par type
                type_key = substage.substage_type
                stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
                
                # Comptage des retards
                if substage.end_date and substage.end_date < today and substage.status != 'COMPLETED':
                    stats['overdue_count'] += 1
            
            return Response({
                'success': True,
                'data': {
                    'pipeline_id': pipeline.id,
                    'opportunity_title': pipeline.opportunity.title,
                    'substages': serializer.data,
                    'stats': stats
                }
            })
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Opportunity ID")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Substages list failed: {str(e)}")
            )
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages')
    def add_substage(self, request, opportunity_id=None):
        """
        POST /opportunities/{id}/pipeline/substages/
        Ajoute un nouveau substage à une étape du pipeline
        
        Body: {
            "stage_id": 123,
            "name": "Nouvelle sous-étape",
            "description": "Description...",
            "substage_type": "INTERACTION_CLIENT",
            "estimated_duration_days": 5,
            "metadata": {...}
        }
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Validation des données requises
            stage_id = request.data.get('stage_id')
            if not stage_id:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="stage_id")
                )
            
            # Vérifier que le stage appartient au pipeline
            try:
                stage = pipeline.stages.get(id=stage_id, client_id=self.get_client_id())
            except PipelineStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.STAGE_NOT_FOUND
                )
            
            # Préparer les données du substage
            substage_data = request.data.copy()
            substage_data['stage'] = stage.id
            substage_data['client_id'] = self.get_client_id()
            
            # Calculer l'ordre automatiquement si non fourni
            if 'order' not in substage_data:
                last_order = stage.substages.filter(is_active=True).aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                substage_data['order'] = last_order + 1
            
            with transaction.atomic():
                # Créer le substage
                serializer = PipelineSubStageSerializer(data=substage_data, context={'client_id': self.get_client_id()})
                serializer.is_valid(raise_exception=True)
                substage = serializer.save(created_by=request.user, updated_by=request.user)
                
                # Créer les métadonnées si fournies
                metadata_data = request.data.get('metadata')
                if metadata_data:
                    from apps.opportunities.serializers import SubStageMetadataSerializer
                    metadata_data['substage'] = substage.id
                    metadata_serializer = SubStageMetadataSerializer(data=metadata_data, context={'client_id': self.get_client_id()})
                    metadata_serializer.is_valid(raise_exception=True)
                    metadata_serializer.save(created_by=request.user, updated_by=request.user)
                
                # Marquer le pipeline comme personnalisé
                pipeline.is_customized = True
                pipeline.save()
                
                return Response({
                    'success': True,
                    'message': f'SubStage "{substage.name}" added to pipeline',
                    'data': {
                        'substage_id': substage.id,
                        'substage_name': substage.name,
                        'stage_name': stage.name,
                        'order': substage.order,
                        'pipeline_id': pipeline.id
                    }
                }, status=status.HTTP_201_CREATED)
                
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_CREATION_FAILED.format(reason=str(e))
            )
    
    @action(detail=False, methods=['put'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)')
    def update_substage(self, request, opportunity_id=None, substage_id=None):
        """
        PUT /opportunities/{id}/pipeline/substages/{substage_id}/
        Met à jour un substage (durée, statut, métadonnées...)
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            with transaction.atomic():
                # Mettre à jour le substage
                serializer = PipelineSubStageSerializer(
                    substage, 
                    data=request.data, 
                    partial=True,
                    context={'client_id': self.get_client_id()}
                )
                serializer.is_valid(raise_exception=True)
                serializer.save(updated_by=request.user)
                
                # Mettre à jour les métadonnées si fournies
                metadata_data = request.data.get('metadata')
                if metadata_data:
                    from apps.opportunities.serializers import SubStageMetadataSerializer
                    if hasattr(substage, 'metadata'):
                        metadata_serializer = SubStageMetadataSerializer(
                            substage.metadata,
                            data=metadata_data,
                            partial=True,
                            context={'client_id': self.get_client_id()}
                        )
                    else:
                        metadata_data['substage'] = substage.id
                        metadata_serializer = SubStageMetadataSerializer(
                            data=metadata_data,
                            context={'client_id': self.get_client_id()}
                        )
                    
                    metadata_serializer.is_valid(raise_exception=True)
                    metadata_serializer.save(updated_by=request.user)
                
                # Marquer le pipeline comme personnalisé
                pipeline.is_customized = True
                pipeline.save()
                
                return Response({
                    'success': True,
                    'message': f'SubStage "{substage.name}" updated successfully',
                    'data': serializer.data
                })
                
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_UPDATE_FAILED.format(reason=str(e))
            )
    
    # ===== INTÉGRATION CAMPAGNES (via SubStageFollowUpService) =====
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/campaigns')
    def list_substage_campaigns(self, request, opportunity_id=None, substage_id=None):
        """
        GET /opportunities/{id}/pipeline/substages/{substage_id}/campaigns/
        Liste toutes les campagnes liées à un substage
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Récupérer les campaign targets liés à ce substage
            campaign_targets = substage.campaign_targets.select_related(
                'campaign', 'contact', 'account', 'lead'
            ).prefetch_related(
                'campaign__targets'
            )
            
            # Organiser par campagne
            campaigns_data = {}
            for target in campaign_targets:
                campaign = target.campaign
                campaign_id = campaign.id
                
                if campaign_id not in campaigns_data:
                    campaigns_data[campaign_id] = {
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'campaign_status': campaign.status,
                        'sequence_type': getattr(campaign, 'sequence_type', None),
                        'created_at': campaign.created_at,
                        'targets': [],
                        'targets_count': 0,
                        'active_targets': 0
                    }
                
                # Ajouter le target
                target_info = {
                    'target_id': target.id,
                    'status': target.status,
                    'target_type': target.get_target_type(),
                    'target_name': target.get_target_name(),
                    'substage_objective': target.substage_objective,
                    'has_context': bool(target.substage_context)
                }
                
                campaigns_data[campaign_id]['targets'].append(target_info)
                campaigns_data[campaign_id]['targets_count'] += 1
                
                if target.status in ['PENDING', 'IN_PROGRESS']:
                    campaigns_data[campaign_id]['active_targets'] += 1
            
            return Response({
                'success': True,
                'data': {
                    'substage_id': substage.id,
                    'substage_name': substage.name,
                    'campaigns': list(campaigns_data.values()),
                    'total_campaigns': len(campaigns_data),
                    'total_targets': sum(c['targets_count'] for c in campaigns_data.values())
                }
            })
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Campaigns list failed: {str(e)}")
            )
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/add-to-followup')
    def add_substage_to_followup(self, request, opportunity_id=None, substage_id=None):
        """
        POST /opportunities/{id}/pipeline/substages/{substage_id}/add-to-followup/
        Ajoute un substage à la campagne follow-up unique via SubStageFollowUpService
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Vérifier que le substage appartient au pipeline
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Utiliser le service existant pour ajouter au follow-up
            from apps.opportunities.services.substage_followup_service import SubStageFollowUpService
            
            response = SubStageFollowUpService.add_substage_to_followup(
                substage_id=int(substage_id),
                user=request.user,
                client_id=self.get_client_id()
            )
            
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Add to follow-up failed: {str(e)}")
            )
    
    @action(detail=False, methods=['delete'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/remove-from-followup')
    def remove_substage_from_followup(self, request, opportunity_id=None, substage_id=None):
        """
        DELETE /opportunities/{id}/pipeline/substages/{substage_id}/remove-from-followup/
        Supprime un substage de la campagne follow-up via SubStageFollowUpService
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Vérifier que le substage appartient au pipeline
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Utiliser le service existant pour supprimer du follow-up
            from apps.opportunities.services.substage_followup_service import SubStageFollowUpService
            
            notes = request.data.get('notes', 'Removed from follow-up via pipeline API')
            
            response = SubStageFollowUpService.remove_substage_from_followup(
                substage_id=int(substage_id),
                client_id=self.get_client_id(),
                user=request.user,
                notes=notes
            )
            
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Remove from follow-up failed: {str(e)}")
            )
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/complete-followup')
    def complete_substage_followup(self, request, opportunity_id=None, substage_id=None):
        """
        POST /opportunities/{id}/pipeline/substages/{substage_id}/complete-followup/
        Marque la séquence follow-up d'un substage comme completed
        
        Body: {
            "notes": "Notes de completion"
        }
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Vérifier que le substage appartient au pipeline
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Utiliser le service existant pour compléter la séquence
            from apps.opportunities.services.substage_followup_service import SubStageFollowUpService
            
            notes = request.data.get('notes', 'Follow-up sequence completed via pipeline API')
            
            response = SubStageFollowUpService.complete_substage_sequence(
                substage_id=int(substage_id),
                client_id=self.get_client_id(),
                user=request.user,
                notes=notes
            )
            
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Complete follow-up failed: {str(e)}")
            )
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/followup-status')
    def get_substage_followup_status(self, request, opportunity_id=None, substage_id=None):
        """
        GET /opportunities/{id}/pipeline/substages/{substage_id}/followup-status/
        Récupère le statut détaillé du substage dans la campagne follow-up
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Vérifier que le substage appartient au pipeline
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Utiliser le service existant pour récupérer le statut
            from apps.opportunities.services.substage_followup_service import SubStageFollowUpService
            
            response = SubStageFollowUpService.get_substage_followup_status(
                substage_id=int(substage_id),
                client_id=self.get_client_id()
            )
            
            return response
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Follow-up status failed: {str(e)}")
            )
    
    @action(detail=False, methods=['get'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/activities')
    def pipeline_activities(self, request, opportunity_id=None):
        """
        GET /opportunities/{id}/pipeline/activities/
        Récupère toutes les activités générées par les campagnes du pipeline
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer tous les substages du pipeline
            substages = PipelineSubStage.objects.filter(
                stage__opportunity_pipeline=pipeline,
                is_active=True,
                client_id=self.get_client_id()
            )
            
            # Récupérer toutes les activités liées via les campagnes
            from apps.activities.models import Activity
            from apps.campaign.models import CampaignTarget
            
            # Récupérer les campaign targets de tous les substages
            campaign_targets = CampaignTarget.objects.filter(
                substage__in=substages
            ).select_related('campaign')
            
            # Récupérer les activités de ces campagnes
            campaign_ids = [target.campaign_id for target in campaign_targets]
            
            activities = Activity.objects.filter(
                campaign_info__campaign_id__in=campaign_ids,
                client_id=self.get_client_id()
            ).select_related(
                'owner', 'campaign_info'
            ).order_by('-scheduled_start')
            
            # Organiser par substage
            activities_by_substage = {}
            
            for activity in activities:
                # Trouver le substage correspondant
                campaign_target = campaign_targets.filter(
                    campaign_id=activity.campaign_info.campaign_id
                ).first()
                
                if campaign_target and campaign_target.substage:
                    substage_id = campaign_target.substage_id
                    if substage_id not in activities_by_substage:
                        activities_by_substage[substage_id] = {
                            'substage_name': campaign_target.substage.name,
                            'stage_name': campaign_target.substage.stage.name,
                            'activities': []
                        }
                    
                    activities_by_substage[substage_id]['activities'].append({
                        'id': activity.id,
                        'title': activity.title,
                        'activity_type': activity.activity_type,
                        'status': activity.status,
                        'scheduled_start': activity.scheduled_start,
                        'completed_at': activity.completed_at,
                        'owner': activity.owner.get_full_name() if activity.owner else None,
                        'campaign_name': campaign_target.campaign.name
                    })
            
            return Response({
                'success': True,
                'data': {
                    'pipeline_id': pipeline.id,
                    'opportunity_title': pipeline.opportunity.title,
                    'activities_by_substage': activities_by_substage,
                    'total_activities': activities.count()
                }
            })
            
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Opportunity ID")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Pipeline activities failed: {str(e)}")
            )
    
    @action(detail=False, methods=['delete'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)')
    def remove_substage(self, request, opportunity_id=None, substage_id=None):
        """
        DELETE /opportunities/{id}/pipeline/substages/{substage_id}/
        Supprime un substage du pipeline (soft delete)
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Vérifier qu'il n'y a pas de campagnes actives liées
            active_campaigns = substage.campaign_targets.filter(
                campaign__status__in=['ACTIVE', 'IN_PROGRESS']
            ).count()
            
            if active_campaigns > 0:
                raise StandardizedValidationError(
                    f"Cannot delete substage '{substage.name}': {active_campaigns} active campaign(s) are linked to it"
                )
            
            with transaction.atomic():
                substage_name = substage.name
                stage_name = substage.stage.name
                
                # Soft delete
                substage.is_active = False
                substage.save()
                
                # Marquer le pipeline comme personnalisé
                pipeline.is_customized = True
                pipeline.save()
                
                return Response({
                    'success': True,
                    'message': f'SubStage "{substage_name}" removed from stage "{stage_name}"'
                }, status=status.HTTP_204_NO_CONTENT)
                
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_UPDATE_FAILED.format(reason=str(e))
            )
    
    # ===== GESTION DES STATUTS =====
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/start')
    def start_substage(self, request, opportunity_id=None, substage_id=None):
        """
        POST /opportunities/{id}/pipeline/substages/{substage_id}/start/
        Démarre un substage (passe de NOT_STARTED à IN_PROGRESS)
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Vérifier le statut actuel
            if substage.status != 'NOT_STARTED':
                raise StandardizedValidationError(
                    f"Cannot start substage '{substage.name}': current status is '{substage.status}'"
                )
            
            with transaction.atomic():
                from django.utils import timezone
                
                # Mettre à jour le statut et les dates
                substage.status = 'IN_PROGRESS'
                substage.start_date = timezone.now().date()
                
                # Calculer la date de fin si durée estimée fournie
                if substage.estimated_duration_days:
                    from datetime import timedelta
                    substage.end_date = substage.start_date + timedelta(days=substage.estimated_duration_days)
                
                substage.save()
                
                return Response({
                    'success': True,
                    'message': f'SubStage "{substage.name}" started successfully',
                    'data': {
                        'substage_id': substage.id,
                        'status': substage.status,
                        'start_date': substage.start_date,
                        'end_date': substage.end_date
                    }
                })
                
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_UPDATE_FAILED.format(reason=str(e))
            )
    
    @action(detail=False, methods=['post'], url_path='(?P<opportunity_id>[^/.]+)/pipeline/substages/(?P<substage_id>[^/.]+)/complete')
    def complete_substage(self, request, opportunity_id=None, substage_id=None):
        """
        POST /opportunities/{id}/pipeline/substages/{substage_id}/complete/
        Complète un substage (passe à COMPLETED)
        
        Body: {
            "completion_notes": "Notes sur la completion",
            "outcome": "SUCCESS|PARTIAL|FAILED"
        }
        """
        try:
            pipeline = self.get_pipeline(int(opportunity_id))
            
            # Récupérer le substage
            try:
                substage = PipelineSubStage.objects.get(
                    id=int(substage_id),
                    stage__opportunity_pipeline=pipeline,
                    client_id=self.get_client_id()
                )
            except PipelineSubStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                )
            
            # Vérifier le statut actuel
            if substage.status == 'COMPLETED':
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_ALREADY_COMPLETED.format(substage_name=substage.name)
                )
            
            with transaction.atomic():
                from django.utils import timezone
                
                # Mettre à jour le statut et les dates
                substage.status = 'COMPLETED'
                substage.completed_at = timezone.now()
                
                # Si pas de start_date, la définir maintenant
                if not substage.start_date:
                    substage.start_date = timezone.now().date()
                
                # Ajouter les notes de completion si fournies
                completion_notes = request.data.get('completion_notes')
                if completion_notes:
                    current_notes = substage.notes or ""
                    substage.notes = f"{current_notes}\n\nCompleted: {completion_notes}".strip()
                
                substage.save()
                
                # Arrêter les campagnes actives liées à ce substage
                active_targets = substage.campaign_targets.filter(
                    campaign__status__in=['ACTIVE', 'IN_PROGRESS']
                )
                
                campaigns_stopped = []
                for target in active_targets:
                    if target.status in ['PENDING', 'IN_PROGRESS']:
                        target.status = 'COMPLETED'
                        target.save()
                        campaigns_stopped.append(target.campaign.name)
                
                return Response({
                    'success': True,
                    'message': f'SubStage "{substage.name}" completed successfully',
                    'data': {
                        'substage_id': substage.id,
                        'status': substage.status,
                        'completed_at': substage.completed_at,
                        'campaigns_affected': len(campaigns_stopped),
                        'campaigns_stopped': campaigns_stopped
                    }
                })
                
        except ValueError:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="ID values must be integers")
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_UPDATE_FAILED.format(reason=str(e))
            )