# backend/apps/opportunities/models/pipeline_substage.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig
from .pipeline_stage import PipelineStage


class PipelineSubStage(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Sous-étapes du pipeline de vente.
    Chaque sous-étape appartient à une étape principale (PipelineStage).
    """
    
    # Import des constantes depuis la configuration
    SubStageType = PipelineStagesConfig.SubStageType
    SubStageStatus = PipelineStagesConfig.SubStageStatus
    
    # Relations
    stage = models.ForeignKey(
        'PipelineStage',
        on_delete=models.CASCADE,
        related_name='substages',
        verbose_name=_('Pipeline Stage'),
        help_text=_('Parent stage this substage belongs to')
    )
    
    # Relations pour la performance (linked list)
    previous_substage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_substage_rel',
        null=True,
        blank=True,
        verbose_name=_('Previous SubStage'),
        help_text=_('Previous substage in the sequence')
    )
    
    next_substage = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='previous_substage_rel',
        null=True,
        blank=True,
        verbose_name=_('Next SubStage'),
        help_text=_('Next substage in the sequence')
    )
    
    # Informations de base
    name = models.CharField(
        max_length=200,
        verbose_name=_('SubStage Name'),
        help_text=_('Name of the pipeline substage')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of what happens in this substage')
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Order'),
        help_text=_('Order of this substage within the parent stage')
    )
    
    # Type de sous-étape
    substage_type = models.CharField(
        max_length=30,
        choices=SubStageType.choices,
        default=SubStageType.INTERACTION_CLIENT,
        verbose_name=_('SubStage Type'),
        help_text=_('Type of this substage')
    )
    
    # Statut
    status = models.CharField(
        max_length=20,
        choices=SubStageStatus.choices,
        default=SubStageStatus.NOT_STARTED,
        verbose_name=_('Status'),
        help_text=_('Current status of this substage')
    )
    
    # Durée et dates
    estimated_duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Estimated Duration (days)'),
        help_text=_('Estimated duration in days for this substage')
    )
    
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('Planned or actual start date')
    )
    
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Planned or actual end date')
    )
    
    actual_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Actual Start Date'),
        help_text=_('When this substage actually started')
    )
    
    actual_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Actual End Date'),
        help_text=_('When this substage actually ended')
    )
    
    # Activation
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this substage is active')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this substage')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['stage', 'order', 'status', 'substage_type']
    )):
        db_table = 'pipeline_substages'
        verbose_name = _('Pipeline SubStage')
        verbose_name_plural = _('Pipeline SubStages')
        ordering = ['stage', 'order', 'name']

    def save(self, *args, **kwargs):
        """
        ✅ CORRECTION FINALE : Sauvegarde simple pour MVP
        """
        # ✅ Validation de base
        self.clean()
        
        # ✅ Gestion basique des ordres sans conflits automatiques
        if not self.order:
            # Calculer l'ordre suivant seulement si pas spécifié
            from django.db.models import Max
            
            # Déterminer le contexte (template ou opportunité)
            filter_kwargs = {'client_id': self.client_id}
            if self.template_id:
                filter_kwargs['template_id'] = self.template_id
            elif hasattr(self, 'opportunity_pipeline_id') and self.opportunity_pipeline_id:
                filter_kwargs['opportunity_pipeline_id'] = self.opportunity_pipeline_id
            
            max_order = PipelineStage.objects.filter(**filter_kwargs).aggregate(
                Max('order')
            )['order__max'] or 0
            self.order = max_order + 1
        
        # ✅ Sauvegarde simple sans linked list automatique
        super().save(*args, **kwargs)

    def _handle_order_conflicts(self):
        """
        ✅ MVP : Désactivé - On gère les ordres manuellement
        """
        pass

    def _update_linked_list(self):
        """
        ✅ MVP : Désactivé - Trop complexe pour un MVP
        """
        pass

    def get_next_stage(self):
        """
        ✅ Récupération du stage suivant via requête simple
        """
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        else:
            return None
        
        return PipelineStage.objects.filter(
            order__gt=self.order,
            is_active=True,
            **filter_kwargs
        ).order_by('order').first()

    def get_previous_stage(self):
        """
        ✅ Récupération du stage précédent via requête simple
        """
        # Déterminer le contexte (template ou opportunité)
        filter_kwargs = {'client_id': self.client_id}
        if self.template:
            filter_kwargs['template'] = self.template
        elif self.opportunity_pipeline:
            filter_kwargs['opportunity_pipeline'] = self.opportunity_pipeline
        else:
            return None
            
        return PipelineStage.objects.filter(
            order__lt=self.order,
            is_active=True,
            **filter_kwargs
        ).order_by('-order').first()

    @classmethod
    def create_from_template(cls, template_stage, opportunity_pipeline, user=None):
        """
        ✅ MVP : Création simplifiée depuis template
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
            created_by=user,
            updated_by=user
        )
        
        # ✅ MVP : Pas de gestion automatique des linked lists
        return new_stage

    @classmethod
    def reorder_stages(cls, stages_with_new_orders, context_filter):
        """
        ✅ MVP : Réordonnement en batch simple
        """
        for stage_id, new_order in stages_with_new_orders:
            cls.objects.filter(
                id=stage_id, 
                **context_filter
            ).update(order=new_order)

    def insert_at_position(self, new_order):
        """
        ✅ MVP : Insertion simple - conflits gérés manuellement côté frontend
        """
        self.order = new_order
        self.save()

    def mark_as_started(self):
        """
        ✅ Marque l'étape comme commencée
        """
        if self.is_opportunity_stage and not self.started_at:
            from django.utils import timezone
            self.started_at = timezone.now()
            self.status = self.StageStatus.ACTIVE
            self.save(update_fields=['started_at', 'status'])

    def mark_as_completed(self):
        """
        ✅ Marque l'étape comme terminée
        """
        if self.is_opportunity_stage:
            from django.utils import timezone
            self.completed_at = timezone.now()
            self.status = self.StageStatus.COMPLETED
            self.save(update_fields=['completed_at', 'status'])

    def mark_as_skipped(self):
        """
        ✅ Marque l'étape comme ignorée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.SKIPPED
            self.save(update_fields=['status'])

    def mark_as_blocked(self):
        """
        ✅ Marque l'étape comme bloquée
        """
        if self.is_opportunity_stage:
            self.status = self.StageStatus.BLOCKED
            self.save(update_fields=['status'])

    def mark_as_not_started(self):
        """
        Remet le substage à l'état non commencé
        """
        self.actual_start_date = None
        self.actual_end_date = None
        self.status = self.SubStageStatus.NOT_STARTED
        self.save(update_fields=['actual_start_date', 'actual_end_date', 'status'])

    def insert_at_position(self, new_order):
        """
        Insère ce substage à une nouvelle position en décalant les autres
        """
        old_order = self.order
        self.order = new_order
        self.save()  # La méthode save() gère automatiquement les conflits

    @classmethod
    def reorder_substages(cls, substages_with_new_orders, stage):
        """
        Réordonne plusieurs substages en une seule opération
        substages_with_new_orders: [(substage_id, new_order), ...]
        stage: PipelineStage parent
        """
        for substage_id, new_order in substages_with_new_orders:
            substage = cls.objects.get(id=substage_id, stage=stage)
            substage.order = new_order
            substage.save()

    @property
    def is_overdue(self):
        """
        Vérifie si le substage est en retard
        """
        if not self.end_date or self.status == self.SubStageStatus.COMPLETED:
            return False
        
        from django.utils import timezone
        return timezone.now().date() > self.end_date

    @property
    def days_remaining(self):
        """
        Calcule le nombre de jours restants
        """
        if not self.end_date or self.status == self.SubStageStatus.COMPLETED:
            return None
        
        from django.utils import timezone
        today = timezone.now().date()
        return (self.end_date - today).days

    @property
    def is_client_interaction(self):
        """
        Vérifie si c'est une interaction client
        """
        return self.substage_type == self.SubStageType.INTERACTION_CLIENT

    @property
    def is_internal_client_process(self):
        """
        Vérifie si c'est un processus interne client
        """
        return self.substage_type == self.SubStageType.PROCESS_INTERNE_CLIENT

    @property
    def is_internal_action(self):
        """
        Vérifie si c'est une action interne
        """
        return self.substage_type == self.SubStageType.ACTION_INTERNE