# backend/apps/opportunities/services/pipeline_template_service.py

from django.db import transaction
from rest_framework.response import Response
from apps.opportunities.models import PipelineTemplate, PipelineStage
from apps.opportunities.config import PipelineStagesConfig
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages


class PipelineTemplateService:
    """
    Service simple pour la gestion des templates de pipeline (MVP).
    Scalable avec dispatch pattern.
    """
    
    @classmethod
    def create_template(cls, template_type: str, client_id: str, user=None) -> Response:
        """
        Crée un template selon le type spécifié (dispatch pattern)
        
        Args:
            template_type: 'default' ou 'renewal'
            client_id: ID du client (passé depuis la vue avec self.get_client_id())
            user: Utilisateur créateur
        """
        # Dispatch vers la bonne méthode selon le type
        if template_type == 'default':
            return cls._create_default_template(client_id, user)
        elif template_type == 'renewal':
            return cls._create_renewal_template(client_id, user)
        else:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_TYPE_NOT_SUPPORTED.format(
                    template_type=template_type,
                    available_types="'default', 'renewal'"
                )
            )
    
    @classmethod
    def get_template_with_stages(cls, template_id: int, client_id: str) -> Response:
        """
        Récupère un template avec ses étapes
        """
        try:
            template = PipelineTemplate.objects.get(
                id=template_id,
                client_id=client_id
            )
            
            stages = template.stages.filter(is_active=True).order_by('order')
            
            return Response({
                'success': True,
                'data': {
                    'template': {
                        'id': template.id,
                        'name': template.name,
                        'description': template.description,
                        'is_default': template.is_default
                    },
                    'stages': [
                        {
                            'id': stage.id,
                            'name': stage.name,
                            'description': stage.description,
                            'order': stage.order
                        }
                        for stage in stages
                    ]
                }
            })
            
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
    
    @classmethod
    def duplicate_template(cls, template_id: int, new_name: str, client_id: str, user=None) -> Response:
        """
        Duplique un template existant
        """
        try:
            with transaction.atomic():
                # Récupérer le template source
                source_template = PipelineTemplate.objects.get(
                    id=template_id,
                    client_id=client_id
                )
                
                # Créer le nouveau template
                new_template = PipelineTemplate.objects.create(
                    name=new_name,
                    description=f"Copy of {source_template.name}",
                    is_default=False,
                    client_id=client_id,
                    user=user
                )
                
                # Dupliquer les étapes
                source_stages = source_template.stages.filter(is_active=True).order_by('order')
                duplicated_count = 0
                
                for source_stage in source_stages:
                    PipelineStage.objects.create(
                        template=new_template,
                        name=source_stage.name,
                        description=source_stage.description,
                        order=source_stage.order,
                        is_active=True,
                        client_id=client_id,
                        user=user
                    )
                    duplicated_count += 1
                
                return Response({
                    'success': True,
                    'message': f'Template duplicated successfully as "{new_name}"',
                    'data': {
                        'template_id': new_template.id,
                        'template_name': new_template.name,
                        'stages_count': duplicated_count
                    }
                })
                
        except PipelineTemplate.DoesNotExist:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_NOT_FOUND
            )
    
    # ===== MÉTHODES PRIVÉES (Dispatch) =====
    
    @classmethod
    def _create_default_template(cls, client_id: str, user=None) -> Response:
        """
        Crée le template par défaut hardcodé
        """
        try:
            with transaction.atomic():
                template = PipelineTemplate.objects.create(
                    name="Default Sales Pipeline",
                    description="Template par défaut avec les 5 étapes standard",
                    is_default=True,
                    client_id=client_id,
                    user=user
                )
                
                stages = PipelineStagesConfig.get_default_stages()
                created_count = cls._create_stages_for_template(template, stages, client_id, user)
                
                return Response({
                    'success': True,
                    'message': 'Default template created successfully',
                    'data': {
                        'template_id': template.id,
                        'template_name': template.name,
                        'template_type': 'default',
                        'stages_count': created_count
                    }
                })
                
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def _create_renewal_template(cls, client_id: str, user=None) -> Response:
        """
        Crée le template de renouvellement hardcodé
        """
        try:
            with transaction.atomic():
                template = PipelineTemplate.objects.create(
                    name="Renewal Pipeline",
                    description="Template pour les renouvellements de contrat",
                    is_default=False,
                    client_id=client_id,
                    user=user
                )
                
                stages = PipelineStagesConfig.get_renewal_stages()
                created_count = cls._create_stages_for_template(template, stages, client_id, user)
                
                return Response({
                    'success': True,
                    'message': 'Renewal template created successfully',
                    'data': {
                        'template_id': template.id,
                        'template_name': template.name,
                        'template_type': 'renewal',
                        'stages_count': created_count
                    }
                })
                
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def _create_stages_for_template(cls, template: PipelineTemplate, stages_data: list, 
                                  client_id: str, user=None) -> int:
        """
        Crée les étapes pour un template (réutilisable)
        """
        created_count = 0
        
        for stage_name, stage_description, stage_order in stages_data:
            PipelineStage.objects.create(
                template=template,
                name=stage_name,
                description=stage_description,
                order=stage_order,
                is_active=True,
                client_id=client_id,
                user=user
            )
            created_count += 1
        
        return created_count