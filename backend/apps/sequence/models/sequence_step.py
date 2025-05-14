# apps/sequence/models.py (add this to the existing file)

from django.db import models
from django.utils.translation import gettext_lazy as _
from .sequence import SequenceTemplate
from apps.core_apps.models import BaseModelApp


class SequenceStep(BaseModelApp):
    """
    Individual step within a sequence template - implemented as double linked list
    """
    class ActivityType(models.TextChoices):
        EMAIL = 'EMAIL', _('Email')
        CALL = 'CALL', _('Call')
        LINKEDIN = 'LINKEDIN', _('LinkedIn Message')
        TASK = 'TASK', _('Manual Task')
    
    sequence_template = models.ForeignKey(
        SequenceTemplate,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('Sequence Template')
    )
    
    step_number = models.IntegerField(
        verbose_name=_('Step Number')
    )
    
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        verbose_name=_('Activity Type')
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name=_('Step Title')
    )
    
    delay_days = models.IntegerField(
        default=1,
        help_text=_('Days after previous step')
    )
    
    # Double linked list pointers
    next_step = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_step',
        verbose_name=_('Next Step')
    )
    
    # Helper fields for UI
    is_first = models.BooleanField(default=False)
    is_last = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('sequence_template', 'step_number')
        ordering = ['step_number']
        verbose_name = _('Sequence Step')
        verbose_name_plural = _('Sequence Steps')
    
    def __str__(self):
        return f"{self.sequence_template.name} - Step {self.step_number}: {self.title}"
    
    def save(self, *args, **kwargs):
        # Auto-set first/last flags
        if self.step_number == 1:
            self.is_first = True
        else:
            self.is_first = False
            
        if self.step_number == self.sequence_template.total_steps:
            self.is_last = True
        else:
            self.is_last = False
            
        super().save(*args, **kwargs)
        
        # Update linked list pointers when step is created/updated
        self._update_linked_list()
    
    def _update_linked_list(self):
        """Update the double linked list pointers"""
        # Find the previous step (current step_number - 1)
        if self.step_number > 1:
            try:
                prev_step = SequenceStep.objects.get(
                    sequence_template=self.sequence_template,
                    step_number=self.step_number - 1
                )
                prev_step.next_step = self
                prev_step.save(update_fields=['next_step'])
            except SequenceStep.DoesNotExist:
                pass
        
        # Find the next step (current step_number + 1)
        if self.step_number < self.sequence_template.total_steps:
            try:
                next_step = SequenceStep.objects.get(
                    sequence_template=self.sequence_template,
                    step_number=self.step_number + 1
                )
                self.next_step = next_step
                self.save(update_fields=['next_step'])
            except SequenceStep.DoesNotExist:
                pass