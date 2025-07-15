# backend/apps/opportunities/services/pipeline_template_service.py

from django.db import transaction
from rest_framework.response import Response
from apps.opportunities.models import PipelineTemplate, PipelineStage
from apps.opportunities.config import PipelineStagesConfig
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer


class PipelineTemplateService:
    """
    Service simple pour la gestion des templates de pipeline (MVP).
    Scalable avec dispatch pattern.
    """
    
    @classmethod  
    def create_template_with_stages(cls, validated_data: dict, request, client_id: str) -> 'PipelineTemplate':
        """
        Crée un template avec ses stages par défaut selon le template_type
        
        Args:
            validated_data: Données validées du serializer (contient client_id automatiquement)
        
        Returns:
            PipelineTemplate: L'instance créée avec ses étapes
        """

        with transaction.atomic():
            # Créer le template avec les données validées
            template = PipelineTemplate(**validated_data)
            # Sauvegarder avec client_id et user (pattern BaseModelApp)
            template.save(client_id=client_id, user=request.user)
            
            # Créer les stages selon le template_type
            stages_created = cls._create_stages_for_template(template, request)
            
            return template
    
    @classmethod
    def _create_stages_for_template(cls, template: 'PipelineTemplate', request) -> int:
        """
        Crée les étapes par défaut selon le template_type
        Méthode privée réutilisable
        """
        from ..models.pipeline_stage import PipelineStage
        
        stages_data = []
        
        # Récupérer les stages selon le template_type
        if template.template_type == PipelineStagesConfig.TemplateType.DEFAULT:
            stages_data = PipelineStagesConfig.get_default_stages()
        elif template.template_type == PipelineStagesConfig.TemplateType.RENEWAL:
            stages_data = PipelineStagesConfig.get_renewal_stages()
        # Pour CUSTOM, pas de stages automatiques
        
        # Créer tous les stages d'abord (sans linked list)
        created_stages = []
        for stage_name, stage_description, stage_order in stages_data:
            # Créer le stage avec les champs normaux
            stage = PipelineStage(
                template=template,
                name=stage_name,
                description=stage_description,
                order=stage_order,
                is_active=True
            )
            
            # Sauvegarder en évitant la mise à jour de linked list
            stage.save(client_id=template.client_id, user=request.user, skip_linked_list_update=True)
            created_stages.append(stage)
        
        # Maintenant mettre à jour la linked list pour tous les stages en une seule fois
        if created_stages:
            cls._update_template_linked_list(template)
        
        return len(created_stages)
        
    @classmethod
    def _update_template_linked_list(cls, template: 'PipelineTemplate'):
        """
        Met à jour la linked list pour tous les stages d'un template
        Méthode optimisée qui évite la récursion
        """
        from ..models.pipeline_stage import PipelineStage
        
        # Récupérer tous les stages du template ordonnés
        stages = PipelineStage.objects.filter(
            template=template,
            is_active=True,
            client_id=template.client_id
        ).order_by('order')
        
        # Mettre à jour les relations previous/next en une seule passe
        stages_list = list(stages)
        
        for i, stage in enumerate(stages_list):
            # Définir previous_stage
            if i > 0:
                stage.previous_stage = stages_list[i - 1]
            else:
                stage.previous_stage = None
            
            # Définir next_stage
            if i < len(stages_list) - 1:
                stage.next_stage = stages_list[i + 1]
            else:
                stage.next_stage = None
            
            # Sauvegarder avec skip_linked_list_update pour éviter la récursion
            stage.save(update_fields=['previous_stage', 'next_stage'], skip_linked_list_update=True)
            
    @classmethod
    def get_template_with_stages(cls, template_id: int) -> dict:
        """
        Récupère un template avec ses étapes
        Utilise le ClientScope automatiquement via le queryset
        
        Args:
            template_id: ID du template à récupérer
        
        Returns:
            dict: Template avec ses étapes
        """
        try:
            from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
            
            # Le ClientScope sera géré par la vue qui appelle cette méthode
            # On assume que le template_id est déjà filtré par client dans la vue
            template = PipelineTemplate.objects.get(id=template_id)
            
            # Récupérer les étapes actives
            stages = template.stages.filter(is_active=True).order_by('order')
            
            # Utiliser les serializers pour la cohérence
            template_serializer = PipelineTemplateSerializer(template)
            stages_serializer = PipelineStageSerializer(stages, many=True)
            
            return {
                'template': template_serializer.data,
                'stages': stages_serializer.data,
                'stages_count': stages.count()
            }
            
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )

    @classmethod
    def duplicate_template(cls, template_id: int, new_name: str) -> 'PipelineTemplate':
        """
        Duplique un template existant
        Utilise les serializers pour respecter le ClientScope
        
        Args:
            template_id: ID du template source
            new_name: Nom du nouveau template
        
        Returns:
            PipelineTemplate: Le template dupliqué
        """
        try:
            from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
            
            with transaction.atomic():
                # Récupérer le template source (le ClientScope sera géré par la vue)
                source_template = PipelineTemplate.objects.get(id=template_id)
                
                # Créer le nouveau template avec le serializer
                template_data = {
                    'name': new_name,
                    'description': f"Copy of {source_template.name}",
                    'is_default': False,
                    'order': source_template.order + 1,  # Décaler l'ordre
                    'is_active': True
                }
                
                template_serializer = PipelineTemplateSerializer(data=template_data)
                if not template_serializer.is_valid():
                    raise StandardizedValidationError(
                        f"Template duplication failed: {template_serializer.errors}"
                    )
                
                new_template = template_serializer.save()
                
                # Dupliquer les étapes avec le serializer
                source_stages = source_template.stages.filter(is_active=True).order_by('order')
                
                for source_stage in source_stages:
                    stage_data = {
                        'template': new_template.id,
                        'name': source_stage.name,
                        'description': source_stage.description,
                        'order': source_stage.order,
                        'is_active': True
                    }
                    
                    stage_serializer = PipelineStageSerializer(data=stage_data)
                    if stage_serializer.is_valid():
                        stage_serializer.save()
                
                return new_template
                
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )

