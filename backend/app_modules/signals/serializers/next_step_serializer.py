# app_modules/signals/serializers/next_step_serializer.py
"""
Serializers for NextStepSignal.

Stack:
  NextStepSignalListSerializer   — lightweight list view
  NextStepSignalDetailSerializer — full detail (validated_*, requested_by,
                                    source_quote, metadata, original_value
                                    on top of the list payload)
  NextStepSignalCreateSerializer — write path
  NextStepSignalUpdateSerializer — restricted PATCH

Notes:
  - The model shadow-overrides `signal_category` to None on the
    concrete NextStepSignal. Among the base serializer fields, only
    `signal_category` (and its `signal_category_display` companion)
    requires filtering — same pattern as BlockerSignal /
    TechStackSignalSerializer.

  - NextStepSignal does not carry canonical axes (no `what` / `dimension`)
    and does not participate in cluster aggregation. The inherited
    `canonical_key` field stays in the base fields for shape
    consistency but is always None on a NextStepSignal — see
    NextStepSignal.save().

  - `suggested_contacts` (M2M Contact) is the next-step-specific
    attribution surface (the future Activity's attendees / recipients).
    It is exposed top-level as a compact list. Contacts who
    PARTICIPATED in the source conversation remain a distinct concept,
    accessible read-only through the standardised `source_context`
    block produced by SignalSourceSerializer.

  - source_activity is required at the model layer
    (NextStepSignal.clean) and re-surfaced at the Create serializer
    for a clean API error payload, mirroring PainSignal /
    BlockerSignal.

  - `source_quote` (inherited from BaseSignal) carries the
    justification / rationale for the suggestion on NextStepSignal
    — see NextStepSignal model docstring and TECH_DEBT.md TD-5.
"""

from rest_framework import serializers

from core.error_messages import ActivityErrorMessages, SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..models import NextStepSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — display + compact contacts
# =============================================================================

class _NextStepDisplayMixin:
    """Shared SerializerMethodField implementations for NextStep serializers."""

    def get_suggested_contacts(self, obj):
        """
        Compact list of suggested contacts — keeps the frontend from
        issuing N separate /contacts/<id>/ fetches just to render the
        suggested attendees on a next-step card. Returns [] when no
        contacts are suggested.

        DORMANT CAPABILITY: this read surface is wired end to end but
        currently always returns [] in practice, because the extraction
        pipeline never populates `suggested_contacts` (the v1 prompt does
        not emit contacts — TD-7). The field is fed only through the
        Create/Update serializers (API), not by the LLM. Kept as the
        foundation for suggested-contact resolution — do not treat the
        empty result as a bug.

        Relies on the parent ViewSet having
        `prefetch_related('suggested_contacts')` on the queryset to
        avoid N+1 — see NextStepSignalViewSet.get_queryset().
        """
        return [
            {
                'id':         str(c.id),
                'first_name': c.first_name,
                'last_name':  c.last_name,
                'job_title':  getattr(c, 'job_title', None),
            }
            for c in obj.suggested_contacts.all()
        ]

    def get_linked_activity(self, obj):
        """
        Compact representation of the Activity materialized from this
        suggestion (via Activity.next_step_signal FK, reverse accessor
        ``created_activities``).  Returns None when no Activity has been
        created yet.

        Relies on the parent ViewSet having
        ``prefetch_related('created_activities')`` on the queryset.
        """
        activity = obj.created_activities.first() if hasattr(obj, '_prefetched_objects_cache') and 'created_activities' in obj._prefetched_objects_cache else obj.created_activities.first()
        return _compact_activity(activity)

    def get_attached_activity(self, obj):
        """
        The EXISTING activity this next step was linked to ("Lier") — same
        compact shape as linked_activity (the activity CREATED from it).
        None when not linked.
        """
        return _compact_activity(obj.attached_activity)

    def get_suggested_decision_step_detail(self, obj):
        """The DC step proposed for this next step — {id, name, order}, or
        None when not deduced."""
        step = obj.suggested_decision_step
        if step is None:
            return None
        return {'id': str(step.id), 'name': step.name, 'order': step.order}

    def get_suggested_people(self, obj):
        """
        Compact list of the People (PeopleSignal) this next step involves,
        with their contact when there is one (it becomes an activity contact
        at conversion). Relies on the ViewSet prefetch of
        ``suggested_people__target_contact``.
        """
        return [
            {
                'id':             str(p.id),
                'full_name':      p.full_name,
                'role':           p.role,
                # 5.8h: a REJECTED People is never used (the pre-fill reads it).
                'status':         p.status,
                'target_contact': (
                    {
                        'id':         str(p.target_contact.id),
                        'first_name': p.target_contact.first_name,
                        'last_name':  p.target_contact.last_name,
                    }
                    if p.target_contact_id else None
                ),
            }
            for p in obj.suggested_people.all()
        ]


