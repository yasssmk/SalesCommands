# app_modules/signals/models/competitor_signal.py
"""
CompetitorSignal — concrete signal for a competitor named on a deal.

Detached signal (DC-only at read time), cloned on the existing signal
pattern. It captures a competitor observed during a conversation:

  * verbatim  — inherited `source_quote` (BaseSignal); NOT redeclared.
  * summary   — one-sentence LLM résumé, declared on this concrete model
                (mirror of ConstraintSignal.summary / PainSignal.summary).
  * competitor_name            — the competitor's identity (required).
  * competitor_name_normalized — derived in save() from competitor_name
                (calqued on TechStackSignal.tech_name_normalized): the key
                used to group / filter / de-duplicate observations of the
                same competitor.

Detachment (mirror of BlockerSignal / ConstraintSignal)
-------------------------------------------------------
  * signal_category is shadow-overridden to None (competitors are not
    tagged with a commercial category).
  * canonical_key stays None on every CompetitorSignal — forced in save()
    (mirror of BlockerSignal.save() / ConstraintSignal.save()). Competitors
    do not cluster on a what × dimension canonical_key; the cluster axis
    (competitor_name_normalized) is resolved at read time.
  * No what / dimension axes are declared — CompetitorSignal is a new model
    with no legacy rows, so there is nothing to keep nullable.

`decision_cycle` is inherited from BaseSignal (NOT shadow-overridden): the
"DC-only" nature is a read-time concern, not a model-level override.

Lifecycle (inherited from BaseSignal)
-------------------------------------
Standard SignalStatus flow:
    MANUAL source    → status = VALIDATED at create
    LLM_EXTRACTED    → status = PENDING at create; rep validates / rejects

Required context (enforced in clean())
--------------------------------------
  - source_activity — every competitor observation must be tied to a
    conversation (mirror of ConstraintSignal.clean()).
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal


class CompetitorSignal(BaseSignal):
    """
    Concrete signal for a competitor named on a deal.

    Structure:
      - competitor_name            : raw display name (required)
      - competitor_name_normalized : derived in save() (lower + trim +
                                     collapse); the grouping / filtering /
                                     de-dup key.
      - summary                    : one-sentence description (required)
      - source_quote               : optional verbatim excerpt (inherited)

    Required context (via clean()):
      - source_activity (every competitor observation must be tied to a
        conversation)

    Cluster identity:
      canonical_key stays None (mirror of BlockerSignal). Competitors are
      grouped on competitor_name_normalized at read time, not on a
      what × dimension canonical_key.
    """

    # =========================================================================
    # SHADOW OVERRIDES
    # =========================================================================
    signal_category = None

    # =========================================================================
    # COMPETITOR IDENTITY (raw + derived normalised key)
    # =========================================================================
    #
    # `competitor_name` is the single source of truth for the competitor's
    # identity. `competitor_name_normalized` is DERIVED from it in save()
    # and must never be authored by a caller — see the SAVE section below.
    # Calqued on TechStackSignal.tech_name / tech_name_normalized.

    competitor_name = models.CharField(
        max_length=255,
        verbose_name=_('Competitor Name'),
        help_text=_(
            'Raw display name of the competitor exactly as it was written '
            'by the LLM or the rep (e.g. "Acme Corp"). Never rewritten — '
            'casing, spacing and wording are preserved for display. '
            'Grouping, filtering and de-duplication use '
            '`competitor_name_normalized` instead.'
        ),
    )

    competitor_name_normalized = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Competitor Name (normalised)'),
        help_text=_(
            'Derived from `competitor_name` on every save: lowercased, '
            'trimmed, internal whitespace collapsed to single spaces. '
            'This is the key used to group, filter and de-duplicate '
            'observations of the same competitor. Read-only by contract — '
            'it is recomputed at save() time, so any value written by a '
            'caller is discarded and the two columns cannot desync. '
            'Empty string when `competitor_name` is blank.'
        ),
    )

    # =========================================================================
    # NARRATIVE CONTENT
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_('One-sentence description of the competitor observation'),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_competitor'
        verbose_name = _('Competitor Signal')
        verbose_name_plural = _('Competitor Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'], name='cmpsig_account_idx'),
            models.Index(fields=['status'], name='cmpsig_status_idx'),
            # Grouping / filtering surface for "which deals name competitor X"
            # and for de-duplicating repeated observations of one competitor.
            models.Index(
                fields=['competitor_name_normalized'],
                name='cmpsig_name_norm_idx',
            ),
            # No what / dimension / canonical_key index: the axes are
            # detached (canonical_key always None, no what/dimension).
        ]

    # =========================================================================
    # SAVE — canonical_key forced to None + competitor_name_normalized derived
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        Force canonical_key to None and recompute competitor_name_normalized
        from competitor_name, then delegate to BaseSignal.save().

        canonical_key: CompetitorSignal does not cluster on a
        what × dimension key — the column is inherited from BaseSignal for
        shape consistency but is explicitly forced to None on every save
        (mirror of BlockerSignal.save() / ConstraintSignal.save()).

        competitor_name_normalized: recomputed on every write from
        competitor_name (calqued on TechStackSignal.save()). This is the
        single normalisation point — every write path goes through
        Model.save(), so the normalised key can never desync from its raw
        name.
        """
        self.canonical_key = None
        self.competitor_name_normalized = self._normalize_competitor_name(
            self.competitor_name
        )
        super().save(*args, **kwargs)

    @staticmethod
    def _normalize_competitor_name(value):
        """
        Lowercase + trim + collapse internal whitespace.

        "  Acme   Corp " -> "acme corp"
        None / "" / "   "     -> ""
        """
        if not value:
            return ''
        # str.split() with no argument splits on arbitrary runs of
        # whitespace AND drops the leading/trailing runs, so the join
        # covers strip + collapse in one pass.
        return ' '.join(str(value).lower().split())

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A competitor signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        return (
            f"CompetitorSignal | "
            f"{self.competitor_name or 'unnamed-competitor'} | "
            f"{self.get_status_display()}"
        )
