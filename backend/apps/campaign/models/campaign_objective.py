# apps/campaign/models/campaign_objective.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class CampaignObjective(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a specific objective for a campaign (MVP simplified version)
    """
    class ObjectiveType(models.TextChoices):
        LEADS = 'LEADS', _('Number of Leads')
        MEETINGS = 'MEETINGS', _('Number of Meetings')
        OPPORTUNITIES = 'OPPORTUNITIES', _('Number of Opportunities')
        PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline Value')
        CLOSED_DEALS = 'CLOSED_DEALS', _('Closed Deals')
        REVENUE = 'REVENUE', _('Revenue')
    
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
    
    class Meta:
        verbose_name = _('Campaign Objective')
        verbose_name_plural = _('Campaign Objectives')
        indexes = [
            models.Index(fields=['campaign', 'is_primary']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign'],
                condition=models.Q(is_primary=True),
                name='unique_primary_objective_per_campaign'
            )
        ]
        
    def __str__(self):
        primary_indicator = " (Primary)" if self.is_primary else ""
        return f"{self.campaign.name} - {self.name}: {self.target_value}{primary_indicator}"
    
    def clean(self):
        """Simple validation for MVP"""
        super().clean()
        
        if self.target_value <= 0:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Target Value (must be greater than 0)")
            )
        
    def save(self, *args, **kwargs):
        """Simple save with primary objective logic"""
        # Run validation
        self.full_clean()
        
        # If this is being set as primary, unset others for this campaign
        if self.is_primary and self.pk:
            type(self).objects.filter(
                campaign=self.campaign, 
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
        
        # Ensure at least one primary objective exists
        if not type(self).objects.filter(campaign=self.campaign, is_primary=True).exists():
            self.is_primary = True
            super().save(update_fields=['is_primary'])
    
    def get_current_value(self):
        """Get current value from campaign tracking (calculated dynamically)"""
        try:
            tracking = self.campaign.get_or_create_result_tracking()
            
            if self.objective_type == self.ObjectiveType.LEADS:
                return tracking.leads_created_count
            elif self.objective_type == self.ObjectiveType.MEETINGS:
                return tracking.meetings_secured_count
            elif self.objective_type == self.ObjectiveType.OPPORTUNITIES:
                return tracking.opportunities_created_count
            elif self.objective_type == self.ObjectiveType.CLOSED_DEALS:
                return tracking.deals_closed_count
            elif self.objective_type == self.ObjectiveType.PIPELINE_VALUE:
                return float(tracking.pipeline_value_created)
            elif self.objective_type == self.ObjectiveType.REVENUE:
                return float(tracking.revenue_generated)
            
            return 0
        except Exception:
            return 0
    
    def get_progress_percentage(self):
        """Calculate progress percentage (simple helper for templates)"""
        try:
            current = self.get_current_value()
            target = float(self.target_value)
            if target == 0:
                return 0
            return min(100, (current / target) * 100)
        except Exception:
            return 0