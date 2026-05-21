# app_modules/signals/models/objective_signal.py
"""
ObjectiveSignal — concrete signal for business objectives.

An ObjectiveSignal captures a structured goal observed at an account
during a conversation. Unlike PainSignal which describes a problem,
ObjectiveSignal describes a desired outcome.

Canonical key (auto-computed in save()):
    canonical_key = "objective:<what>:<dimension>"

The canonical_key enables cluster aggregation across multiple observations
of the same objective on the same account — regardless of who reported it
or when. Objective clusters share the same backend plumbing as Pain
clusters (see SignalClusterService). The UI renders ObjectiveSignals as
individual cards for MVP; cluster consumption is reserved for the
Pre-call Game Plan LLM pipeline.

Required context (enforced in clean()):
  - source_activity — the call/meeting where the objective was surfaced.
    Added in Sprint Refonte ImpactSignal — every signal of qualification
    (Pain / Objective / TechStack / Impact) must now be tied to a real
    conversation. This ensures every signal has a clear provenance and supports

Scope-conditional requirements (enforced in clean()):
  - scope_level = PERSONAL   → target_contact required, target_department forbidden
  - scope_level = DEPARTMENT → target_department required, target_contact forbidden
  - scope_level = BUSINESS   → neither target_contact nor target_department

signal_category is inherited from BaseSignal as a general-purpose tag;
it is intentionally shadow-overridden to None here so it is neither
stored nor exposed for ObjectiveSignal. the
field will be retired from BaseSignal once People and TechStack are
refactored.

Wave B notes:
  - This is a destructive rewrite of the legacy ObjectiveSignal. All
    previous fields (goal_level, measurement_method, horizon,
    source_contact, impacted_contact) are removed. Migration 1.2 drops
    and recreates the underlying table.
  - The field `scope_level` replaces `goal_level` and adopts the shared
    ScopeLevel enum introduced in Wave A.

    Standardisation refactor notes:
  - source_contact and source_department are no longer fields on any
    signal type — they were removed from BaseSignal abstract during
    the standardisation refactor. Contacts who participated in the
    source conversation are now derived at read time from
    `source_activity.contacts` and exposed through the standardised
    `source` block in serializers (see SignalSourceMixin in
    base_serializer.py).
  - target_contact (PERSONAL scope) is unaffected by the refactor —
    it captures who OWNS the objective, not who reported it. The two
    concepts are distinct and target_contact remains a first-class
    FK on this model.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages

from .base_model import BaseSignal
from ..constants import ScopeLevel, SignalDimension, SignalWhat


class ObjectiveSignal(BaseSignal):
    """
    Concrete signal for a business objective.

    Structure:
      - Canonical axes: what × dimension (drive canonical_key)
      - Scope axis:     scope_level (BUSINESS / DEPARTMENT / PERSONAL)
      - Descriptive:    summary (required), success_criteria (optional),
                        target_date (optional), notes (optional)
      - Target:         target_contact (PERSONAL) or target_department
                        (DEPARTMENT), conditional

    Cluster identity:
      canonical_key = "objective:<what>:<dimension>" — auto-computed in save().

    Source contacts:
      Contacts who participated in `source_activity` are derived at
      read time from `source_activity.contacts` and exposed through
      the standardised `source` block in serializers. The signal does
      not carry a dedicated source_contact FK — see BaseSignal class
      docstring for the rationale. target_contact (PERSONAL scope) is
      a distinct concept that captures who OWNS the objective, not
      who reported it.

    Signal-category suppression:
      signal_category is set to None at the class level to shadow the
      field inherited from BaseSignal. This prevents the column from
      being created in the concrete table and ensures the filter
      (which still declares it at the SignalFilter level) simply returns
      no match on ObjectiveSignal — the dynamic filter-model rebinding
      in BaseSignalViewSet.filter_queryset() tolerates absent fields.
    """

    # =========================================================================
    # SHADOW OVERRIDE — drop signal_category for this signal type
    # =========================================================================
    # Abstract fields from BaseSignal can be shadowed by assigning `None`
    # on the concrete subclass. Django treats this as "this field does
    # not exist on the concrete model" — no column is created, no
    # get_FIELD_display, no serialization.
    signal_category = None

    # =========================================================================
    # CANONICAL AXES (required — form canonical_key)
    # =========================================================================

    what = models.CharField(
        max_length=20,
        choices=SignalWhat.choices,
        verbose_name=_('What'),
        help_text=_('Domain axis of the objective (first component of canonical_key)')
    )

    dimension = models.CharField(
        max_length=20,
        choices=SignalDimension.choices,
        verbose_name=_('Dimension'),
        help_text=_('Outcome axis of the objective (second component of canonical_key)')
    )

    # =========================================================================
    # SCOPE (required — drives conditional target requirements)
    # =========================================================================

    scope_level = models.CharField(
        max_length=20,
        choices=ScopeLevel.choices,
        verbose_name=_('Scope Level'),
        help_text=_('Organisational scope of the objective (BUSINESS / DEPARTMENT / PERSONAL)')
    )

    # =========================================================================
    # DESCRIPTIVE
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('The objective described in plain language (e.g. "Reduce onboarding time by 30%")')
    )

    success_criteria = models.TextField(
        blank=True,
        verbose_name=_('Success Criteria'),
        help_text=_('How success is defined — KPIs, thresholds, measurement method')
    )

    target_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Target Date'),
        help_text=_('When this objective should be achieved')
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional qualitative context (source quotes, caveats, etc.)')
    )

    # =========================================================================
    # TARGET — conditional on scope_level
    # =========================================================================

    target_contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='objective_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Contact'),
        help_text=_('Contact driving this objective — required when scope_level=PERSONAL')
    )

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='objective_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_('Department driving this objective — required when scope_level=DEPARTMENT')
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
            models.Index(fields=['account'],     name='objsig_account_idx'),
            models.Index(fields=['what'],        name='objsig_what_idx'),
            models.Index(fields=['dimension'],   name='objsig_dimension_idx'),
            models.Index(fields=['scope_level'], name='objsig_scope_level_idx'),
            models.Index(fields=['status'],      name='objsig_status_idx'),
            # Composite index for cluster lookups by canonical_key scoped to account.
            # Serves SignalClusterService.list_clusters_for_account for Objective
            # (activated in Phase 4 of the Wave B port).
            models.Index(
                fields=['account', 'canonical_key'],
                name='objsig_account_canon_idx',
            ),
        ]

    # =========================================================================
    # SAVE — canonical_key auto-computation
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "objective:<what>:<dimension>"

        Both what and dimension are required; the key is always set on
        a fully-constructed instance. BaseSignal.save() then applies
        shared business rules (MANUAL → VALIDATED, source_department
        inherit from source_contact).
        """
        if self.what and self.dimension:
            self.canonical_key = f"objective:{self.what}:{self.dimension}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce ObjectiveSignal-specific constraints.

        Rules:
          1. source_activity is required — every objective must be tied
             to a real conversation. Added in Sprint Refonte ImpactSignal;
             aligned with PainSignal / TechStackSignal / ImpactSignal.
             The DB column was simultaneously durified to NOT NULL via
             migration 0014. Raising early here yields a clean
             ValidationError on the API surface rather than an
             IntegrityError.
          2. scope_level = PERSONAL
                → target_contact required
                → target_department forbidden
          3. scope_level = DEPARTMENT
                → target_department required
                → target_contact forbidden
          4. scope_level = BUSINESS
                → neither target_contact nor target_department

        Historical note (Wave B decision 3, partially superseded):
          The original Wave B stance was "at least one of source_activity
          / decision_cycle / campaign — but none individually required".
          Sprint Refonte ImpactSignal tightened the rule: source_activity
          is now strictly required, in line with the LLM-driven extraction
          path (every signal originates from a transcript anchored to an
          Activity). decision_cycle and campaign remain available as
          nullable fields inherited from BaseSignal and are auto-populated
          by SignalManager._propagate_activity_context from source_activity
          at create time.
        """
        super().clean()

        errors = {}

        # --- Rule 1: source_activity required (Sprint Refonte ImpactSignal) ---
        if not self.source_activity_id:
            errors['source_activity'] = (
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        # --- Rules 2-4: scope-conditional target requirements ---
        if self.scope_level == ScopeLevel.PERSONAL:
            if not self.target_contact_id:
                errors['target_contact'] = _(
                    'Personal objectives require a target contact.'
                )
            if self.target_department_id:
                errors['target_department'] = _(
                    'Personal objectives must not specify a target department. '
                    'Use a department-scoped objective instead.'
                )

        elif self.scope_level == ScopeLevel.DEPARTMENT:
            if not self.target_department_id:
                errors['target_department'] = _(
                    'Department objectives require a target department.'
                )
            if self.target_contact_id:
                errors['target_contact'] = _(
                    'Department objectives must not specify a target contact. '
                    'Use a personal-scoped objective instead.'
                )

        elif self.scope_level == ScopeLevel.BUSINESS:
            if self.target_contact_id:
                errors['target_contact'] = _(
                    'Business objectives must not specify a target contact.'
                )
            if self.target_department_id:
                errors['target_department'] = _(
                    'Business objectives must not specify a target department.'
                )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"ObjectiveSignal | "
            f"{self.get_what_display()} × {self.get_dimension_display()} | "
            f"{self.get_scope_level_display()} | "
            f"{self.get_status_display()}"
        )