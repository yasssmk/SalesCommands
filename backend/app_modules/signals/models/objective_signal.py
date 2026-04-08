# app_modules/signals/models/objective_signal.py
"""
ObjectiveSignal — concrete signal for goal data.

Captures a goal observed at an account during a conversation.
One signal = one objective, scoped to an organisational level.

source_contact and source_activity are required — enforced in clean().
canonical_key is not auto-computed — set manually or by LLM.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import GoalLevel


class ObjectiveSignal(BaseSignal):
    """
    Concrete signal for goal data.

    Captures an objective expressed by a contact during a conversation,
    including its organisational scope, success criteria, measurement
    method, the person driving it, and free-text notes.

    source_contact and source_activity are required (validated in clean()).
    canonical_key is not auto-computed — assigned manually or by LLM.
    """

    # =========================================================================
    # GOAL DESCRIPTION
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('The goal described in plain language')
    )

    goal_level = models.CharField(
        max_length=20,
        choices=GoalLevel.choices,
        verbose_name=_('Goal Level'),
        help_text=_('Organisational scope of the objective')
    )

    # =========================================================================
    # MEASUREMENT
    # =========================================================================

    success_criteria = models.TextField(
        blank=True,
        verbose_name=_('Success Criteria'),
        help_text=_('How success is defined for this objective')
    )

    measurement_method = models.TextField(
        blank=True,
        verbose_name=_('Measurement Method'),
        help_text=_('How progress toward this objective will be measured')
    )

    # =========================================================================
    # TARGET — who is driving the goal
    # =========================================================================

    target_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='objective_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Contact'),
        help_text=_('Contact driving this objective')
    )

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='objective_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_('Department driving this objective')
    )

    # =========================================================================
    # CONTEXT
    # =========================================================================

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional context about this objective')
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_objective'
        verbose_name = _('Objective Signal')
        verbose_name_plural = _('Objective Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],    name='objsig_account_idx'),
            models.Index(fields=['goal_level'], name='objsig_goal_level_idx'),
            models.Index(fields=['status'],     name='objsig_status_idx'),
        ]

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce required context fields for ObjectiveSignal.

        source_contact and source_activity are required — an objective
        must always be anchored to a known contact and a CRM activity.
        """
        super().clean()

        errors = {}

        if not self.source_contact_id:
            errors['source_contact'] = _(
                'An objective signal must be linked to a source contact.'
            )

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'An objective signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"ObjectiveSignal | "
            f"{self.get_goal_level_display()} | "
            f"{self.get_status_display()}"
        )