def _compact_activity(activity):
    """Compact Activity shape shared by linked_activity / attached_activity."""
    if not activity:
        return None
    return {
        'id':                    str(activity.id),
        'title':                 activity.title,
        'activity_type':         activity.activity_type,
        'activity_type_display': activity.get_activity_type_display(),
        'status':                activity.status,
        'status_display':        activity.get_status_display(),
        'scheduled_date':        activity.scheduled_date.isoformat() if activity.scheduled_date else None,
        'due_date':              activity.due_date.isoformat() if activity.due_date else None,
    }


# Sprint Next steps (1.1 / 1.3) — the structured fields of the activity
# proposal, read by List AND Detail (one list keeps the two in sync).
_STRUCTURED_READ_FIELDS = [
    'suggested_date_text',
    'suggested_decision_step',
    'suggested_decision_step_detail',
    'suggested_topics',
    'suggested_success_criterion',
    'carried_by_prospect',
    'suggested_people',
    'suggested_people_names',
    'suggested_internal_names',
    'attached_activity',
    'advice_rationale',
]

# The same fields, editable by PATCH (attached_activity excepted: the link to
# an existing activity goes through the link service, which validates it and
# keeps it exclusive with the created activity).
_STRUCTURED_WRITE_FIELDS = [
    'suggested_date_text',
    'suggested_decision_step',
    'suggested_topics',
    'suggested_success_criterion',
    'carried_by_prospect',
    'suggested_people',
    'suggested_people_names',
    'suggested_internal_names',
    'advice_rationale',
]


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# NextStepSignal shadow-overrides `signal_category` to None on the
# concrete model. Among the base serializer fields, only signal_category
# and its signal_category_display companion need to be stripped — they
# are declared at the top level of BaseSignalListSerializer /
# BaseSignalDetailSerializer / BaseSignalCreateSerializer /
# BaseSignalUpdateSerializer. We strip them here once and reuse the
# resulting filtered lists in every Meta below — keeps the four
# serializers in sync. Same pattern as BlockerSignal / TechStackSignal.

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})


