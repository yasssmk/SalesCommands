# app_modules/signals/serializers/base_serializer.py
"""
Base serializers for the Signals module.

Defines the shared serializer hierarchy used by both QualificationSignal
and TechStackSignal. Concrete serializers (qualification_serializer,
tech_stack_serializer) inherit from these bases and set Meta.model.

Serializer map:
  BaseSignalListSerializer   — lightweight, list views
  BaseSignalDetailSerializer — full detail, retrieve views
  BaseSignalCreateSerializer — write path, enforces field_name/signal_type compat
  BaseSignalUpdateSerializer — restricted PATCH, routes value changes through edit()
  SignalLLMSerializer        — read-only compact format for LLM prompt injection
"""

from django.utils import timezone
from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import (
    SignalStatus,
    SignalSource,
    SignalCategory,
    QualificationField,
    TechStackField,
)

# Allowed field_name choices per signal type — used in create validation.
_FIELD_CHOICES_MAP = {
    'qualification': {choice[0] for choice in QualificationField.choices},
    'tech_stack':    {choice[0] for choice in TechStackField.choices},
}

# Fields allowed in PATCH — any key not in this set is silently ignored.
_UPDATE_ALLOWED_FIELDS = {
    'value',
    'signal_category',
    'source_department',
    'source_contact',
    'source_quote',
    'metadata',
}


# =============================================================================
# NESTED HELPER SERIALIZERS
# =============================================================================

class _MinimalUserSerializer(serializers.Serializer):
    """Compact user representation for signal responses."""
    id         = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name  = serializers.CharField()
    email      = serializers.EmailField()


class _MinimalContactSerializer(serializers.Serializer):
    """Compact contact representation for signal responses."""
    id         = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name  = serializers.CharField()
    job_title  = serializers.CharField(allow_null=True)


class _MinimalDepartmentSerializer(serializers.Serializer):
    """Compact department representation for signal responses."""
    id   = serializers.UUIDField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_name_display() if hasattr(obj, 'get_name_display') else str(obj)


