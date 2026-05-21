# app_modules/signals/models/impact_signal.py
"""
ImpactSignal — concrete signal for the consequence of a pain or the
proof of value behind an objective.

ImpactSignal captures structured evidence of what the prospect's
current situation produces — quantitative consequences (cost, time,
revenue lost) and qualitative ones (frustration, overload, risk
exposure). It is the "proof layer" that complements PainSignal (the
diagnosis) and ObjectiveSignal (the target).

Architectural alignment with Pain / Objective
---------------------------------------------
ImpactSignal follows the same canonical-cluster pattern as Pain and
Objective:

  * Inherits from BaseSignal (shared lifecycle, audit, source tracking).
  * canonical_key auto-computed in save() before delegating to
    BaseSignal.save() which applies MANUAL → VALIDATED rule.
  * Conditional validation in clean() — limited here to the
    `source_activity required` rule (mirror of PainSignal).
  * Cluster aggregation delegated entirely to SignalClusterService via
    the shared dispatch — see _list_impact_clusters_for_account in
    signal_cluster_service.py.

Sits alongside Pain and Objective on the canonical (WHAT × DIMENSION)
axis. A cluster identified by (what, dimension) on an account can now
expose three parallel sections — pains, objectives, and impacts —
all sharing the same canonical_key prefix-suffix mechanism.

Canonical key (auto-computed in save()):
    canonical_key = "impact:<what>:<dimension>"

Examples:
  - "30k€/month lost on inefficient onboarding"
      → what=OPS, dimension=COST, scope=BUSINESS,
        impact_type=FINANCIAL, summary="Monthly cost of onboarding
        inefficiency", metric_text="30000€/month"
  - "Managers spend 5h/week on manual reports"
      → what=DATA, dimension=TIME, scope=DEPARTMENT,
        impact_type=TIME, summary="Manual reporting overhead for
        managers", metric_text="5h/week"
  - "Team is frustrated by data quality issues"
      → what=DATA, dimension=QUALITY, scope=DEPARTMENT,
        impact_type=HUMAN, summary="Data quality drains morale",
        human_impact=FRUSTRATION
  - "Customer churn at 15%"
      → what=GROWTH, dimension=RISK, scope=BUSINESS,
        impact_type=CUSTOMER, summary="Customer churn rate",
        metric_text="15%"

Shadow-override of signal_category
----------------------------------
signal_category is set to None at the class level to shadow the field
inherited from BaseSignal. Categorisation on ImpactSignal is driven by
the dedicated impact_type axis (FINANCIAL / TIME / HUMAN / ...);
the generic signal_category tag is meaningless here. Mirror of the
stance taken by ObjectiveSignal and TechStackSignal.

Source contacts
---------------
Contacts associated with the source conversation are derived at read
time from `source_activity.contacts` and exposed through the
standardised `source_context` block in serializers (see
SignalSourceMixin in base_serializer.py). The model does not carry a
dedicated source_contact FK — see BaseSignal class docstring for the
rationale.

Validation rules (enforced in clean())
--------------------------------------
  1. source_activity is required — every impact must be tied to a
     conversation. Sprint Refonte ImpactSignal also durified Pain,
     Objective, and TechStack on this rule via the migration's
     NOT NULL alter — ImpactSignal enforces it at the model layer
     as well so the API surface yields a clean ValidationError
     (rather than an IntegrityError) when an unwrapped Impact is
     submitted without an activity.

  No conditional logic on (impact_type, human_impact):
    The brief allows human_impact to coexist with any impact_type when
    relevant (e.g. a RISK impact that also notes stress). The data
    layer stays permissive; UX guidance (frontend) suggests human_impact
    primarily on impact_type=HUMAN.

Status creation rule
--------------------
ImpactSignal does not override BaseSignal.save()'s source-driven
status logic:

  * source = MANUAL              → status forced to VALIDATED
  * source = LLM_EXTRACTED       → status starts PENDING
  * source = LLM_MODIFIED        → status starts PENDING
  * source = EXTERNAL_RESEARCH   → status starts PENDING (rep validates)

Multi-observations are expected
-------------------------------
There is intentionally NO UniqueConstraint on (account, what,
dimension). Multiple impact observations on the same canonical key are
the corroboration mechanism: each conversation surfacing the same
business-area × dimension consequence adds one ImpactSignal, and the
cluster service rolls them up. Mirror of Pain / Objective stance.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages

from .base_model import BaseSignal
from ..constants import (
    HumanImpactType,
    ImpactType,
    ScopeLevel,
    SignalDimension,
    SignalWhat,
)


class ImpactSignal(BaseSignal):
    """
    Concrete signal for the consequence of a pain or the proof of value
    behind an objective.

    Structure:
      - Canonical axes : what × dimension (drive canonical_key)
      - Scope axis     : scope_level (BUSINESS / DEPARTMENT / PERSONAL)
      - Identification : impact_type (required, ImpactType choices)
      - Narrative      : summary (required)
      - Metric         : metric_text (optional, free text)
      - Human          : human_impact (optional, HumanImpactType choices)

    Cluster identity:
      canonical_key = "impact:<what>:<dimension>" — auto-computed in save().

    Required context (via clean()):
      - source_activity (every impact must be tied to a conversation)
    """

    # =========================================================================
    # SHADOW OVERRIDE — drop signal_category for this signal type
    # =========================================================================
    # Categorisation on ImpactSignal is driven by impact_type (below);
    # the generic signal_category tag has no semantics here. Same
    # stance as ObjectiveSignal and TechStackSignal — Django treats
    # `= None` on a concrete subclass as "this field does not exist on
    # the concrete model" (no column created, no get_FIELD_display, no
    # serialisation).
    signal_category = None

    # =========================================================================
    # CANONICAL AXES (required — form canonical_key)
    # =========================================================================

    what = models.CharField(
        max_length=20,
        choices=SignalWhat.choices,
        verbose_name=_('What'),
        help_text=_('Domain axis of the impact (first component of canonical_key)')
    )

    dimension = models.CharField(
        max_length=20,
        choices=SignalDimension.choices,
        verbose_name=_('Dimension'),
        help_text=_('Outcome axis of the impact (second component of canonical_key)')
    )

    # =========================================================================
    # SCOPE (required — purely descriptive on ImpactSignal)
    # =========================================================================

    scope_level = models.CharField(
        max_length=20,
        choices=ScopeLevel.choices,
        verbose_name=_('Scope Level'),
        help_text=_(
            'Organisational scope at which the impact is measured '
            '(BUSINESS / DEPARTMENT / PERSONAL). Purely descriptive — '
            'no conditional FK requirement on ImpactSignal (contrast '
            'with ObjectiveSignal where scope drives target_contact / '
            'target_department).'
        )
    )

    # =========================================================================
    # IMPACT NATURE (required)
    # =========================================================================

    impact_type = models.CharField(
        max_length=20,
        choices=ImpactType.choices,
        verbose_name=_('Impact Type'),
        help_text=_(
            'Nature of the impact observation — FINANCIAL, TIME, '
            'PRODUCTIVITY, REVENUE, RISK, CUSTOMER, HUMAN, STRATEGIC, '
            'or METRIC. Orthogonal axis to (what, dimension): two '
            'observations sharing the same canonical_key can carry '
            'different impact_types (e.g. one FINANCIAL, one HUMAN).'
        )
    )

    # =========================================================================
    # NARRATIVE (required)
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('The impact described in plain language')
    )

    # =========================================================================
    # METRIC — optional free text
    # =========================================================================

    metric_text = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Metric (free text)'),
        help_text=_(
            'Quantified value as expressed during the conversation. '
            'Free text — e.g. "30k€/month", "5h/week", "around 50 '
            'people", "between 100 and 200". Intentionally NOT a '
            'structured numeric field — values are reported with '
            'widely varying granularity, units, and currency by reps; '
            'structured capture would lose nuance and force false '
            'precision.'
        )
    )

    # =========================================================================
    # HUMAN DIMENSION — optional
    # =========================================================================

    human_impact = models.CharField(
        max_length=20,
        choices=HumanImpactType.choices,
        blank=True,
        null=True,
        verbose_name=_('Human Impact'),
        help_text=_(
            'Optional human dimension — FRUSTRATION / OVERLOAD / '
            'STRESS / DEMOTIVATION / CONFLICT. Typically paired with '
            'impact_type=HUMAN but the model layer stays permissive: '
            'a RISK or STRATEGIC impact may also legitimately carry '
            'a human note. Frontend UX guidance suggests human_impact '
            'primarily on impact_type=HUMAN.'
        )
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_impact'
        verbose_name = _('Impact Signal')
        verbose_name_plural = _('Impact Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],     name='impsig_account_idx'),
            models.Index(fields=['what'],        name='impsig_what_idx'),
            models.Index(fields=['dimension'],   name='impsig_dimension_idx'),
            models.Index(fields=['scope_level'], name='impsig_scope_level_idx'),
            models.Index(fields=['impact_type'], name='impsig_impact_type_idx'),
            models.Index(fields=['status'],      name='impsig_status_idx'),
            # Composite index for cluster lookups by canonical_key
            # scoped to account. Serves
            # SignalClusterService._fetch_impact_signals.
            models.Index(
                fields=['account', 'canonical_key'],
                name='impsig_account_canon_idx',
            ),
        ]

    # =========================================================================
    # SAVE — canonical_key auto-computation
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "impact:<what>:<dimension>"

        Both what and dimension are required; the key is always set on
        a fully-constructed instance. BaseSignal.save() then applies
        the shared business rules (MANUAL → VALIDATED + confidence
        cleared, LLM-create-time guard against VALIDATED state).
        """
        if self.what and self.dimension:
            self.canonical_key = f"impact:{self.what}:{self.dimension}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce ImpactSignal-specific constraints.

        Rules:
          1. source_activity is required — every impact must be tied
             to a real conversation. Mirror of PainSignal.clean();
             Sprint Refonte ImpactSignal also durified the database
             column to NOT NULL across Pain / Objective / TechStack /
             ImpactSignal via migration 0014. The clean()-level check
             here yields a clean ValidationError (rather than an
             IntegrityError) on a payload missing the activity.

        No conditional rules on (impact_type, human_impact, metric_text):
          The data layer is intentionally permissive on cross-field
          coherence — human_impact may be set on any impact_type,
          metric_text may be set on any impact_type (including
          HUMAN — e.g. "70% of the team reports frustration").
          Frontend UX may suggest defaults but does not enforce.
        """
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = (
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"ImpactSignal | "
            f"{self.get_what_display()} × {self.get_dimension_display()} | "
            f"{self.get_impact_type_display()} | "
            f"{self.get_scope_level_display()} | "
            f"{self.get_status_display()}"
        )