def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without NextStep's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without NextStep's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class NextStepSignalListSerializer(_NextStepDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for NextStepSignal list endpoints.

    Exposes the structured payload (suggested_title,
    suggested_activity_type, suggested_due_date, suggested_contacts)
    and the standardised `source_context` block inherited from the
    base.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    suggested_contacts             = serializers.SerializerMethodField()
    suggested_activity_type_display = serializers.SerializerMethodField()
    linked_activity                = serializers.SerializerMethodField()
    attached_activity              = serializers.SerializerMethodField()
    suggested_decision_step_detail = serializers.SerializerMethodField()
    suggested_people               = serializers.SerializerMethodField()

    def get_suggested_activity_type_display(self, obj):
        return obj.get_suggested_activity_type_display()

    class Meta(BaseSignalListSerializer.Meta):
        model = NextStepSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'suggested_title',
            'suggested_activity_type',
            'suggested_activity_type_display',
            'suggested_due_date',
            'suggested_objective',
            'suggested_contacts',
            'linked_activity',
        ] + _STRUCTURED_READ_FIELDS
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class NextStepSignalDetailSerializer(_NextStepDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for NextStepSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer.

    Note on `source_quote` semantics: for NextStepSignal, it carries
    the justification / rationale for the suggestion — see the model
    docstring and TECH_DEBT.md (TD-5).

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    suggested_contacts             = serializers.SerializerMethodField()
    suggested_activity_type_display = serializers.SerializerMethodField()
    linked_activity                = serializers.SerializerMethodField()
    attached_activity              = serializers.SerializerMethodField()
    suggested_decision_step_detail = serializers.SerializerMethodField()
    suggested_people               = serializers.SerializerMethodField()

    def get_suggested_activity_type_display(self, obj):
        return obj.get_suggested_activity_type_display()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = NextStepSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'suggested_title',
            'suggested_activity_type',
            'suggested_activity_type_display',
            'suggested_due_date',
            'suggested_objective',
            'suggested_contacts',
            'linked_activity',
        ] + _STRUCTURED_READ_FIELDS
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class NextStepSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for NextStepSignal creation.

    signal_type is fixed to 'next_step' via HiddenField (consumed by
    SignalManager.create() — same identifier across all layers).

    Required:
      - account                  (inherited)
      - source_activity          — every suggestion must be tied to a
                                    conversation
      - suggested_title          — proposed Activity title
      - suggested_activity_type  — proposed ActivityType

    Optional:
      - suggested_due_date       — proposed deadline (nullable)
      - suggested_contacts       — proposed attendees (M2M)
      - source_quote (= justification for the suggestion — see model
         docstring),
        language_original, source, confidence, is_inferred, metadata
        (inherited)

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    source_activity rule is enforced at both the model level
    (NextStepSignal.clean) and the serializer level for a consistent
    API error payload — mirror of PainSignal / BlockerSignal.
    """

    signal_type = serializers.HiddenField(default='next_step')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = NextStepSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        # `suggested_contacts` is a DORMANT-but-wired M2M: writable here via
        # the API, but the extraction pipeline never sets it (the v1 prompt
        # does not emit contacts — TD-7). Keep it exposed for write — it is
        # the foundation for suggested-contact resolution. Do not remove.
        fields = _base_fields + [
            'suggested_title',
            'suggested_activity_type',
            'suggested_due_date',
            'suggested_contacts',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'suggested_title':         {'required': True},
            'suggested_activity_type': {'required': True},
            'suggested_due_date':      {'required': False, 'allow_null': True},
            'suggested_contacts':      {'required': False},
        }

    def validate(self, attrs):
        """
        Enforce NextStep-specific contextual rules, then delegate to base.

        Rule (re-surfaced from NextStepSignal.clean()):
          1. source_activity always required — every suggestion must
             be tied to a real conversation.
        """
        if not attrs.get('source_activity'):
            raise StandardizedValidationError(
                SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
            )

        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class NextStepSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for NextStepSignal.

    Allowed beyond base fields (source_quote, metadata):
      - suggested_title         — title may be refined post-extraction
      - suggested_activity_type — type may be corrected (e.g. CALL → MEETING)
      - suggested_due_date      — deadline may be set or updated
      - suggested_contacts      — attendee list may be amended
      - suggested_objective     — the activity objective (→ call_to_action)
      - the structured proposal (_STRUCTURED_WRITE_FIELDS): date text, DC
        step (must be a step of the next step's own cycle), topics, success
        criterion, carried_by_prospect, People (same tenant AND account —
        base _validate_fk_scope), unresolved / internal names (lists of
        strings), advice rationale.

    Not writable here: attached_activity (link service, bloc 2).

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = NextStepSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        # `suggested_contacts` stays PATCH-able (dormant capability): the API
        # can amend it, but nothing feeds it automatically yet — the LLM
        # extraction never emits contacts (TD-7). Kept for the future
        # suggested-contact resolution feature. Do not remove.
        fields = _base_fields + [
            'suggested_title',
            'suggested_activity_type',
            'suggested_due_date',
            'suggested_contacts',
            'suggested_objective',
        ] + _STRUCTURED_WRITE_FIELDS
        extra_kwargs = {
            **_base_extra_kwargs,
            'suggested_title':         {'required': False},
            'suggested_activity_type': {'required': False},
            'suggested_due_date':      {'required': False, 'allow_null': True},
            'suggested_contacts':      {'required': False},
            'suggested_objective':     {'required': False, 'allow_null': True},
            'suggested_decision_step': {'required': False, 'allow_null': True},
            'suggested_people':        {'required': False},
        }

    # JSON columns: typed as lists of non-empty names (a bare string or any
    # other JSON shape is a 400, never stored).
    suggested_people_names   = serializers.ListField(
        child=serializers.CharField(max_length=255), required=False,
    )
    suggested_internal_names = serializers.ListField(
        child=serializers.CharField(max_length=255), required=False,
    )

    def validate(self, attrs):
        """
        Base guard first (tenant + account of every FK / M2M, People
        included), then: the proposed DC step must belong to the next step's
        own decision cycle — DecisionStep carries no account_id, so the base
        guard cannot see a step of another deal.
        """
        attrs = super().validate(attrs)
        step = attrs.get('suggested_decision_step')
        if step is not None and (
            self.instance is None
            or step.cycle_id != self.instance.decision_cycle_id
        ):
            raise StandardizedValidationError(
                ActivityErrorMessages.STEP_MUST_BELONG_TO_CYCLE
            )
        return attrs
