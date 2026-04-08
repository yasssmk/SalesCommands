# app_modules/signals/models/people_signal.py
"""
PeopleSignal — concrete signal for stakeholder mapping.

Captures the commercial role and influence of a contact at an account.
One signal = one observed role for one target contact.

source_contact and source_activity remain optional (inherited from BaseSignal).
canonical_key is auto-computed in save() when target_contact is set.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import PeopleRole, InfluenceLevel


class PeopleSignal(BaseSignal):
    """
    Concrete signal for stakeholder mapping.

    Captures who a contact is in the buying process at an account —
    their commercial role (required) and influence level (optional).

    canonical_key is computed as "people:{target_contact_id}:{role}"
    when target_contact is set, enabling corroboration across observations
    of the same stakeholder role.
    """

    # =========================================================================
    # TARGET — who the signal is about
    # =========================================================================

    target_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='targeted_people_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Contact'),
        help_text=_('Contact this signal describes')
    )

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='targeted_people_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_('Department of the target contact')
    )

    # =========================================================================
    # ROLE & INFLUENCE
    # =========================================================================

    role = models.CharField(
        max_length=30,
        choices=PeopleRole.choices,
        verbose_name=_('Role'),
        help_text=_('Commercial role this person plays in the buying process')
    )

    influence_level = models.CharField(
        max_length=10,
        choices=InfluenceLevel.choices,
        null=True,
        blank=True,
        verbose_name=_('Influence Level'),
        help_text=_('Perceived influence level of this stakeholder')
    )

    # =========================================================================
    # CONTEXT
    # =========================================================================

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Free-text context about this stakeholder')
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_people'
        verbose_name = _('People Signal')
        verbose_name_plural = _('People Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],           name='psig_account_idx'),
            models.Index(fields=['role'],              name='psig_role_idx'),
            models.Index(fields=['status'],            name='psig_status_idx'),
            models.Index(fields=['source_department'], name='psig_department_idx'),
        ]

    # =========================================================================
    # SAVE
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "people:{target_contact_id}:{role}"
        Only set when target_contact_id is present.
        Remains None when target_contact is not set.
        """
        if self.target_contact_id:
            self.canonical_key = f"people:{self.target_contact_id}:{self.role}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        contact = self.target_contact_id or 'Unknown contact'
        return (
            f"PeopleSignal | "
            f"{contact} | "
            f"{self.get_role_display()} | "
            f"{self.get_status_display()}"
        )