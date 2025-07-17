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
    PipelineTemplate, PipelineStage, OpportunityPipeline, PipelineSubStage
)
from apps.opportunities.serializers import (
    PipelineTemplateSerializer, PipelineStageSerializer
)
from apps.opportunities.services.buying_process_service import BuyingProcessService
from apps.opportunities.services.buying_process_substage_service import SubstageService 


class BuyingProcessViewSet(BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints pour la gestion des process de vente et leurs stages
    """
    
    # ✅ Attributs obligatoires ajoutés
    queryset = PipelineTemplate.objects.all()
    serializer_class = PipelineTemplateSerializer
    entity_name = 'pipeline_template'

    def get_queryset(self):
        """Get templates for the current client with annotations"""
        queryset = PipelineTemplate.objects.all()
        
        # Apply client scoping
        queryset = self.filter_queryset_by_client(queryset)
        
        # Add annotations for better performance
        queryset = queryset.annotate(
            stages_count=Count('stages', filter=Q(stages__is_active=True)),
            pipelines_count=Count('opportunity_pipelines')
        ).prefetch_related('stages', 'opportunity')
        
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
        queryset = self.filter_queryset(self.get_queryset())

        # Filtres
        opportunity_id = request.query_params.get('opportunity_id')
        is_default = request.query_params.get('is_default')
        search = request.query_params.get('search')
        
        if opportunity_id:
            queryset = queryset.filter(opportunity_id=opportunity_id)
        if is_default:
            queryset = queryset.filter(is_default=is_default.lower() == 'true')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

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
                    'opportunity_id': opportunity_id,
                    'is_default': is_default,
                    'search': search
                }
            }
        })
        
    def retrieve(self, request, *args, **kwargs):
        """
        Récupère un template avec ses étapes en utilisant le service
        """
        # get_object() applique automatiquement le ClientScope
        instance = self.get_object()
        
        # Utiliser le service pour récupérer les données complètes
        template_data = BuyingProcessService.get_template_with_stages(
            template_id=instance.id
        )
        
        return Response({
            'success': True,
            'data': template_data
        })
        
    def create(self, request, *args, **kwargs):
        """
        Crée un nouveau template avec client_id
        """
        client_id = self.get_client_id()
            
        # Valider les données
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Créer le template avec le service en passant le client_id
        template = BuyingProcessService.create_template_with_stages(
            validated_data=serializer.validated_data, 
            request=request,
            client_id=client_id
        )
        
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
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        instance.mark_as_custom_if_modified()
        
        serializer.save()
        
        return Response({
            'success': True,
            'message': f'Template "{instance.name}" updated successfully',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Supprime un template (validation obsolète "template utilisé" supprimée)
        """
        instance = self.get_object()
        
        template_name = instance.name
        instance.delete()
        
        return Response({
            'success': True,
            'message': f'Template "{template_name}" deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)

    # ===== GESTION DES STAGES =====
    
    @action(detail=True, methods=['get'])
    def list_stages(self, request, pk=None):
        """
        Liste les étapes d'un template spécifique (utilise aussi le service)
        """
        # get_object() applique automatiquement le ClientScope
        instance = self.get_object()
        
        # Utiliser le service pour récupérer les données
        template_data = BuyingProcessService.get_template_with_stages(
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

    @action(detail=True, methods=['post'], url_path='stages')
    def add_stage(self, request, pk=None):
        """
        POST /pipeline-templates/{id}/stages/
        Ajoute un nouveau stage au template
        """
        template = self.get_object()
        
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

        template.mark_as_custom_if_modified()
        
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
    
    @action(detail=True, methods=['put'], url_path='stages/(?P<stage_id>[^/.]+)')
    def update_stage(self, request, pk=None, stage_id=None):
        """
        PUT /pipeline-templates/{id}/stages/{stage_id}/
        Met à jour un stage du template
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        # Mettre à jour le stage
        serializer = PipelineStageSerializer(
            stage,
            data=request.data,
            partial=True,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        updated_stage = serializer.save(updated_by=request.user)

        template.mark_as_custom_if_modified()
        
        return Response({
            'success': True,
            'message': f'Stage "{updated_stage.name}" updated successfully',
            'data': {
                'stage_id': updated_stage.id,
                'stage_name': updated_stage.name,
                'stage_order': updated_stage.order,
                'template_id': template.id
            }
        })

    @action(detail=True, methods=['delete'], url_path='stages/(?P<stage_id>[^/.]+)')
    def remove_stage(self, request, pk=None, stage_id=None):
        """
        DELETE /pipeline-templates/{id}/stages/{stage_id}/
        Supprime un stage du template
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        stage_name = stage.name
        stage.is_active = False  # Soft delete
        stage.save()
        
        return Response({
            'success': True,
            'message': f'Stage "{stage_name}" removed from template "{template.name}"'
        }, status=status.HTTP_204_NO_CONTENT)

    # ===== GESTION DES SUBSTAGES =====
    
    @action(detail=True, methods=['get'], url_path='stages/(?P<stage_id>[^/.]+)/substages')
    def list_substages(self, request, pk=None, stage_id=None):
        """
        GET /pipeline-templates/{id}/stages/{stage_id}/substages/
        Liste les substages d'un stage spécifique
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id)
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        # Utiliser le service pour récupérer les substages
        substages_data = SubstageService.get_substages_for_stage(
            stage_id=stage.id,
            client_id=self.get_client_id()
        )
        
        return Response({
            'success': True,
            'data': {
                'template_id': template.id,
                'stage_id': stage.id,
                'stage_name': stage.name,
                'substages': substages_data['substages'],
                'substages_count': substages_data['substages_count']
            }
        })
    
    @action(detail=True, methods=['post'], url_path='stages/(?P<stage_id>[^/.]+)/substages')
    def add_substage(self, request, pk=None, stage_id=None):
        """
        POST /pipeline-templates/{id}/stages/{stage_id}/substages/
        Ajoute une nouvelle substage au stage
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        # Préparer les données pour la substage
        substage_data = request.data.copy()
        substage_data['stage'] = stage.id
        substage_data['client_id'] = self.get_client_id()
        
        # Calculer l'ordre automatiquement si non fourni
        if 'order' not in substage_data:
            last_order = stage.substages.aggregate(
                max_order=Max('order')
            )['max_order'] or 0
            substage_data['order'] = last_order + 1
        
        # Utiliser le service pour créer la substage
        substage = SubstageService.create_substage_with_metadata(
            validated_data=substage_data,
            metadata_data=request.data.get('metadata', {}),
            user=request.user,
            client_id=self.get_client_id()
        )

        template.mark_as_custom_if_modified()
        
        return Response({
            'success': True,
            'message': f'SubStage "{substage.name}" added to stage "{stage.name}"',
            'data': {
                'substage_id': substage.id,
                'substage_name': substage.name,
                'substage_order': substage.order,
                'stage_id': stage.id,
                'stage_name': stage.name,
                'template_id': template.id
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['put'], url_path='stages/(?P<stage_id>[^/.]+)/substages/(?P<substage_id>[^/.]+)')
    def update_substage(self, request, pk=None, stage_id=None, substage_id=None):
        """
        PUT /pipeline-templates/{id}/stages/{stage_id}/substages/{substage_id}/
        Met à jour une substage
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        # Récupérer la substage
        try:
            substage = stage.substages.get(id=substage_id, client_id=self.get_client_id())
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
        
        # Utiliser le service pour mettre à jour
        updated_substage = SubstageService.update_substage_with_metadata(
            substage=substage,
            substage_data=request.data,
            metadata_data=request.data.get('metadata', {}),
            user=request.user,
            client_id=self.get_client_id()
        )

        template.mark_as_custom_if_modified()
        
        return Response({
            'success': True,
            'message': f'SubStage "{updated_substage.name}" updated successfully',
            'data': {
                'substage_id': updated_substage.id,
                'substage_name': updated_substage.name,
                'substage_order': updated_substage.order,
                'stage_id': stage.id,
                'stage_name': stage.name,
                'template_id': template.id
            }
        })
    
    @action(detail=True, methods=['delete'], url_path='stages/(?P<stage_id>[^/.]+)/substages/(?P<substage_id>[^/.]+)')
    def remove_substage(self, request, pk=None, stage_id=None, substage_id=None):
        """
        DELETE /pipeline-templates/{id}/stages/{stage_id}/substages/{substage_id}/
        Supprime une substage
        """
        template = self.get_object()
        
        # Récupérer le stage
        try:
            stage = template.stages.get(id=stage_id, client_id=self.get_client_id())
        except PipelineStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.STAGE_NOT_FOUND
            )
        
        # Récupérer la substage
        try:
            substage = stage.substages.get(id=substage_id, client_id=self.get_client_id())
        except PipelineSubStage.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )
        
        substage_name = substage.name
        substage.is_active = False  # Soft delete
        substage.save()
        
        return Response({
            'success': True,
            'message': f'SubStage "{substage_name}" removed from stage "{stage.name}"'
        }, status=status.HTTP_204_NO_CONTENT)
    
    # ===== OPPORTUNITY PROCESS OVERVIEW =====
    
    @action(detail=False, methods=['get'], url_path='opportunity/(?P<opportunity_id>[^/.]+)/overview')
    def opportunity_overview(self, request, opportunity_id=None):
        """
        GET /pipeline-templates/opportunity/{opportunity_id}/overview/
        Récupère l'aperçu complet du processus d'une opportunité avec tous les stages et leurs données
        """
        # Récupérer l'opportunité et son template
        from apps.opportunities.models import Opportunity
        
        try:
            opportunity = Opportunity.objects.get(
                id=int(opportunity_id),
                client_id=self.get_client_id()
            )
        except Opportunity.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.OPPORTUNITY_NOT_FOUND
            )
        
        # Récupérer le template de l'opportunité
        try:
            template = opportunity.pipeline_templates.get(client_id=self.get_client_id())
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_NOT_FOUND
            )
        
        # Utiliser le service pour récupérer les données complètes
        overview_data = BuyingProcessService.get_opportunity_process_overview(
            opportunity_id=opportunity.id,
            template_id=template.id,
            client_id=self.get_client_id()
        )
        
        return Response({
            'success': True,
            'data': overview_data
        })