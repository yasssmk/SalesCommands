# backend/apps/opportunities/models/pipeline_template.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp


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
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Display order for this template')
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
        index_fields=['order', 'is_active', 'is_default']
    )):
        db_table = 'pipeline_templates'
        verbose_name = _('Pipeline Template')
        verbose_name_plural = _('Pipeline Templates')
        ordering = ['order', 'name']

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

    @classmethod
    def create_default_template(cls, client_id, user=None, template_type='default'):
        """
        Crée un template par défaut en utilisant la configuration centralisée
        """
        from ..config.pipeline_stages import PipelineStagesConfig
        
        if template_type == 'renewal':
            stages = PipelineStagesConfig.get_renewal_stages()
            name = "Renewal Pipeline"
            description = "Template pour les renouvellements de contrat"
        else:
            stages = PipelineStagesConfig.get_default_stages()
            name = "Default Sales Pipeline"
            description = "Template par défaut avec les 5 étapes standard du processus de vente"
        
        template = cls.objects.create(
            name=name,
            description=description,
            order=0,
            is_active=True,
            is_default=True,
            client_id=client_id,
            user=user
        )
        
        # Créer les étapes du template
        from .pipeline_stage import PipelineStage
        for stage_name, stage_description, stage_order in stages:
            PipelineStage.objects.create(
                template=template,
                name=stage_name,
                description=stage_description,
                order=stage_order,
                is_active=True,
                client_id=client_id,
                user=user
            )
        
        return template