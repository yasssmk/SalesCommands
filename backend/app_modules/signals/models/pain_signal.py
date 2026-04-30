# app_modules/signals/models/pain_signal.py
"""
PainSignal — concrete signal for qualitative pain diagnosis.

Pain = the DIAGNOSIS (qualitative)
Impact = the PROOF  (quantitative and/or human)

A PainSignal captures the structural problem an account is experiencing,
identified by two orthogonal canonical axes (what × dimension). It is
deliberately narrative-only:

  * No metrics, costs, or numeric evidence — those live in PainImpact.
  * No impacted department / contact — those live in PainImpact.
  * No human impact enum — those live in PainImpact (PERSONAL type).

Canonical key (auto-computed in save()):
    canonical_key = "pain:<what>:<dimension>"

The canonical_key enables cluster aggregation across multiple observations
of the same pain on the same account — regardless of who reported it,
when, or which angle was documented. See SignalClusterService (Sprint 2)
for how clusters roll up PainImpacts across their member Pains.

Required context (enforced in clean()):
  - source_contact — the contact who reported the pain
  - source_activity — the call/meeting where the pain was identified

Note: source_activity is REQUIRED here. Unlike earlier drafts that accepted
"at least one of activity / cycle / campaign", every Pain must now be tied
to a real conversation — this guarantees that every Pain has a traceable
origin for audit and LLM retrieval purposes. Decision cycle and campaign
remain optional secondary links inherited from BaseSignal.

Cross-reference with TechStack (Sprint TechStack)
-------------------------------------------------
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
from ..constants import SignalWhat, SignalDimension


class PainSignal(BaseSignal):
    """
    Concrete signal for a qualitative pain diagnosis.

    Structure:
      - what      : domain of the pain (SignalWhat enum, required)
      - dimension : friction experienced (SignalDimension enum, required)
      - summary   : free-text description of the pain (required)
      - source_quote : optional verbatim excerpt from the transcript
      - notes   : optional additional context

    Required context (via clean()):
      - source_contact
      - source_activity

    Cluster identity:
      canonical_key = "pain:<what>:<dimension>" — auto-computed in save().

    Metrics, cost estimates, impacted parties, and human consequences all
    live on the related PainImpact model. A Pain can have zero or many
    PainImpacts (1:N, FK on PainImpact.pain_signal).
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
    # CROSS-REFERENCE — TechStack (Sprint TechStack)
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
            models.Index(fields=['account'],    name='painsig_account_idx'),
            models.Index(fields=['what'],       name='painsig_what_idx'),
            models.Index(fields=['dimension'],  name='painsig_dimension_idx'),
            models.Index(fields=['status'],     name='painsig_status_idx'),
            # Composite index for cluster lookups by canonical_key scoped to account.
            # Serves SignalClusterService.list_clusters_for_account (Sprint 2).
            models.Index(
                fields=['account', 'canonical_key'],
                name='painsig_account_canon_idx',
            ),
            # Composite index for TechStack cluster's related_pain_clusters
            # lookup: "find all Pains on account X cross-referencing
            # TechCatalog entry Y". See SignalClusterService Phase 6.
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
          1. source_contact is required  — every pain has an origin contact.
          2. source_activity is required — every pain has an origin conversation.

        All quantitative and human-level validation (who is impacted, what
        the metric is, etc.) lives on PainImpact and is enforced there.
        """
        super().clean()

        errors = {}

        if not self.source_contact_id:
            errors['source_contact'] = _(
                'A pain signal must be linked to a source contact.'
            )

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