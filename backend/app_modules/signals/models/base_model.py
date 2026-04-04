# app_modules/signals/models/base_model.py
"""
Signal models for the Signals module.

Three concrete signal types, all inheriting from BaseSignal (abstract):
  - QualificationSignal  — commercial qualification data (MEDPICC-style)
  - TechStackSignal      — tools and technology used by the account

RhetoricalSignal is out of scope for Sprint 1.

Creation modes:
  - MANUAL        → status forced to VALIDATED, confidence forced to None
  - LLM_EXTRACTED → status starts PENDING, rep must validate
  - LLM_MODIFIED  → LLM-extracted then edited by rep before validation
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager

from ..constants import (
    SignalStatus,
    SignalSource,
    SignalCategory,
    QualificationField,
    TechStackField,
)




# =============================================================================
# BASE SIGNAL (abstract)
# =============================================================================

class BaseSignal(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Abstract base for all signal types.

    Provides:
      - Multi-tenant isolation via ClientScopeManager.ModelMixin
      - Full audit trail via ModuleBaseModel (id, client_id, created_by,
        updated_by, created_at, updated_at)
      - Context FKs (account required; activity, contact, department optional)
      - Signal content fields (field_name, value, source_quote, confidence…)
      - Source tracking (source, requested_by, language_original)
      - Lifecycle management (status, validated_by, validated_at,
        confirmation_count, merged_into, is_superseded, superseded_by)
      - Modification tracking (last_modified_by, last_modified_at,
        original_value)

    Business rules enforced in save():
      - source=MANUAL  → status=VALIDATED, confidence=None
      - source_contact → auto-populate source_department from contact
                         if source_department is not already set
    """

    # =========================================================================
    # CONTEXT — required
    # =========================================================================

    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='%(class)s_signals',
        verbose_name=_('Account'),
        help_text=_('Account this signal belongs to — required')
    )

    source_activity = models.ForeignKey(
        'module_activities.Activity',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Activity'),
        help_text=_('Activity (call/meeting) from which this signal was extracted')
    )

    # =========================================================================
    # CONTEXT — optional
    # =========================================================================

    source_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Contact'),
        help_text=_('Contact who provided or confirmed this signal')
    )

    source_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Department'),
        help_text=_(
            'Department this signal originates from. '
            'Auto-populated from source_contact.standard_department if not set.'
        )
    )

    decision_cycle = models.ForeignKey(
        'decision_cycles.DecisionCycle',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Decision Cycle'),
        help_text=_('Decision cycle this signal is associated with')
    )

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Campaign'),
        help_text=_('Campaign this signal is associated with')
    )

    # =========================================================================
    # SIGNAL CONTENT
    # =========================================================================

    field_name = models.CharField(
        max_length=50,
        verbose_name=_('Field Name'),
        help_text=_(
            'Controlled vocabulary identifier for the signal. '
            'Constrained to choices defined on each concrete model.'
        )
    )

    value = models.JSONField(
        verbose_name=_('Value'),
        help_text=_('Structured signal data — format depends on field_name')
    )

    source_quote = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Source Quote'),
        help_text=_(
            'Exact excerpt from the transcript that supports this signal, '
            'preserved in its original language'
        )
    )

    confidence = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Confidence'),
        help_text=_(
            'LLM confidence score (0.0–1.0). '
            'Null for manually entered signals.'
        )
    )

    is_inferred = models.BooleanField(
        default=False,
        verbose_name=_('Is Inferred'),
        help_text=_(
            'False = verbatim from transcript. '
            'True = deduced / inferred by LLM.'
        )
    )

    signal_category = models.CharField(
        max_length=20,
        choices=SignalCategory.choices,
        null=True,
        blank=True,
        verbose_name=_('Signal Category'),
        help_text=_('High-level commercial category of the signal')
    )

    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Flexible storage for merge history, LLM context, etc.')
    )

    # =========================================================================
    # SOURCE TRACKING
    # =========================================================================

    source = models.CharField(
        max_length=20,
        choices=SignalSource.choices,
        default=SignalSource.MANUAL,
        verbose_name=_('Source'),
        help_text=_('How the signal was created (manual entry vs. LLM)')
    )

    requested_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='%(class)s_requested',
        null=True,
        blank=True,
        verbose_name=_('Requested By'),
        help_text=_('User who triggered the LLM extraction (null for manual signals)')
    )

    language_original = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name=_('Original Language'),
        help_text=_('BCP-47 language tag of the source transcript (e.g. "fr", "en-US")')
    )

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    status = models.CharField(
        max_length=20,
        choices=SignalStatus.choices,
        default=SignalStatus.PENDING,
        verbose_name=_('Status'),
        help_text=_(
            'PENDING = awaiting rep validation (LLM signals). '
            'VALIDATED = approved (manual signals start here). '
            'REJECTED = dismissed. '
            'MERGED = absorbed into another signal.'
        )
    )

    validated_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='%(class)s_validated',
        null=True,
        blank=True,
        verbose_name=_('Validated By'),
        help_text=_('Rep who validated this signal (was approved_by in legacy)')
    )

    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Validated At'),
        help_text=_('When the signal was validated (was approved_at in legacy)')
    )

    confirmation_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Confirmation Count'),
        help_text=_('Number of times this signal has been independently confirmed')
    )

    last_confirmed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Last Confirmed At')
    )

    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='merged_from',
        null=True,
        blank=True,
        verbose_name=_('Merged Into'),
        help_text=_('Surviving signal when this one was merged (status=MERGED)')
    )

    is_superseded = models.BooleanField(
        default=False,
        verbose_name=_('Is Superseded'),
        help_text=_('True when a newer signal for the same field has replaced this one')
    )

    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='supersedes',
        null=True,
        blank=True,
        verbose_name=_('Superseded By'),
        help_text=_('Signal that replaced this one')
    )

    # =========================================================================
    # MODIFICATION TRACKING
    # =========================================================================

    last_modified_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='%(class)s_modified',
        null=True,
        blank=True,
        verbose_name=_('Last Modified By'),
        help_text=_('User who last edited the signal value after creation')
    )

    last_modified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Modified At')
    )

    original_value = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Original Value'),
        help_text=_(
            'Snapshot of value before the first manual edit. '
            'Null for signals that have never been edited.'
        )
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta:
        abstract = True

    # =========================================================================
    # SAVE — business rules
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Enforce signal business rules before delegating to ModuleBaseModel.save().

        Rules:
          1. source=MANUAL → status=VALIDATED, confidence=None
             Manual signals are trusted by definition — no LLM confidence score.

          2. source_contact set + source_department not set
             → auto-populate source_department from contact.standard_department
             Avoids requiring the rep to fill department separately when the
             contact already carries that information.
        """
        # Rule 1 — manual signals are immediately validated
        if self.source == SignalSource.MANUAL:
            self.status = SignalStatus.VALIDATED
            self.confidence = None

        # Rule 2 — inherit department from contact when not explicitly set
        if (
            self.source_contact_id
            and not self.source_department_id
            and hasattr(self.source_contact, 'standard_department')
            and self.source_contact.standard_department is not None
        ):
            self.source_department = self.source_contact.standard_department

        super().save(*args, **kwargs)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"{self.__class__.__name__} | "
            f"{self.field_name} | "
            f"{self.get_status_display()}"
        )