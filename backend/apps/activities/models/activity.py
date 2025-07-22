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
            substage_opportunity = self._get_substage_opportunity()
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
        
        if self.pipeline_substage and self.status == 'COMPLETED':
            self._process_pipeline_completion()
        

        super().save(*args, **kwargs)
    
    def _get_substage_opportunity(self):
        """Helper pour récupérer l'opportunity d'un substage"""
        if not self.pipeline_substage or not self.pipeline_substage.stage:
            return None
            
        stage = self.pipeline_substage.stage
        
        # Cas 1: Stage d'instance
        if hasattr(stage, 'opportunity_pipeline') and stage.opportunity_pipeline:
            return stage.opportunity_pipeline.opportunity
        
        # Cas 2: Stage de template
        elif hasattr(stage, 'template') and stage.template and hasattr(stage.template, 'opportunity'):
            return stage.template.opportunity
        
        return None
    
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
    
    def link_to_substage(self, substage):
        """
        Lie cette activité à une sous-étape de pipeline - VERSION CORRIGÉE
        """
        # Setter le substage directement
        self.pipeline_substage = substage
        self.save(update_fields=['pipeline_substage'])
        
        from apps.opportunities.models import SubStageActivity
        
        # Vérifier si la liaison existe déjà
        link, created = SubStageActivity.objects.get_or_create(
            substage=substage,
            activity=self,
            client_id=self.client_id,
            defaults={
                'created_by': getattr(self, '_created_by_user', None),
            }
        )
        
        return link

    def unlink_from_substage(self):
        """
        Supprime la liaison avec la sous-étape - VERSION CORRIGÉE
        """
        if self.pipeline_substage:
            # ✅ SIMPLIFIÉ: Supprimer directement la liaison
            from apps.opportunities.models import SubStageActivity
            SubStageActivity.objects.filter(
                substage=self.pipeline_substage,
                activity=self,
                client_id=self.client_id
            ).delete()
            
            # Nettoyer le champ pipeline_substage
            self.pipeline_substage = None
            self.save(update_fields=['pipeline_substage'])

    def _process_pipeline_completion(self):
        """
        Traite la completion de l'activité dans le contexte du pipeline - VERSION CORRIGÉE
        """
        if not self.pipeline_substage:
            return
        
        # ✅ CORRIGÉ: Créer ou mettre à jour la liaison simplement
        from apps.opportunities.models import SubStageActivity
        try:
            link = SubStageActivity.objects.get(
                substage=self.pipeline_substage,
                activity=self,
                client_id=self.client_id
            )
            # La liaison existe déjà, pas besoin de modification spéciale
            
        except SubStageActivity.DoesNotExist:
            # ✅ CORRIGÉ: Créer la liaison si elle n'existe pas
            SubStageActivity.objects.create(
                substage=self.pipeline_substage,
                activity=self,
                client_id=self.client_id,
                created_by=getattr(self, '_created_by_user', None)
            )
        
        # ✅ OPTIONAL: Notifier le pipeline de la completion (simplifié)
        try:
            if self.opportunity and hasattr(self.opportunity, 'pipeline'):
                # Le pipeline peut réagir à la completion
                # Mais pour MVP, on garde ça simple
                pass
        except Exception as e:
            print(f"Failed to process pipeline completion for activity: {str(e)}", self.id)
            # Ne pas faire échouer la completion si notification échoue
            pass

    def get_pipeline_context(self):
        """
        Récupère le contexte pipeline de cette activité - VERSION CORRIGÉE
        """
        if not self.pipeline_substage:
            return None
        
        # ✅ CORRIGÉ: Utiliser la méthode helper pour récupérer l'opportunity
        substage_opportunity = self._get_substage_opportunity()
        if not substage_opportunity:
            return None
        
        # Récupérer le pipeline depuis l'opportunity
        pipeline = getattr(substage_opportunity, 'pipeline', None)
        
        context = {
            'substage_id': self.pipeline_substage.id,
            'substage_name': self.pipeline_substage.name,
            'stage_id': self.pipeline_substage.stage.id,
            'stage_name': self.pipeline_substage.stage.name,
            'opportunity_id': substage_opportunity.id,
            'opportunity_title': substage_opportunity.title,
        }
        
        # Ajouter les infos de template/pipeline selon le contexte
        stage = self.pipeline_substage.stage
        if hasattr(stage, 'template') and stage.template:
            context.update({
                'template_id': stage.template.id,
                'template_name': stage.template.name,
            })
        elif hasattr(stage, 'opportunity_pipeline') and stage.opportunity_pipeline:
            context.update({
                'pipeline_id': stage.opportunity_pipeline.id,
            })
        
        return context
    
    @property
    def is_pipeline_activity(self):
        """
        Vérifie si cette activité fait partie d'un pipeline
        """
        return self.pipeline_substage is not None
    
        
    def set_substage_context(self, substage, campaign_target=None):
        """Set context from substage and campaign target - VERSION SIMPLIFIÉE"""
        if not substage:
            return
            
        # Set basic substage info
        self.substage_name = substage.name
        self.pipeline_substage = substage
        
        # ✅ SIMPLIFIÉ: Auto-set opportunity (sera fait dans save())
        if not self.opportunity:
            substage_opportunity = self._get_substage_opportunity()
            if substage_opportunity:
                self.opportunity = substage_opportunity
        
        # Build objectives - SIMPLIFIÉ car opportunity est maintenant disponible
        objectives_parts = []
        if hasattr(substage, 'metadata') and substage.metadata.objective:
            objectives_parts.append(f"SubStage Goal: {substage.metadata.objective}")
        
        # Add stage context
        if substage.stage:
            objectives_parts.append(f"Stage: {substage.stage.name}")
            
        # Add opportunity context - SIMPLIFIÉ
        if self.opportunity:
            objectives_parts.append(f"Opportunity: {self.opportunity.title}")
        
        self.objectives = " | ".join(objectives_parts)
        
        # Build context info - SIMPLIFIÉ
        context = {
            'substage_id': substage.id,
            'substage_type': substage.get_substage_type_display(),
            'stage_name': substage.stage.name if substage.stage else None,
            'opportunity_id': self.opportunity.id if self.opportunity else None,
            'opportunity_title': self.opportunity.title if self.opportunity else None,
            'stakeholders': [],
            'validation_criteria': []
        }
        
        # Add stakeholder info from metadata
        if hasattr(substage, 'metadata'):
            metadata = substage.metadata
            
            # Add stakeholders
            for stakeholder in metadata.stakeholders.all():
                context['stakeholders'].append({
                    'id': stakeholder.id,
                    'name': f"{stakeholder.first_name} {stakeholder.last_name}",
                    'title': stakeholder.title,
                    'email': stakeholder.email
                })
            
            # Add validation criteria
            if metadata.validation_criteria:
                context['validation_criteria'] = metadata.validation_criteria
                
            # Add process notes
            if metadata.process_notes:
                context['process_notes'] = metadata.process_notes
        
        # Add campaign target context if provided
        if campaign_target:
            context['campaign_target_id'] = campaign_target.id
            context['campaign_id'] = campaign_target.campaign.id
            context['campaign_name'] = campaign_target.campaign.name
            
        self.context_info = context
        
        # Set call to action based on substage type
        self.set_call_to_action_from_substage(substage)
    
    def set_call_to_action_from_substage(self, substage):
        """Generate appropriate call-to-action based on substage type"""
        if not substage:
            return
            
        stage_name = substage.stage.name if substage.stage else "process"
        substage_name = substage.name
        
        if substage.substage_type == 'INTERACTION_CLIENT':
            self.call_to_action = f"Schedule meeting to discuss {substage_name} for {stage_name}"
        elif substage.substage_type == 'PROCESS_INTERNE_CLIENT':
            self.call_to_action = f"Follow up on {substage_name} status - ask for timeline update"
        elif substage.substage_type == 'ACTION_INTERNE':
            self.call_to_action = f"Update client on progress of {substage_name}"
        else:
            self.call_to_action = f"Follow up on {substage_name} for {stage_name}"
    
    def get_context_summary(self):
        """Get a summary of context information for display"""
        summary = {
            'has_substage': bool(self.substage_name),
            'substage_name': self.substage_name,
            'objectives': self.objectives,
            'call_to_action': self.call_to_action,
            'stakeholder_count': len(self.context_info.get('stakeholders', [])) if self.context_info else 0
        }
        
        return summary