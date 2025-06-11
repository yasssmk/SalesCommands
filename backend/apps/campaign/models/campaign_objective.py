# apps/campaign/models/campaign_objective.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages

class CampaignObjective(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a specific objective for a campaign.
    This allows for multiple and custom objectives per campaign.
    """
    class ObjectiveType(models.TextChoices):
        LEADS = 'LEADS', _('Number of Leads')
        MEETINGS = 'MEETINGS', _('Number of Meetings')
        OPPORTUNITIES = 'OPPORTUNITIES', _('Number of Opportunities')
        PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline Value')
        CLOSED_DEALS = 'CLOSED_DEALS', _('Closed Deals')
        REVENUE = 'REVENUE', _('Revenue')
        CUSTOM = 'CUSTOM', _('Custom Objective')
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='objectives',
        verbose_name=_('Campaign')
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Objective Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    objective_type = models.CharField(
        max_length=30,
        choices=ObjectiveType.choices,
        verbose_name=_('Objective Type')
    )
    
    target_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Target Value')
    )
    
    current_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name=_('Current Value')
    )
    
    unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Unit of Measurement')
    )
    
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_('Is Primary Objective')
    )
    
    # For tracking when objective was last updated
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Updated')
    )
    
    class Meta:
        verbose_name = _('Campaign Objective')
        verbose_name_plural = _('Campaign Objectives')
        indexes = [
            models.Index(fields=['campaign', 'objective_type']),
            models.Index(fields=['is_primary']),
        ]
        
    def __str__(self):
        return f"{self.campaign.name} - {self.name}: {self.current_value}/{self.target_value}"
    
    def clean(self):
        """Validate objective data using standardized validation"""
        super().clean()
        
        try:
            # Validate numeric values
            if self.target_value <= 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Target Value (must be greater than 0)")
                )
            
            # Ensure current value is not negative
            if self.current_value < 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Current Value (cannot be negative)")
                )
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective validation failed")
            )
        
    def save(self, *args, **kwargs):
        """Save with standardized validation and business logic"""
        try:
            # Run clean validation first
            self.full_clean()
            
            # Ensure current value is not negative (auto-correct)
            if self.current_value < 0:
                self.current_value = 0
                
            # Check if this is the first objective for this campaign
            is_first = not type(self).objects.filter(campaign=self.campaign).exists()
            
            # Make first objective primary by default
            if is_first:
                self.is_primary = True
            
            # If this is being set as primary, unset others
            if self.is_primary:
                # Only update DB if the instance already exists
                if self.pk:
                    type(self).objects.filter(
                        campaign=self.campaign, 
                        is_primary=True
                    ).exclude(
                        pk=self.pk
                    ).update(is_primary=False)
            
            super().save(*args, **kwargs)
            
            # If no primary objective exists for this campaign after save, make this one primary
            if not type(self).objects.filter(campaign=self.campaign, is_primary=True).exists():
                self.is_primary = True
                super().save(update_fields=['is_primary'])
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Objective save failed")
            )
            
    def progress_percentage(self):
        """Calculate progress as a percentage"""
        try:
            if self.target_value == 0:
                return 0
            return min(100, (self.current_value / self.target_value) * 100)
        except Exception:
            # Return 0 if calculation fails
            return 0
    
    def update_progress(self, new_value, increment=False):
        """
        Update the current value of this objective
        
        Args:
            new_value (Decimal/float): The new value to set or add
            increment (bool): If True, add to current value; if False, set as new value
            
        Returns:
            float: Updated progress percentage
            
        Raises:
            StandardizedValidationError: If validation fails
        """
        try:
            # Validate new_value
            if new_value is None:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Progress value")
                )
                
            # Convert to decimal for validation
            from decimal import Decimal
            try:
                new_value = Decimal(str(new_value))
            except (ValueError, TypeError, TypeError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Progress value (must be a number)")
                )
            
            # Validate value is not negative
            if new_value < 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="Progress value (cannot be negative)")
                )
            
            # Update the value
            if increment:
                self.current_value += new_value
            else:
                self.current_value = new_value
                
            # Save and return progress
            self.save()
            return self.progress_percentage()
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Progress update failed")
            )