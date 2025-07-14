# backend/apps/opportunities/models/pipeline_template.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig


class PipelineTemplate(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Template de pipeline de vente avec les étapes par défaut.
    Sert de base pour créer des pipelines personnalisés par opportunité.
    """
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Template Name'),
        help_text=_('Name of the pipeline template')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of the pipeline template')
    )
    
    template_type = models.CharField(
        max_length=20,
        choices=PipelineStagesConfig.TemplateType.choices,
        default=PipelineStagesConfig.TemplateType.DEFAULT,
        verbose_name=_('Template Type'),
        help_text=_('Type of template that determines the default stages')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this template is available for use')
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Is Default'),
        help_text=_('Whether this is the default template for new opportunities')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=['is_active', 'is_default', 'template_type']
    )):
        db_table = 'pipeline_templates'
        verbose_name = _('Pipeline Template')
        verbose_name_plural = _('Pipeline Templates')
        ordering = ['name', 'template_type']

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        """
        Sauvegarde standard - plusieurs templates par défaut autorisés
        """
  
        super().save(*args, **kwargs)

    @classmethod
    def get_default_template(cls, client_id, context=None):
        """
        Retourne un template par défaut pour un client donné
        Le contexte peut être utilisé pour différencier les départements/branches
        """
        query = cls.objects.filter(client_id=client_id, is_default=True, is_active=True)
        
        if context:
            # Possibilité d'ajouter un filtrage par contexte (département, branche, etc.)
            # Pour le moment, on retourne le premier trouvé
            pass
        
        return query.first()

    def create_stages_from_type(self):
        """
        Crée les étapes par défaut selon le template_type
        Appelé après la création du template
        """
        from .pipeline_stage import PipelineStage
        
        # Récupérer les étapes selon le type
        if self.template_type == PipelineStagesConfig.TemplateType.DEFAULT:
            stages = PipelineStagesConfig.get_default_stages()
        elif self.template_type == PipelineStagesConfig.TemplateType.RENEWAL:
            stages = PipelineStagesConfig.get_renewal_stages()
        else:
            # Pour CUSTOM, ne pas créer d'étapes automatiquement
            return 0
        
        created_count = 0
        for stage_name, stage_description, stage_order in stages:
            PipelineStage.objects.create(
                template=self,
                name=stage_name,
                description=stage_description,
                order=stage_order,
                is_active=True,
                client_id=self.client_id,
                user=self.user
            )
            created_count += 1
        
        return created_count