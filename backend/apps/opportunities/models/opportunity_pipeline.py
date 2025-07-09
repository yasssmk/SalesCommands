# backend/apps/opportunities/models/opportunity_pipeline.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig


class OpportunityPipeline(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Instance de pipeline liée à une opportunité spécifique.
    Représente l'état actuel du processus de vente pour cette opportunité.
    """
    
    PipelineStatus = PipelineStagesConfig.PipelineStatus
    
    # Relations principales
    opportunity = models.OneToOneField(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='pipeline',
        verbose_name=_('Opportunity'),
        help_text=_('Opportunity this pipeline belongs to')
    )
    
    template = models.ForeignKey(
        'PipelineTemplate',
        on_delete=models.PROTECT,
        related_name='opportunity_pipelines',
        verbose_name=_('Pipeline Template'),
        help_text=_('Template used to create this pipeline')
    )
    
    # Étape courante
    current_stage = models.ForeignKey(
        'PipelineStage',
        on_delete=models.SET_NULL,
        related_name='current_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Current Stage'),
        help_text=_('Current stage of this pipeline')
    )
    
    # Statut du pipeline
    status = models.CharField(
        max_length=20,
        choices=PipelineStatus.choices,
        default=PipelineStatus.ACTIVE,
        verbose_name=_('Pipeline Status'),
        help_text=_('Current status of this pipeline')
    )
    
    # Dates importantes
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Started At'),
        help_text=_('When this pipeline was started')
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Updated'),
        help_text=_('When this pipeline was last updated')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
        help_text=_('When this pipeline was completed')
    )
    
    # Métriques de progression
    total_stages = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Total Stages'),
        help_text=_('Total number of stages in this pipeline')
    )
    
    completed_stages = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Completed Stages'),
        help_text=_('Number of completed stages')
    )
    
    # Durée estimée totale (en jours)
    estimated_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Estimated Duration (days)'),
        help_text=_('Total estimated duration for this pipeline')
    )
    
    # Notes et commentaires
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this pipeline')
    )
    
    # Métadonnées
    is_customized = models.BooleanField(
        default=False,
        verbose_name=_('Is Customized'),
        help_text=_('Whether this pipeline has been customized from the original template')
    )
    
    customization_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Customization Notes'),
        help_text=_('Notes about customizations made to this pipeline')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['opportunity', 'template', 'current_stage', 'status']
    )):
        db_table = 'opportunity_pipelines'
        verbose_name = _('Opportunity Pipeline')
        verbose_name_plural = _('Opportunity Pipelines')
        ordering = ['-started_at']

    def __str__(self):
        return f"Pipeline - {self.opportunity.title}"

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec mise à jour automatique des métriques
        """
        # Calculer les métriques avant sauvegarde
        self._update_metrics()
        
        super().save(*args, **kwargs)

    def _update_metrics(self):
        """
        Met à jour les métriques de progression
        """
        # Compter le nombre total d'étapes
        self.total_stages = self.stages.count()
        
        # Compter les étapes terminées
        self.completed_stages = self.stages.filter(
            status=PipelineStagesConfig.StageStatus.COMPLETED
        ).count()

    @property
    def progress_percentage(self):
        """
        Calcule le pourcentage de progression
        """
        if self.total_stages == 0:
            return 0
        return round((self.completed_stages / self.total_stages) * 100, 1)

    @property
    def is_completed(self):
        """
        Vérifie si le pipeline est terminé
        """
        return self.status == self.PipelineStatus.COMPLETED

    @property
    def is_active(self):
        """
        Vérifie si le pipeline est actif
        """
        return self.status == self.PipelineStatus.ACTIVE

    @property
    def days_since_started(self):
        """
        Calcule le nombre de jours depuis le début
        """
        if not self.started_at:
            return 0
        return (timezone.now() - self.started_at).days

    def get_next_stage(self):
        """
        Récupère l'étape suivante
        """
        if not self.current_stage:
            return self.stages.filter(is_active=True).order_by('order').first()
        
        return self.current_stage.get_next_stage()

    def get_previous_stage(self):
        """
        Récupère l'étape précédente
        """
        if not self.current_stage:
            return None
        
        return self.current_stage.get_previous_stage()

    def move_to_next_stage(self):
        """
        Passe à l'étape suivante
        """
        if not self.current_stage:
            # Premier démarrage, aller à la première étape
            first_stage = self.stages.filter(is_active=True).order_by('order').first()
            if first_stage:
                self.current_stage = first_stage
                first_stage.mark_as_started()
                self.save(update_fields=['current_stage'])
                return first_stage
        else:
            # Marquer l'étape courante comme terminée
            self.current_stage.mark_as_completed()
            
            # Passer à l'étape suivante
            next_stage = self.get_next_stage()
            if next_stage:
                self.current_stage = next_stage
                next_stage.mark_as_started()
                self.save(update_fields=['current_stage'])
                return next_stage
            else:
                # Pas d'étape suivante, pipeline terminé
                self.mark_as_completed()
                return None

    def move_to_previous_stage(self):
        """
        Revient à l'étape précédente
        """
        if not self.current_stage:
            return None
        
        # Remettre l'étape courante à l'état actif
        self.current_stage.status = PipelineStagesConfig.StageStatus.ACTIVE
        self.current_stage.completed_at = None
        self.current_stage.save(update_fields=['status', 'completed_at'])
        
        # Revenir à l'étape précédente
        previous_stage = self.get_previous_stage()
        if previous_stage:
            self.current_stage = previous_stage
            previous_stage.status = PipelineStagesConfig.StageStatus.ACTIVE
            previous_stage.completed_at = None
            previous_stage.save(update_fields=['status', 'completed_at'])
            self.save(update_fields=['current_stage'])
            return previous_stage
        
        return None

    def mark_as_completed(self):
        """
        Marque le pipeline comme terminé
        """
        self.status = self.PipelineStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def mark_as_paused(self):
        """
        Met en pause le pipeline
        """
        self.status = self.PipelineStatus.PAUSED
        self.save(update_fields=['status'])

    def mark_as_cancelled(self):
        """
        Annule le pipeline
        """
        self.status = self.PipelineStatus.CANCELLED
        self.save(update_fields=['status'])

    def mark_as_failed(self):
        """
        Marque le pipeline comme échoué
        """
        self.status = self.PipelineStatus.FAILED
        self.save(update_fields=['status'])

    def resume(self):
        """
        Reprend un pipeline en pause
        """
        if self.status == self.PipelineStatus.PAUSED:
            self.status = self.PipelineStatus.ACTIVE
            self.save(update_fields=['status'])

    def mark_as_customized(self, notes=None):
        """
        Marque le pipeline comme personnalisé
        """
        self.is_customized = True
        if notes:
            self.customization_notes = notes
        self.save(update_fields=['is_customized', 'customization_notes'])

    @classmethod
    def create_from_template(cls, opportunity, template, user=None):
        """
        Crée un pipeline d'opportunité à partir d'un template
        """
        # Créer le pipeline
        pipeline = cls.objects.create(
            opportunity=opportunity,
            template=template,
            status=cls.PipelineStatus.ACTIVE,
            client_id=opportunity.client_id,
            user=user
        )
        
        # Créer les étapes à partir du template
        from .pipeline_stage import PipelineStage
        template_stages = template.stages.filter(is_active=True).order_by('order')
        
        for template_stage in template_stages:
            PipelineStage.create_from_template(
                template_stage=template_stage,
                opportunity_pipeline=pipeline,
                user=user
            )
        
        # Mettre à jour les métriques
        pipeline._update_metrics()
        pipeline.save()
        
        return pipeline

    def get_all_stages(self):
        """
        Récupère toutes les étapes du pipeline ordonnées
        """
        return self.stages.filter(is_active=True).order_by('order')

    def get_current_substages(self):
        """
        Récupère les sous-étapes de l'étape courante
        """
        if not self.current_stage:
            return []
        
        return self.current_stage.substages.filter(is_active=True).order_by('order')