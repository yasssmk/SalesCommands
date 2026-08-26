# app_modules/signals/models/base_model.py
"""
Signal models for the Signals module.

Four concrete signal types, all inheriting from BaseSignal (abstract):
  - PainSignal           — qualitative pain diagnosis (what × dimension)
  - ObjectiveSignal      — business objectives (what × dimension × scope)
  - TechStackSignal      — tools used by the account (catalog-anchored)

Creation modes:
  - MANUAL            → status forced to VALIDATED, confidence forced to None
  - LLM_EXTRACTED     → status starts PENDING, rep must validate
  - LLM_MODIFIED      → LLM-extracted then edited by rep before validation
  - EXTERNAL_RESEARCH → status starts PENDING (rep validates)
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus, SignalSource, SignalCategory


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
    - Context FKs (account required; source_activity, decision_cycle,
        campaign optional)
    - Signal content fields (source_quote, confidence, canonical_key…)
    - Source tracking (source, requested_by, language_original)
    - Lifecycle management (status, validated_by, validated_at)
    - Modification tracking (
        original_value)

    Source contacts and departments are NOT stored on the signal — they
    are derived at read time from `source_activity.contacts` (m2m on
    Activity) and exposed through the standardised `source` block in
    serializers (see SignalSourceMixin in base_serializer.py).

    decision_cycle and campaign are kept as direct FKs for indexed
    scoping queries (cluster service, cluster filter API), but they
    are NEVER written directly by the API. SignalManager
    ._propagate_activity_context populates them from source_activity
    at create time and the Update serializer does not expose them.

 Business rules enforced in save():
    - source=MANUAL  → status=VALIDATED, confidence=None
    - CREATE-time guard: source ∈ {LLM_EXTRACTED, LLM_MODIFIED}
      may not start with status=VALIDATED — must transit through
      PENDING via SignalManager.validate() (which sets validated_by /
      validated_at and triggers the audit trail).
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
        help_text=_(
            'Activity (call/meeting) from which this signal was extracted. '
            'Nullable + on_delete=SET_NULL is INTENTIONAL: a validated signal '
            'survives the deletion of its source conversation as an '
            'account-level observation. The "source_activity required at '
            'create" rule is enforced at the application layer — in '
            'concrete model clean() methods and in the Create serializers '
            '(see PainSignal.clean, BlockerSignal.clean, etc.) — never via '
            'a DB-level NOT NULL constraint, because durifying the column '
            'would contradict the SET_NULL deletion semantic.'
        )
    )

    source_run = models.ForeignKey(
        'module_ai_pipelines.AIPipelineRun',
        on_delete=models.SET_NULL,
        related_name='%(class)s_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Pipeline Run'),
        help_text=_(
            'AIPipelineRun that created this signal. Used to scope cache '
            'replay queries to a single run and prevent cross-run leakage. '
            'Null for manually created signals.'
        )
    )

    # =========================================================================
    # CONTEXT — optional
    # =========================================================================


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

    canonical_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('Canonical Key'),
        help_text=_(
            'Stable identifier used to group multiple observations of the '
            'same fact for corroboration. Auto-computed by concrete model '
            'save() for PeopleSignal and TechStackSignal. Set manually or '
            'by LLM for PainSignal and ObjectiveSignal.'
        )
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

    # =========================================================================
    # DATA-QUALITY EXCLUSION (orthogonal to the review lifecycle above)
    # =========================================================================

    is_domain_valid = models.BooleanField(
        default=True,
        verbose_name=_('Domain valid'),
        help_text=_(
            'False when the LLM emitted a `what` (domain) value outside the '
            'controlled SignalWhat vocabulary — e.g. a dimension word like '
            '"COST" placed in the domain slot. Such a signal is PERSISTED '
            '(not dropped) so it stays recoverable for reprocessing, but it '
            'is EXCLUDED from every user-facing list, cluster and count. '
            'Always True for signal types that have no `what` axis and for '
            'manually created signals (serializer-validated). This flag is '
            'orthogonal to `status`: it is a data-quality gate, not a review '
            'state.'
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


    # =========================================================================
    # MODIFICATION TRACKING
    # =========================================================================


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
             Manual signals are trusted by definition — no LLM
             confidence score. Universal across all concrete signal
             types. Enforced only at CREATE time so that
             SignalManager.reopen() and reject() can transition a
             MANUAL signal away from VALIDATED without save()
             overriding the new status.

          2. CREATE-time guard: source ∈ {LLM_EXTRACTED, LLM_MODIFIED}
             may not start with status=VALIDATED.
             Any LLM-sourced signal MUST transit through PENDING and
             be moved to VALIDATED via SignalManager.validate() —
             which sets validated_by and validated_at and records
             the audit trail. Creating an LLM signal directly as
             VALIDATED would bypass the human-review gate and the
             audit trail entirely. Enforced only at CREATE
             (self._state.adding=True) — the legitimate
             PENDING → VALIDATED transition performed by
             SignalManager.validate().save() runs after the INSERT
             and is not blocked.

        Removed in standardisation refactor:
          - "auto-populate source_department from
             source_contact.standard_department" rule. Both
             source_contact and source_department have been removed
             from BaseSignal — the source surface is now derived at
             read time from source_activity.contacts via the
             SignalSourceMixin in the base serializer. The rule
             became obsolete and was dropped.
        """
        # Rule 1 — manual signals are immediately validated (CREATE only)
        if self._state.adding and self.source == SignalSource.MANUAL:
            self.status = SignalStatus.VALIDATED
            self.confidence = None

        # Rule 2 — CREATE-time guard against bypassing the LLM review gate.
        # Any LLM-sourced signal must start PENDING and only transit to
        # VALIDATED through SignalManager.validate(), which records
        # validated_by / validated_at. The check is gated on
        # self._state.adding so legitimate PENDING → VALIDATED updates
        # performed by SignalManager.validate() are not blocked.
        if (
            self._state.adding
            and self.source in (
                SignalSource.LLM_EXTRACTED,
                SignalSource.LLM_MODIFIED,
            )
            and self.status == SignalStatus.VALIDATED
        ):
            raise ValidationError({
                'status': SignalErrorMessages.LLM_CANNOT_CREATE_VALIDATED,
            })

        super().save(*args, **kwargs)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"{self.__class__.__name__} | "
            f"{self.account_id} | "
            f"{self.get_status_display()}"
        )