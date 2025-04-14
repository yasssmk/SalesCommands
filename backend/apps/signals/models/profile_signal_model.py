# apps/signals/models/profile_signal_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from .base_signal_model import BaseSignal
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver



class ProfileSignal(BaseSignal):
    """
    Signal model for company profile data.
    Tracks basic company information like size, revenue, etc.
    """
    
    class Field(models.TextChoices):
        COMPANY_SIZE = 'company_size', _('Company Size')
        ANNUAL_REVENUE = 'annual_revenue', _('Annual Revenue')
    
    field_name = models.CharField(
        max_length=50,
        choices=Field.choices,
        verbose_name=_('Profile Field')
    )
    
    class Meta:
        verbose_name = _('Profile Signal')
        verbose_name_plural = _('Profile Signals')
        indexes = [
            models.Index(fields=['account', 'field_name']),
            models.Index(fields=['status']),
        ]
    
    def clean(self):
        """Validate numeric fields"""
        super().clean()
        
        # Convert numeric values to their proper format
        if self.field_name in [self.Field.COMPANY_SIZE, self.Field.ANNUAL_REVENUE]:
            # Allow for strings with numeric values
            if isinstance(self.value, str):
                try:
                    # Try to clean up the string (remove currency symbols, etc.)
                    cleaned_value = self.value.replace('$', '').replace(',', '')
                    # Store as numeric if possible
                    numeric_value = float(cleaned_value)
                    self.value = numeric_value
                except ValueError:
                    # If it's not convertible to a number, keep as is
                    pass
            # For non-numeric, non-string values, raise validation error
            elif not isinstance(self.value, (int, float)):
                raise ValidationError({
                    'value': _(f'{self.get_field_name_display()} should be a numeric value')
                })
            
    
    def __str__(self):
        return f"Profile: {self.get_field_name_display()} [{self.get_status_display()}]"

@receiver(post_save, sender=ProfileSignal)
def update_account_profile_fields(sender, instance, created, **kwargs):
        """
        Update the account's profile fields when a profile signal is saved.
        """
        from apps.accounts.models import Account
        # Only update for approved signals
        if instance.status == ProfileSignal.Status.APPROVED:
            account = instance.account
            
            # Check which field is being updated
            if instance.field_name == ProfileSignal.Field.COMPANY_SIZE:
                if isinstance(instance.value, (int, float)):
                    account.company_size = str(instance.value)
                else:
                    account.company_size = instance.value
                    
            elif instance.field_name == ProfileSignal.Field.ANNUAL_REVENUE:
                if isinstance(instance.value, (int, float)):
                    account.annual_revenue = str(instance.value)
                else:
                    account.annual_revenue = instance.value
            
            # Save the account without triggering the full save logic
            # to avoid potential infinite loops
            Account.objects.filter(id=account.id).update(
                company_size=account.company_size if instance.field_name == ProfileSignal.Field.COMPANY_SIZE else account.company_size,
                annual_revenue=account.annual_revenue if instance.field_name == ProfileSignal.Field.ANNUAL_REVENUE else account.annual_revenue
            )