# app_modules/campaigns/models/campaign_account.py
"""
CampaignAccount pivot model.

Links a Campaign to a CompanyAccount.
Contact-scoped state (callback, no_answer, activities_generated) has been
moved to CampaignContact. CampaignAccount tracks account-level enrollment only.

State machine: PENDING → IN_PROGRESS → COMPLETED / STOPPED
Account is considered complete when all its CampaignContacts are COMPLETED or STOPPED.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages

from ..constants import CampaignAccountStatus, CAMPAIGN_ACCOUNT_TRANSITIONS, FINAL_ACCOUNT_STATES


class CampaignAccount(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Pivot linking a Campaign to a CompanyAccount.

    Each row = one account enrolled in one campaign.
    Optional M2M filters narrow execution to specific departments/contacts.
    Per-contact progress is tracked in CampaignContact rows.
    """

    # ==========================================================================
    # CORE RELATIONSHIPS
    # ==========================================================================

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name='campaign_accounts',
        verbose_name=_('Campaign'),
    )

    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='campaign_enrollments',
        verbose_name=_('Account'),
    )

    # ==========================================================================
    # OPTIONAL TARGETING FILTERS
    # ==========================================================================

    target_departments = models.ManyToManyField(
        'core_modules.StandardDepartment',
        related_name='campaign_account_targets',
        blank=True,
        verbose_name=_('Target Departments'),
        help_text=_('Optional: narrow activities to these departments'),
    )

    target_contacts = models.ManyToManyField(
        'module_contacts.Contact',
        related_name='campaign_account_targets',
        blank=True,
        verbose_name=_('Target Contacts'),
        help_text=_('Optional: narrow activities to these contacts'),
    )

    # ==========================================================================
    # STATUS & NOTES
    # ==========================================================================

    status = models.CharField(
        max_length=20,
        choices=CampaignAccountStatus.choices,
        default=CampaignAccountStatus.PENDING,
        verbose_name=_('Status'),
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
        help_text=_('Context or reason for this account enrollment'),
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta:
        app_label = 'module_campaigns'
        verbose_name = _('Campaign Account')
        verbose_name_plural = _('Campaign Accounts')
        db_table = 'module_campaign_accounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'status'], name='mod_ca_camp_status_idx'),
            models.Index(fields=['account'],             name='mod_ca_account_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'account', 'client_id'],
                name='unique_campaign_account_client',
            )
        ]

    def __str__(self):
        return f"{self.account} — {self.campaign}"

    # ==========================================================================
    # STATE MACHINE
    # ==========================================================================

    def _validate_transition(self, new_status):
        allowed = CAMPAIGN_ACCOUNT_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.INVALID_STATUS_TRANSITION.format(
                    current=self.status,
                    new=new_status,
                )
            )

    def update_status(self, new_status, notes=None, user=None):
        """Validate and apply a status transition."""
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

    def start_progress(self, user=None, notes=None):
        """PENDING → IN_PROGRESS."""
        return self.update_status(
            CampaignAccountStatus.IN_PROGRESS,
            notes=notes or "Started working on account",
            user=user,
        )

    def mark_completed(self, user=None, notes=None):
        """IN_PROGRESS → COMPLETED."""
        return self.update_status(
            CampaignAccountStatus.COMPLETED,
            notes=notes or "Account completed",
            user=user,
        )

    def mark_stopped(self, reason=None, user=None, notes=None):
        """Any non-final → STOPPED."""
        stop_notes = f"Stopped: {reason}" if reason else "Account stopped"
        if notes:
            stop_notes += f" — {notes}"
        return self.update_status(
            CampaignAccountStatus.STOPPED,
            notes=stop_notes,
            user=user,
        )

    # ==========================================================================
    # HELPERS
    # ==========================================================================

    @property
    def is_in_final_state(self):
        return self.status in FINAL_ACCOUNT_STATES

    def all_contacts_done(self):
        """
        Returns True when every CampaignContact for this account
        is in a final state (COMPLETED or STOPPED).
        Used to auto-complete the account after last contact resolves.
        """
        from app_modules.campaigns.models.campaign_contact import FINAL_CONTACT_STATES
        return not self.campaign_contacts.exclude(
            status__in=FINAL_CONTACT_STATES
        ).exists()

    def revive_if_active(self, user=None):
        """
        TARGETED re-chase support — re-derive the stored status UPWARD when the
        account has regained an active (non-final) contact.

        1A fix: `_check_account_completion` only ever drives the account DOWN to a
        final state; nothing brought it back up when a contact was re-chased. This
        does the missing upward recalc.

        Administrative reset — deliberately BYPASSES CAMPAIGN_ACCOUNT_TRANSITIONS
        (STOPPED/COMPLETED are terminal there), exactly like
        CampaignContact.reactivate(). It is TARGETED-only: OUTBOUND accounts are
        one-shot and must never be revived, so this is a strict no-op for them and
        the shared transition table is left untouched.

        No-op unless ALL hold: the campaign is TARGETED, the account is not already
        IN_PROGRESS, and at least one CampaignContact is non-final. A genuinely
        finished account (every contact final, or zero contacts) is NEVER revived
        (anti-over-correction). Does not touch all_contacts_done() nor the downward
        _check_account_completion.

        Returns the transition dict when it revives, else None.
        """
        from ..constants import CampaignType, CampaignContactStatus  # noqa: F401
        from app_modules.campaigns.models.campaign_contact import FINAL_CONTACT_STATES

        if self.campaign.campaign_type != CampaignType.TARGETED:
            return None
        if self.status == CampaignAccountStatus.IN_PROGRESS:
            return None
        has_active_contact = self.campaign_contacts.exclude(
            status__in=FINAL_CONTACT_STATES
        ).exists()
        if not has_active_contact:
            return None

        previous_status = self.status
        self.status = CampaignAccountStatus.IN_PROGRESS
        self.save(user=user)
        return {
            'previous_status': previous_status,
            'new_status': CampaignAccountStatus.IN_PROGRESS,
        }