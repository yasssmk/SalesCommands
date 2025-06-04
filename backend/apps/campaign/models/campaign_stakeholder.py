# apps/campaign/models/campaign_stakeholder.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp


class CampaignStakeholder(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Junction table linking campaigns to users with specific roles
    """
    class StakeholderRole(models.TextChoices):
        OWNER = 'OWNER', _('Campaign Owner')
        EXECUTOR = 'EXECUTOR', _('Executor')
        RECEIVER = 'RECEIVER', _('Receiver ')
        OBSERVER = 'OBSERVER', _('Observer')
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='stakeholder_links', 
        verbose_name=_('Campaign')
    )
    
    user = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='campaign_roles',
        verbose_name=_('User')
    )
    
    role = models.CharField(
        max_length=20,
        choices=StakeholderRole.choices,
        default=StakeholderRole.OBSERVER,
        verbose_name=_('Role')
    )
    
    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Added At')
    )

    added_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='+',  # No reverse relation
        null=True,
        blank=True,
        verbose_name=_('Added By')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['campaign', 'user', 'role'],
        index_fields=['role']
    )):
        verbose_name = _('Campaign Stakeholder')
        verbose_name_plural = _('Campaign Stakeholders')
        ordering = ['campaign', 'role']
        indexes = [
            models.Index(fields=['campaign', 'role']),
            models.Index(fields=['user', 'role']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_role_display()} for {self.campaign.name}"