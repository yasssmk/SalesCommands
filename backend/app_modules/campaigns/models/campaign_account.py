# app_modules/campaigns/models/campaign_account.py
"""
CampaignAccount pivot model.

Replaces legacy polymorphic CampaignTarget with a single, clean pivot
centered on CompanyAccount. Each CampaignAccount represents one account
enrolled in a campaign, with optional department/contact filters.

State machine: PENDING → IN_PROGRESS → CALLBACK_PENDING → COMPLETED / STOPPED
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages


class CampaignAccountStatus(models.TextChoices):
    """CampaignAccount lifecycle status."""
    PENDING = 'PENDING', _('Pending')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
    CALLBACK_PENDING = 'CALLBACK_PENDING', _('Callback Pending')
    COMPLETED = 'COMPLETED', _('Completed')
    STOPPED = 'STOPPED', _('Stopped')


# Valid state transitions
CAMPAIGN_ACCOUNT_TRANSITIONS = {
    CampaignAccountStatus.PENDING: [
        CampaignAccountStatus.IN_PROGRESS,
        CampaignAccountStatus.STOPPED,
    ],
    CampaignAccountStatus.IN_PROGRESS: [
        CampaignAccountStatus.CALLBACK_PENDING,
        CampaignAccountStatus.COMPLETED,
        CampaignAccountStatus.STOPPED,
    ],
    CampaignAccountStatus.CALLBACK_PENDING: [
        CampaignAccountStatus.IN_PROGRESS,
        CampaignAccountStatus.COMPLETED,
        CampaignAccountStatus.STOPPED,
    ],
    CampaignAccountStatus.COMPLETED: [],
    CampaignAccountStatus.STOPPED: [],
}

FINAL_STATES = {CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED}


class CampaignAccount(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Pivot linking a Campaign to a CompanyAccount.

    Each row = one account enrolled in one campaign.
    Optional M2M filters narrow execution to specific departments/contacts.

    Features:
        - State machine for per-account progress tracking
        - Optional department/contact targeting
        - Callback scheduling
        - Activity generation tracking
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """

    # ==========================================================================
    # CORE RELATIONSHIPS
    # ==========================================================================

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name='campaign_accounts',
        verbose_name=_('Campaign')
    )

    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='campaign_enrollments',
        verbose_name=_('Account')
    )

    # ==========================================================================
    # OPTIONAL TARGETING FILTERS
    # ==========================================================================

    target_departments = models.ManyToManyField(
        'core_modules.StandardDepartment',
        related_name='campaign_account_targets',
        blank=True,
        verbose_name=_('Target Departments'),
        help_text=_('Optional: narrow activities to these departments')
    )

    target_contacts = models.ManyToManyField(
        'module_contacts.Contact',
        related_name='campaign_account_targets',
        blank=True,
        verbose_name=_('Target Contacts'),
        help_text=_('Optional: narrow activities to these contacts')
    )

    # ==========================================================================
    # STATUS & TRACKING
    # ==========================================================================

    status = models.CharField(
        max_length=20,
        choices=CampaignAccountStatus.choices,
        default=CampaignAccountStatus.PENDING,
        verbose_name=_('Status')
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('TARGETED: specific reason / context for this account')
    )

    callback_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Callback Date'),
        help_text=_('Scheduled callback date when in CALLBACK_PENDING')
    )

    activities_generated = models.BooleanField(
        default=False,
        verbose_name=_('Activities Generated'),
        help_text=_('Whether sequence activities have been generated for this account')
    )

    no_answer_count = models.IntegerField(
        default=0,
        verbose_name=_('No Answer Count'),
        help_text=_('Number of unanswered call attempts')
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['campaign', 'account'],
        index_fields=['status']
    )):
        db_table = 'module_campaign_accounts'
        verbose_name = _('Campaign Account')
        verbose_name_plural = _('Campaign Accounts')
        ordering = ['campaign', 'created_at']
        indexes = [
            models.Index(fields=['campaign', 'status'], name='mod_ca_camp_status_idx'),
            models.Index(fields=['account'], name='mod_ca_account_idx'),
        ]

    def __str__(self):
        account_name = getattr(self.account, 'company_name', 'Unknown')
        return f"{account_name} in {self.campaign.name} ({self.get_status_display()})"

    # ==========================================================================
    # PROPERTIES
    # ==========================================================================

    @property
    def is_in_final_state(self):
        """Check if this account is in a terminal state."""
        return self.status in FINAL_STATES

    # ==========================================================================
    # STATE MACHINE
    # ==========================================================================

    def _validate_transition(self, new_status):
        """Validate a status transition is allowed."""
        if self.is_in_final_state:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.ACCOUNT_FINAL_STATE.format(
                    state=self.get_status_display()
                )
            )

        allowed = CAMPAIGN_ACCOUNT_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            allowed_display = ', '.join(allowed) if allowed else 'none'
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.ACCOUNT_TRANSITION_INVALID.format(
                    from_state=self.status,
                    to_state=new_status,
                    allowed_transitions=allowed_display,
                )
            )

    def update_status(self, new_status, notes=None, user=None):
        """
        Transition to a new status with validation.

        Args:
            new_status: Target CampaignAccountStatus value
            notes: Optional notes for the transition
            user: User performing the action (for audit)

        Returns:
            dict: Transition result summary
        """
        old_status = self.status
        self._validate_transition(new_status)

        self.status = new_status
        if notes:
            self.notes = notes
        self.save(user=user)

        return {
            'campaign_account_id': str(self.id),
            'from_status': old_status,
            'to_status': new_status,
            'is_final_state': self.is_in_final_state,
            'timestamp': timezone.now().isoformat(),
        }

    # ==========================================================================
    # CONVENIENCE METHODS
    # ==========================================================================

    def start_progress(self, user=None, notes=None):
        """PENDING → IN_PROGRESS."""
        return self.update_status(
            CampaignAccountStatus.IN_PROGRESS,
            notes=notes or "Started working on account",
            user=user,
        )

    def request_callback(self, callback_date=None, user=None, notes=None):
        """IN_PROGRESS → CALLBACK_PENDING."""
        if callback_date:
            self.callback_date = callback_date
        return self.update_status(
            CampaignAccountStatus.CALLBACK_PENDING,
            notes=notes or f"Callback requested for {callback_date}",
            user=user,
        )

    def resume_from_callback(self, user=None, notes=None):
        """CALLBACK_PENDING → IN_PROGRESS."""
        self.callback_date = None
        return self.update_status(
            CampaignAccountStatus.IN_PROGRESS,
            notes=notes or "Resumed from callback",
            user=user,
        )

    def mark_completed(self, user=None, notes=None):
        """IN_PROGRESS / CALLBACK_PENDING → COMPLETED."""
        return self.update_status(
            CampaignAccountStatus.COMPLETED,
            notes=notes or "Account completed",
            user=user,
        )

    def mark_stopped(self, reason=None, user=None, notes=None):
        """Any non-final → STOPPED."""
        stop_notes = f"Stopped: {reason}" if reason else "Account stopped"
        if notes:
            stop_notes += f" - {notes}"
        return self.update_status(
            CampaignAccountStatus.STOPPED,
            notes=stop_notes,
            user=user,
        )

    def mark_activities_generated(self, user=None):
        """Flag that sequence activities have been created for this account."""
        self.activities_generated = True
        self.save(user=user)

    def increment_no_answer(self, user=None):
        """Increment the no-answer counter."""
        self.no_answer_count += 1
        self.save(user=user)