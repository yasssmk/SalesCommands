from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages
from django.utils import timezone


class Activity(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Core activity model - simplified and focused on essential fields
    """
    class ActivityType(models.TextChoices):
        CALL = 'CALL', _('Phone Call')
        EMAIL = 'EMAIL', _('Email')
        MEETING = 'MEETING', _('Meeting')
        TASK = 'TASK', _('Task')
        LINKEDIN = 'LINKEDIN', _('LinkedIn Message')
        CUSTOM = 'CUSTOM', _('Custom Activity')
    
    class Status(models.TextChoices):
        PLANNED = 'PLANNED', _('Planned')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    # Basic information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Activity Title')
    )
    
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        verbose_name=_('Activity Type')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    # Related entities
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name=_('Account')
    )
    
    contacts = models.ManyToManyField(
        'accounts.Contact',
        related_name='activities',
        blank=True,
        verbose_name=_('Contacts')
    )
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='owned_activities',
        verbose_name=_('Activity Owner')
    )
    
    objectives = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Activity Objectives'),
        help_text=_('Specific objectives or goals for this activity (e.g., from substage)')
    )
    
    context_info = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Context Information'),
        help_text=_('Additional context information (substage details, stakeholder info, etc.)')
    )
    
    substage_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_('SubStage Name'),
        help_text=_('Name of the related substage for quick reference')
    )
    
    call_to_action = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Call to Action'),
        help_text=_('Clear action the salesperson should take (e.g., "Ask about legal review timeline")')
    )

    # Scheduling information
    scheduled_start = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Scheduled Start')
    )
    
    scheduled_end = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Scheduled End')
    )
    
    # State tracking
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        verbose_name=_('Status')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    
    # Basic outcome tracking
    outcome_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Outcome Notes')
    )
    
    # Opportunity connection
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
        verbose_name=_('Related Opportunity')
    )

    pipeline_substage = models.ForeignKey(
        'opportunities.PipelineSubStage',
        on_delete=models.SET_NULL,
        related_name='direct_activities',
        null=True,
        blank=True,
        verbose_name=_('Pipeline SubStage'),
        help_text=_('Pipeline substage this activity is directly linked to')
    )
    
    # Linked list fields for sequence navigation
    previous_activity = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_activity_rel',
        null=True,
        blank=True,
        verbose_name=_('Previous Activity')
    )
    
    next_activity = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        related_name='previous_activity_rel',
        null=True,
        blank=True,
        verbose_name=_('Next Activity')
    )
    
    class Meta:
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')
        ordering = ['scheduled_start']
        indexes = [
            models.Index(fields=['owner', 'scheduled_start']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['previous_activity']),
            models.Index(fields=['next_activity']),
            models.Index(fields=['status', 'scheduled_start'], name='activity_status_date_idx'),
            models.Index(fields=['completed_at'], name='activity_completed_idx'),
            models.Index(fields=['status', 'activity_type', 'owner'], name='activity_filter_idx'),
            models.Index(fields=['pipeline_substage'], name='activity_substage_idx'),
            models.Index(fields=['pipeline_substage', 'status'], name='activity_substage_status_idx'),
            models.Index(fields=['pipeline_substage', 'status']),
            models.Index(fields=['substage_name']),
        ]

    def __str__(self):
        return f"{self.title} - {self.account.company_name} ({self.get_activity_type_display()})"
        
    def save(self, *args, **kwargs):
        # Track status changes
        is_new = self.pk is None
        was_completed = False
        
        if not is_new:
            try:
                old_instance = type(self).objects.get(pk=self.pk)
                was_completed = (old_instance.status != self.Status.COMPLETED and 
                               self.status == self.Status.COMPLETED)
            except type(self).DoesNotExist:
                pass
        
        if self.pipeline_substage and not self.opportunity:
            from apps.opportunities.services.activity_substage_service import ActivitySubStageService
            substage_opportunity = ActivitySubStageService.get_substage_opportunity(self.pipeline_substage)
            if substage_opportunity:
                self.opportunity = substage_opportunity
        
        # Set completed_at when activity is completed
        if was_completed:
            self.completed_at = timezone.now()
        
        # Validate scheduled dates
        if self.scheduled_end and self.scheduled_start and self.scheduled_end < self.scheduled_start:
            raise ValidationError(CoreErrorMessages.INVALID_DATE_RANGE.format(
                start_date=self.scheduled_start,
                end_date=self.scheduled_end
            ))
          

        super().save(*args, **kwargs)
    

    
    def complete(self, outcome_notes=None, save=True):
        """Mark activity as completed"""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        
        if outcome_notes:
            self.outcome_notes = outcome_notes
        
        if save:
            self.save()
        
        return self
    
    def cancel(self, reason=None, save=True):
        """Mark activity as cancelled"""
        self.status = self.Status.CANCELLED
        
        if reason:
            self.outcome_notes = reason
        
        if save:
            self.save()
        
        return self
    
    
    @property
    def is_pipeline_activity(self):
        """
        Vérifie si cette activité fait partie d'un pipeline
        """
        return self.pipeline_substage is not None
    
        
    def set_substage_context(self, substage, campaign_target=None):
        """
        ✅ GARDER - Set context from substage and campaign target (version MVP simplifiée)
        
        Cette méthode enrichit l'activité avec le contexte du substage.
        Elle ne gère pas la liaison DB (ça c'est dans ActivitySubStageService).
        """
        if not substage:
            return
            
        # Set basic substage info
        self.substage_name = substage.name
        self.pipeline_substage = substage
        
        # Build objectives - version MVP simplifiée
        objectives_parts = []
        if hasattr(substage, 'metadata') and substage.metadata and substage.metadata.objective:
            objectives_parts.append(f"SubStage Goal: {substage.metadata.objective}")
        
        # Add stage context
        if substage.stage:
            objectives_parts.append(f"Stage: {substage.stage.name}")
            
        # Add opportunity context - direct depuis self.opportunity
        if self.opportunity:
            objectives_parts.append(f"Opportunity: {self.opportunity.title}")
        
        self.objectives = " | ".join(objectives_parts) if objectives_parts else ""
        
        # Build context info - version MVP
        context = {
            'substage_id': substage.id,
            'substage_type': substage.get_substage_type_display() if hasattr(substage, 'get_substage_type_display') else substage.substage_type,
            'stage_name': substage.stage.name if substage.stage else None,
            'opportunity_id': self.opportunity.id if self.opportunity else None,
            'opportunity_title': self.opportunity.title if self.opportunity else None,
            'stakeholders': [],
            'validation_criteria': []
        }
        
        # Add stakeholder info from metadata (avec protection MVP)
        try:
            if hasattr(substage, 'metadata') and substage.metadata:
                metadata = substage.metadata
                
                # Add stakeholders
                if hasattr(metadata, 'stakeholders'):
                    for stakeholder in metadata.stakeholders.all():
                        context['stakeholders'].append({
                            'id': stakeholder.id,
                            'name': f"{stakeholder.first_name} {stakeholder.last_name}",
                            'title': stakeholder.title or "",
                            'email': stakeholder.email or ""
                        })
                
                # Add validation criteria
                if hasattr(metadata, 'validation_criteria') and metadata.validation_criteria:
                    context['validation_criteria'] = metadata.validation_criteria
                    
                # Add process notes
                if hasattr(metadata, 'process_notes') and metadata.process_notes:
                    context['process_notes'] = metadata.process_notes
        except Exception:
            # Fail silently pour MVP - pas de crash si metadata incomplète
            pass
        
        # Add campaign target context if provided
        if campaign_target:
            try:
                context['campaign_target_id'] = campaign_target.id
                context['campaign_id'] = campaign_target.campaign.id
                context['campaign_name'] = campaign_target.campaign.name
            except Exception:
                # Fail silently pour MVP
                pass
                
        self.context_info = context
        
        # Set call to action based on substage type
        self.set_call_to_action_from_substage(substage)

    def set_call_to_action_from_substage(self, substage):
        """
        ✅ GARDER - Generate appropriate call-to-action based on substage type
        
        Méthode utilitaire simple pour l'UX - pas de logique DB complexe.
        """
        if not substage:
            return
            
        stage_name = substage.stage.name if substage.stage else "process"
        substage_name = substage.name
        substage_type = getattr(substage, 'substage_type', 'UNKNOWN')
        
        # Mapping simple pour MVP
        if substage_type == 'INTERACTION_CLIENT':
            self.call_to_action = f"Schedule meeting to discuss {substage_name} for {stage_name}"
        elif substage_type == 'PROCESS_INTERNE_CLIENT':
            self.call_to_action = f"Follow up on {substage_name} status - ask for timeline update"
        elif substage_type == 'ACTION_INTERNE':
            self.call_to_action = f"Update client on progress of {substage_name}"
        else:
            self.call_to_action = f"Follow up on {substage_name} for {stage_name}"

    def get_context_summary(self):
        """
        ✅ GARDER - Get a summary of context information for display
        
        Méthode utilitaire pour l'UI - retourne un résumé du contexte.
        """
        try:
            stakeholder_count = 0
            if self.context_info and isinstance(self.context_info, dict):
                stakeholders = self.context_info.get('stakeholders', [])
                if isinstance(stakeholders, list):
                    stakeholder_count = len(stakeholders)
            
            summary = {
                'has_substage': bool(self.substage_name),
                'substage_name': self.substage_name or "",
                'objectives': self.objectives or "",
                'call_to_action': self.call_to_action or "",
                'stakeholder_count': stakeholder_count
            }
            
            return summary
        except Exception:
            # Fail silently pour MVP - retourner une structure vide
            return {
                'has_substage': False,
                'substage_name': "",
                'objectives': "",
                'call_to_action': "",
                'stakeholder_count': 0
            }
