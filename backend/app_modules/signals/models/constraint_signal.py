# app_modules/signals/models/constraint_signal.py
"""
ConstraintSignal — concrete signal for decision constraints and metrics.

Captures rules, criteria, and decision metrics (the M of MEDDPICC)
that govern a buying decision. A firm constraint is a non-negotiable
criterion ("ROI > 20%"); a flexible one is a preference ("ideally
before Q3").

Classification axis (nature)
----------------------------
ConstraintSignal is classified on `nature` (ConstraintNature) — a
constraint-specific taxonomy (FUNCTIONAL / TECHNICAL / FINANCIAL /
CONTRACTUAL / OPERATIONAL / SECURITY). It is DETACHED from the business
what × dimension axes used by Pain / Objective / Impact:

  * `nature` is required — the kind of decision criterion.
  * `what` / `dimension` are LEGACY and now nullable: kept (non-destructive)
    for historical rows but no longer authored nor used to key clusters.
  * `canonical_key` stays None on every ConstraintSignal — see save()
    below (mirror of BlockerSignal). Constraints do not cluster on
    canonical_key anymore; the scope (target_department) is the intended
    cluster axis, resolved at read time.
  * signal_category is shadow-overridden to None (constraints are
    not tagged with a commercial category).
  * Cache invalidation targets both SIGNALS_CACHE_TAG and
    SIGNAL_CLUSTERS_CACHE_TAG.

Lifecycle (inherited from BaseSignal)
-------------------------------------
Standard SignalStatus flow:
    MANUAL source    → status = VALIDATED at create
    LLM_EXTRACTED    → status = PENDING at create; rep validates / rejects

Required context (enforced in clean())
--------------------------------------
  - source_activity — every constraint must be tied to a conversation
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import SignalWhat, SignalDimension, Rigidity, ConstraintNature


class ConstraintSignal(BaseSignal):
    """
    Concrete signal for a decision constraint or metric (M of MEDDPICC).

    Structure:
      - nature           : constraint taxonomy (ConstraintNature enum, required)
      - summary          : free-text description (required)
      - target_department: FK to the department that owns this constraint
      - rigidity         : firm vs flexible (Rigidity enum, required)
      - notes            : additional context
      - what / dimension : LEGACY, nullable — no longer authored (see save())

    Required context (via clean()):
      - source_activity (every constraint must be tied to a conversation)

    Cluster identity:
      canonical_key stays None (mirror of BlockerSignal). Constraints are
      classified on `nature` and scoped on `target_department`, not on a
      what × dimension canonical_key.
    """

    # =========================================================================
    # SHADOW OVERRIDES
    # =========================================================================
    signal_category = None

    # =========================================================================
    # CLASSIFICATION AXIS (required)
    # =========================================================================

    nature = models.CharField(
        max_length=20,
        choices=ConstraintNature.choices,
        verbose_name=_('Nature'),
        help_text=_(
            'Kind of decision criterion (FUNCTIONAL / TECHNICAL / FINANCIAL / '
            'CONTRACTUAL / OPERATIONAL / SECURITY). The classification axis for '
            'constraints — replaces the business what × dimension axes.'
        ),
    )

    # =========================================================================
    # LEGACY AXES (nullable — no longer authored, kept for historical rows)
    # =========================================================================

    what = models.CharField(
        max_length=20,
        choices=SignalWhat.choices,
        null=True,
        blank=True,
        verbose_name=_('What'),
        help_text=_('LEGACY domain axis — deprecated for constraints, kept nullable for historical rows'),
    )

    dimension = models.CharField(
        max_length=20,
        choices=SignalDimension.choices,
        null=True,
        blank=True,
        verbose_name=_('Dimension'),
        help_text=_('LEGACY friction axis — deprecated for constraints, kept nullable for historical rows'),
    )

    # =========================================================================
    # NARRATIVE CONTENT
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('Description of the constraint or decision criterion'),
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional context about this constraint'),
    )

    # =========================================================================
    # ATTRIBUTION
    # =========================================================================

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='constraint_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_(
            'Department that owns or enforces this constraint. '
            'Purely descriptive — no conditional enforcement.'
        ),
    )

    # =========================================================================
    # TARGET DEPARTMENTS (multi-department — WHO the constraint concerns)
    # =========================================================================
    #
    # A constraint can legitimately concern SEVERAL departments at once
    # (e.g. a security requirement owned by IT AND Security & Risk). This M2M
    # is the multi-department carrier that supersedes the single-FK
    # target_department above, mirroring TechStackSignal.usage_departments
    # (tech_stack_signal.py) — the established multi-department pattern in
    # this module.
    #
    #   * blank=True — a constraint may concern NO specific department
    #     (company-wide / cross-departmental — the common case).
    #   * Direct M2M (no `through`) to the shared StandardDepartment
    #     controlled list — same shape as TechStackSignal.usage_departments,
    #     Campaign.target_departments and DecisionStep.departments. A plain
    #     link table (module_signals_constraint_target_departments) is
    #     enough: the relation carries no extra attributes.
    #   * StandardDepartment is GLOBAL reference data (no client_id of its
    #     own), so the link never crosses tenants: the tenant boundary lives
    #     on THIS signal (client_id), the department rows are shared vocabulary.
    #   * related_name distinct from the FK's `constraint_signals` and from
    #     TechStack's `tech_stack_signals_used_by`.
    #
    # During the FK→M2M transition the legacy target_department is backfilled
    # into this M2M as its first entry (data migration); readers move onto the
    # M2M in a later sub-step before the FK is dropped.
    target_departments = models.ManyToManyField(
        'core_modules.StandardDepartment',
        related_name='constraint_signals_scoped_to',
        blank=True,
        verbose_name=_('Target Departments'),
        help_text=_(
            'The set of departments this constraint concerns (multi-department: '
            'a constraint can be owned by IT and Security & Risk at once). '
            'Supersedes the legacy single-FK target_department. Empty when no '
            'department is designated (company-wide / cross-departmental).'
        ),
    )

    # =========================================================================
    # RIGIDITY
    # =========================================================================

    rigidity = models.CharField(
        max_length=20,
        choices=Rigidity.choices,
        verbose_name=_('Rigidity'),
        help_text=_(
            'Whether this constraint is non-negotiable (FIRM) or a '
            'preference (FLEXIBLE).'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_constraint'
        verbose_name = _('Constraint Signal')
        verbose_name_plural = _('Constraint Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'], name='constsig_account_idx'),
            models.Index(fields=['nature'], name='constsig_nature_idx'),
            models.Index(fields=['status'], name='constsig_status_idx'),
            # what / dimension / canonical_key indexes dropped: the axes are
            # detached (canonical_key always None, what/dimension legacy). The
            # classification axis is `nature`; the scope axis (target_department)
            # gets its index when constraint clustering lands.
        ]

    # =========================================================================
    # SAVE — canonical_key forced to None (constraint is detached from
    # the what × dimension canonical axes)
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        ConstraintSignal no longer clusters on canonical_key.

        The `canonical_key` column is inherited from BaseSignal (nullable,
        indexed) for shape consistency with other signal types, but is
        explicitly forced to None on every save — constraints are classified
        on `nature` and scoped on `target_department`, not on a
        what × dimension key. Mirror of BlockerSignal.save().
        """
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
                'A constraint signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"ConstraintSignal | "
            f"{self.get_nature_display() if self.nature else '—'} | "
            f"{self.get_rigidity_display() if self.rigidity else '—'} | "
            f"{self.get_status_display()}"
        )
