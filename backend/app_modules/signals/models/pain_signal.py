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
Two optional fields enable a Pain to reference a tool that is part of
the diagnosed problem — typically (but not exclusively) when what=TECH:

  * related_techstack          — FK to a tenant-level TechCatalog entry
                                  (structured cross-reference)
  * related_techstack_mention  — free-text mention of a tool not yet
                                  catalogued, or whose identity could
                                  not be resolved at extraction time

The two fields are NOT mutually exclusive at the model level. Both may
be set simultaneously during a migration window where a textual mention
gets enriched with a structured FK. The frontend UI hides the textual
field once a FK is set, but that is purely a UX convenience — the
backend stays permissive so that progressive enrichment (mention →
identification → FK) is possible without changing schema state.

Why SET_NULL on related_techstack
---------------------------------
The cluster identity of a Pain is driven solely by what × dimension;
a related_techstack FK is secondary metadata. Removing a catalog entry
does not destroy a Pain — only its enriched cross-reference. The
mention field can survive as a textual trace.

This contrasts with TechStackSignal.tech_catalog_entry which uses
PROTECT, because that FK directly drives the TechStack cluster identity
(canonical_key = "techstack:<entry.id>") and cannot be safely nulled.

UI conditionality (frontend only)
---------------------------------
The form rule "show related_techstack* fields only when what=TECH" is
intentionally NOT enforced in the model. A Pain with what=DATA might
legitimately reference a BI tool (TechCatalog entry), and the rep
should be able to surface that cross-reference without the schema
fighting them.
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
    # ATTRIBUTION
    # =========================================================================

    target_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='pain_signals',
        null=True,
        blank=True,
        verbose_name=_('Target Department'),
        help_text=_(
            'Department concerned by this pain. Purely descriptive — '
            'no conditional enforcement (unlike ObjectiveSignal). '
            'Source (who speaks) ≠ concerned (the subject): the CTO '
            'may report a pain felt by Marketing.'
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
    # Both fields are optional and not mutually exclusive at the model
    # level — see class docstring for rationale. The frontend hides the
    # mention TextField when the FK is set, as a UX convenience.
    #
    # Used by SignalClusterService when computing the TechStack cluster's
    # `related_pain_clusters` payload: filter PainSignal.related_techstack
    # = <catalog_entry_id> on the same account, group by canonical_key,
    # and return enriched cluster summaries. The composite index below
    # (account, related_techstack) supports that lookup pattern.

    related_techstack = models.ForeignKey(
        'tech_catalog.TechCatalog',
        on_delete=models.SET_NULL,
        related_name='related_pain_signals',
        null=True,
        blank=True,
        verbose_name=_('Related TechStack'),
        help_text=_(
            'Optional structured cross-reference to a tool involved in '
            'this pain. Set when the rep can identify the tool against '
            'the tenant tech catalog. SET_NULL on catalog deletion — the '
            'pain itself remains valid, only the enriched cross-ref is lost.'
        ),
    )

    related_techstack_mention = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Related TechStack Mention'),
        help_text=_(
            'Free-text mention of a tool that could not be matched against '
            'the catalog (or whose match was deferred). Allows progressive '
            'enrichment: a textual mention can later be promoted to a '
            'structured FK once the catalog includes the tool.'
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
            # Composite index for TechStack cluster's related_pain_clusters
            # lookup: "find all Pains on account X cross-referencing
            # TechCatalog entry Y". See SignalClusterService.
            models.Index(
                fields=['account', 'related_techstack'],
                name='painsig_account_techref_idx',
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