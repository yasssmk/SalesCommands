from core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.activities.models import Activity

class ActivitySequence(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Tracks sequence-specific information for activities
    Handles the sequence flow and outcomes
    """
    class SequenceOutcome(models.TextChoices):
        NO_ANSWER = 'NO_ANSWER', _('No Answer')
        NOT_INTERESTED = 'NOT_INTERESTED', _('Not Interested')
        CALLBACK_REQUESTED = 'CALLBACK_REQUESTED', _('Callback Requested')
        MEETING_SCHEDULED = 'MEETING_SCHEDULED', _('Meeting Scheduled')
    
    class SourceType(models.TextChoices):
        CAMPAIGN = 'CAMPAIGN', _('Campaign Sequence')
        MANUAL = 'MANUAL', _('Manual Activity')
        LEAD = 'LEAD', _('Lead Sequence')
        OPPORTUNITY = 'OPPORTUNITY', _('Opportunity Sequence')
    
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        related_name='sequence_info',
        verbose_name=_('Activity')
    )
    
    # Source tracking
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.CAMPAIGN,
        verbose_name=_('Activity Source')
    )
    
    # Position in sequence (1-10 for chasing sequence)
    sequence_position = models.IntegerField(
        verbose_name=_('Sequence Position'),
        help_text=_('Position in the sequence (e.g., 1-10 for chasing)')
    )
    
    # Sequence outcome tracking
    sequence_outcome = models.CharField(
        max_length=30,
        choices=SequenceOutcome.choices,
        null=True,
        blank=True,
        verbose_name=_('Sequence Outcome')
    )
    
    # Call attempt tracking for the 3-attempts rule
    call_attempts = models.IntegerField(
        default=0,
        verbose_name=_('Call Attempts'),
        help_text=_('Number of call attempts made (max 3 per step)')
    )
    
    # Callback/reschedule tracking
    callback_requested_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Callback Requested Date'),
        help_text=_('Date when contact requested to be called back')
    )
    
    # Sequence pause/resume tracking
    sequence_paused_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Sequence Paused Until'),
        help_text=_('Sequence is paused until this date')
    )
    
    # Days since last activity in sequence
    days_since_last_sequence_activity = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Days Since Last Sequence Activity')
    )
    
    # Next sequence activity link (for better sequence management)
    next_sequence_activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        related_name='previous_sequence_activities',
        null=True,
        blank=True,
        verbose_name=_('Next Sequence Activity')
    )
    
    class Meta:
        verbose_name = _('Activity Sequence Information')
        verbose_name_plural = _('Activity Sequence Information')
        indexes = [
            models.Index(fields=['source_type', 'sequence_position']),
            models.Index(fields=['sequence_outcome']),
            models.Index(fields=['callback_requested_date']),
            models.Index(fields=['sequence_paused_until']),
        ]
    
    def __str__(self):
        return f"{self.activity.title} - Sequence {self.sequence_position}"
    
    def increment_call_attempts(self, save=True):
        """Increment call attempts and check if limit reached"""
        self.call_attempts += 1
        
        # If it's a call and we've reached 3 attempts, mark as completed
        if (self.activity.activity_type == Activity.ActivityType.CALL and 
            self.call_attempts >= 3):
            self.activity.status = Activity.Status.COMPLETED
            self.activity.save()
        
        if save:
            self.save()
        
        return self.call_attempts
    
    def set_outcome(self, outcome, notes=None, callback_date=None, save=True):
        """Set the sequence outcome and handle accordingly"""
        self.sequence_outcome = outcome
        
        if notes:
            self.activity.outcome_notes = notes
            self.activity.save()
        
        if outcome == self.SequenceOutcome.CALLBACK_REQUESTED and callback_date:
            self.callback_requested_date = callback_date
            # Pause sequence until callback date
            self.sequence_paused_until = callback_date
        
        if save:
            self.save()
        
        return self
    
    def pause_until(self, date, save=True):
        """Pause the sequence until a specific date"""
        self.sequence_paused_until = date
        
        if save:
            self.save()
        
        return self