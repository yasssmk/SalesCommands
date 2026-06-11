# app_modules/signals/models/people_signal.py
"""
PeopleSignal — concrete signal for stakeholder role attribution.

Captures who plays what role in the buying process at the account.
Each PeopleSignal records an observed stakeholder role (PeopleRole)
and optional influence level for a contact or department involved
in a decision cycle.

Non-clustering signal
---------------------
PeopleSignal is intentionally excluded from the cluster model:
  * signal_category is shadow-overridden to None.
  * canonical_key stays None on every instance (see save()).
  * Cache invalidation targets only SIGNALS_CACHE_TAG.

Lifecycle (inherited from BaseSignal)
-------------------------------------
Standard SignalStatus flow:
    MANUAL source    → status = VALIDATED at create
    LLM_EXTRACTED    → status = PENDING at create; rep validates / rejects

Required context (enforced in clean())
--------------------------------------
  - source_activity — every PeopleSignal must be tied to a conversation
  - at least one of target_contact / target_department
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import PeopleRole, InfluenceLevel


class PeopleSignal(BaseSignal):
    """
    Concrete signal for stakeholder role attribution in a buying process.

    Structure:
      - role             : stakeholder role (PeopleRole enum, required)
      - influence        : perceived influence level (optional)
      - target_contact   : FK to the contact playing this role (optional)
      - target_department: FK to the department (optional)
      - notes            : additional context

    Required context (via clean()):
      - source_activity (every PeopleSignal must be tied to a conversation)
      - at least one of target_contact / target_department

    Cluster identity:
      None. PeopleSignal does not participate in the cluster model.
    """

    # =========================================================================
    # SHADOW OVERRIDES
    # =========================================================================
    signal_category = None

    # =========================================================================
    # ROLE & INFLUENCE
    # =========================================================================

    role = models.CharField(
        max_length=20,
        choices=PeopleRole.choices,
        verbose_name=_('Role'),
        help_text=_('Stakeholder role in the buying process (MEDDPICC-aligned)'),
    )

    influence = models.CharField(
        max_length=20,
        choices=InfluenceLevel.choices,
        null=True,
        blank=True,
        verbose_name=_('Influence Level'),
        help_text=_('Perceived influence level of the stakeholder'),
    )

    # =========================================================================
    # ATTRIBUTION
    # =========================================================================

    target_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='people_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Contact'),
        help_text=_(
            'Contact playing this role. Nullable because a role may be '
            'attributed at the department level when the specific person '
            'is not yet identified.'
        ),
    )

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='people_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_(
            'Department associated with this stakeholder role. Used when '
            'the specific contact is not yet identified, or as additional '
            'context alongside target_contact.'
        ),
    )

    # =========================================================================
    # NARRATIVE CONTENT
    # =========================================================================

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional context about this stakeholder observation'),
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
            models.Index(fields=['account'], name='pplsig_account_idx'),
            models.Index(fields=['status'], name='pplsig_status_idx'),
            models.Index(fields=['role'], name='pplsig_role_idx'),
            models.Index(fields=['target_contact'], name='pplsig_contact_idx'),
            models.Index(
                fields=['account', 'source_activity'],
                name='pplsig_account_activity_idx',
            ),
        ]

    # =========================================================================
    # SAVE — force canonical_key to None (PeopleSignal does not cluster)
    # =========================================================================

    def save(self, *args, **kwargs):
        self.canonical_key = None
        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A people signal must be linked to a source activity.'
            )

        if not self.target_contact_id and not self.target_department_id:
            errors['target_contact'] = _(
                'At least one of target_contact or target_department '
                'is required.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        target = ''
        if self.target_contact_id:
            target = f'contact={self.target_contact_id}'
        elif self.target_department_id:
            target = f'dept={self.target_department_id}'
        return (
            f"PeopleSignal | "
            f"{self.get_role_display()} | "
            f"{target} | "
            f"{self.get_status_display()}"
        )
