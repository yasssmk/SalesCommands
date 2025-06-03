# apps/campaign/models/campaign.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages
from apps.sequence.sequences.sequence_dispatcher import SequenceDisptacher

class Campaign(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a sales campaign with targeting criteria and objectives
    """
    class CampaignType(models.TextChoices):
        HUNTING = 'HUNTING', _('New Account Hunting')
        UPSELL = 'UPSELL', _('Existing Account Upsell')
        FOLLOW_UP = 'FOLLOW_UP', _('Opportunity Follow-up')
        RENEWAL = 'RENEWAL', _('Contract Renewal')
        CHASING = 'CHASING', _('Chasing')
        CALL_LIST = 'CALL_LIST', _('Call List')
        LEAD_NURTURE = 'LEAD_NURTURE', _('Lead Nurturing')
        CUSTOM = 'CUSTOM', _('Custom Campaign')
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Campaign Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    campaign_type = models.CharField(
        max_length=20,
        choices=CampaignType.choices,
        verbose_name=_('Campaign Type')
    )
    
    sequence_type = models.CharField(
        max_length=30,
        choices=SequenceDisptacher.SEQUENCE_CHOICES,
        default=None,
        blank=True,
        null=True,
        verbose_name=_('Sequence Type'),
        help_text=_('Leave empty for campaigns without automated sequences (e.g., call lists)')
    )
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='owned_campaigns',
        verbose_name=_('Campaign Owner')
    )
    
    start_date = models.DateField(
        verbose_name=_('Start Date')
    )
    
    end_date = models.DateField(
        verbose_name=_('End Date')
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('ACTIVE', 'Active'),
            ('PAUSED', 'Paused'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='DRAFT'
    )
    
    class Meta:
        verbose_name = _('Campaign')
        verbose_name_plural = _('Campaigns')
        indexes = [
            models.Index(fields=['owner', 'start_date']),
            models.Index(fields=['campaign_type']),
            models.Index(fields=['sequence_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"
    
    def has_sequence(self):
        """Check if this campaign uses automated sequences"""
        return self.sequence_type is not None
    
    def is_call_list(self):
        """Check if this is a simple call list campaign (no sequences)"""
        return self.sequence_type is None
    
    def get_target_summary(self):
        """Get a summary of target types in this campaign"""
        summary = {
            'accounts': self.targets.filter(account__isnull=False, contact__isnull=True, lead__isnull=True).count(),
            'contacts': self.targets.filter(contact__isnull=False).count(),
            'leads': self.targets.filter(lead__isnull=False).count(),
            'total': self.targets.count()
        }
        return summary
    
    def has_mixed_targets(self):
        """Check if campaign has multiple target types"""
        summary = self.get_target_summary()
        target_types = sum([
            1 if summary['accounts'] > 0 else 0,
            1 if summary['contacts'] > 0 else 0,
            1 if summary['leads'] > 0 else 0
        ])
        return target_types > 1
        
    def save(self, *args, **kwargs):
        # Ensure end date is after start date
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError(
                CoreErrorMessages.INVALID_DATE_RANGE.format(
                    start_date=self.start_date,
                    end_date=self.end_date
                )
            )

        from django.utils import timezone
        today = timezone.now().date()
        if self.end_date and self.end_date < today:
            raise ValidationError(
                _("Campaign end date must be in the future. Current date: {today}, End date: {end_date}").format(
                    today=today,
                    end_date=self.end_date
                )
            )
                
        super().save(*args, **kwargs)