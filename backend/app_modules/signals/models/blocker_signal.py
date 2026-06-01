# app_modules/signals/models/blocker_signal.py
"""
BlockerSignal — concrete signal for deal-blocking objections / freins.

A BlockerSignal captures something raised during a sales conversation that
stands in the way of moving the deal forward — an objection, a missing
piece of information, a stakeholder hesitation, a budget concern, a
timing constraint. Unlike Pain / Objective / Impact / TechStack, a
blocker is intentionally NOT clustered: each blocker is a one-shot
observation tied to its source conversation and (optionally) to the
specific contact who raised it.

Rationale for the minimal field surface
---------------------------------------
The deliberate design choice is "free text + one contact":

  * `summary`  — free-text narrative of the blocker as expressed during
                 the call. No canonical axes, no taxonomy. Blockers
                 are too varied and too contextual to fit a controlled
                 vocabulary, and forcing one would erode signal at
                 capture time.

  * `contact`  — optional FK to the Contact who raised the blocker.
                 Nullable because not every blocker is attributable
                 to a single contact (a budget issue may be a company
                 stance, not a personal one). SET_NULL on contact
                 deletion keeps the blocker valid as a deal-level
                 observation even when its attribution is lost.

No participation in cluster aggregation
---------------------------------------
BlockerSignal is intentionally excluded from the cluster model:

  * `signal_category` is shadow-overridden to None — no commercial
    categorisation. Blockers are operational obstacles, not
    diagnostic signals.

  * `canonical_key` stays None on every BlockerSignal — see save()
    below. The column is inherited from BaseSignal as nullable and
    indexed, but no key is ever computed because there is no canonical
    axis on which to cluster blockers.

  * Cache invalidation targets only SIGNALS_CACHE_TAG (never
    SIGNAL_CLUSTERS_CACHE_TAG). See
    app_modules/signals/signals/cache_invalidation.py.

Lifecycle (inherited from BaseSignal)
-------------------------------------
Standard SignalStatus flow:
    MANUAL source    → status = VALIDATED at create
    LLM_EXTRACTED    → status = PENDING at create; rep validates / rejects
                       via the dedicated endpoints.

Required context (enforced in clean())
--------------------------------------
  - source_activity — every blocker must be tied to a real conversation.
    Mirror of PainSignal's strict stance. The activity is the only
    durable anchor for audit and LLM retrieval purposes.

Contacts attribution
--------------------
Two distinct surfaces:

  * `contact`             — single FK to the Contact who raised the
                             blocker (optional, blocker-specific
                             attribution).
  * `source_activity.contacts` — the full participant list of the
                             source conversation, exposed read-only
                             via the standardised `source_context`
                             block in serializers (SignalSourceMixin
                             in base_serializer.py).

These are NOT redundant: the FK identifies the originator of the
blocker; the m2m on the activity identifies the room. A blocker may
have been raised by one participant while three were present.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.client_scope import ClientScopeManager

from .base_model import BaseSignal


class BlockerSignal(BaseSignal):
    """
    Concrete signal for a deal-blocking objection / frein.

    Structure:
      - summary : free-text narrative of the blocker (required)
      - contact : optional FK to the Contact who raised the blocker

    Required context (via clean()):
      - source_activity — every blocker must be tied to a conversation

    Cluster identity:
      None. BlockerSignal does not participate in the cluster model:
      `signal_category` is shadow-overridden, `canonical_key` stays
      None on every instance, and cache invalidation does NOT bust
      the cluster tag.
    """

    # =========================================================================
    # SHADOW OVERRIDES — narrow the BaseSignal field set
    # =========================================================================
    # `signal_category` is shadow-overridden to None: blockers are
    # operational obstacles, not diagnostic signals, and have no
    # meaningful commercial categorisation. Django treats `= None` on
    # a concrete subclass as "this field does not exist on the
    # concrete model" — no column is created, no get_FIELD_display, no
    # serialization.
    #
    # Inherited fields kept as-is:
    #   account, source_activity, decision_cycle, campaign, source_quote,
    #   confidence, is_inferred, metadata, source, requested_by,
    #   language_original, status, validated_by, validated_at,
    #   original_value, canonical_key, audit fields. canonical_key
    #   remains a queryable column for shape consistency with other
    #   signal types, but is never populated (see save()).
    signal_category = None

    # =========================================================================
    # NARRATIVE CONTENT
    # =========================================================================

    summary = models.TextField(
        verbose_name=_('Summary'),
        help_text=_(
            'Free-text description of the blocker as raised during the '
            'conversation (objection, hesitation, missing information, '
            'budget concern, timing constraint, etc.). No canonical '
            'taxonomy — blockers are captured verbatim.'
        ),
    )

    # =========================================================================
    # ATTRIBUTION
    # =========================================================================

    contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.SET_NULL,
        related_name='blocker_signals',
        null=True,
        blank=True,
        verbose_name=_('Contact'),
        help_text=_(
            'Optional FK to the Contact who raised the blocker. '
            'Nullable: not every blocker is attributable to a single '
            'contact (a company-wide budget stance has no single '
            'originator). SET_NULL preserves the blocker as a '
            'deal-level observation even when its attribution is lost.'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_blocker'
        verbose_name = _('Blocker Signal')
        verbose_name_plural = _('Blocker Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'], name='blksig_account_idx'),
            models.Index(fields=['status'],  name='blksig_status_idx'),
            models.Index(fields=['contact'], name='blksig_contact_idx'),
            # Composite index supporting the Activity workspace's primary
            # access path: "list blockers on activity X".
            models.Index(
                fields=['account', 'source_activity'],
                name='blksig_account_activity_idx',
            ),
        ]

    # =========================================================================
    # SAVE — force canonical_key to None (BlockerSignal does not cluster)
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        BlockerSignal never participates in cluster aggregation.

        The `canonical_key` column is inherited from BaseSignal (nullable,
        indexed) for shape consistency with other signal types, but is
        explicitly forced to None on every save — no canonical axis exists
        on a blocker and no clustering ever runs over them.

        BaseSignal.save() then applies the shared business rules
        (MANUAL → VALIDATED + confidence cleared, LLM-create guard).
        """
        self.canonical_key = None
        super().save(*args, **kwargs)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    def clean(self):
        """
        Enforce BlockerSignal-specific constraints.

        Rules:
          1. source_activity is required — every blocker has an origin
             conversation. Mirror of PainSignal's strict stance.
        """
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A blocker signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        truncated = (self.summary or '')[:60]
        return (
            f"BlockerSignal | "
            f"{truncated} | "
            f"{self.get_status_display()}"
        )
