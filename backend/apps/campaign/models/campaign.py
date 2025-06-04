# apps/campaign/models/campaign.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import ValidationError
from core.error_messages import CoreErrorMessages
from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
from django.db.models import Q

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
        choices=SequenceDispatcher.SEQUENCE_CHOICES,
        default=None,
        blank=True,
        null=True,
        verbose_name=_('Sequence Type'),
        help_text=_('Leave empty for campaigns without automated sequences (e.g., call lists)')
    )
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,  
        related_name='owned_campaigns',
        null=True,  # Make it nullable
        blank=True,  # Allow blank in forms
        verbose_name=_('Campaign Owner (Legacy)')
    )
    
    # Add this field to establish the M2M relationship
    stakeholders = models.ManyToManyField(
    'end_users.User',
    through='campaign.CampaignStakeholder',
    through_fields=('campaign', 'user'),  # Specify which fields to use
    related_name='participated_campaigns',  # Change related_name to avoid clash
    verbose_name=_('Stakeholders')
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
    
    def add_stakeholder(self, user, role, added_by=None):
        """
        Add a stakeholder to this campaign with a specific role
        
        Args:
            user: The user to add
            role: The role to assign (from CampaignStakeholder.StakeholderRole)
            added_by: The user who is adding this stakeholder
            
        Returns:
            The created CampaignStakeholder instance
        """
        from .campaign_stakeholder import CampaignStakeholder
        
        # Check if this user already has this role
        existing = CampaignStakeholder.objects.filter(
            campaign=self,
            user=user,
            role=role
        ).first()
        
        if existing:
            return existing
            
        # Create new stakeholder
        return CampaignStakeholder.objects.create(
            campaign=self,
            user=user,
            role=role,
            added_by=added_by,
            client_id=self.client_id
        )
    
    def remove_stakeholder(self, user, role=None):
        """
        Remove a stakeholder from this campaign
        
        Args:
            user: The user to remove (if None, removes all users with the given role)
            role: The role to remove (if None, removes all roles for the given user)
            
        Returns:
            int: Number of stakeholders removed
        """
        from .campaign_stakeholder import CampaignStakeholder
        
        query = Q(campaign=self)
        
        if user:
            query &= Q(user=user)
            
        if role:
            query &= Q(role=role)
            
        return CampaignStakeholder.objects.filter(query).delete()[0]
    
    def get_stakeholders_by_role(self, role):
        """
        Get all stakeholders with a specific role
        
        Args:
            role: The role to filter by (from CampaignStakeholder.StakeholderRole)
            
        Returns:
            QuerySet of User objects with the specified role
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        return User.objects.filter(
            campaign_roles__campaign=self,
            campaign_roles__role=role
        )
    
    def get_owners(self):
        """Get campaign owners"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.OWNER)
    
    def get_executors(self):
        """Get campaign executors"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.EXECUTOR)
    
    def get_receivers(self):
        """Get campaign receivers"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.RECEIVER)
    
        
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

        # If this is a new campaign and owner is set, add owner as OWNER stakeholder
        if self.owner and not hasattr(self, '_owner_added_as_stakeholder'):
            from .campaign_stakeholder import CampaignStakeholder
            self.add_stakeholder(self.owner, CampaignStakeholder.StakeholderRole.OWNER)
            self._owner_added_as_stakeholder = True