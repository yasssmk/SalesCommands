# backend/apps/opportunities/models/pipeline_stage.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig

class PipelineStage(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Étapes principales du pipeline de vente.
    Peut être utilisé dans un template ou dans une instance d'opportunité.
    """
    
    StageStatus = PipelineStagesConfig.StageStatus
    
    # Relations
    template = models.ForeignKey(
        'PipelineTemplate',
        on_delete=models.CASCADE,
        related_name='stages',
        null=True,
        blank=True,
        verbose_name=_('Pipeline Template'),
        help_text=_('Template this stage belongs to (null for opportunity-specific stages)')
    )
    
    opportunity_pipeline = models.ForeignKey(
        'OpportunityPipeline',
        on_delete=models.CASCADE,
        related_name='stages',
        null=True,
        blank=True,
        verbose_name=_('Opportunity Pipeline'),
        help_text=_('Opportunity pipeline this stage belongs to (null for template stages)')
    )
    
    # Relations pour la performance (linked list)
    previous_stage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_stage_rel',
        null=True,
        blank=True,
        verbose_name=_('Previous Stage'),
        help_text=_('Previous stage in the pipeline sequence')
    )
    
    next_stage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='previous_stage_rel',
        null=True,
        blank=True,
        verbose_name=_('Next Stage'),
        help_text=_('Next stage in the pipeline sequence')
    )
    
    # Informations de base
    name = models.CharField(
        max_length=200,
        verbose_name=_('Stage Name'),
        help_text=_('Name of the pipeline stage')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of what happens in this stage')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Order of this stage in the pipeline')
    )
    
    # Statut (uniquement pour les instances d'opportunité)
    status = models.CharField(
        max_length=20,
        choices=StageStatus.choices,
        default=StageStatus.ACTIVE,
        verbose_name=_('Status'),
        help_text=_('Current status of this stage')
    )
    
    # Activation/désactivation
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this stage is active')
    )
    
    # Dates de progression (pour les instances d'opportunité)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Started At'),
        help_text=_('When this stage was started')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
        help_text=_('When this stage was completed')
    )
    
    # Durée estimée (en jours)
    estimated_duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Estimated Duration (days)'),
        help_text=_('Estimated duration in days for this stage')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['template', 'opportunity_pipeline', 'order', 'status']
    )):
        db_table = 'pipeline_stages'
        verbose_name = _('Pipeline Stage')
        verbose_name_plural = _('Pipeline Stages')
        ordering = ['order', 'name']

    def __str__(self):
        if self.template:
            return f"{self.template.name} - {self.name}"
        elif self.opportunity_pipeline:
            return f"Opp {self.opportunity_pipeline.id} - {self.name}"
        return f"{self.name}"

    def clean(self):
        """
        Validation simple : une étape doit appartenir soit à un template, soit à une opportunité
        """
        from django.core.exceptions import ValidationError
        
        if not self.template and not self.opportunity_pipeline:
            raise ValidationError(
                _('A stage must belong to either a template or an opportunity pipeline')
            )
        
        if self.template and self.opportunity_pipeline:
            raise ValidationError(
                _('A stage cannot belong to both a template and an opportunity pipeline')
            )

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec gestion automatique des ordres
        """
        skip_linked_list_update = kwargs.pop('skip_linked_list_update', False)

        self.clean()
        
        if not skip_linked_list_update:
            self._handle_order_conflicts()
        
        super().save(*args, **kwargs)
        
        # Mise à jour des relations previous/next après sauvegarde (seulement si pas de skip)
        if not skip_linked_list_update:
            self._update_linked_list()

    def _handle_order_conflicts(self):
        """
        Gère automatiquement les conflits d'ordre en décalant les stages existants
        """
        if not self.order:
            return
        
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        
        # Trouver les stages qui ont un ordre >= au nouveau stage
        conflicting_stages = PipelineStage.objects.filter(
            order__gte=self.order,
            **filter_kwargs
        ).exclude(pk=self.pk)
        
        if conflicting_stages.exists():
            # Décaler tous les stages conflictuels
            for stage in conflicting_stages:
                stage.order += 1
                stage.save(update_fields=['order'])

    def _update_linked_list(self):
        """
        Met à jour les relations previous/next stage avec protection contre la récursion
        """
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        
        # Récupérer tous les stages du même contexte ordonnés
        all_stages = PipelineStage.objects.filter(**filter_kwargs).order_by('order')
        
        # Mettre à jour les relations - VERSION OPTIMISÉE
        stages_list = list(all_stages)
        
        for i, stage in enumerate(stages_list):
            # Définir previous_stage
            new_previous = stages_list[i - 1] if i > 0 else None
            # Définir next_stage  
            new_next = stages_list[i + 1] if i < len(stages_list) - 1 else None
            
            # Sauvegarder seulement si les relations ont changé
            changes = {}
            if stage.previous_stage != new_previous:
                changes['previous_stage'] = new_previous
            if stage.next_stage != new_next:
                changes['next_stage'] = new_next
            
            # Sauvegarder avec skip_linked_list_update pour éviter la récursion
            if changes:
                for field, value in changes.items():
                    setattr(stage, field, value)
                stage.save(update_fields=list(changes.keys()), skip_linked_list_update=True)

    def get_next_stage(self):
        """
        Récupère le stage suivant (performance optimisée)
        """
        return self.next_stage

    def get_previous_stage(self):
        """
        Récupère le stage précédent (performance optimisée)
        """
        return self.previous_stage

    @property
    def is_template_stage(self):
        """
        Vérifie si c'est une étape de template
        """
        return self.template is not None

    @property
    def is_opportunity_stage(self):
        """
        Vérifie si c'est une étape d'opportunité
        """
        return self.opportunity_pipeline is not None

    def mark_as_started(self):
        """
        Marque l'étape comme commencée
        """
        if self.is_opportunity_stage and not self.started_at:
            from django.utils import timezone
            self.started_at = timezone.now()
            self.status = self.StageStatus.ACTIVE
            self.save(update_fields=['started_at', 'status'])

    def mark_as_completed(self):
        """
        Marque l'étape comme terminée
        """
        if self.is_opportunity_stage:
            from django.utils import timezone
            self.completed_at = timezone.now()
            self.status = self.StageStatus.COMPLETED
            self.save(update_fields=['completed_at', 'status'])

    def mark_as_skipped(self):
        """
        Marque l'étape comme ignorée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.SKIPPED
            self.save(update_fields=['status'])

    def mark_as_blocked(self):
        """
        Marque l'étape comme bloquée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.BLOCKED
            self.save(update_fields=['status'])

    @classmethod
    def create_from_template(cls, template_stage, opportunity_pipeline, user=None):
        """
        Crée une étape d'opportunité à partir d'une étape de template
        """
        new_stage = cls.objects.create(
            opportunity_pipeline=opportunity_pipeline,
            name=template_stage.name,
            description=template_stage.description,
            order=template_stage.order,
            is_active=template_stage.is_active,
            estimated_duration=template_stage.estimated_duration,
            status=cls.StageStatus.ACTIVE,
            client_id=opportunity_pipeline.client_id,
            user=user
        )
        
        # Les relations previous/next seront automatiquement gérées par _update_linked_list()
        return new_stage

    @classmethod
    def reorder_stages(cls, stages_with_new_orders, context_filter):
        """
        Réordonne plusieurs stages en une seule opération
        stages_with_new_orders: [(stage_id, new_order), ...]
        context_filter: dict pour filtrer par template ou opportunity_pipeline
        """
        for stage_id, new_order in stages_with_new_orders:
            stage = cls.objects.get(id=stage_id, **context_filter)
            stage.order = new_order
            stage.save()

    def insert_at_position(self, new_order):
        """
        Insère ce stage à une nouvelle position en décalant les autres
        """
        old_order = self.order
        self.order = new_order
        self.save()  # La méthode save() gère automatiquement les conflits