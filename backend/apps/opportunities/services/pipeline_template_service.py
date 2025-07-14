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
    def create_template(cls, template_data: dict) -> 'PipelineTemplate':
        """
        Crée un template selon le type spécifié (dispatch pattern)
        
        Args:
            template_type: 'default' ou 'renewal'
            client_id: ID du client (passé depuis la vue avec self.get_client_id())
            user: Utilisateur créateur
        """
        serializer = PipelineTemplateSerializer(data=template_data)
        if not serializer.is_valid():
            raise StandardizedValidationError(
                f"Template validation failed: {serializer.errors}"
            )
        
        template = serializer.save()
        return template
    
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

    
    # # ===== MÉTHODES PRIVÉES (Dispatch) =====
    
    # @classmethod
    # def _create_default_template(cls, custom_name: str = None) -> 'PipelineTemplate':
    #     """
    #     Crée le template par défaut hardcodé
    #     """
    #     try:
    #         from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            
    #         # Nom par défaut ou personnalisé
    #         template_name = custom_name if custom_name else "Default Sales Pipeline"
            
    #         # Données du template
    #         template_data = {
    #             'name': template_name,
    #             'description': "Template par défaut avec les 5 étapes standard",
    #             'is_default': True,
    #             'order': 0,
    #             'is_active': True
    #         }
            
    #         # Utiliser le serializer qui gère automatiquement le ClientScope
    #         serializer = PipelineTemplateSerializer(data=template_data)
    #         if not serializer.is_valid():
    #             raise StandardizedValidationError(
    #                 f"Template validation failed: {serializer.errors}"
    #             )
            
    #         # Créer le template
    #         template = serializer.save()
            
    #         # Créer les étapes par défaut
    #         stages = PipelineStagesConfig.get_default_stages()
    #         cls._create_stages_for_template(template, stages)
            
    #         return template
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
    #         )

    # @classmethod
    # def _create_renewal_template(cls, custom_name: str = None) -> 'PipelineTemplate':
    #     """
    #     Crée le template de renouvellement hardcodé
    #     """
    #     try:
    #         from ..serializers.pipeline_template_serializer import PipelineTemplateSerializer
            
    #         # Nom par défaut ou personnalisé
    #         template_name = custom_name if custom_name else "Renewal Pipeline"
            
    #         # Données du template
    #         template_data = {
    #             'name': template_name,
    #             'description': "Template pour les renouvellements de contrat",
    #             'is_default': False,
    #             'order': 1,
    #             'is_active': True
    #         }
            
    #         # Utiliser le serializer qui gère automatiquement le ClientScope
    #         serializer = PipelineTemplateSerializer(data=template_data)
    #         if not serializer.is_valid():
    #             raise StandardizedValidationError(
    #                 f"Template validation failed: {serializer.errors}"
    #             )
            
    #         # Créer le template
    #         template = serializer.save()
            
    #         # Créer les étapes de renouvellement
    #         stages = PipelineStagesConfig.get_renewal_stages()
    #         cls._create_stages_for_template(template, stages)
            
    #         return template
            
    #     except StandardizedValidationError:
    #         raise
    #     except Exception as e:
    #         raise StandardizedValidationError(
    #             OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
    #         )

    # @classmethod
    # def _create_stages_for_template(cls, template: 'PipelineTemplate', stages_data: list) -> int:
    #     """
    #     Crée les étapes pour un template (réutilisable)
    #     Utilise aussi le ClientScope automatiquement via le serializer
    #     """
    #     from ..serializers.pipeline_stage_serializer import PipelineStageSerializer
        
    #     created_count = 0
        
    #     for stage_name, stage_description, stage_order in stages_data:
    #         stage_data = {
    #             'template': template.id,
    #             'name': stage_name,
    #             'description': stage_description,
    #             'order': stage_order,
    #             'is_active': True
    #         }
            
    #         # Utiliser le serializer pour la cohérence
    #         serializer = PipelineStageSerializer(data=stage_data)
    #         if serializer.is_valid():
    #             serializer.save()
    #             created_count += 1
        
    #     return created_count