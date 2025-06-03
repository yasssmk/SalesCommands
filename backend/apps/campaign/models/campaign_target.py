# apps/campaign/models/campaign_target.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages


class CampaignTarget(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Links ONE target (account OR contact OR lead) to a campaign
    A campaign can have many targets of different types
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
        verbose_name=_('Target Account'),
        blank=True,
        null=True
    )
    
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Contact'),
        blank=True,
        null=True
    )
    
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Lead'),
        blank=True,
        null=True
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
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['sequence_created']),
        ]
        constraints = [
            # Ensure unique account per campaign
            models.UniqueConstraint(
                fields=['campaign', 'account'],
                condition=models.Q(contact__isnull=True, lead__isnull=True),
                name='unique_campaign_account_only'
            ),
            # Ensure unique contact per campaign
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                condition=models.Q(contact__isnull=False),
                name='unique_campaign_contact'
            ),
            # Ensure unique lead per campaign
            models.UniqueConstraint(
                fields=['campaign', 'lead'],
                condition=models.Q(lead__isnull=False),
                name='unique_campaign_lead'
            )
        ]

    def __str__(self):
        if self.contact:
            return f"{self.campaign.name} - Contact: {self.contact.first_name} {self.contact.last_name} ({self.get_status_display()})"
        elif self.lead:
            return f"{self.campaign.name} - Lead: {self.lead.title} ({self.get_status_display()})"
        elif self.account:
            return f"{self.campaign.name} - Account: {self.account.company_name} ({self.get_status_display()})"
        return f"{self.campaign.name} - No Target ({self.get_status_display()})"
    
    def clean(self):
        """Validate that exactly one target type is set"""
        super().clean()
        
        target_count = sum([
            bool(self.account),
            bool(self.contact),
            bool(self.lead)
        ])
        
        if target_count == 0:
            raise ValidationError(
                "One target (account, contact, or lead) must be specified"
            )
        
        if target_count > 1:
            raise ValidationError(
                "Only one target type can be specified per campaign target"
            )
    
    def save(self, *args, **kwargs):
        # Run clean validation
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_target_type(self):
        """Return the type of target"""
        if self.contact:
            return 'contact'
        elif self.lead:
            return 'lead'
        elif self.account:
            return 'account'
        return None
    
    def get_target(self):
        """Return the actual target object"""
        if self.contact:
            return self.contact
        elif self.lead:
            return self.lead
        elif self.account:
            return self.account
        return None
    
    def get_target_account(self):
        """Get the account associated with this target"""
        if self.account:
            return self.account
        elif self.contact:
            return self.contact.account
        elif self.lead:
            return self.lead.account
        return None
    
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