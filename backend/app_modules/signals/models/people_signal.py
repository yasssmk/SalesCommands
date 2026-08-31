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
  - source_activity — required for LLM-sourced signals; MANUAL signals
    may omit it when anchored to a decision_cycle instead
  - at least one of target_contact / target_department
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import PeopleRole, InfluenceLevel, SignalSource


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
      - source_activity required for LLM-sourced signals; MANUAL signals
        may omit it when anchored to a decision_cycle instead
      - at least one of target_contact / target_department

    Cluster identity:
      None. PeopleSignal does not participate in the cluster model.
    """

    # =========================================================================
    # SHADOW OVERRIDES
    # =========================================================================
    signal_category = None

    # =========================================================================
    # PERSON IDENTITY (raw + derived normalised key)
    # =========================================================================
    #
    # `full_name` is a THIRD, OPTIONAL identity path alongside target_contact /
    # target_department: a person can be NAMED even when not yet linked to a
    # directory Contact. It does NOT relax the clean() invariant (at least one
    # of target_contact / target_department stays required). `full_name` is the
    # single source of truth; `full_name_normalized` is DERIVED from it in
    # save() and must never be authored by a caller — see the SAVE section.
    # Calqued on TechStackSignal.tech_name / tech_name_normalized and
    # CompetitorSignal.competitor_name / competitor_name_normalized.

    full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Full Name'),
        help_text=_(
            'Raw display name of the stakeholder exactly as observed '
            '(e.g. "Marc Dubois"). Optional — a role may still be attributed '
            'via target_contact / target_department only. Never rewritten; '
            'casing and spacing are preserved for display. Grouping and '
            'matching use `full_name_normalized` instead.'
        ),
    )

    full_name_normalized = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Full Name (normalised)'),
        help_text=_(
            'Derived from `full_name` on every save: lowercased, trimmed, '
            'internal whitespace collapsed to single spaces. Empty string '
            'when `full_name` is blank. Read-only by contract — recomputed at '
            'save() time, so the two columns cannot desync.'
        ),
    )

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
            # Grouping / matching surface for the future per-person cluster and
            # contact reconciliation (mirror of tech / competitor name index).
            models.Index(
                fields=['full_name_normalized'],
                name='peoplesig_name_norm_idx',
            ),
        ]

    # =========================================================================
    # SAVE — force canonical_key to None (PeopleSignal does not cluster)
    # =========================================================================

    def save(self, *args, **kwargs):
        self.canonical_key = None
        self.full_name_normalized = self._normalize_full_name(self.full_name)
        super().save(*args, **kwargs)

    @staticmethod
    def _normalize_full_name(value):
        """
        Lowercase + trim + collapse internal whitespace.

        "  Marc   Dubois " -> "marc dubois"
        None / "" / "   "   -> ""

        Exact clone of TechStackSignal._normalize_tech_name /
        CompetitorSignal._normalize_competitor_name. This is the single
        normalisation point — every write path goes through Model.save(), so
        the normalised key can never desync from its raw name.
        """
        if not value:
            return ''
        # str.split() with no argument splits on arbitrary runs of whitespace
        # and drops leading/trailing runs — strip + collapse in one pass.
        return ' '.join(str(value).lower().split())

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        super().clean()

        errors = {}

        if not self.source_activity_id:
            if self.source != SignalSource.MANUAL or not self.decision_cycle_id:
                errors['source_activity'] = _(
                    'A people signal must be linked to a source activity.'
                )

        if (not self.target_contact_id
                and not self.target_department_id
                and not (self.full_name or '').strip()):
            errors['target_contact'] = _(
                'At least one of target_contact, target_department or '
                'full_name is required.'
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
