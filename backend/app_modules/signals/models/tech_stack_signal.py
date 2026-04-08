# app_modules/signals/models/tech_stack_signal.py
"""
TechStackSignal — concrete signal for technology stack data.

Captures structured intelligence about a tool used by the account,
as expressed during a conversation.

One signal = one tool observation on one account.
tech_name holds the tool name as mentioned in the transcript — free text,
no FK to any TechStack entity.

source_contact and source_activity are required — enforced in clean().
canonical_key is auto-computed in save() as "tech:{tech_name.lower().strip()}"
when tech_name is not empty.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import TechCategory, Satisfaction


class TechStackSignal(BaseSignal):
    """
    Concrete signal for technology stack data.

    Captures what tool the account uses, how they use it, how satisfied
    they are, what its limitations are, and when the contract renews.

    canonical_key is computed as "tech:{tech_name.lower().strip()}"
    when tech_name is set, enabling corroboration across observations
    of the same tool at the same account.
    """

    # =========================================================================
    # TOOL IDENTIFICATION
    # =========================================================================

    tech_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Tech Name'),
        help_text=_(
            'Name of the tool as mentioned in the conversation. '
            'Free text — no FK to a canonical entity.'
        )
    )

    category = models.CharField(
        max_length=20,
        choices=TechCategory.choices,
        null=True,
        blank=True,
        verbose_name=_('Category'),
        help_text=_('Technology category of this tool')
    )

    # =========================================================================
    # USAGE & SATISFACTION
    # =========================================================================

    usage = models.TextField(
        blank=True,
        verbose_name=_('Usage'),
        help_text=_('What the account uses this tool for')
    )

    satisfaction = models.CharField(
        max_length=10,
        choices=Satisfaction.choices,
        null=True,
        blank=True,
        verbose_name=_('Satisfaction'),
        help_text=_('Satisfaction level expressed during the conversation')
    )

    # =========================================================================
    # FRICTION
    # =========================================================================

    limitations = models.TextField(
        blank=True,
        verbose_name=_('Limitations'),
        help_text=_('What does not work or frustrates the account with this tool')
    )

    workarounds = models.TextField(
        blank=True,
        verbose_name=_('Workarounds'),
        help_text=_('How the account compensates for the limitations of this tool')
    )

    # =========================================================================
    # INTEGRATIONS & CONTRACT
    # =========================================================================

    integrations = models.TextField(
        blank=True,
        verbose_name=_('Integrations'),
        help_text=_('Other tools this one connects to, as mentioned in conversation')
    )

    renewal_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Renewal Date'),
        help_text=_('When the contract for this tool renews')
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_tech_stack'
        verbose_name = _('Tech Stack Signal')
        verbose_name_plural = _('Tech Stack Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],           name='tsig_account_idx'),
            models.Index(fields=['category'],          name='tsig_category_idx'),
            models.Index(fields=['satisfaction'],      name='tsig_satisfaction_idx'),
            models.Index(fields=['status'],            name='tsig_status_idx'),
            models.Index(fields=['source_department'], name='tsig_department_idx'),
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce required context fields for TechStackSignal.

        source_contact and source_activity are required — a tech stack
        observation must always be anchored to a known contact and a
        CRM activity.
        """
        super().clean()

        errors = {}

        if not self.source_contact_id:
            errors['source_contact'] = _(
                'A tech stack signal must be linked to a source contact.'
            )

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A tech stack signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # SAVE
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "tech:{tech_name.lower().strip()}"
        Only set when tech_name is not empty.
        Remains None when tech_name is blank.
        """
        if self.tech_name and self.tech_name.strip():
            self.canonical_key = f"tech:{self.tech_name.lower().strip()}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        tool = self.tech_name or 'Unknown tool'
        return (
            f"TechStackSignal | "
            f"{tool} | "
            f"{self.get_status_display()}"
        )