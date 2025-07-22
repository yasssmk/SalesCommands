# backend/apps/opportunities/models/substage_activity.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp


class SubStageActivity(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Liaison simple entre PipelineSubStage et Activity.
    Une activité peut être liée à une seule sous-étape par client.
    """
    
    # Relations principales
    substage = models.ForeignKey(
        'PipelineSubStage',
        on_delete=models.CASCADE,
        related_name='activity_links',
        verbose_name=_('Pipeline SubStage'),
        help_text=_('SubStage this activity is linked to')
    )
    
    activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.CASCADE,
        related_name='substage_links',
        verbose_name=_('Activity'),
        help_text=_('Activity linked to this substage')
    )

    class Meta:
        verbose_name = _('SubStage Activity Link')
        verbose_name_plural = _('SubStage Activity Links')
        db_table = 'substage_activities'
        ordering = ['substage', 'created_at']
        
        # Index pour optimiser les requêtes
        indexes = [
            models.Index(fields=['substage', 'activity', 'client_id']),
            models.Index(fields=['substage', 'created_at']),
            models.Index(fields=['activity']),
        ]
        
        # Contrainte d'unicité : une activité ne peut être liée qu'à un substage par client
        constraints = [
            models.UniqueConstraint(
                fields=('substage', 'activity', 'client_id'),
                name='unique_substage_activity_per_client'
            )
        ]

    def __str__(self):
        return f"{self.substage.name} → {self.activity.title}"

    def clean(self):
        """
        Validation : l'activité et le substage doivent appartenir à la même opportunity
        """
        from django.core.exceptions import ValidationError
        
        if self.substage and self.activity:
            # Récupérer l'opportunity du substage
            substage_opportunity = self.substage.stage.template.opportunity
            
            # Vérifier que l'activité appartient à la même opportunity
            if self.activity.opportunity != substage_opportunity:
                raise ValidationError(
                    _("L'activité doit appartenir à la même opportunité que le substage")
                )
    
    def _get_substage_opportunity(self):
        """Helper pour récupérer l'opportunity d'un substage - COHÉRENT avec Activity"""
        if not self.substage or not self.substage.stage:
            return None
            
        stage = self.substage.stage
        
        # Cas 1: Stage d'instance (opportunity_pipeline)
        if hasattr(stage, 'opportunity_pipeline') and stage.opportunity_pipeline:
            return stage.opportunity_pipeline.opportunity
        
        # Cas 2: Stage de template
        elif hasattr(stage, 'template') and stage.template and hasattr(stage.template, 'opportunity'):
            return stage.template.opportunity
        
        return None

    def save(self, *args, **kwargs):
        """Override save pour appeler clean() automatiquement"""
        self.clean()
        super().save(*args, **kwargs)

    @property
    def opportunity(self):
        """Retourne l'opportunity associée via le substage"""
        return self.substage.stage.template.opportunity

    @property
    def timeline_position(self):
        """
        Retourne la position temporelle de l'activité par rapport au substage
        Utile pour affichage timeline
        """
        if not self.activity.scheduled_start:
            return 'no_date'
        
        substage_start = self.substage.start_date
        substage_end = self.substage.end_date
        
        if not substage_start and not substage_end:
            return 'no_substage_dates'
        
        activity_start = self.activity.scheduled_start
        
        if substage_start and activity_start < substage_start:
            return 'before_substage'
        elif substage_end and activity_start > substage_end:
            return 'after_substage'
        else:
            return 'within_substage'