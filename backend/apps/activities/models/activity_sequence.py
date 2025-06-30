from apps.core_apps.models import BaseModelApp
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
        COMPLETED = 'COMPLETED', _('Completed')
    
    class SourceType(models.TextChoices):
        CAMPAIGN = 'CAMPAIGN', _('Campaign Sequence')
        MANUAL = 'MANUAL', _('Manual Activity')
        LEAD = 'LEAD', _('Lead Sequence')
        OPPORTUNITY = 'OPPORTUNITY', _('Opportunity Sequence')
    
    # ===== NEW: Import sequence variants from base class =====
    # Note: We'll import this dynamically to avoid circular imports
    @property
    def get_sequence_variant_choices(self):
        """Get sequence variant choices from base Sequence class"""
        try:
            from apps.sequence.sequences.base_sequence import Sequence
            return Sequence.SequenceVariant.get_choices()
        except ImportError:
            # Fallback choices if import fails
            return [
                ('standard', 'Standard (All Channels)'),
                ('without_phone', 'Without Phone'),
                ('without_email', 'Without Email'),
                ('phone_only', 'Phone Only'),
            ]
    
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
    
    # ===== NEW: Sequence identification fields =====
    sequence_type = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        verbose_name=_('Sequence Type'),
        help_text=_('Type of sequence (CHASING, NURTURING, etc.) - copied from campaign for fast access')
    )
    
    sequence_variant = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_('Sequence Variant'),
        help_text=_('Variant of sequence used (standard, without_phone, without_email, phone_only)')
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

    # Minimum delay before this activity can be worked on
    min_delay_days = models.IntegerField(
        default=0,
        verbose_name=_('Minimum Delay Days'),
        help_text=_('Days to wait since previous activity before this becomes available')
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
            # ===== NEW: Indexes for sequence identification =====
            models.Index(fields=['sequence_type']),
            models.Index(fields=['sequence_variant']),
            models.Index(fields=['sequence_type', 'sequence_variant']),
        ]
    
    def __str__(self):
        sequence_info = ""
        if self.sequence_type and self.sequence_variant:
            sequence_info = f" ({self.sequence_type} - {self.sequence_variant})"
        return f"{self.activity.title} - Sequence {self.sequence_position}{sequence_info}"
    
    def get_sequence_type_display(self):
        """Get human-readable display for sequence type"""
        if not self.sequence_type:
            return None
            
        # Map sequence types to display names
        sequence_type_mapping = {
            'CHASING': 'Chasing',
            'NURTURING': 'Nurturing', 
            'FOLLOW_UP': 'Follow-up',
            'RENEWAL': 'Renewal',
            # Add other sequence types as needed
        }
        return sequence_type_mapping.get(self.sequence_type, self.sequence_type.title())
    
    def get_sequence_variant_display(self):
        """Get human-readable display for sequence variant"""
        if not self.sequence_variant:
            return None
            
        try:
            from apps.sequence.sequences.base_sequence import Sequence
            return Sequence.SequenceVariant.get_display_name(self.sequence_variant)
        except ImportError:
            # Fallback mapping if import fails
            variant_mapping = {
                'standard': 'Standard (All Channels)',
                'without_phone': 'Without Phone',
                'without_email': 'Without Email',
                'phone_only': 'Phone Only',
            }
            return variant_mapping.get(self.sequence_variant, self.sequence_variant.replace('_', ' ').title())
    
    def is_from_sequence(self):
        """Check if this activity is from a sequence (not manual)"""
        return self.source_type == self.SourceType.CAMPAIGN and self.sequence_type is not None
    
    def get_full_sequence_info(self):
        """Get complete sequence information as dict for API responses"""
        return {
            'is_from_sequence': self.is_from_sequence(),
            'sequence_type': self.sequence_type,
            'sequence_type_display': self.get_sequence_type_display(),
            'sequence_variant': self.sequence_variant,
            'sequence_variant_display': self.get_sequence_variant_display(),
            'sequence_position': self.sequence_position,
            'source_type': self.source_type,
            'call_attempts': self.call_attempts,
            'min_delay_days': self.min_delay_days
        }
    
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