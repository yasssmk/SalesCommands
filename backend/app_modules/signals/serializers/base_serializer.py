# app_modules/signals/serializers/base_serializer.py
"""
Base serializers for the Signals module.

Defines the shared serializer hierarchy used by all 3 concrete signal types:
  PainSignal, ObjectiveSignal, TechStackSignal.

Serializer map:
  SignalSourceSerializer       — standardised provenance block exposed
                                  under `source_context` on every signal
  BaseSignalListSerializer     — lightweight, list views
  BaseSignalDetailSerializer   — full detail, retrieve views
  BaseSignalCreateSerializer   — write path, routes signal_type to SignalManager
  BaseSignalUpdateSerializer   — restricted PATCH, routes edits through edit()
  SignalLLMSerializer          — read-only compact format for LLM prompt injection

Standardisation refactor
------------------------
- source_contact and source_department fields removed from List/Detail/
  Create/Update. Contacts who participated in the source conversation
  are now derived at read time from `source_activity.contacts` and
  exposed under `source_context.contacts`.
- last_modified_by / last_modified_at removed. updated_by / updated_at
  inherited from ModuleBaseModel cover the same need (read via the
  base ModelSerializer machinery).
- corroboration_count removed from Detail. CorroborationService is
  being deprecated (PHASE D); cluster confirmation_count is the
  replacement.
- decision_cycle / campaign removed from Create/Update fields. They
  are populated by SignalManager._propagate_activity_context from
  source_activity at create time — never written directly by the API.
- The new `source_context` block aggregates: activity (compact),
  contacts (list), decision_cycle, campaign, decision_step. Naming
  chosen to avoid collision with the existing `source` enum
  (SignalSource: MANUAL / LLM_EXTRACTED / etc.).

Shadow override support
-----------------------
Concrete signal types may shadow-override inherited base fields to None
on the model (e.g. ObjectiveSignal.signal_category = None). The base
Meta.fields list still declares `signal_category` so that other types
expose it normally. Concrete serializers that shadow-override are
expected to filter the inherited field out of their own Meta.fields
via list/dict comprehensions (see TechStackSignalSerializer for the
canonical pattern).
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError


# =============================================================================
# SIGNAL SOURCE SERIALIZER
# =============================================================================

class SignalSourceSerializer(serializers.Serializer):
    """
    Standardised provenance block for every signal type.

    Aggregates everything derivable from `source_activity`:
      - activity        : compact ActivityCompactSerializer payload or null
      - contacts        : list of contacts who participated in the
                          activity, derived from activity.contacts (m2m).
                          Empty list when source_activity is null.
      - decision_cycle  : compact dict {id, name} or null
      - campaign        : compact dict {id, name} or null
      - decision_step   : compact dict {id, name} or null

    Used via `source_context = SignalSourceSerializer(source='*', read_only=True)`
    on parent List/Detail serializers — `source='*'` passes the entire
    signal instance to this serializer.

    Empty-source semantics
    ----------------------
    Most fields gracefully degrade to None when source_activity is null:
      - activity        → None
      - contacts        → [] (empty list, never null)
      - decision_cycle  → None (read from signal.decision_cycle directly
                                on Pain/Objective; falls back to
                                activity.decision_cycle on TechStack)
      - campaign        → None (same fallback strategy)
      - decision_step   → None (no FK on signals — always derived from
                                activity.decision_step)

    decision_cycle / campaign read strategy
    ---------------------------------------
    For Pain and Objective, decision_cycle and campaign are direct FKs
    on the model — populated by SignalManager from source_activity at
    create time. We read them from the model directly (fast, indexed).

    For TechStack, both fields are shadow-overridden to None on the
    model. We fall back to source_activity.decision_cycle / .campaign
    when the direct attribute is None. The fallback uses getattr() with
    a default to avoid an explicit branch on signal type.

    Performance
    -----------
    Relies on the parent ViewSet having
    `prefetch_related('source_activity__contacts')` and
    `select_related('source_activity', 'source_activity__decision_cycle',
    'source_activity__campaign', 'source_activity__decision_step')` set
    on the queryset. See BaseSignalViewSet.get_queryset (PHASE E).
    """

    activity        = serializers.SerializerMethodField()
    contacts        = serializers.SerializerMethodField()
    decision_cycle  = serializers.SerializerMethodField()
    campaign        = serializers.SerializerMethodField()
    decision_step   = serializers.SerializerMethodField()

    # -------------------------------------------------------------------------
    # ACTIVITY
    # -------------------------------------------------------------------------

    def get_activity(self, signal):
        """
        Compact ActivityCompactSerializer payload for source_activity.
        Returns None if source_activity is not set.
        """
        activity = signal.source_activity
        if not activity:
            return None
        # Lazy import — avoid circular dependency between signals and
        # activities modules at module load time.
        from app_modules.activities.serializers import ActivityCompactSerializer
        return ActivityCompactSerializer(activity, context=self.context).data

    # -------------------------------------------------------------------------
    # CONTACTS (derived from activity)
    # -------------------------------------------------------------------------

    def get_contacts(self, signal):
        """
        List of contacts who participated in source_activity, derived
        from the activity's m2m. Empty list when source_activity is null.
        """
        activity = signal.source_activity
        if not activity:
            return []
        return [
            self._compact_contact(contact)
            for contact in activity.contacts.all()
        ]

    @staticmethod
    def _compact_contact(contact):
        """Render a Contact as a compact dict for the source_context block."""
        return {
            'id':         str(contact.id),
            'first_name': contact.first_name,
            'last_name':  contact.last_name,
            'job_title':  getattr(contact, 'job_title', None),
        }

    # -------------------------------------------------------------------------
    # DECISION CYCLE
    # -------------------------------------------------------------------------

    def get_decision_cycle(self, signal):
        """
        Compact decision_cycle dict {id, name} or None.

        Pain/Objective: direct FK on the model.
        TechStack:       shadow-overridden to None — falls back to
                         source_activity.decision_cycle.
        """
        dc = getattr(signal, 'decision_cycle', None)
        if dc is None:
            activity = signal.source_activity
            if activity is not None:
                dc = getattr(activity, 'decision_cycle', None)
        if dc is None:
            return None
        return {'id': str(dc.id), 'name': getattr(dc, 'name', None)}

    # -------------------------------------------------------------------------
    # CAMPAIGN
    # -------------------------------------------------------------------------

    def get_campaign(self, signal):
        """Compact campaign dict {id, name} or None — same fallback pattern."""
        c = getattr(signal, 'campaign', None)
        if c is None:
            activity = signal.source_activity
            if activity is not None:
                c = getattr(activity, 'campaign', None)
        if c is None:
            return None
        return {'id': str(c.id), 'name': getattr(c, 'name', None)}

    # -------------------------------------------------------------------------
    # DECISION STEP (always derived from activity)
    # -------------------------------------------------------------------------

    def get_decision_step(self, signal):
        """
        Compact decision_step dict {id, name} or None.

        No signal type carries decision_step directly — always derived
        from source_activity.decision_step when set.
        """
        activity = signal.source_activity
        if activity is None:
            return None
        step = getattr(activity, 'decision_step', None)
        if step is None:
            return None
        return {'id': str(step.id), 'name': getattr(step, 'name', None)}


# =============================================================================
# LIST SERIALIZER  (lightweight — list views)
# =============================================================================

class BaseSignalListSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Lightweight serializer for signal list endpoints.

    Performance considerations:
      - No deep nesting at the top level — provenance is consolidated
        under the `source_context` block via SignalSourceSerializer.
      - SerializerMethodField used only for display labels.

    Concrete serializers must set Meta.model and extend Meta.fields.
    """

    # Computed display labels
    status_display          = serializers.SerializerMethodField()
    source_display          = serializers.SerializerMethodField()
    signal_category_display = serializers.SerializerMethodField()

    # Standardised provenance block — derived from source_activity at read time
    source_context = SignalSourceSerializer(source='*', read_only=True)

    class Meta:
        abstract = True
        fields = [
            # Identity
            'id',
            # Corroboration anchor
            'canonical_key',
            # Content
            'signal_category', 'signal_category_display',
            # Lifecycle
            'status', 'status_display',
            'source', 'source_display',
            'confidence', 'is_inferred',
            # Provenance (derived block)
            'source_context',
            # Timestamps
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    # --- display labels ---

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_source_display(self, obj):
        return obj.get_source_display()

    def get_signal_category_display(self, obj):
        return obj.get_signal_category_display() if obj.signal_category else None


# =============================================================================
# DETAIL SERIALIZER  (full — retrieve views)
# =============================================================================

class BaseSignalDetailSerializer(BaseSignalListSerializer):
    """
    Full detail serializer for single-signal retrieve endpoints.

    Extends list serializer with:
      - source_quote, metadata, original_value
      - validated_at, validated_by (compact user)
      - language_original, requested_by (compact user)

    Removed during the standardisation refactor:
      - corroboration_count → CorroborationService deprecated; use the
                              cluster service's confirmation_count.
      - account              → was a top-level compact FK; account is
                               always present on every signal but no
                               longer needed at the top level since
                               source_context covers the conversation
                               context. If a list of all signals across
                               accounts ever needs account names again,
                               it should be added back as a dedicated
                               field — for now it lives only as the FK
                               id, accessible via signal.account_id at
                               query time.
      - source_activity      → consolidated under source_context.activity
      - decision_cycle       → consolidated under source_context.decision_cycle
      - campaign             → consolidated under source_context.campaign
      - last_modified_by/at  → use updated_by / updated_at inherited
                                from ModuleBaseModel.

    Concrete serializers must set Meta.model and extend Meta.fields.
    """

    # Compact user FKs that survive at the top level
    validated_by = serializers.SerializerMethodField()
    requested_by = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        abstract = True
        fields = BaseSignalListSerializer.Meta.fields + [
            # Content extras
            'source_quote', 'metadata', 'original_value',
            # Lifecycle detail
            'validated_at', 'validated_by',
            'language_original',
            'requested_by',
        ]
        read_only_fields = fields

    @staticmethod
    def _compact_user(user):
        if not user:
            return None
        return {
            'id':         str(user.id),
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'email':      user.email,
        }

    def get_validated_by(self, obj):
        return self._compact_user(obj.validated_by)

    def get_requested_by(self, obj):
        return self._compact_user(obj.requested_by)


# =============================================================================
# CREATE SERIALIZER
# =============================================================================

class BaseSignalCreateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Write serializer for signal creation.

    Validation rules:
      - confidence must be between 0.0 and 1.0 when provided.
      - client_id is injected from JWT context.

    signal_type is write-only — consumed by SignalManager.create() and
    never stored on the model. Concrete serializers override it with
    HiddenField(default='<type>').

    Removed during the standardisation refactor:
      - decision_cycle / campaign fields (auto-populated by
         SignalManager._propagate_activity_context from source_activity
         — never accepted directly from the API)

    The serializer does NOT call save() — the view's perform_create()
    must call SignalManager.create(serializer.validated_data, user,
    client_id).
    """

    # Write-only — consumed by SignalManager, not stored on the model.
    # Concrete serializers override with HiddenField(default='...').
    signal_type = serializers.ChoiceField(
        choices=['pain', 'objective', 'tech_stack'],
        write_only=True,
    )

    class Meta:
        abstract = True
        fields = [
            # signal_type routing
            'signal_type',
            # Context
            'account',
            'source_activity',
            # Content
            'source_quote',
            'confidence',
            'is_inferred',
            'signal_category',
            'metadata',
            # Source
            'source',
            'language_original',
        ]
        extra_kwargs = {
            'account':           {'required': True},
            'source':            {'required': False},
            'source_activity':   {'required': False, 'allow_null': True},
            'source_quote':      {'required': False, 'allow_null': True},
            'confidence':        {'required': False, 'allow_null': True},
            'is_inferred':       {'required': False},
            'signal_category':   {'required': False, 'allow_null': True},
            'metadata':          {'required': False, 'allow_null': True},
            'language_original': {'required': False, 'allow_null': True},
        }

    # -------------------------------------------------------------------------
    # FIELD-LEVEL VALIDATION
    # -------------------------------------------------------------------------

    def validate_confidence(self, value):
        """Confidence must be between 0.0 and 1.0 when provided."""
        if value is not None and not (0.0 <= value <= 1.0):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='confidence')
            )
        return value

    # -------------------------------------------------------------------------
    # GLOBAL VALIDATION
    # -------------------------------------------------------------------------

    def validate(self, attrs):
        """
        Inject client_id from JWT context.

        No cross-FK validation needed at the base level — concrete
        serializers (Pain, Objective) enforce their own contextual
        rules in their own validate().
        """
        attrs['client_id'] = self._get_client_id_from_context()
        return attrs


# =============================================================================
# UPDATE SERIALIZER
# =============================================================================

class BaseSignalUpdateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Restricted write serializer for signal PATCH.

    Allowed base fields: signal_category, source_quote, metadata.

    Forbidden via PATCH:
      - status, validated_by, validated_at  (go through validate/reject)
      - source                              (set at create time only)
      - account, source_activity            (provenance immutable post
                                              creation)
      - decision_cycle, campaign            (derived from source_activity
                                              by SignalManager — never
                                              writable)

    Canonical axes rewritable:
        For PainSignal and ObjectiveSignal, the canonical axes
        `what` / `dimension` ARE rewritable via PATCH —
        their concrete Update serializers add these fields to
        Meta.fields. The model's save() recomputes canonical_key from
        the new axes automatically; `canonical_key` itself is NOT
        writable via the serializer.

    Concrete serializers extend Meta.fields with their own typed fields.
    Value-like changes (summary, notes, etc.) are routed through
    SignalManager.edit() inside update() so the original_value snapshot
    and LLM_MODIFIED flip are enforced consistently.

    Shadow-override note:
        signal_category is declared here as a writable base field.
        ObjectiveSignal and TechStackSignal shadow-override it to None
        on the model — their concrete Update serializers filter the
        field out of Meta.fields and extra_kwargs. Pain retains normal
        write access to signal_category.
    """

    class Meta:
        abstract = True
        fields = [
            'signal_category',
            'source_quote',
            'metadata',
        ]
        extra_kwargs = {
            'signal_category':   {'required': False, 'allow_null': True},
            'source_quote':      {'required': False, 'allow_null': True},
            'metadata':          {'required': False, 'allow_null': True},
        }

    def update(self, instance, validated_data):
        """
        Apply partial update via SignalManager.edit().

        All field changes are routed through SignalManager.edit() so
        that guards (REJECTED cannot be edited), the original_value
        snapshot, and the LLM_MODIFIED flip are enforced consistently.
        """
        from ..services import SignalManager

        user = (
            self.context['request'].user
            if self.context.get('request') else None
        )

        # Route all updates through SignalManager.edit() for guard enforcement.
        if validated_data:
            SignalManager.edit(instance, validated_data, user)

        return instance


# =============================================================================
# LLM SERIALIZER  (read-only compact format)
# =============================================================================

class SignalLLMSerializer(serializers.Serializer):
    """
    Read-only serializer for LLM prompt context.

    Produces a compact format aligned with the standardised provenance
    surface. Used in views that expose the LLM context endpoint
    directly so the output is consistent whether it comes from a
    queryset or a single instance.

    Output fields:
      type, category, summary, contacts, confirmed, date

    Standardisation refactor changes:
      - `contact` (single name) → `contacts` (list of names) derived
         from source_activity.contacts. Empty list when no activity.
      - `department` removed. source_department was the previous
         basis; with that field gone, no uniform department surface
         remains. TechStack carries usage_department (who USES the
         tool, distinct concept) — exposed elsewhere if needed.
      - `confirmed` retained as a static 1; CorroborationService was
         deprecated and the cluster confirmation_count is the
         replacement metric, but it is not derivable per-signal here.
    """

    type      = serializers.SerializerMethodField()
    category  = serializers.CharField(source='signal_category', allow_null=True)
    summary   = serializers.SerializerMethodField()
    contacts  = serializers.SerializerMethodField()
    confirmed = serializers.SerializerMethodField()
    date      = serializers.SerializerMethodField()

    def get_type(self, obj):
        return obj.__class__.__name__

    def get_summary(self, obj):
        # Pain/Objective expose `summary`; TechStack uses tech_catalog_entry
        # display + notes (full implementation in SignalDataService.format_for_llm).
        # Here we keep a simple fallback chain to avoid a per-type branch
        # that duplicates the service logic.
        return (
            getattr(obj, 'summary', None)
            or getattr(obj, 'notes', None)
            or ''
        )

    def get_contacts(self, obj):
        """
        List of contact display names from source_activity.contacts.
        Empty list when source_activity is null.
        """
        activity = getattr(obj, 'source_activity', None)
        if not activity:
            return []
        names = []
        for c in activity.contacts.all():
            name = (
                f"{getattr(c, 'first_name', '') or ''} "
                f"{getattr(c, 'last_name', '') or ''}"
            ).strip()
            if name:
                names.append(name)
        return names

    def get_confirmed(self, obj):
        # Static 1 in MVP — CorroborationService deprecated, cluster
        # confirmation_count is the replacement at the cluster level.
        return 1

    def get_date(self, obj):
        validated_at = getattr(obj, 'validated_at', None)
        if validated_at:
            return validated_at.strftime('%Y-%m-%d')
        return None