class _MinimalSignalSerializer(serializers.Serializer):
    """Minimal signal representation — used for merged_into / superseded_by."""
    id         = serializers.UUIDField()
    field_name = serializers.CharField()
    status     = serializers.CharField()
    value      = serializers.JSONField()


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
      - No deep nesting — FK relations as compact objects only.
      - SerializerMethodField used for relations to avoid N+1 when
        select_related is applied by the view's get_queryset().

    Concrete serializers must set Meta.model.
    """

    # Computed display labels
    status_display          = serializers.SerializerMethodField()
    source_display          = serializers.SerializerMethodField()
    signal_category_display = serializers.SerializerMethodField()
    field_name_display      = serializers.SerializerMethodField()

    # Compact FK objects
    source_contact    = serializers.SerializerMethodField()
    source_department = serializers.SerializerMethodField()

    class Meta:
        # Concrete serializer must override model.
        abstract = True
        fields = [
            # Identity
            'id', 'field_name', 'field_name_display',

            # Content
            'value', 'signal_category', 'signal_category_display',

            # Lifecycle
            'status', 'status_display',
            'source', 'source_display',
            'confidence', 'is_inferred',
            'confirmation_count', 'last_confirmed_at',
            'is_superseded',

            # Relations (compact)
            'source_contact', 'source_department',

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

    def get_field_name_display(self, obj):
        return obj.get_field_name_display()

    # --- compact FK objects ---

    def get_source_contact(self, obj):
        c = obj.source_contact
        if not c:
            return None
        return {
            'id':        str(c.id),
            'first_name': c.first_name,
            'last_name':  c.last_name,
            'job_title':  getattr(c, 'job_title', None),
        }

    def get_source_department(self, obj):
        d = obj.source_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


# =============================================================================
# DETAIL SERIALIZER  (full — retrieve views)
# =============================================================================

class BaseSignalDetailSerializer(BaseSignalListSerializer):
    """
    Full detail serializer for single-signal retrieve endpoints.

    Extends list serializer with:
      - All audit FK fields
      - source_quote, metadata, original_value
      - merged_into / superseded_by compact objects
      - validated_by, last_modified_by compact objects

    Concrete serializers must set Meta.model.
    """

    # Full audit FKs — compact objects
    account        = serializers.SerializerMethodField()
    source_activity = serializers.SerializerMethodField()
    decision_cycle = serializers.SerializerMethodField()
    campaign       = serializers.SerializerMethodField()

    validated_by     = serializers.SerializerMethodField()
    last_modified_by = serializers.SerializerMethodField()
    requested_by     = serializers.SerializerMethodField()

    merged_into   = serializers.SerializerMethodField()
    superseded_by = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        abstract = True
        fields = BaseSignalListSerializer.Meta.fields + [
            # Content extras
            'source_quote', 'metadata', 'original_value',

            # Context FKs
            'account', 'source_activity', 'decision_cycle', 'campaign',

            # Lifecycle detail
            'validated_at', 'validated_by',
            'last_modified_at', 'last_modified_by',
            'language_original',
            'requested_by',

            # Supersede chain
            'merged_into', 'superseded_by',
        ]
        read_only_fields = fields

    def get_account(self, obj):
        a = obj.account
        if not a:
            return None
        return {'id': str(a.id), 'company_name': a.company_name}

    def get_source_activity(self, obj):
        act = obj.source_activity
        if not act:
            return None
        return {'id': str(act.id)}

    def get_decision_cycle(self, obj):
        dc = obj.decision_cycle
        if not dc:
            return None
        return {'id': str(dc.id), 'name': getattr(dc, 'name', None)}

    def get_campaign(self, obj):
        c = obj.campaign
        if not c:
            return None
        return {'id': str(c.id), 'name': getattr(c, 'name', None)}

    def _compact_user(self, user):
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

    def get_last_modified_by(self, obj):
        return self._compact_user(obj.last_modified_by)

    def get_requested_by(self, obj):
        return self._compact_user(obj.requested_by)

    def get_merged_into(self, obj):
        t = obj.merged_into
        if not t:
            return None
        return {
            'id':         str(t.id),
            'field_name': t.field_name,
            'status':     t.status,
        }

    def get_superseded_by(self, obj):
        s = obj.superseded_by
        if not s:
            return None
        return {
            'id':         str(s.id),
            'field_name': s.field_name,
            'status':     s.status,
        }


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
      - field_name must be compatible with signal_type.
      - source_contact must belong to the same account as the signal.
      - source=MANUAL → source_quote and confidence are optional.
      - signal_type is write-only; consumed by SignalManager.create().

    Concrete serializers set Meta.model and the fixed signal_type default
    via a HiddenField so the view can delegate directly to SignalManager.

    The serializer does NOT call save() — the view's perform_create() must
    call SignalManager.create(serializer.validated_data, user, client_id).
    """

    # Write-only — consumed by SignalManager, not stored on the model.
    # Concrete serializers override this with HiddenField(default='...').
    signal_type = serializers.ChoiceField(
        choices=['qualification', 'tech_stack'],
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
            'source_contact',
            'source_department',
            'decision_cycle',
            'campaign',

            # Content
            'field_name',
            'value',
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
            'account':        {'required': True},
            'field_name':     {'required': True},
            'value':          {'required': True},
            'source':         {'required': False},
            'source_quote':   {'required': False, 'allow_null': True},
            'confidence':     {'required': False, 'allow_null': True},
            'is_inferred':    {'required': False},
            'signal_category': {'required': False, 'allow_null': True},
            'metadata':       {'required': False, 'allow_null': True},
            'language_original': {'required': False, 'allow_null': True},
        }

    # -------------------------------------------------------------------------
    # FIELD-LEVEL VALIDATION
    # -------------------------------------------------------------------------

    def validate_field_name(self, value):
        """
        Validate field_name against the signal_type choices.

        Called after individual field validation — signal_type is guaranteed
        to be in initial_data at this point (DRF processes fields in order,
        but validate_<field> is called per-field before validate()).
        We defer the cross-field check to validate() where both values
        are available.
        """
        return value

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
        Cross-field validation:
          1. field_name must be valid for signal_type.
          2. source_contact must belong to the same account.
          3. Inject client_id from JWT context.
        """
        client_id   = self._get_client_id_from_context()
        signal_type = attrs.get('signal_type')
        field_name  = attrs.get('field_name')
        account     = attrs.get('account')

        # --- 1. field_name ↔ signal_type compatibility ---
        allowed_fields = _FIELD_CHOICES_MAP.get(signal_type, set())
        if field_name and field_name not in allowed_fields:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='field_name')
            )

        # --- 2. source_contact must belong to the same account ---
        source_contact = attrs.get('source_contact')
        if source_contact and account:
            if str(source_contact.account_id) != str(account.id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='source_contact')
                )

        # --- 3. Inject client_id ---
        attrs['client_id'] = client_id

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

    Allowed fields: value, signal_category, source_department,
                    source_contact, source_quote, metadata.

    Forbidden via PATCH: status, validated_by, validated_at, source,
                         field_name, account. These go through dedicated
                         action endpoints (validate/, reject/, merge/, supersede/).

    Value change routing:
      When 'value' is present in validated_data, update() calls
      SignalManager.edit() so the original_value snapshot and
      LLM_MODIFIED flip are enforced consistently.
      Remaining allowed fields are applied in the same transaction
      with a second save() call.

    Concrete serializers set Meta.model.
    """

    class Meta:
        abstract = True
        fields = [
            'value',
            'signal_category',
            'source_department',
            'source_contact',
            'source_quote',
            'metadata',
        ]
        extra_kwargs = {
            'value':            {'required': False},
            'signal_category':  {'required': False, 'allow_null': True},
            'source_department': {'required': False, 'allow_null': True},
            'source_contact':   {'required': False, 'allow_null': True},
            'source_quote':     {'required': False, 'allow_null': True},
            'metadata':         {'required': False, 'allow_null': True},
        }

    def validate_source_contact(self, value):
        """source_contact must belong to the signal's account."""
        if value is None:
            return value
        instance = getattr(self, 'instance', None)
        if instance and str(value.account_id) != str(instance.account_id):
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='source_contact')
            )
        return value

    def update(self, instance, validated_data):
        """
        Apply partial update.

        If 'value' is present, delegate to SignalManager.edit() first
        (guards + snapshot + source flip + save). Then apply any remaining
        allowed fields and save once more.
        """
        from ..services import SignalManager

        user = self.context['request'].user if self.context.get('request') else None

        # --- value change → SignalManager.edit() ---
        if 'value' in validated_data:
            new_value = validated_data.pop('value')
            # edit() enforces guards (REJECTED/MERGED) and saves internally.
            SignalManager.edit(instance, new_value, user)

        # --- remaining allowed fields ---
        for attr, val in validated_data.items():
            setattr(instance, attr, val)

        if validated_data:
            # Only save again if there were non-value fields to apply.
            instance.save(user=user)

        return instance


