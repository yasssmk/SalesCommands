# app_modules/campaigns/models/campaign_member.py
"""
CampaignMember model — links users to campaigns with specific roles.

Replaces legacy CampaignStakeholder with clearer naming and
an explicit is_primary_owner flag (replaces legacy Campaign.owner FK).

4 roles:
- OWNER: Creator/pilot, sees everything, manages lifecycle
- EXECUTOR: Sales rep on their own accounts (account_owner == user)
- RECEIVER: Sales rep on delegated accounts (cross-product assignment)
- OBSERVER: Manager/Marketing, dashboard only, no activities
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager


class CampaignMember(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Junction table linking campaigns to users with specific roles.

    Features:
        - 4 distinct roles for cross-product team assignments
        - is_primary_owner flag (exactly one per campaign)
        - added_by tracking for audit
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """

    class MemberRole(models.TextChoices):
        OWNER = 'OWNER', _('Campaign Owner')
        EXECUTOR = 'EXECUTOR', _('Executor')
        RECEIVER = 'RECEIVER', _('Receiver')
        OBSERVER = 'OBSERVER', _('Observer')

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('Campaign')
    )

    user = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='campaign_memberships',
        verbose_name=_('User')
    )

    # ==========================================================================
    # ROLE & FLAGS
    # ==========================================================================

    role = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
        default=MemberRole.OBSERVER,
        verbose_name=_('Role')
    )

    is_primary_owner = models.BooleanField(
        default=False,
        verbose_name=_('Is Primary Owner'),
        help_text=_('Exactly one member per campaign should be the primary owner')
    )

    # ==========================================================================
    # AUDIT
    # ==========================================================================

    added_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Added At')
    )

    added_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='+',
        null=True,
        blank=True,
        verbose_name=_('Added By')
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['campaign', 'user', 'role'],
        index_fields=['role']
    )):
        db_table = 'module_campaign_members'
        verbose_name = _('Campaign Member')
        verbose_name_plural = _('Campaign Members')
        ordering = ['campaign', 'role', 'added_at']
        indexes = [
            models.Index(fields=['campaign', 'role'], name='mod_cm_camp_role_idx'),
            models.Index(fields=['user', 'role'], name='mod_cm_user_role_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign'],
                condition=models.Q(is_primary_owner=True),
                name='unique_primary_owner_per_campaign'
            ),
        ]

    def __str__(self):
        user_name = getattr(self.user, 'email', 'Unknown')
        return f"{user_name} - {self.get_role_display()} for {self.campaign.name}"