# apps/signals/models/tech_stack_signal_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from .base_signal_model import BaseSignal
import re
from django.core.exceptions import ValidationError


class TechStackSignal(BaseSignal):
    """
    Signal model for technology stack information.
    Tracks details about software, tools, and platforms used by the account.
    """
    
    class Field(models.TextChoices):
        PURPOSE = 'purpose', _('Purpose')
        PROS = 'pros', _('Pros')
        CONS = 'cons', _('Cons')
        COSTS = 'costs', _('Costs')
        RENEWAL_DATE = 'renewal_date', _('Renewal Date')
        START_YEAR_OF_USAGE = 'start_year_of_usage', _('Start year of Usage')
    
    field_name = models.CharField(
        max_length=50,
        choices=Field.choices,
        verbose_name=_('Tech Stack Field')
    )
    
    # Link to the specific technology
    tech_stack = models.ForeignKey(
        'accounts.TechStack',
        on_delete=models.CASCADE,
        related_name='signals',
        verbose_name=_('Technology'),
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = _('Tech Stack Signal')
        verbose_name_plural = _('Tech Stack Signals')
        indexes = [
            models.Index(fields=['account', 'tech_stack']),
            models.Index(fields=['field_name']),
        ]
    
    def clean(self):
        """Validate field-specific data formats"""
        super().clean()
        
        # Field-specific validation
        if self.field_name == self.Field.RENEWAL_DATE and isinstance(self.value, str):
            # Validate date format
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', self.value):
                raise ValidationError({
                    'value': _('Renewal date must be in YYYY-MM-DD format')
                })
                
        if self.field_name == self.Field.START_YEAR_OF_USAGE:
            # Validate year
            try:
                year = int(self.value)
                if year < 1900 or year > 2100:
                    raise ValidationError({
                        'value': _('Year must be between 1900 and 2100')
                    })
            except (ValueError, TypeError):
                raise ValidationError({
                    'value': _('Start year must be a valid year')
                })
                
        if self.field_name == self.Field.COSTS:
            # For costs, we allow more flexible structure to capture different cost models
            # The value can be a list of cost objects or a single cost object
            if isinstance(self.value, dict):
                # Single cost object validation
                self._validate_cost_object(self.value)
            elif isinstance(self.value, list):
                # List of cost objects validation
                for cost_item in self.value:
                    if isinstance(cost_item, dict):
                        self._validate_cost_object(cost_item)
            else:
                # If it's just a string or number, convert to a simple cost object
                self.value = {
                    "cost_name": "General cost",
                    "cost": str(self.value),
                    "recurrence": "unknown"
                }
    
    def _validate_cost_object(self, cost_obj):
        """Helper method to validate a cost object structure"""
        # Ensure required fields exist with defaults if needed
        if 'cost_name' not in cost_obj:
            cost_obj['cost_name'] = 'Unspecified'
        if 'cost' not in cost_obj:
            cost_obj['cost'] = 'Unknown'
        if 'recurrence' not in cost_obj:
            cost_obj['recurrence'] = 'Unknown'
    
    def validate_for_approval(self):
        """
        Validate if this tech stack signal can be approved.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        if not self.tech_stack:
            tech_name = self.get_pending_tech_name() or "Unknown"
            return (False, f"Tech stack is required for approval (for: {tech_name})")
        
        return (True, None)
    
    def __str__(self):
        tech_name = self.tech_stack.tech_name if self.tech_stack else "Unknown"
        return f"Tech: {tech_name} - {self.get_field_name_display()} [{self.get_status_display()}]"
    
    def get_pending_tech_name(self):
        """Get the pending tech name from metadata if available"""
        if self.metadata and 'pending_tech_name' in self.metadata:
            return self.metadata['pending_tech_name']
        return None