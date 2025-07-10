# backend/apps/opportunities/models/substage_activity.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from ..config.pipeline_stages import PipelineStagesConfig


class SubStageActivity(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Liaison many-to-many entre PipelineSubStage et Activity.
    Permet de lier des activités aux sous-étapes du pipeline.
    """
    
    activityLinkType = PipelineStagesConfig.ActivityLinkType
    
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
    
    # Type de liaison
    link_type = models.CharField(
        max_length=20,
        choices=activityLinkType.choices,
        default=activityLinkType.FUTURE_ACTIVITY,
        verbose_name=_('Link Type'),
        help_text=_('Type of link between substage and activity')
    )
    
    # Ordre de priorité dans la sous-étape
    priority_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Priority Order'),
        help_text=_('Priority order of this activity within the substage')
    )
    
    # Statut de la liaison
    is_required = models.BooleanField(
        default=False,
        verbose_name=_('Is Required'),
        help_text=_('Whether this activity is required to complete the substage')
    )
    
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Is Completed'),
        help_text=_('Whether this activity has been completed')
    )
    
    # Informations sur l'automatisation
    auto_created = models.BooleanField(
        default=False,
        verbose_name=_('Auto Created'),
        help_text=_('Whether this link was created automatically')
    )
    
    # Dates importantes
    linked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Linked At'),
        help_text=_('When this activity was linked to the substage')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At'),
        help_text=_('When this activity was completed')
    )
    
    # Notes sur la liaison
    link_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Link Notes'),
        help_text=_('Notes about why this activity is linked to this substage')
    )
    
    # Résultat de l'activité par rapport à la sous-étape
    substage_outcome = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('SubStage Outcome'),
        help_text=_('How the activity outcome affects the substage')
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['substage', 'activity', 'link_type']
    )):
        db_table = 'substage_activities'
        verbose_name = _('SubStage Activity Link')
        verbose_name_plural = _('SubStage Activity Links')
        ordering = ['substage', 'priority_order', 'linked_at']
        
        # Contrainte d'unicité : une activité ne peut être liée qu'une fois à une sous-étape
        constraints = [
            models.UniqueConstraint(
                fields=['substage', 'activity', 'client_id'],
                name='unique_substage_activity_per_client'
            )
        ]

    def __str__(self):
        return f"{self.substage} - {self.activity.title} ({self.get_link_type_display()})"

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec logique métier simplifiée
        """
        # Synchroniser le statut avec l'activité
        if self.activity and self.activity.status == 'COMPLETED':
            self.is_completed = True
            if not self.completed_at:
                self.completed_at = self.activity.completed_at
        
        super().save(*args, **kwargs)
        
        # Mettre à jour le statut de la sous-étape si nécessaire
        self._update_substage_status()

    def mark_as_completed(self):
        """
        Marque la liaison comme terminée
        """
        from django.utils import timezone
        
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=['is_completed', 'completed_at'])

    def _update_substage_status(self):
        """
        Met à jour le statut de la sous-étape en fonction des activités liées
        Version simplifiée pour MVP
        """
        # Récupérer toutes les activités requises de la sous-étape
        required_activities = self.substage.activity_links.filter(is_required=True)
        
        # Si cette activité est requise et vient d'être terminée
        if self.is_required and self.is_completed:
            # Vérifier si toutes les activités requises sont terminées
            all_required_completed = all(
                link.is_completed for link in required_activities
            )
            
            if all_required_completed:
                # Marquer la sous-étape comme terminée
                self.substage.mark_as_completed()

    @classmethod
    def create_link(cls, substage, activity, link_type='FUTURE_ACTIVITY', 
                     is_required=False, user=None):
        """
        Crée une liaison entre une sous-étape et une activité
        """
        return cls.objects.create(
            substage=substage,
            activity=activity,
            link_type=link_type,
            is_required=is_required,
            client_id=substage.client_id,
            user=user
        )

    @classmethod
    def link_activity_to_substage(cls, activity_id: int, substage_id: int, 
                                client_id: str, link_type='FUTURE_ACTIVITY',
                                is_required=False, user=None):
        """
        Lie une activité existante à une sous-étape
        """
        from apps.activities.models import Activity
        
        try:
            activity = Activity.objects.get(id=activity_id, client_id=client_id)
            substage = cls._get_substage(substage_id, client_id)
            
            # Vérifier que l'activité appartient au même compte que l'opportunité
            if activity.account != substage.stage.opportunity_pipeline.opportunity.account:
                from core.exceptions import StandardizedValidationError
                from core.error_messages import OpportunityErrorMessages
                raise StandardizedValidationError(
                    OpportunityErrorMessages.ACTIVITY_NOT_IN_PIPELINE
                )
            
            return cls.create_link(
                substage=substage,
                activity=activity,
                link_type=link_type,
                is_required=is_required,
                user=user
            )
            
        except Activity.DoesNotExist:
            from core.exceptions import StandardizedValidationError
            from core.error_messages import CoreErrorMessages
            raise StandardizedValidationError(
                CoreErrorMessages.OBJECT_NOT_FOUND.format(object_type='Activity')
            )

    @classmethod
    def get_substage_activities(cls, substage_id: int, client_id: str, 
                             link_type=None, completed_only=False):
        """
        Récupère les activités liées à une sous-étape
        """
        queryset = cls.objects.filter(
            substage_id=substage_id,
            client_id=client_id
        ).select_related('activity', 'substage')
        
        if link_type:
            queryset = queryset.filter(link_type=link_type)
        
        if completed_only:
            queryset = queryset.filter(is_completed=True)
        
        return queryset.order_by('priority_order', 'linked_at')

    @classmethod
    def get_activity_substages(cls, activity_id: int, client_id: str):
        """
        Récupère les sous-étapes liées à une activité
        """
        return cls.objects.filter(
            activity_id=activity_id,
            client_id=client_id
        ).select_related('substage', 'activity')

    @classmethod
    def _get_substage(cls, substage_id: int, client_id: str):
        """
        Récupère une sous-étape avec validation
        """
        from apps.opportunities.models import PipelineSubStage
        try:
            return PipelineSubStage.objects.get(id=substage_id, client_id=client_id)
        except PipelineSubStage.DoesNotExist:
            from core.exceptions import StandardizedValidationError
            from core.error_messages import OpportunityErrorMessages
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
            )

    @property
    def is_overdue(self):
        """
        Vérifie si l'activité liée est en retard
        """
        if self.activity and self.activity.scheduled_end:
            from django.utils import timezone
            return timezone.now() > self.activity.scheduled_end and not self.is_completed
        return False

    @property
    def days_until_due(self):
        """
        Calcule le nombre de jours avant l'échéance de l'activité
        """
        if self.activity and self.activity.scheduled_end:
            from django.utils import timezone
            delta = self.activity.scheduled_end.date() - timezone.now().date()
            return delta.days
        return None