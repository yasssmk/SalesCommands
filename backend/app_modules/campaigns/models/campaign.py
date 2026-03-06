# app_modules/campaigns/models/campaign.py
"""
Campaign model for the new Campaign module.

Two campaign types:
- OUTBOUND: Territory-based prospection with automated sequences
- TARGETED: Manual account selection, no auto-sequence

Lifecycle: DRAFT → ACTIVE → PAUSED → COMPLETED / CANCELLED
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages, CoreErrorMessages


class CampaignType(models.TextChoices):
    """Campaign type choices."""
    OUTBOUND = 'OUTBOUND', _('Outbound Campaign')
    TARGETED = 'TARGETED', _('Targeted Campaign')


class CampaignStatus(models.TextChoices):
    """Campaign lifecycle status choices."""
    DRAFT = 'DRAFT', _('Draft')
    ACTIVE = 'ACTIVE', _('Active')
    PAUSED = 'PAUSED', _('Paused')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')


# Valid state transitions
CAMPAIGN_STATUS_TRANSITIONS = {
    CampaignStatus.DRAFT: [CampaignStatus.ACTIVE, CampaignStatus.CANCELLED],
    CampaignStatus.ACTIVE: [CampaignStatus.PAUSED, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED],
    CampaignStatus.PAUSED: [CampaignStatus.ACTIVE, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED],
    CampaignStatus.COMPLETED: [],
    CampaignStatus.CANCELLED: [],
}


class Campaign(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Campaign model — execution engine for sales activities.

    OUTBOUND campaigns pull accounts from a Territory and generate
    sequenced activities (via SequenceDispatcher).
    TARGETED campaigns work on manually selected accounts with
    manual or single-step activities.

    Features:
        - Territory-based or manual account targeting
        - Automated sequence support (optional)
        - Lifecycle state machine (DRAFT → ACTIVE → ...)
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """

    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================

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
        verbose_name=_('Campaign Type'),
        help_text=_('OUTBOUND = territory-based, TARGETED = manual account selection')
    )

    sequence_type = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        verbose_name=_('Sequence Type'),
        help_text=_('Automated sequence pattern. NULL for campaigns without sequences.')
    )

    # ==========================================================================
    # TERRITORY RELATIONSHIP (source of accounts for OUTBOUND)
    # ==========================================================================

    territories = models.ManyToManyField(
        'module_territories.Territory',
        related_name='campaigns',
        blank=True,
        verbose_name=_('Territories'),
        help_text=_('Source territories for OUTBOUND campaigns')
    )

    # ==========================================================================
    # DATES
    # ==========================================================================

    start_date = models.DateField(
        verbose_name=_('Start Date')
    )

    end_date = models.DateField(
        verbose_name=_('End Date')
    )

    # ==========================================================================
    # STATUS
    # ==========================================================================

    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
        verbose_name=_('Status')
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['name'],
        index_fields=['status']
    )):
        db_table = 'module_campaigns'
        verbose_name = _('Campaign')
        verbose_name_plural = _('Campaigns')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign_type'], name='mod_camp_type_idx'),
            models.Index(fields=['start_date', 'end_date'], name='mod_camp_dates_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"

    # ==========================================================================
    # PROPERTIES
    # ==========================================================================

    @property
    def has_sequence(self):
        """Check if this campaign uses automated sequences."""
        return self.sequence_type is not None

    @property
    def is_in_final_state(self):
        """Check if campaign is in a terminal state."""
        return self.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED)

    @property
    def is_modifiable(self):
        """Check if campaign can be modified."""
        return self.status in (CampaignStatus.DRAFT, CampaignStatus.ACTIVE, CampaignStatus.PAUSED)

    # ==========================================================================
    # DISPLAY HELPERS
    # ==========================================================================

    def get_sequence_type_display_safe(self):
        """Sequence type display with safe fallback."""
        if not self.sequence_type:
            return "No Sequence"

        try:
            from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
            for choice in SequenceDispatcher.SEQUENCE_CHOICES:
                if choice[0] == self.sequence_type:
                    return choice[1]
        except (ImportError, AttributeError):
            pass

        return self.sequence_type.replace('_', ' ').title()

    # ==========================================================================
    # STATE MACHINE
    # ==========================================================================

    def _validate_transition(self, new_status):
        """Validate a status transition is allowed."""
        allowed = CAMPAIGN_STATUS_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_TRANSITION_INVALID.format(
                    from_state=self.get_status_display(),
                    to_state=new_status
                )
            )

    def transition_to(self, new_status, user=None):
        """
        Transition campaign to a new status.

        Args:
            new_status: Target CampaignStatus value
            user: User performing the transition (for audit)
        """
        self._validate_transition(new_status)
        self.status = new_status
        self.save(user=user)

    def start(self, user=None):
        """Start the campaign (DRAFT → ACTIVE)."""
        self.transition_to(CampaignStatus.ACTIVE, user=user)

    def pause(self, user=None):
        """Pause the campaign (ACTIVE → PAUSED)."""
        self.transition_to(CampaignStatus.PAUSED, user=user)

    def resume(self, user=None):
        """Resume the campaign (PAUSED → ACTIVE)."""
        self.transition_to(CampaignStatus.ACTIVE, user=user)

    def complete(self, user=None):
        """Complete the campaign (ACTIVE/PAUSED → COMPLETED)."""
        self.transition_to(CampaignStatus.COMPLETED, user=user)

    def cancel(self, user=None):
        """Cancel the campaign (any non-final → CANCELLED)."""
        self.transition_to(CampaignStatus.CANCELLED, user=user)

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    def clean(self):
        """Validate campaign data."""
        super().clean()

        # Date range validation
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_DATE_INVALID
            )

        # OUTBOUND requires at least one territory
        if self.campaign_type == CampaignType.OUTBOUND and self.pk and not self.territories.exists():
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CAMPAIGN_TERRITORY_REQUIRED
            )


    # ==========================================================================
    # MEMBER HELPERS (delegates to CampaignMember)
    # ==========================================================================

    def add_member(self, user, role, added_by=None, is_primary_owner=False):
        """
        Add a member to this campaign.

        Args:
            user: User to add
            role: Member role (OWNER, EXECUTOR, RECEIVER, OBSERVER)
            added_by: User performing the action
            is_primary_owner: Whether this is the primary owner

        Returns:
            CampaignMember instance
        """
        from .campaign_member import CampaignMember

        existing = CampaignMember.objects.filter(
            campaign=self, user=user, role=role
        ).first()
        if existing:
            return existing

        return CampaignMember.objects.create(
            campaign=self,
            user=user,
            role=role,
            is_primary_owner=is_primary_owner,
            added_by=added_by,
            client_id=self.client_id,
        )

    def remove_member(self, user, role=None):
        """
        Remove member(s) from this campaign.

        Args:
            user: User to remove
            role: Optional specific role to remove (removes all roles if None)

        Returns:
            int: Number of members removed
        """
        from .campaign_member import CampaignMember
        from django.db.models import Q

        query = Q(campaign=self, user=user)
        if role:
            query &= Q(role=role)

        return CampaignMember.objects.filter(query).delete()[0]

    def get_members_by_role(self, role):
        """Get all users with a specific role in this campaign."""
        from .campaign_member import CampaignMember
        from end_users.models import User

        user_ids = CampaignMember.objects.filter(
            campaign=self, role=role
        ).values_list('user_id', flat=True)

        return User.objects.filter(id__in=user_ids)

    def get_owners(self):
        """Get campaign owners."""
        from .campaign_member import CampaignMember
        return self.get_members_by_role(CampaignMember.MemberRole.OWNER)

    def get_executors(self):
        """Get campaign executors."""
        from .campaign_member import CampaignMember
        return self.get_members_by_role(CampaignMember.MemberRole.EXECUTOR)

    def get_receivers(self):
        """Get campaign receivers."""
        from .campaign_member import CampaignMember
        return self.get_members_by_role(CampaignMember.MemberRole.RECEIVER)

    def get_primary_owner(self):
        """Get the primary owner of this campaign."""
        from .campaign_member import CampaignMember

        primary = CampaignMember.objects.filter(
            campaign=self, role=CampaignMember.MemberRole.OWNER, is_primary_owner=True
        ).select_related('user').first()

        return primary.user if primary else None