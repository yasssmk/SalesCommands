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
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='pipeline_templates',
        verbose_name=_('Opportunity'),
        help_text=_('Opportunity this pipeline template belongs to')
    )

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

    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Is Default'),
        help_text=_('Whether this is the default template for new opportunities')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['opportunity', 'name'],
        index_fields=[ 'is_default', 'template_type', 'opportunity']
    )):
        db_table = 'pipeline_templates'
        verbose_name = _('Pipeline Template')
        verbose_name_plural = _('Pipeline Templates')
        ordering = ['opportunity', 'name', 'template_type']

    def __str__(self):
        return f"{self.opportunity.title} - {self.name}"

    def save(self, *args, **kwargs):
        """
        Sauvegarde standard - plusieurs templates par défaut autorisés
        """
        if self.opportunity and not self.client_id:
                    self.client_id = self.opportunity.client_id
                
        super().save(*args, **kwargs)
        
    @classmethod
    def get_default_template(cls, opportunity, context=None):
        """
        Retourne un template par défaut pour un client donné
        Le contexte peut être utilisé pour différencier les départements/branches
        """
        query = cls.objects.filter(
            opportunity=opportunity,
            is_default=True, 
        )
        
        if context:
            # Possibilité d'ajouter un filtrage par contexte (département, branche, etc.)
            pass
        
        return query.first()

    def mark_as_custom_if_modified(self):
        """
        Marque le template comme CUSTOM si il était DEFAULT ou RENEWAL et qu'il est modifié
        
        Args:
            modification_type: Type de modification pour le logging
        """
        if self.template_type in [PipelineStagesConfig.TemplateType.DEFAULT, PipelineStagesConfig.TemplateType.RENEWAL]:
            # Sauvegarder l'ancien type pour le logging
            old_type = self.template_type
            
            # Marquer comme CUSTOM
            self.template_type = PipelineStagesConfig.TemplateType.CUSTOM
            
            # Modifier le nom pour refléter le changement si nécessaire
            if not self.name.endswith("(Custom)"):
                self.name = f"{self.name} (Custom)"
            
            # Sauvegarder les changements
            self.save(update_fields=['template_type', 'name'])
            
    
    def should_convert_to_custom(self):
        """
        Vérifie si le template devrait être converti en CUSTOM
        
        Returns:
            bool: True si le template devrait être converti
        """
        return self.template_type in [
            PipelineStagesConfig.TemplateType.DEFAULT, 
            PipelineStagesConfig.TemplateType.RENEWAL
        ]
    
    @classmethod
    def create_default_for_opportunity(cls, opportunity, user=None):
        """
        Crée un template par défaut pour une opportunité donnée
        """
        template = cls.objects.create(
            opportunity=opportunity,
            name=f"Pipeline Process - {opportunity.title}",
            description="Default pipeline process for this opportunity",
            template_type=PipelineStagesConfig.TemplateType.DEFAULT,
            is_default=True,
            client_id=opportunity.client_id,
            created_by=user,
            updated_by=user
        )
        
        return template