# app_modules/campaigns/models/campaign_contact.py
"""
CampaignContact pivot model.

One row per contact enrolled in a CampaignAccount.
Owns all contact-scoped state: status, callback_date, no_answer_count,
activities_generated.

State machine:
    PENDING → IN_PROGRESS → CALLBACK_PENDING → COMPLETED / STOPPED
                         └──────────────────┘ (resume)
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignModuleErrorMessages


class CampaignContactStatus(models.TextChoices):
    """Per-contact lifecycle status within a campaign."""
    PENDING          = 'PENDING',          _('Pending')
    IN_PROGRESS      = 'IN_PROGRESS',      _('In Progress')
    CALLBACK_PENDING = 'CALLBACK_PENDING', _('Callback Pending')
    COMPLETED        = 'COMPLETED',        _('Completed')
    STOPPED          = 'STOPPED',          _('Stopped')


CAMPAIGN_CONTACT_TRANSITIONS = {
    CampaignContactStatus.PENDING: [
        CampaignContactStatus.IN_PROGRESS,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.IN_PROGRESS: [
        CampaignContactStatus.CALLBACK_PENDING,
        CampaignContactStatus.COMPLETED,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.CALLBACK_PENDING: [
        CampaignContactStatus.IN_PROGRESS,
        CampaignContactStatus.COMPLETED,
        CampaignContactStatus.STOPPED,
    ],
    CampaignContactStatus.COMPLETED: [],
    CampaignContactStatus.STOPPED:   [],
}

FINAL_CONTACT_STATES = {
    CampaignContactStatus.COMPLETED,
    CampaignContactStatus.STOPPED,
}


class CampaignContact(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Pivot linking a CampaignAccount to a specific Contact.

    Carries all state that is contact-scoped:
        - status / state machine
        - callback_date
        - no_answer_count
        - activities_generated flag
    """

    # ==========================================================================
    # CORE RELATIONSHIPS
    # ==========================================================================

    campaign_account = models.ForeignKey(
        'module_campaigns.CampaignAccount',
        on_delete=models.CASCADE,
        related_name='campaign_contacts',
        verbose_name=_('Campaign Account'),
    )

    contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.CASCADE,
        related_name='campaign_contacts',
        verbose_name=_('Contact'),
    )

    # ==========================================================================
    # STATUS & TRACKING
    # ==========================================================================

    status = models.CharField(
        max_length=20,
        choices=CampaignContactStatus.choices,
        default=CampaignContactStatus.PENDING,
        verbose_name=_('Status'),
    )

    callback_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Callback Date'),
        help_text=_('Scheduled callback date when status is CALLBACK_PENDING'),
    )

    activities_generated = models.BooleanField(
        default=False,
        verbose_name=_('Activities Generated'),
        help_text=_('Whether sequence activities have been generated for this contact'),
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes'),
    )

    # ==========================================================================
    # META
    # ==========================================================================

    class Meta:
        app_label = 'module_campaigns'
        verbose_name = _('Campaign Contact')
        verbose_name_plural = _('Campaign Contacts')
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['campaign_account', 'contact'],
                name='unique_campaign_account_contact',
            )
        ]

    def __str__(self):
        return f"{self.contact} — {self.campaign_account}"

    # ==========================================================================
    # STATE MACHINE
    # ==========================================================================

    def _transition_to(self, new_status, user=None, notes=None):
        """
        Validate and apply a status transition.
        Raises StandardizedValidationError on invalid transition.
        """
        allowed = CAMPAIGN_CONTACT_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.EXECUTION_FAILED.format(
                    reason=f"Cannot transition contact from '{self.status}' to '{new_status}'"
                )
            )
        self.status = new_status
        if notes:
            self.notes = notes
        self.save(user=user)
        return {
            'previous_status': self.status,
            'new_status': new_status,
        }

    def start_progress(self, user=None):
        """PENDING → IN_PROGRESS."""
        return self._transition_to(CampaignContactStatus.IN_PROGRESS, user=user)

    def request_callback(self, callback_date, user=None, notes=None):
        """IN_PROGRESS → CALLBACK_PENDING. Sets callback_date."""
        if not callback_date:
            raise StandardizedValidationError(
                CampaignModuleErrorMessages.CALLBACK_DATE_REQUIRED
            )
        self.callback_date = callback_date
        return self._transition_to(
            CampaignContactStatus.CALLBACK_PENDING, user=user, notes=notes
        )

    def resume_from_callback(self, user=None, notes=None):
        """CALLBACK_PENDING → IN_PROGRESS. Clears callback_date."""
        result = self._transition_to(
            CampaignContactStatus.IN_PROGRESS, user=user, notes=notes
        )
        self.callback_date = None
        self.save(user=user)
        return result

    def mark_completed(self, user=None, notes=None):
        """→ COMPLETED."""
        return self._transition_to(
            CampaignContactStatus.COMPLETED, user=user, notes=notes
        )

    def mark_stopped(self, user=None, notes=None):
        """→ STOPPED."""
        return self._transition_to(
            CampaignContactStatus.STOPPED, user=user, notes=notes
        )

    def mark_activities_generated(self, user=None):
        """Set activities_generated = True."""
        self.activities_generated = True
        self.save(user=user)

    # ==========================================================================
    # HELPERS
    # ==========================================================================

    @property
    def is_final(self):
        """True when contact has reached a terminal state."""
        return self.status in FINAL_CONTACT_STATES

    @property
    def campaign(self):
        """Shortcut to parent campaign."""
        return self.campaign_account.campaign