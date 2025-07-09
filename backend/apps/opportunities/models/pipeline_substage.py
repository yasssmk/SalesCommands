# backend/apps/opportunities/models/pipeline_substage.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig


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

    def __str__(self):
        return f"{self.stage} - {self.name}"

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec gestion automatique des ordres
        """
        # Gestion automatique des ordres avant sauvegarde
        self._handle_order_conflicts()
        
        super().save(*args, **kwargs)
        
        # Mise à jour des relations previous/next après sauvegarde
        self._update_linked_list()

    def _handle_order_conflicts(self):
        """
        Gère automatiquement les conflits d'ordre en décalant les substages existants
        """
        if not self.order:
            return
        
        # Trouver les substages qui ont un ordre >= au nouveau substage dans le même stage
        conflicting_substages = PipelineSubStage.objects.filter(
            stage=self.stage,
            order__gte=self.order,
            client_id=self.client_id
        ).exclude(pk=self.pk)
        
        if conflicting_substages.exists():
            # Décaler tous les substages conflictuels
            for substage in conflicting_substages:
                substage.order += 1
                substage.save(update_fields=['order'])

    def _update_linked_list(self):
        """
        Met à jour les relations previous/next substage
        """
        # Récupérer tous les substages du même stage ordonnés
        all_substages = PipelineSubStage.objects.filter(
            stage=self.stage,
            client_id=self.client_id
        ).order_by('order')
        
        # Mettre à jour les relations
        previous_substage = None
        for substage in all_substages:
            substage.previous_substage = previous_substage
            if previous_substage:
                previous_substage.next_substage = substage
                previous_substage.save(update_fields=['next_substage'])
            previous_substage = substage
        
        # Sauvegarder le dernier substage
        if previous_substage:
            previous_substage.next_substage = None
            previous_substage.save(update_fields=['next_substage'])

    def get_next_substage(self):
        """
        Récupère le substage suivant (performance optimisée)
        """
        return self.next_substage

    def get_previous_substage(self):
        """
        Récupère le substage précédent (performance optimisée)
        """
        return self.previous_substage

    def mark_as_started(self):
        """
        Marque le substage comme commencé
        """
        if not self.actual_start_date:
            self.actual_start_date = timezone.now()
            self.status = self.SubStageStatus.IN_PROGRESS
            self.save(update_fields=['actual_start_date', 'status'])

    def mark_as_completed(self):
        """
        Marque le substage comme terminé
        """
        self.actual_end_date = timezone.now()
        self.status = self.SubStageStatus.COMPLETED
        self.save(update_fields=['actual_end_date', 'status'])

    def mark_as_blocked(self):
        """
        Marque le substage comme bloqué
        """
        self.status = self.SubStageStatus.BLOCKED
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