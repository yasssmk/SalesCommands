# apps\activities\models\activity.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages
from django.utils import timezone

class Activity(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a sales activity (call, email, meeting, etc.)
    Core tracking model for sales rep interactions with accounts.
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
    
    # Scheduling information
    scheduled_start = models.DateTimeField(
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
    
    # Campaign integration
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
        verbose_name=_('Related Campaign')
    )
    
    campaign_target = models.ForeignKey(
        'campaign.CampaignTarget',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
        verbose_name=_('Campaign Target')
    )
    
    # Sequence integration
    sequence_step = models.ForeignKey(
        'sales_assistant.AccountSequenceStep',
        on_delete=models.SET_NULL,
        related_name='activities',
        null=True,
        blank=True,
        verbose_name=_('Sequence Step')
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
    
    # Outcome tracking
    outcome_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Outcome Notes')
    )
    
    # Campaign tracking flags
    meeting_scheduled = models.BooleanField(
        default=False,
        verbose_name=_('Meeting Scheduled')
    )
    
    opportunity_created = models.BooleanField(
        default=False,
        verbose_name=_('Opportunity Created')
    )
    
    # Next steps tracking
    next_activity = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='previous_activities',
        null=True,
        blank=True,
        verbose_name=_('Next Activity')
    )
    
    next_step_summary = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Next Step Summary')
    )
    
    next_step_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Next Step Date')
    )
    
    # Transcript and analysis
    transcript = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Call Transcript')
    )
    
    has_transcript_analysis = models.BooleanField(
        default=False,
        verbose_name=_('Has Transcript Analysis')
    )
    
    class Meta:
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')
        ordering = ['scheduled_start']
        indexes = [
            models.Index(fields=['owner', 'scheduled_start']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['campaign', 'campaign_target']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['next_step_date']),
        ]

    def __str__(self):
        return f"{self.title} - {self.account.company_name} ({self.get_activity_type_display()})"
        
    def save(self, *args, **kwargs):
        # Track status changes
        is_new = self.pk is None
        was_completed = False
        was_cancelled = False
        
        if not is_new:
            try:
                old_instance = type(self).objects.get(pk=self.pk)
                was_completed = (old_instance.status != self.Status.COMPLETED and 
                               self.status == self.Status.COMPLETED)
                was_cancelled = (old_instance.status != self.Status.CANCELLED and 
                               self.status == self.Status.CANCELLED)
            except type(self).DoesNotExist:
                pass
        
        # Set completed_at when activity is completed
        if was_completed:
            self.completed_at = timezone.now()
        
        # Validate scheduled dates
        if self.scheduled_end and self.scheduled_start and self.scheduled_end < self.scheduled_start:
            raise ValidationError(CoreErrorMessages.INVALID_DATE_RANGE.format(
                start_date=self.scheduled_start,
                end_date=self.scheduled_end
            ))
        
        # Save the activity
        super().save(*args, **kwargs)
        
        # Update campaign metrics if this activity is linked to a campaign
        if self.campaign and was_completed:
            self._update_campaign_metrics()
            
        # Update sequence step status if applicable
        if self.sequence_step and (was_completed or was_cancelled):
            self._update_sequence_step()
            
        # Create NextStepSummary if next step info was added
        if (is_new or not old_instance.next_step_summary) and self.next_step_summary and self.next_step_date:
            self._create_next_step_summary()
    
    def complete(self, outcome_notes=None, meeting_scheduled=False, 
                opportunity_created=False, next_step_summary=None, next_step_date=None, save=True):
        """
        Mark activity as completed with outcome details
        
        Args:
            outcome_notes (str, optional): Notes about the outcome
            meeting_scheduled (bool): Whether a meeting was scheduled
            opportunity_created (bool): Whether an opportunity was created
            next_step_summary (str, optional): Summary of next steps
            next_step_date (date, optional): Date for next steps
            save (bool): Whether to save changes immediately
        """
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        
        if outcome_notes:
            self.outcome_notes = outcome_notes
            
        self.meeting_scheduled = meeting_scheduled
        self.opportunity_created = opportunity_created
        
        if next_step_summary:
            self.next_step_summary = next_step_summary
            
        if next_step_date:
            self.next_step_date = next_step_date
        
        if save:
            self.save()
            
        return self
    
    def cancel(self, reason=None, save=True):
        """
        Mark activity as cancelled with optional reason
        
        Args:
            reason (str, optional): Reason for cancellation
            save (bool): Whether to save changes immediately
        """
        self.status = self.Status.CANCELLED
        
        if reason:
            self.outcome_notes = reason
            
        if save:
            self.save()
            
        return self
    
    def create_follow_up_activity(self, title, activity_type, scheduled_date, 
                             description=None, save=True):
        """
        Create a follow-up activity linked to this one
        
        Args:
            title (str): Title for the new activity
            activity_type (str): Type of activity (use Activity.ActivityType)
            scheduled_date (datetime): When the activity is scheduled
            description (str, optional): Detailed description
            save (bool): Whether to save changes immediately
            
        Returns:
            Activity: The newly created activity
        """
        # Create datetime if date was provided
        if not isinstance(scheduled_date, timezone.datetime):
            scheduled_date = timezone.datetime.combine(
                scheduled_date,
                timezone.datetime.min.time() + timezone.timedelta(hours=9)  # 9 AM default
            )
            scheduled_date = timezone.make_aware(scheduled_date)
        
        next_activity = type(self)(
            title=title,
            activity_type=activity_type,
            description=description,
            account=self.account,
            owner=self.owner,
            scheduled_start=scheduled_date,
            # Maintain campaign connections
            campaign=self.campaign,
            campaign_target=self.campaign_target,
            opportunity=self.opportunity
        )
        
        if save:
            next_activity.save()
            # Update the link
            self.next_activity = next_activity
            self.save(update_fields=['next_activity'])
            
        # Create a next step summary
        NextStepSummary.objects.create(
            account=self.account,
            due_date=scheduled_date.date(),
            description=title,
            detailed_notes=description,
            activity_type=activity_type,
            owner=self.owner,
            source_activity=self,
            generated_activity=next_activity,
            campaign=self.campaign,
            opportunity=self.opportunity,
            sequence_step=next_activity.sequence_step
        )
        
        # Link contacts
        if self.contacts.exists():
            next_activity.contacts.set(self.contacts.all())
        
        return next_activity
    
    def set_next_step(self, summary, due_date, save=True):
        """
        Set the next step information without creating an activity
        
        Args:
            summary (str): Summary of the next step
            due_date (date): When the next step is due
            save (bool): Whether to save changes immediately
            
        Returns:
            NextStepSummary: The created next step summary
        """
        self.next_step_summary = summary
        self.next_step_date = due_date
        
        if save:
            self.save(update_fields=['next_step_summary', 'next_step_date'])
            
        # Create a next step summary without a generated activity
        next_step = self._create_next_step_summary()
        return next_step
    
    def _create_next_step_summary(self):
        """Create a NextStepSummary from the current next step info"""
        if not self.next_step_summary or not self.next_step_date:
            return None
            
        next_step = NextStepSummary.objects.create(
            account=self.account,
            due_date=self.next_step_date,
            description=self.next_step_summary,
            activity_type=self.activity_type,  # Use same type by default
            owner=self.owner,
            source_activity=self,
            campaign=self.campaign,
            opportunity=self.opportunity,
            sequence_step=self.sequence_step
        )
        
        # Link contacts
        if self.contacts.exists():
            next_step.contacts.set(self.contacts.all())
        
        return next_step
    
    def _update_campaign_metrics(self):
        """Update campaign objectives when activity is completed"""
        if not self.campaign:
            return
            
        from apps.campaign.models.campaign_objective import CampaignObjective
        
        # Update activity count objectives if they exist
        activity_objectives = self.campaign.objectives.filter(
            objective_type=CampaignObjective.ObjectiveType.ACTIVITIES
        )
        
        for objective in activity_objectives:
            objective.current_value += 1
            objective.save(update_fields=['current_value', 'last_updated'])
        
        # If a meeting was scheduled, update meeting objectives
        if self.meeting_scheduled:
            meeting_objectives = self.campaign.objectives.filter(
                objective_type=CampaignObjective.ObjectiveType.MEETINGS
            )
            
            for objective in meeting_objectives:
                objective.current_value += 1
                objective.save(update_fields=['current_value', 'last_updated'])
                
        # Update campaign target status if needed
        if self.campaign_target:
            self._update_campaign_target()
    
    def _update_campaign_target(self):
        """Update campaign target status based on activity outcomes"""
        if not self.campaign_target:
            return
            
        from apps.campaign.models.campaign_target import CampaignTarget
        
        # If activity resulted in meeting, update status to MEETING_SECURED
        if self.meeting_scheduled and self.campaign_target.status in [
            CampaignTarget.Status.PENDING,
            CampaignTarget.Status.IN_PROGRESS
        ]:
            self.campaign_target.update_status(CampaignTarget.Status.MEETING_SECURED)
            
        # If activity resulted in opportunity, update status to OPPORTUNITY_CREATED
        if self.opportunity_created and self.campaign_target.status in [
            CampaignTarget.Status.PENDING,
            CampaignTarget.Status.IN_PROGRESS,
            CampaignTarget.Status.MEETING_SECURED
        ]:
            self.campaign_target.update_status(CampaignTarget.Status.OPPORTUNITY_CREATED)
    
    def _update_sequence_step(self):
        """Update the status of associated sequence step"""
        if not self.sequence_step:
            return
            
        if self.status == self.Status.COMPLETED:
            # Call complete method if it exists
            if hasattr(self.sequence_step, 'complete'):
                self.sequence_step.complete(notes=self.outcome_notes)
            
        elif self.status == self.Status.CANCELLED:
            # Call skip method if it exists
            if hasattr(self.sequence_step, 'skip'):
                self.sequence_step.skip(reason=self.outcome_notes)