# =============================================================================
# LLM SERIALIZER  (read-only compact format)
# =============================================================================

class SignalLLMSerializer(serializers.Serializer):
    """
    Read-only serializer for LLM prompt context.

    Produces the same compact format as SignalDataService.format_for_llm().
    Used in views that expose the LLM context endpoint directly, so the
    output is consistent whether it comes from a queryset or a single instance.

    Output fields:
      field, value, category, contact, department, confirmed, date
    """

    field      = serializers.SerializerMethodField()
    value      = serializers.JSONField(source='value')
    category   = serializers.CharField(source='signal_category', allow_null=True)
    contact    = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    confirmed  = serializers.IntegerField(source='confirmation_count')
    date       = serializers.SerializerMethodField()

    def get_field(self, obj):
        return obj.field_name

    def get_contact(self, obj):
        c = getattr(obj, 'source_contact', None)
        if not c:
            return None
        return (
            f"{getattr(c, 'first_name', '') or ''} "
            f"{getattr(c, 'last_name', '') or ''}"
        ).strip() or None

    def get_department(self, obj):
        d = getattr(obj, 'source_department', None)
        if not d:
            return None
        return d.get_name_display() if hasattr(d, 'get_name_display') else str(d)

    def get_date(self, obj):
        lca = getattr(obj, 'last_confirmed_at', None)
        if lca:
            return lca.strftime('%Y-%m-%d')
        return None