# app_modules/signals/serializers/base_serializer.py
"""
Base serializers for the Signals module.

Defines the shared serializer hierarchy used by all 4 concrete signal types:
  PeopleSignal, PainSignal, ObjectiveSignal, TechStackSignal.

Serializer map:
  BaseSignalListSerializer   — lightweight, list views
  BaseSignalDetailSerializer — full detail, retrieve views
  BaseSignalCreateSerializer — write path, routes signal_type to SignalManager
  BaseSignalUpdateSerializer — restricted PATCH, routes edits through edit()
  SignalLLMSerializer        — read-only compact format for LLM prompt injection
"""

from django.utils import timezone
from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import SignalStatus, SignalSource, SignalCategory


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

    Concrete serializers must set Meta.model and extend Meta.fields.
    """

    # Computed display labels
    status_display          = serializers.SerializerMethodField()
    source_display          = serializers.SerializerMethodField()
    signal_category_display = serializers.SerializerMethodField()

    # Compact FK objects
    source_contact    = serializers.SerializerMethodField()
    source_department = serializers.SerializerMethodField()

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

    # --- compact FK objects ---

    def get_source_contact(self, obj):
        c = obj.source_contact
        if not c:
            return None
        return {
            'id':         str(c.id),
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
      - All audit FK fields (account, source_activity, decision_cycle, campaign)
      - source_quote, metadata, original_value
      - validated_by, last_modified_by, requested_by compact objects
      - corroboration_count — computed via CorroborationService

    Concrete serializers must set Meta.model and extend Meta.fields.
    """

    # Corroboration — detail only for performance
    corroboration_count = serializers.SerializerMethodField()

    # Full audit FKs — compact objects
    account          = serializers.SerializerMethodField()
    source_activity  = serializers.SerializerMethodField()
    decision_cycle   = serializers.SerializerMethodField()
    campaign         = serializers.SerializerMethodField()
    validated_by     = serializers.SerializerMethodField()
    last_modified_by = serializers.SerializerMethodField()
    requested_by     = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        abstract = True
        fields = BaseSignalListSerializer.Meta.fields + [
            # Corroboration
            'corroboration_count',
            # Content extras
            'source_quote', 'metadata', 'original_value',
            # Context FKs
            'account', 'source_activity', 'decision_cycle', 'campaign',
            # Lifecycle detail
            'validated_at', 'validated_by',
            'last_modified_at', 'last_modified_by',
            'language_original',
            'requested_by',
        ]
        read_only_fields = fields

    def get_corroboration_count(self, obj):
        from ..services import CorroborationService
        return CorroborationService.compute_for_signal(obj)

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
      - source_contact must belong to the same account as the signal.
      - confidence must be between 0.0 and 1.0 when provided.
      - client_id is injected from JWT context.

    signal_type is write-only — consumed by SignalManager.create() and
    never stored on the model. Concrete serializers override it with
    HiddenField(default='<type>').

    The serializer does NOT call save() — the view's perform_create() must
    call SignalManager.create(serializer.validated_data, user, client_id).
    """

    # Write-only — consumed by SignalManager, not stored on the model.
    # Concrete serializers override with HiddenField(default='...').
    signal_type = serializers.ChoiceField(
        choices=['people', 'pain', 'objective', 'tech_stack'],
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
            'source_contact':    {'required': False, 'allow_null': True},
            'source_department': {'required': False, 'allow_null': True},
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
        Cross-field validation:
          1. source_contact must belong to the same account.
          2. Inject client_id from JWT context.
        """
        client_id = self._get_client_id_from_context()
        account   = attrs.get('account')

        # --- source_contact must belong to the same account ---
        source_contact = attrs.get('source_contact')
        if source_contact and account:
            if str(source_contact.account_id) != str(account.id):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='source_contact')
                )

        # --- Inject client_id ---
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

    Allowed base fields: signal_category, source_department,
                         source_contact, source_quote, metadata.

    Forbidden via PATCH: status, validated_by, validated_at, source,
                         account. These go through dedicated action
                         endpoints (validate/, reject/).

    Concrete serializers extend Meta.fields with their own typed fields.
    Value-like changes (summary, notes, etc.) are routed through
    SignalManager.edit() inside update() so the original_value snapshot
    and LLM_MODIFIED flip are enforced consistently.
    """

    class Meta:
        abstract = True
        fields = [
            'signal_category',
            'source_department',
            'source_contact',
            'source_quote',
            'metadata',
        ]
        extra_kwargs = {
            'signal_category':   {'required': False, 'allow_null': True},
            'source_department': {'required': False, 'allow_null': True},
            'source_contact':    {'required': False, 'allow_null': True},
            'source_quote':      {'required': False, 'allow_null': True},
            'metadata':          {'required': False, 'allow_null': True},
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
        Apply partial update via SignalManager.edit().

        All field changes are routed through SignalManager.edit() so that
        guards (REJECTED cannot be edited), the original_value snapshot,
        and the LLM_MODIFIED flip are enforced consistently.
        """
        from ..services import SignalManager

        user = self.context['request'].user if self.context.get('request') else None

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

    Produces the same compact format as SignalDataService.format_for_llm().
    Used in views that expose the LLM context endpoint directly, so the
    output is consistent whether it comes from a queryset or a single instance.

    Output fields:
      type, category, summary, contact, department, confirmed, date
    """

    type       = serializers.SerializerMethodField()
    category   = serializers.CharField(source='signal_category', allow_null=True)
    summary    = serializers.SerializerMethodField()
    contact    = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    confirmed  = serializers.SerializerMethodField()
    date       = serializers.SerializerMethodField()

    def get_type(self, obj):
        return obj.__class__.__name__

    def get_summary(self, obj):
        return (
            getattr(obj, 'summary', None)
            or getattr(obj, 'tech_name', None)
            or getattr(obj, 'notes', None)
            or ''
        )

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

    def get_confirmed(self, obj):
        # Always 1 in MVP — CorroborationService not called here for performance.
        return 1

    def get_date(self, obj):
        validated_at = getattr(obj, 'validated_at', None)
        if validated_at:
            return validated_at.strftime('%Y-%m-%d')
        return None