# apps/signals/models/qualification_signal_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from .base_signal_model import BaseSignal


class QualificationSignal(BaseSignal):
    """
    Signal model for qualification data from MEDPICC and other sales qualification frameworks.
    Tracks key account qualification elements like objectives, pain points, metrics, etc.
    """
    
    class Field(models.TextChoices):
        OBJECTIVES = 'objectives', _('Objectives')
        MOTIVATIONS = 'motivations', _('Motivations')
        METRICS = 'metrics', _('Metrics')
        PAIN_POINTS = 'pain_points', _('Pain Points')
        IMPLICATIONS = 'implications', _('Implications')
    
    field_name = models.CharField(
        max_length=50,
        choices=Field.choices,
        verbose_name=_('Qualification Field')
    )
    
    
    class Meta:
        verbose_name = _('Qualification Signal')
        verbose_name_plural = _('Qualification Signals')
        indexes = [
            models.Index(fields=['account', 'field_name']),
            models.Index(fields=['status']),
        ]
    
    
    def __str__(self):
        return f"Qualification: {self.get_field_name_display()} [{self.get_status_display()}]"