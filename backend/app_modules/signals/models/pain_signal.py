# app_modules/signals/models/pain_signal.py
"""
PainSignal — concrete signal for pain point data.

Captures a pain observed at an account during a conversation.
One signal = one pain point, scoped to a category and organisational level.

source_contact and source_activity are required — enforced in clean().
canonical_key is not auto-computed — set manually or by LLM.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import PainCategory, PainLevel


class PainSignal(BaseSignal):
    """
    Concrete signal for pain point data.

    Captures a pain expressed by a contact during a conversation,
    including its category, organisational scope, business cost,
    impacted department, downstream impact, and free-text notes.

    source_contact and source_activity are required (validated in clean()).
    canonical_key is not auto-computed — assigned manually or by LLM.
    """

    # =========================================================================
    # PAIN DESCRIPTION
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('The pain described in plain language')
    )

    category = models.CharField(
        max_length=20,
        choices=PainCategory.choices,
        verbose_name=_('Category'),
        help_text=_('Nature of the pain')
    )

    pain_level = models.CharField(
        max_length=20,
        choices=PainLevel.choices,
        verbose_name=_('Pain Level'),
        help_text=_('Organisational scope of the pain')
    )

    # =========================================================================
    # IMPACT
    # =========================================================================

    business_cost = models.TextField(
        blank=True,
        verbose_name=_('Business Cost'),
        help_text=_('Financial or operational cost estimate mentioned during the conversation')
    )

    impacted_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='impacted_pain_signals',
        null=True,
        blank=True,
        verbose_name=_('Impacted Department'),
        help_text=_('Department affected by this pain')
    )

    impact_summary = models.TextField(
        blank=True,
        verbose_name=_('Impact Summary'),
        help_text=_('Downstream consequences of this pain')
    )

    # =========================================================================
    # CONTEXT
    # =========================================================================

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional context about this pain point')
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_pain'
        verbose_name = _('Pain Signal')
        verbose_name_plural = _('Pain Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],    name='painsig_account_idx'),
            models.Index(fields=['category'],   name='painsig_category_idx'),
            models.Index(fields=['pain_level'], name='painsig_pain_level_idx'),
            models.Index(fields=['status'],     name='painsig_status_idx'),
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce required context fields for PainSignal.

        source_contact and source_activity are required — a pain point
        must always be anchored to a known contact and a CRM activity.
        """
        super().clean()

        errors = {}

        if not self.source_contact_id:
            errors['source_contact'] = _(
                'A pain signal must be linked to a source contact.'
            )

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A pain signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"PainSignal | "
            f"{self.get_category_display()} | "
            f"{self.get_pain_level_display()} | "
            f"{self.get_status_display()}"
        )