# app_modules/signals/models/pain_signal.py
"""
PainSignal — concrete signal for qualitative pain diagnosis.

Pain = the DIAGNOSIS (qualitative)
Impact = the PROOF  (quantitative and/or human)

A PainSignal captures the structural problem an account is experiencing,
identified by two orthogonal canonical axes (what × dimension) and
anchored at an organisational scope (scope_level). It is deliberately
narrative-only on the proof axis:

  * No metrics, costs, or numeric evidence — those live in ImpactSignal.
  * No impacted department / contact field — the impacted parties are
    derived from the conversation's contacts (via source_activity) and
    refined through related ImpactSignal observations sharing the same
    canonical_key on the account.
  * No human impact enum — captured on ImpactSignal when relevant
    (human_impact field, HumanImpactType choices).

Canonical key (auto-computed in save()):
    canonical_key = "pain:<what>:<dimension>"

Scope axis:
    scope_level documents the organisational layer at which the pain
    is felt (BUSINESS / DEPARTMENT / PERSONAL). It defaults to
    BUSINESS — the safest interpretation when no specific scope was
    surfaced during the conversation. The LLM emission for Pain (see
    pain_v1.py) is expected to provide an explicit value; the default
    is a defence-in-depth fallback. Aligned with ObjectiveSignal and
    ImpactSignal — the triangulation (Pain × Objective × Impact)
    works on a shared (what, dimension, scope_level) axis.

The canonical_key enables cluster aggregation across multiple observations
of the same pain on the same account — regardless of who reported it,
when, or which angle was documented. See SignalClusterService for how
clusters roll up their member Pain signals.

Required context (enforced in clean()):
  - source_activity — the call/meeting where the pain was identified

Note: source_activity is REQUIRED. Every Pain must be tied to a real
conversation, which guarantees a traceable origin for audit and LLM
retrieval purposes. The list of contacts who participated in that
conversation is derived at read time from `source_activity.contacts`
and exposed through the standardised `source` block in serializers
(see SignalSourceMixin in base_serializer.py) — there is no single
source_contact FK on the signal. Decision cycle and campaign are
inherited from BaseSignal as indexed-FK columns and are auto-populated
from source_activity by SignalManager._propagate_activity_context at
create time.

Cross-reference with TechStack
------------------------------
`related_techstack_mention` — free text — lets a Pain name a tool that
is part of the diagnosed problem, typically (but not exclusively) when
what=TECH.

S10 removed the structured companion `related_techstack`, a FK to the
tenant TechCatalog. The catalogue is gone, and TechStackSignal now
carries its own free-text identity (`tech_name` + the normalised key),
so a structured Pain→tool link has nothing left to point at. The
textual mention survives as the trace it always was.

If a structured link is wanted again later, the natural target is the
normalised tech name shared with TechStackSignal.tech_name_normalized —
not a resurrected catalogue.

UI conditionality (frontend only)
---------------------------------
The form rule "show related_techstack_mention only when what=TECH" is
intentionally NOT enforced in the model. A Pain with what=DATA might
legitimately reference a BI tool, and the rep should be able to surface
that cross-reference without the schema fighting them.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal
from ..constants import ScopeLevel, SignalWhat, SignalDimension


class PainSignal(BaseSignal):
    """
    Concrete signal for a qualitative pain diagnosis.

    Structure:
      - what         : domain of the pain (SignalWhat enum, required)
      - dimension    : friction experienced (SignalDimension enum, required)
      - summary      : free-text description of the pain (required)
      - source_quote : optional verbatim excerpt from the transcript
      - notes        : optional additional context

    Required context (via clean()):
      - source_activity (every pain must be tied to a conversation)

    Cluster identity:
      canonical_key = "pain:<what>:<dimension>" — auto-computed in save().

    Source contacts:
      The contacts who participated in `source_activity` are derived at
      read time from `source_activity.contacts` and exposed through the
      standardised `source` block in serializers. The signal does not
      carry a dedicated source_contact FK — see BaseSignal class
      docstring for the rationale.

    Metrics, cost estimates, impacted parties, and human consequences live
    on ImpactSignal observations sharing the same canonical_key on the
    account.
    """

    # =========================================================================
    # CANONICAL AXES (required — form canonical_key)
    # =========================================================================

    what = models.CharField(
        max_length=20,
        choices=SignalWhat.choices,
        verbose_name=_('What'),
        help_text=_('Domain axis of the pain (first component of canonical_key)')
    )

    dimension = models.CharField(
        max_length=20,
        choices=SignalDimension.choices,
        verbose_name=_('Dimension'),
        help_text=_('Friction axis of the pain (second component of canonical_key)')
    )

    # =========================================================================
    # SCOPE (required — defence-in-depth default to BUSINESS)
    # =========================================================================

    scope_level = models.CharField(
        max_length=20,
        choices=ScopeLevel.choices,
        default=ScopeLevel.BUSINESS,
        verbose_name=_('Scope Level'),
        help_text=_(
            'Organisational scope at which the pain is felt '
            '(BUSINESS / DEPARTMENT / PERSONAL). Purely descriptive — '
            'no conditional FK requirement on PainSignal (contrast '
            'with ObjectiveSignal where scope drives target_contact / '
            'target_department). Defaults to BUSINESS — the safest '
            'interpretation when no specific scope is provided. LLM '
            'extraction is expected to emit an explicit value (see '
            'pain_v1.py); the default is a defence-in-depth fallback '
            'guaranteeing the field is never empty even if the API or '
            'LLM omits it.'
        )
    )

    # =========================================================================
    # TARGET DEPARTMENTS (multi-department — WHO the pain concerns)
    # =========================================================================
    #
    # A pain can legitimately concern SEVERAL departments at once. This M2M is
    # the multi-department scope carrier, mirroring
    # TechStackSignal.usage_departments and ConstraintSignal.target_departments
    # (constraint_signal.py) — the established multi-department pattern in this
    # module. It replaced the legacy single-FK target_department, dropped in
    # sub-step 2d once every reader/writer moved onto the M2M (backfill in
    # migrations 0039/0040; the drop in 0041). scope_level is unaffected — it
    # stays as the descriptive organisational-scope axis.
    #
    #   * blank=True — a pain may concern NO specific department (BUSINESS).
    #   * Direct M2M (no `through`) to the shared StandardDepartment controlled
    #     list — a plain link table (module_signals_pain_target_departments)
    #     is enough. StandardDepartment is GLOBAL reference data (no client_id),
    #     so the link never crosses tenants (the tenant boundary is on THIS
    #     signal). related_name distinct from TechStack's / Constraint's.
    target_departments = models.ManyToManyField(
        'core_modules.StandardDepartment',
        related_name='pain_signals_scoped_to',
        blank=True,
        verbose_name=_('Target Departments'),
        help_text=_(
            'The set of departments this pain concerns (multi-department). '
            'Supersedes the legacy single-FK target_department. Empty when no '
            'department is designated (BUSINESS / company-wide).'
        ),
    )

    # =========================================================================
    # NARRATIVE CONTENT
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('The pain described in plain language')
    )

    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional qualitative context about this pain')
    )

    # =========================================================================
    # CROSS-REFERENCE — TechStack
    # =========================================================================
    #
    # Optional — see class docstring. The structured FK companion
    # (related_techstack -> TechCatalog) was removed in S10 along with
    # the catalogue; the mention is the whole cross-reference now.

    related_techstack_mention = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Related TechStack Mention'),
        help_text=_(
            'Free-text mention of a tool involved in this pain '
            '(e.g. "Salesforce"). Not linked to any TechStackSignal — '
            'purely a textual trace captured alongside the pain.'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_pain'
        verbose_name = _('Pain Signal')
        verbose_name_plural = _('Pain Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'],     name='painsig_account_idx'),
            models.Index(fields=['what'],        name='painsig_what_idx'),
            models.Index(fields=['dimension'],   name='painsig_dimension_idx'),
            models.Index(fields=['scope_level'], name='painsig_scope_level_idx'),
            models.Index(fields=['status'],      name='painsig_status_idx'),
            # Composite index for cluster lookups by canonical_key scoped to account.
            # Serves SignalClusterService.list_clusters_for_account.
            models.Index(
                fields=['account', 'canonical_key'],
                name='painsig_account_canon_idx',
            ),
        ]

    # =========================================================================
    # SAVE — canonical_key auto-computation
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Compute canonical_key before delegating to BaseSignal.save().

        canonical_key = "pain:<what>:<dimension>"
        Both what and dimension are required; the key is always set on
        a fully-constructed instance. BaseSignal.save() then applies
        shared business rules (MANUAL → VALIDATED, department inherit
        from contact).
        """
        if self.what and self.dimension:
            self.canonical_key = f"pain:{self.what}:{self.dimension}"
        else:
            self.canonical_key = None

        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce PainSignal-specific constraints.

        Rules:
          1. source_activity is required — every pain has an origin
             conversation. Decision cycle and campaign are propagated
             from the activity by SignalManager._propagate_activity_context
             at create time, so a non-null source_activity is the single
             anchor that guarantees a complete deal-level context.

        Removed during the standardisation refactor:
          - "source_contact required" rule. The field was removed from
             BaseSignal — the contacts who participated in the source
             conversation are now derived from source_activity.contacts
             at read time.

        All quantitative and human-level validation (who is impacted,
        what the metric is, etc.) lives on ImpactSignal and is enforced
        there.
        """
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A pain signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"PainSignal | "
            f"{self.get_what_display()} × {self.get_dimension_display()} | "
            f"{self.get_status_display()}"
        )