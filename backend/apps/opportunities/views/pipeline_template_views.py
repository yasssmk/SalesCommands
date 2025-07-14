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


class PipelineTemplateViewSet(BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des templates de pipeline et leurs stages
    """
    queryset = PipelineTemplate.objects.all()
    serializer_class = PipelineTemplateSerializer
    entity_name = 'pipeline_template'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = [ 'name']
    
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
        Récupère un template avec ses étapes en utilisant le service
        """
        try:
            # get_object() applique automatiquement le ClientScope
            instance = self.get_object()
            
            # Utiliser le service pour récupérer les données complètes
            template_data = PipelineTemplateService.get_template_with_stages(
                template_id=instance.id
            )
            
            return Response({
                'success': True,
                'data': template_data
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
        
    def create(self, request, *args, **kwargs):
        """
        Crée un nouveau template
        """

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template = serializer.save()
        
        return Response({
            'success': True,
            'message': f'Template "{template.name}" created successfully',
            'data': {
                'template_id': template.id,
                'template_name': template.name,
                "template_type": template.template_type,
                'is_default': template.is_default,
                'stages_count': template.stages.filter(is_active=True).count()
            }
        }, status=status.HTTP_201_CREATED)
            
    
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
        Liste les étapes d'un template spécifique (utilise aussi le service)
        """
        try:
            # get_object() applique automatiquement le ClientScope
            instance = self.get_object()
            
            # Utiliser le service pour récupérer les données
            template_data = PipelineTemplateService.get_template_with_stages(
                template_id=instance.id
            )
            
            return Response({
                'success': True,
                'data': {
                    'template_id': instance.id,
                    'template_name': instance.name,
                    'stages': template_data['stages'],
                    'stages_count': template_data['stages_count']
                }
            })
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
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
        Duplique un template en utilisant le service refactorisé
        """
        try:
            # get_object() applique automatiquement le ClientScope
            source_template = self.get_object()
            
            # Récupérer le nouveau nom
            new_name = request.data.get('name')
            if not new_name:
                raise StandardizedValidationError(
                    "name is required for template duplication"
                )
            
            with transaction.atomic():
                # Préparer les données du nouveau template
                template_data = {
                    'name': new_name,
                    'description': f"Copy of {source_template.name}",
                    'template_type': source_template.template_type,  # Garder le même type
                    'is_default': False,  # Les copies ne sont jamais par défaut
                    'order': source_template.order + 1,
                    'is_active': True
                }
                
                # Créer le nouveau template avec le serializer (qui a le contexte)
                serializer = self.get_serializer(data=template_data)
                serializer.is_valid(raise_exception=True)
                new_template = serializer.save()
                
                # Dupliquer les étapes manuellement (pas les étapes par défaut du type)
                source_stages = source_template.stages.filter(is_active=True).order_by('order')
                
                for source_stage in source_stages:
                    # Créer les étapes directement (pas besoin de serializer pour ça)
                    from ..models.pipeline_stage import PipelineStage
                    PipelineStage.objects.create(
                        template=new_template,
                        name=source_stage.name,
                        description=source_stage.description,
                        order=source_stage.order,
                        is_active=True,
                        client_id=self.get_client_id(),  # Contexte de la vue
                        user=request.user
                    )
            
            # Calculer le nombre d'étapes copiées
            stages_count = new_template.stages.filter(is_active=True).count()
            
            return Response({
                'success': True,
                'message': f'Template duplicated successfully as "{new_name}"',
                'data': {
                    'source_template_id': source_template.id,
                    'source_template_name': source_template.name,
                    'new_template_id': new_template.id,
                    'new_template_name': new_template.name,
                    'stages_copied': stages_count
                }
            }, status=status.HTTP_201_CREATED)
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
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