class NextStepSummary(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Aggregated next step information for reporting and dashboard views.
    """
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='next_steps',
        verbose_name=_('Account')
    )
    
    contacts = models.ManyToManyField(
        'accounts.Contact',
        related_name='next_steps',
        blank=True,
        verbose_name=_('Related Contacts')
    )
    
    # Scheduled timing
    due_date = models.DateField(
        verbose_name=_('Due Date')
    )
    
    # Step details
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description')
    )
    
    detailed_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Detailed Notes')
    )
    
    # Type of follow-up
    activity_type = models.CharField(
        max_length=20,
        choices=Activity.ActivityType.choices,
        verbose_name=_('Activity Type')
    )
    
    # Assigned owner
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='owned_next_steps',
        verbose_name=_('Owner')
    )
    
    # Status tracking
    is_completed = models.BooleanField(
        default=False,
        verbose_name=_('Is Completed')
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Completed At')
    )
    
    # Source references
    source_activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        related_name='generated_next_steps',
        null=True,
        blank=True,
        verbose_name=_('Source Activity')
    )
    
    # Optional link to created activity
    generated_activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        related_name='next_step_source',
        null=True,
        blank=True,
        verbose_name=_('Generated Activity')
    )
    
    # Campaign and opportunity tracking
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.SET_NULL,
        related_name='next_steps',
        null=True,
        blank=True,
        verbose_name=_('Related Campaign')
    )
    
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='next_steps',
        null=True,
        blank=True,
        verbose_name=_('Related Opportunity')
    )
    
    # Sequence tracking
    sequence_step = models.ForeignKey(
        'sales_assistant.AccountSequenceStep',
        on_delete=models.SET_NULL,
        related_name='next_steps',
        null=True,
        blank=True,
        verbose_name=_('Sequence Step')
    )
    
    class Meta:
        verbose_name = _('Next Step Summary')
        verbose_name_plural = _('Next Step Summaries')
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['account', 'due_date']),
            models.Index(fields=['owner', 'due_date']),
            models.Index(fields=['is_completed']),
            models.Index(fields=['campaign']),
            models.Index(fields=['opportunity']),
        ]
        
    def __str__(self):
        return f"{self.account.company_name} - {self.description} (Due: {self.due_date})"
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
    def complete(self, completed_at=None, save=True):
        """
        Mark this next step as completed
        
        Args:
            completed_at (datetime, optional): When it was completed (defaults to now)
            save (bool): Whether to save changes immediately
        """
        self.is_completed = True
        self.completed_at = completed_at or timezone.now()
        
        if save:
            self.save()
            
        # If there's a linked generated activity, mark it as completed too
        if self.generated_activity and self.generated_activity.status != Activity.Status.COMPLETED:
            self.generated_activity.status = Activity.Status.COMPLETED
            self.generated_activity.completed_at = self.completed_at
            self.generated_activity.save(update_fields=['status', 'completed_at'])
            
        return self
        
    def create_activity(self, save=True):
        """
        Create an activity from this next step summary
        
        Returns:
            Activity: The newly created activity
        """
        if self.generated_activity:
            return self.generated_activity
            
        # Create the activity
        activity = Activity(
            title=self.description,
            activity_type=self.activity_type,
            description=self.detailed_notes,
            account=self.account,
            owner=self.owner,
            scheduled_start=timezone.make_aware(timezone.datetime.combine(
                self.due_date, 
                timezone.datetime.min.time() + timezone.timedelta(hours=9)  # 9 AM
            )),
            campaign=self.campaign,
            opportunity=self.opportunity,
            sequence_step=self.sequence_step
        )
        
        if save:
            activity.save()
            
            # Link the activity back to this next step
            self.generated_activity = activity
            self.save(update_fields=['generated_activity'])
            
            # Link contacts
            if self.contacts.exists():
                activity.contacts.set(self.contacts.all())
        
        return activity