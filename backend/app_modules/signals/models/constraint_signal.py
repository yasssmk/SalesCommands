# app_modules/signals/models/constraint_signal.py
"""
ConstraintSignal — concrete signal for decision constraints and metrics.

Captures rules, criteria, and decision metrics (the M of MEDDPICC)
that govern a buying decision. A firm constraint is a non-negotiable
criterion ("ROI > 20%"); a flexible one is a preference ("ideally
before Q3").

Clustering signal
-----------------
ConstraintSignal participates in the cluster model on the same
canonical axes as Pain / Objective / Impact:
  * canonical_key = "constraint:<what>:<dimension>" (auto-computed)
  * signal_category is shadow-overridden to None (constraints are
    not tagged with a commercial category)
  * Cache invalidation targets both SIGNALS_CACHE_TAG and
    SIGNAL_CLUSTERS_CACHE_TAG

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
from ..constants import SignalWhat, SignalDimension, Rigidity


class ConstraintSignal(BaseSignal):
    """
    Concrete signal for a decision constraint or metric (M of MEDDPICC).

    Structure:
      - what             : domain axis (SignalWhat enum, required)
      - dimension        : friction axis (SignalDimension enum, required)
      - summary          : free-text description (required)
      - target_department: FK to the department that owns this constraint
      - rigidity         : firm vs flexible (Rigidity enum, required)
      - notes            : additional context

    Required context (via clean()):
      - source_activity (every constraint must be tied to a conversation)

    Cluster identity:
      canonical_key = "constraint:<what>:<dimension>" — auto-computed.
    """

    # =========================================================================
    # SHADOW OVERRIDES
    # =========================================================================
    signal_category = None

    # =========================================================================
    # CANONICAL AXES (required — form canonical_key)
    # =========================================================================

    what = models.CharField(
        max_length=20,
        choices=SignalWhat.choices,
        verbose_name=_('What'),
        help_text=_('Domain axis of the constraint (first component of canonical_key)'),
    )

    dimension = models.CharField(
        max_length=20,
        choices=SignalDimension.choices,
        verbose_name=_('Dimension'),
        help_text=_('Friction axis of the constraint (second component of canonical_key)'),
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
            models.Index(fields=['what'], name='constsig_what_idx'),
            models.Index(fields=['dimension'], name='constsig_dimension_idx'),
            models.Index(fields=['status'], name='constsig_status_idx'),
            models.Index(
                fields=['account', 'canonical_key'],
                name='constsig_account_canon_idx',
            ),
        ]

    # =========================================================================
    # SAVE — canonical_key auto-computation
    # =========================================================================

    def save(self, *args, **kwargs):
        if self.what and self.dimension:
            self.canonical_key = f"constraint:{self.what}:{self.dimension}"
        else:
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
            f"{self.get_what_display()} × {self.get_dimension_display()} | "
            f"{self.get_rigidity_display()} | "
            f"{self.get_status_display()}"
        )
