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

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages


from ..constants import CampaignType, CampaignStatus, ChannelOverride, CAMPAIGN_STATUS_TRANSITIONS


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

    channel_override = models.CharField(
        max_length=20,
        choices=ChannelOverride.choices,
        default=ChannelOverride.AUTO,
        verbose_name=_('Channel Override'),
        help_text=_(
            'AUTO = backend selects variant per contact channels. '
            'NO_CALLS = never call; email or LinkedIn only.'
        )
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

    planned_start_date = models.DateField(
        verbose_name=_('Planned Start Date'),
        help_text=_('User-defined campaign start date')
    )

    planned_end_date = models.DateField(
        verbose_name=_('Planned End Date'),
        help_text=_('User-defined campaign end date')
    )

    actual_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Actual Start Date'),
        help_text=_('Auto-set when campaign is started')
    )

    actual_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Actual End Date'),
        help_text=_('Auto-set when campaign is completed or last activity is done')
    )

    # ==========================================================================
    # OWNERSHIP
    # ==========================================================================

    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.PROTECT,
        related_name='module_owned_campaigns',
        verbose_name=_('Owner'),
        help_text=_('User who created and manages this campaign'),
    )

    executor = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='module_executing_campaigns',
        verbose_name=_('Executor'),
        help_text=_('User who executes activities. Defaults to owner if not set.'),
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
        index_fields=['status']
    )):
        db_table = 'module_campaigns'
        verbose_name = _('Campaign')
        verbose_name_plural = _('Campaigns')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign_type'], name='mod_camp_type_idx'),
            models.Index(fields=['planned_start_date', 'planned_end_date'], name='mod_camp_dates_idx'),
        ]
        constraints = [
            # One TARGETED campaign per user per client
            models.UniqueConstraint(
                fields=['client_id', 'campaign_type', 'owner'],
                condition=models.Q(campaign_type='TARGETED'),
                name='unique_targeted_campaign_per_user',
            ),
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
    def is_targeted(self):
        """Check if this campaign is a TARGETED singleton campaign."""
        return self.campaign_type == CampaignType.TARGETED

    @property
    def is_in_final_state(self):
        """Check if campaign is in a terminal state."""
        return self.status in (CampaignStatus.COMPLETED, CampaignStatus.CANCELLED)

    @property
    def is_modifiable(self):
        """Check if campaign can be modified."""
        return self.status in (CampaignStatus.DRAFT, CampaignStatus.ACTIVE, CampaignStatus.PAUSED)
    
    @property
    def active_executor(self):
        """Return executor if set, otherwise owner."""
        return self.executor or self.owner

    # ==========================================================================
    # DISPLAY HELPERS
    # ==========================================================================

    def get_sequence_type_display_safe(self):
        """Sequence type display with safe fallback."""
        if not self.sequence_type:
            return "No Sequence"

        try:
            from app_modules.sequences.sequence_dispatcher import SequenceDispatcher
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
        """Complete the campaign (ACTIVE/PAUSED → COMPLETED).

        TARGETED campaigns are perpetual and must never reach a terminal state.
        This model-level guard backs up the view (_assert_not_targeted) and
        signal frontiers so a direct model call cannot break the invariant.
        """
        if self.is_targeted:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.TARGETED_CAMPAIGN_COMPLETE_FORBIDDEN
            )
        self.transition_to(CampaignStatus.COMPLETED, user=user)

    def cancel(self, user=None):
        """Cancel the campaign (any non-final → CANCELLED).

        TARGETED campaigns are perpetual and must never reach a terminal state
        (see complete() — same model-level backstop).
        """
        if self.is_targeted:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.TARGETED_CAMPAIGN_CANCEL_FORBIDDEN
            )
        self.transition_to(CampaignStatus.CANCELLED, user=user)

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    def clean(self):
        """Validate campaign data."""
        super().clean()

        if self.planned_end_date and self.planned_start_date and self.planned_end_date < self.planned_start_date:
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

        member = CampaignMember(
            campaign=self,
            user=user,
            role=role,
            is_primary_owner=is_primary_owner,
            added_by=added_by,
        )
        member.save(user=added_by, client_id=self.client_id)
        return member

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