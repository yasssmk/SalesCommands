# apps/campaign/models/campaign_target.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages

class CampaignTarget(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Links accounts to campaigns as targets for outreach
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        MEETING_SECURED = 'MEETING_SECURED', _('Meeting Secured')
        OPPORTUNITY_CREATED = 'OPPORTUNITY_CREATED', _('Opportunity Created')
        COMPLETED = 'COMPLETED', _('Completed')
        STOPPED = 'STOPPED', _('Stopped')
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='targets',
        verbose_name=_('Campaign')
    )
    
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Account')
    )
    
    # Status tracking
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    
    sequence_created = models.BooleanField(
        default=False,
        verbose_name=_('Sequence Created')
    )
    
    # Basic expected value
    expected_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Expected Value')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    # Opportunity connection
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='campaign_targets',
        null=True,
        blank=True,
        verbose_name=_('Linked Opportunity')
    )
    
    class Meta:
        verbose_name = _('Campaign Target')
        verbose_name_plural = _('Campaign Targets')
        unique_together = ('campaign', 'account')
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['sequence_created']),
        ]

    def __str__(self):
        return f"{self.campaign.name} - {self.account.company_name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def mark_sequence_created(self, save=True):
        """Mark that a sequence has been created for this target"""
        self.sequence_created = True
        
        if save:
            self.save()
    
    def update_status(self, new_status, save=True):
        """
        Update the status
        
        Args:
            new_status (str): New status value
            save (bool): Whether to save the instance
        """
        self.status = new_status
        
        if save:
            self.save()
    
    def link_opportunity(self, opportunity, save=True):
        """Link an opportunity to this target"""
        self.opportunity = opportunity
        self.update_status(self.Status.OPPORTUNITY_CREATED, save=False)
        
        if save:
            self.save()