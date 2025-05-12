# apps/sequence/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp

class SequenceTemplate(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Defines a template for sequences (e.g., chasing, nurturing, follow-up)
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_('Sequence Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    total_steps = models.IntegerField(
        default=10,
        verbose_name=_('Total Steps')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Sequence Template')
        verbose_name_plural = _('Sequence Templates')
        indexes = [
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.total_steps} steps)"