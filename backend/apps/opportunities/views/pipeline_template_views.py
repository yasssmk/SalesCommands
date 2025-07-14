# apps/opportunities/views/pipeline_template_views.py

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Max
from django.db import transaction
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from core.apps_shared_methods import BaseAPIView
from apps.opportunities.models import (
    PipelineTemplate, PipelineStage, OpportunityPipeline
)
from apps.opportunities.serializers import (
    PipelineTemplateSerializer, PipelineStageSerializer
)
from apps.opportunities.services.pipeline_template_service import PipelineTemplateService


class PipelineTemplateViewSet(BaseAPIView, ClientScopeManager.ViewMixin, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des templates de pipeline et leurs stages
    """
    queryset = PipelineTemplate.objects.all()
    serializer_class = PipelineTemplateSerializer
    entity_name = 'pipeline_template'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['order', 'name', 'created_at']
    ordering = ['order', 'name']
    
    def get_queryset(self):
        """Get templates for the current client with annotations"""
        queryset = PipelineTemplate.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Add annotations for better performance
        queryset = queryset.annotate(
            stages_count=Count('stages', filter=Q(stages__is_active=True)),
            pipelines_count=Count('opportunity_pipelines')
        ).prefetch_related('stages')
        
        return queryset
    
    def get_serializer_context(self):
        """Add client_id to serializer context"""
        context = super().get_serializer_context()
        context['client_id'] = self.get_client_id()
        return context
    
    def list(self, request, *args, **kwargs):
        """
        Liste tous les templates avec informations supplémentaires
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            
            # Ajouter des stats globales
            stats = {
                'total_templates': queryset.count(),
                'active_templates': queryset.filter(is_active=True).count(),
                'default_templates': queryset.filter(is_default=True).count()
            }
            
            return Response({
                'success': True,
                'data': serializer.data,
                'meta': {
                    'stats': stats,
                    'filters_applied': {
                        'is_active': request.query_params.get('is_active'),
                        'is_default': request.query_params.get('is_default'),
                        'search': request.query_params.get('search')
                    }
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Template list failed: {str(e)}")
            )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Récupère un template avec tous ses stages
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            
            # Récupérer les stages du template
            stages = instance.stages.filter(is_active=True).order_by('order')
            stages_serializer = PipelineStageSerializer(stages, many=True)
            
            return Response({
                'success': True,
                'data': {
                    'template': serializer.data,
                    'stages': stages_serializer.data,
                    'stages_count': stages.count(),
                    'is_in_use': instance.opportunity_pipelines.exists()
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
    
    def create(self, request, *args, **kwargs):
        """
        Crée un nouveau template
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Utiliser le service pour la création
            template = PipelineTemplateService.create_template(
                client_id=self.get_client_id(),
                user=request.user,
                **serializer.validated_data
            )
            
            return Response({
                'success': True,
                'message': f'Template "{template.name}" created successfully',
                'data': {
                    'template_id': template.id,
                    'template_name': template.name,
                    'is_default': template.is_default
                }
            }, status=status.HTTP_201_CREATED)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )
    
    def update(self, request, *args, **kwargs):
        """
        Met à jour un template existant
        """
        try:
            instance = self.get_object()
            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            
            # Vérifier si le template est utilisé avant modification majeure
            if instance.opportunity_pipelines.exists():
                if 'is_active' in request.data and not request.data['is_active']:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                            template_name=instance.name,
                            pipelines_count=instance.opportunity_pipelines.count()
                        )
                    )
            
            serializer.save()
            
            return Response({
                'success': True,
                'message': f'Template "{instance.name}" updated successfully',
                'data': serializer.data
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_UPDATE_FAILED.format(reason=str(e))
            )
    
    # ===== GESTION DES STAGES =====
    
    @action(detail=True, methods=['get'], url_path='stages')
    def list_stages(self, request, pk=None):
        """
        GET /pipeline-templates/{id}/stages/
        Liste tous les stages d'un template
        """
        try:
            template = self.get_object()
            stages = template.stages.filter(is_active=True).order_by('order')
            serializer = PipelineStageSerializer(stages, many=True)
            
            return Response({
                'success': True,
                'data': {
                    'template_id': template.id,
                    'template_name': template.name,
                    'stages': serializer.data,
                    'stages_count': stages.count()
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Stages list failed: {str(e)}")
            )
    
    @action(detail=True, methods=['post'], url_path='stages')
    def add_stage(self, request, pk=None):
        """
        POST /pipeline-templates/{id}/stages/
        Ajoute un nouveau stage au template
        """
        try:
            template = self.get_object()
            
            # Vérifier que le template n'est pas utilisé
            if template.opportunity_pipelines.exists():
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                        template_name=template.name,
                        pipelines_count=template.opportunity_pipelines.count()
                    )
                )
            
            # Préparer les données pour le stage
            stage_data = request.data.copy()
            stage_data['template'] = template.id
            stage_data['client_id'] = self.get_client_id()
            
            # Calculer l'ordre automatiquement si non fourni
            if 'order' not in stage_data:
                last_order = template.stages.aggregate(
                    max_order=Max('order')
                )['max_order'] or 0
                stage_data['order'] = last_order + 1
            
            serializer = PipelineStageSerializer(data=stage_data, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            stage = serializer.save(created_by=request.user, updated_by=request.user)
            
            return Response({
                'success': True,
                'message': f'Stage "{stage.name}" added to template "{template.name}"',
                'data': {
                    'stage_id': stage.id,
                    'stage_name': stage.name,
                    'stage_order': stage.order,
                    'template_id': template.id
                }
            }, status=status.HTTP_201_CREATED)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_CREATION_FAILED.format(reason=str(e))
            )
    
    @action(detail=True, methods=['put'], url_path='stages/(?P<stage_id>[^/.]+)')
    def update_stage(self, request, pk=None, stage_id=None):
        """
        PUT /pipeline-templates/{id}/stages/{stage_id}/
        Met à jour un stage du template
        """
        try:
            template = self.get_object()
            
            # Vérifier que le template n'est pas utilisé
            if template.opportunity_pipelines.exists():
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                        template_name=template.name,
                        pipelines_count=template.opportunity_pipelines.count()
                    )
                )
            
            # Récupérer le stage
            try:
                stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
            except PipelineStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.STAGE_NOT_FOUND
                )
            
            serializer = PipelineStageSerializer(stage, data=request.data, partial=True, context=self.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)
            
            return Response({
                'success': True,
                'message': f'Stage "{stage.name}" updated successfully',
                'data': serializer.data
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_UPDATE_FAILED.format(reason=str(e))
            )
    
    # ===== ACTIONS SPÉCIALES =====
    
    @action(detail=True, methods=['post'], url_path='duplicate')
    def duplicate(self, request, pk=None):
        """
        POST /pipeline-templates/{id}/duplicate/
        Duplique un template avec tous ses stages
        """
        try:
            source_template = self.get_object()
            
            # Récupérer le nouveau nom
            new_name = request.data.get('name', f"{source_template.name} (Copy)")
            new_description = request.data.get('description', f"Copy of {source_template.description or source_template.name}")
            
            # Vérifier unicité du nom
            if PipelineTemplate.objects.filter(
                name=new_name,
                client_id=self.get_client_id()
            ).exists():
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_ALREADY_EXISTS
                )
            
            with transaction.atomic():
                # Créer le nouveau template
                new_template = PipelineTemplate.objects.create(
                    name=new_name,
                    description=new_description,
                    order=source_template.order,
                    is_active=True,
                    is_default=False,  # Les copies ne sont jamais par défaut
                    client_id=self.get_client_id(),
                    created_by=request.user,
                    updated_by=request.user
                )
                
                # Dupliquer tous les stages
                stages_created = 0
                for stage in source_template.stages.filter(is_active=True).order_by('order'):
                    PipelineStage.objects.create(
                        template=new_template,
                        name=stage.name,
                        description=stage.description,
                        order=stage.order,
                        is_active=True,
                        estimated_duration=stage.estimated_duration,
                        client_id=self.get_client_id(),
                        created_by=request.user,
                        updated_by=request.user
                    )
                    stages_created += 1
                
                return Response({
                    'success': True,
                    'message': f'Template "{source_template.name}" duplicated successfully',
                    'data': {
                        'new_template_id': new_template.id,
                        'new_template_name': new_template.name,
                        'source_template_id': source_template.id,
                        'stages_copied': stages_created
                    }
                }, status=status.HTTP_201_CREATED)
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_DUPLICATION_FAILED.format(reason=str(e))
            )
    
    @action(detail=True, methods=['post'], url_path='set-as-default')
    def set_as_default(self, request, pk=None):
        """
        POST /pipeline-templates/{id}/set-as-default/
        Définit ce template comme template par défaut
        """
        try:
            template = self.get_object()
            
            # Vérifier que le template est actif
            if not template.is_active:
                raise StandardizedValidationError(
                    "Cannot set inactive template as default"
                )
            
            with transaction.atomic():
                # Enlever le statut par défaut des autres templates
                PipelineTemplate.objects.filter(
                    client_id=self.get_client_id(),
                    is_default=True
                ).update(is_default=False)
                
                # Définir ce template comme par défaut
                template.is_default = True
                template.save()
                
                return Response({
                    'success': True,
                    'message': f'Template "{template.name}" is now the default template',
                    'data': {
                        'template_id': template.id,
                        'template_name': template.name,
                        'is_default': template.is_default
                    }
                })
                
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_UPDATE_FAILED.format(reason=str(e))
            )
    
    @action(detail=False, methods=['get'], url_path='choices')
    def choices(self, request):
        """
        GET /pipeline-templates/choices/
        Retourne les templates actifs pour les sélecteurs
        """
        try:
            templates = self.get_queryset().filter(is_active=True).order_by('order', 'name')
            
            choices = []
            for template in templates:
                choices.append({
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'is_default': template.is_default,
                    'stages_count': template.stages_count if hasattr(template, 'stages_count') else template.stages.filter(is_active=True).count()
                })
            
            return Response({
                'success': True,
                'data': choices,
                'meta': {
                    'total_count': len(choices),
                    'default_template_id': next((t['id'] for t in choices if t['is_default']), None)
                }
            })
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail=f"Template choices failed: {str(e)}")
            )
    
    @action(detail=True, methods=['delete'], url_path='stages/(?P<stage_id>[^/.]+)')
    def remove_stage(self, request, pk=None, stage_id=None):
        """
        DELETE /pipeline-templates/{id}/stages/{stage_id}/
        Supprime un stage du template
        """
        try:
            template = self.get_object()
            
            # Vérifier que le template n'est pas utilisé
            if template.opportunity_pipelines.exists():
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                        template_name=template.name,
                        pipelines_count=template.opportunity_pipelines.count()
                    )
                )
            
            # Récupérer le stage
            try:
                stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
            except PipelineStage.DoesNotExist:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.STAGE_NOT_FOUND
                )
            
            # Vérifier qu'il reste au moins une stage après suppression
            remaining_stages = template.stages.filter(is_active=True).exclude(id=stage_id).count()
            if remaining_stages == 0:
                raise StandardizedValidationError(
                    "Cannot delete last stage: template must have at least one stage"
                )
            
            stage_name = stage.name
            stage.is_active = False  # Soft delete
            stage.save()
            
            return Response({
                'success': True,
                'message': f'Stage "{stage_name}" removed from template "{template.name}"'
            }, status=status.HTTP_204_NO_CONTENT)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_UPDATE_FAILED.format(reason=str(e))
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprime un template (uniquement si non utilisé)
        """
        try:
            instance = self.get_object()
            
            # Vérifier que le template n'est pas utilisé
            pipelines_count = instance.opportunity_pipelines.count()
            if pipelines_count > 0:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                        template_name=instance.name,
                        pipelines_count=pipelines_count
                    )
                )
            
            template_name = instance.name
            instance.delete()
            
            return Response({
                'success': True,
                'message': f'Template "{template_name}" deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_UPDATE_FAILED.format(reason=str(e))
            )