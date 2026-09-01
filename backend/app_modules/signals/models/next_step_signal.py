# app_modules/signals/models/next_step_signal.py
"""
NextStepSignal — concrete signal for a follow-up action suggested
post-conversation.

A NextStepSignal captures something proposed after a sales conversation
as the next move to keep the deal moving forward — typically a
follow-up call, an email recap, a meeting invitation, a task to send
documentation. Unlike Pain / Objective / Impact / TechStack, a
next-step is intentionally NOT clustered: each suggestion is a
one-shot, conversation-anchored proposal whose value collapses the
moment the rep either materialises it into an actual Activity or
dismisses it.

Distinction from BlockerSignal
------------------------------
Both NextStepSignal and BlockerSignal are non-clustering, conversation-
anchored signals, but they carry DIFFERENT shapes:

  * BlockerSignal  — single free-text `summary`, optional FK to a
                     single attribution contact. Captures "what stands
                     in the way" verbatim, with no taxonomy.

  * NextStepSignal — STRUCTURED payload (suggested_title,
                     suggested_activity_type, suggested_due_date,
                     suggested_contacts M2M). The structure mirrors
                     the shape of a future Activity so the rep can
                     materialise the suggestion in one click into a
                     real Activity row (see
                     `Activity.next_step_signal` FK introduced in the
                     activities migration of this sprint).

Rationale for the structured payload
------------------------------------
The end-game of a NextStepSignal is to BECOME an Activity. Storing
free text would force the rep to re-type fields the LLM already
inferred (title, type, date, attendees). The four structured fields
below are EXACTLY the minimal Activity scaffolding required to
pre-fill the create-activity form:

  * `suggested_title`         — CharField, required. The proposed
                                 Activity title.
  * `suggested_activity_type` — CharField with choices=ActivityType,
                                 required. Drives the icon / category
                                 of the materialised Activity.
  * `suggested_due_date`      — DateField, nullable. The LLM may
                                 suggest a follow-up without a hard
                                 deadline ("send a recap soon"); the
                                 rep fills it at validation time.
  * `suggested_contacts`      — M2M to Contact, optional. Future
                                 attendees / recipients. Distinct
                                 from the participants of the SOURCE
                                 conversation (those remain
                                 accessible via the standardised
                                 source_context block).

source_quote contract
---------------------
`source_quote` is INHERITED from BaseSignal. For NextStepSignal it
must carry the JUSTIFICATION / RATIONALE for the suggestion — NOT an
arbitrary verbatim excerpt from the transcript.

Example:
  source_quote = "Le DSI a demandé un récap chiffré sous 48h"
                  (NOT "Et donc voilà, à plus tard.")

This contract is enforced by the future next-steps LLM extraction
pipeline (Sprint B4). Documented here so the semantics do not drift
when B4 lands. See TECH_DEBT.md (TD-5).

No participation in cluster aggregation
---------------------------------------
NextStepSignal is intentionally excluded from the cluster model, for
the same reasons as BlockerSignal:

  * `signal_category` is shadow-overridden to None — no commercial
    categorisation. A next step is an operational proposal, not a
    diagnostic signal.

  * `canonical_key` stays None on every NextStepSignal — see save()
    below. Column is inherited from BaseSignal as nullable and
    indexed, but no key is ever computed because there is no
    canonical axis on which to cluster suggestions.

  * Cache invalidation targets only SIGNALS_CACHE_TAG (never
    SIGNAL_CLUSTERS_CACHE_TAG). See
    app_modules/signals/signals/cache_invalidation.py.

Lifecycle (inherited from BaseSignal)
-------------------------------------
Standard SignalStatus flow:
    MANUAL source    → status = VALIDATED at create
    LLM_EXTRACTED    → status = PENDING at create; rep validates /
                       rejects via the dedicated endpoints.

The "validate" semantic on a NextStepSignal is the green light for
the rep to materialise the suggestion into an actual Activity via the
LLMNextStepActivityFormModal (frontend, Sprint F7).

Required context (enforced in clean())
--------------------------------------
  - source_activity — every suggestion must be tied to the real
    conversation that produced it. Mirror of PainSignal /
    BlockerSignal strict stance. The activity is the only durable
    anchor for audit and LLM retrieval purposes.

Reverse relation from Activity
------------------------------
The Activity model carries a `next_step_signal` FK pointing here
(introduced in the activities migration of this sprint, with
`related_name='created_activities'`). The reverse accessor is then:

    next_step_signal.created_activities.all()

It returns the Activities that were materialised from this
suggestion. DB-level cardinality is FK (not OneToOne) so technically
multiple Activities could reference the same suggestion; the product
contract is "logically 1:1" (one suggestion → one Activity created
from it), but we do not enforce uniqueness because:

  * Soft duplicates from retries / network failures should not raise.
  * REJECTING a NextStepSignal that already has an associated
    materialised Activity leaves the FK intact for audit ("this
    Activity was created from a suggestion that was later
    rejected").
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from app_modules.activities.constants import ActivityType
from core.client_scope import ClientScopeManager

from .base_model import BaseSignal


class NextStepSignal(BaseSignal):
    """
    Concrete signal for a post-conversation follow-up suggestion.

    Structured payload (mirror of Activity scaffolding):
      - suggested_title         : CharField, required
      - suggested_activity_type : CharField (ActivityType choices), required
      - suggested_due_date      : DateField, nullable
      - suggested_contacts      : M2M to Contact, blank=True

    Required context (via clean()):
      - source_activity — every suggestion must be tied to its
        originating conversation.

    Cluster identity:
      None. NextStepSignal does not participate in the cluster model:
      `signal_category` is shadow-overridden, `canonical_key` stays
      None on every instance, and cache invalidation does NOT bust
      the cluster tag.
    """

    # =========================================================================
    # SHADOW OVERRIDES — narrow the BaseSignal field set
    # =========================================================================
    # `signal_category` is shadow-overridden to None: next steps are
    # operational proposals, not diagnostic signals, and have no
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
    # STRUCTURED PAYLOAD — mirror of Activity scaffolding
    # =========================================================================

    suggested_title = models.CharField(
        max_length=255,
        verbose_name=_('Suggested Title'),
        help_text=_(
            'Proposed title for the Activity that would materialise '
            'this suggestion. Max length aligned with Activity.title.'
        ),
    )

    suggested_activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        verbose_name=_('Suggested Activity Type'),
        help_text=_(
            'Proposed type of the next-step Activity (CALL / EMAIL / '
            'MEETING / TASK / LINKEDIN / OTHER). Choices imported '
            'directly from ActivityType to keep a single source of '
            'truth — no enum duplication.'
        ),
    )

    suggested_due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Suggested Due Date'),
        help_text=_(
            'Optional proposed deadline for the materialised Activity. '
            'Nullable: the LLM may legitimately suggest a follow-up '
            'without a hard deadline ("send a recap soon"); the rep '
            'fills the actual due date at materialisation time.'
        ),
    )

    # DORMANT CAPABILITY — do NOT remove. `suggested_contacts` is fully
    # wired (writable via the Create/Update serializers → SignalManager's
    # M2M .set() path, read/displayed by the next-step front surfaces) and
    # covered by tests, but it is NEVER fed by the extraction pipeline: the
    # v1 next-steps prompt does not emit contacts and NextStepExtractor
    # leaves the M2M empty (TD-7). It is the foundation for the future
    # "suggested contact resolution" feature — kept intentionally.
    suggested_contacts = models.ManyToManyField(
        'module_contacts.Contact',
        related_name='suggested_in_next_steps',
        blank=True,
        verbose_name=_('Suggested Contacts'),
        help_text=_(
            'Optional list of contacts proposed as attendees / '
            'recipients of the materialised Activity. Distinct from '
            'the participants of the SOURCE conversation, who remain '
            'accessible read-only through the standardised '
            'source_context block (derived from source_activity.contacts).'
        ),
    )

    # A NextStepSignal carries the OBJECTIVE of the activity it proposes
    # (what it is for, the stakes — prospect + commercial angle). It is
    # generated by the next-steps extraction prompt and pre-fills
    # Activity.call_to_action at materialisation (see the mapping in
    # app_modules/activities/serializers.py, ActivityCreateSerializer.create).
    suggested_objective = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Suggested Objective'),
        help_text=_(
            'Optional proposed objective for the materialised Activity. '
            'Mapped onto Activity.call_to_action at materialisation (the '
            'unified "Activity Objective") when the create payload does not '
            'set one explicitly. The prompt that fills this is out of scope '
            'here — this only lays the field + mapping.'
        ),
    )

    # =========================================================================
    # META
    # =========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=[],
    )):
        db_table = 'module_signals_next_step'
        verbose_name = _('Next Step Signal')
        verbose_name_plural = _('Next Step Signals')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account'], name='nxstsig_account_idx'),
            models.Index(fields=['status'],  name='nxstsig_status_idx'),
            # Composite index supporting the Activity workspace's primary
            # access path: "list next-step suggestions on activity X".
            models.Index(
                fields=['account', 'source_activity'],
                name='nxstsig_acc_act_idx',
            ),
            # Supports the Next Steps Tab UI sort/filter on upcoming
            # deadlines.
            models.Index(
                fields=['suggested_due_date'],
                name='nxstsig_due_idx',
            ),
        ]

    # =========================================================================
    # SAVE — force canonical_key to None (NextStepSignal does not cluster)
    # =========================================================================

    def save(self, *args, **kwargs):
        """
        NextStepSignal never participates in cluster aggregation.

        The `canonical_key` column is inherited from BaseSignal (nullable,
        indexed) for shape consistency with other signal types, but is
        explicitly forced to None on every save — no canonical axis exists
        on a suggestion and no clustering ever runs over them.

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
        Enforce NextStepSignal-specific constraints.

        Rules:
          1. source_activity is required — every suggestion has an
             originating conversation. Mirror of PainSignal /
             BlockerSignal strict stance.
        """
        super().clean()

        errors = {}

        if not self.source_activity_id:
            errors['source_activity'] = _(
                'A next-step signal must be linked to a source activity.'
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================================
    # STR
    # =========================================================================

    def __str__(self):
        truncated = (self.suggested_title or '')[:60]
        return (
            f"NextStepSignal | "
            f"{truncated} | "
            f"{self.suggested_activity_type} | "
            f"{self.get_status_display()}"
        )
