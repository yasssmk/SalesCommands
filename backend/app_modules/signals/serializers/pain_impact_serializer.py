# app_modules/signals/serializers/pain_impact_serializer.py
"""
Serializers for PainImpact — evidence attached to a PainSignal.

Pain = the DIAGNOSIS (qualitative)
Impact = the PROOF (quantitative and/or human)

Three Impact levels (BUSINESS / DEPARTMENT / PERSONAL) with distinct
required fields — enforced in both the model's clean() and the create/
update serializers.

Stack:
  PainImpactReadSerializer     — compact read-only payload used inline
                                 in PainSignal list/detail ('impacts' field)
  PainImpactListSerializer     — standalone list endpoint
  PainImpactDetailSerializer   — standalone retrieve endpoint
  PainImpactCreateSerializer   — write path with level-conditional rules
  PainImpactUpdateSerializer   — restricted PATCH, merged-state validation

The serializers do NOT use SignalManager — PainImpact has no lifecycle
(no PENDING/VALIDATED/REJECTED, no source enum). Creation and updates
go through straightforward ModelSerializer save() with audit fields
injected via save(user=..., client_id=...).
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import ScopeLevel
from ..models import PainImpact, PainSignal


# =============================================================================
# HELPERS — compact nested objects reused across serializers
# =============================================================================

def _compact_contact(contact):
    """Render a Contact as a compact object for impact payloads."""
    if not contact:
        return None
    return {
        'id':         str(contact.id),
        'first_name': contact.first_name,
        'last_name':  contact.last_name,
        'job_title':  getattr(contact, 'job_title', None),
    }


def _compact_department(dept):
    """Render a StandardDepartment as a compact object for impact payloads."""
    if not dept:
        return None
    return {
        'id':   str(dept.id),
        'name': dept.get_name_display() if hasattr(dept, 'get_name_display') else str(dept),
    }


class _ImpactDisplayMixin:
    """Shared display-field methods across all Impact serializers."""

    def get_level_display(self, obj):
        return obj.get_level_display() if obj.level else None

    def get_human_impact_display(self, obj):
        return obj.get_human_impact_display() if obj.human_impact else None

    def get_impacted_department(self, obj):
        return _compact_department(obj.impacted_department)

    def get_impacted_contact(self, obj):
        return _compact_contact(obj.impacted_contact)


# =============================================================================
# READ — compact payload for nesting inside PainSignal
# =============================================================================

class PainImpactReadSerializer(
    _ImpactDisplayMixin,
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Read-only compact serializer used when nesting impacts inside a
    PainSignal response (e.g. PainSignalListSerializer.impacts).

    Never used for writes. Excludes audit metadata beyond created_at to
    keep nested payloads lean on Pain list views.
    """

    level_display        = serializers.SerializerMethodField()
    human_impact_display = serializers.SerializerMethodField()
    impacted_department  = serializers.SerializerMethodField()
    impacted_contact     = serializers.SerializerMethodField()

    class Meta:
        model = PainImpact
        fields = [
            'id',
            'level', 'level_display',
            'human_impact', 'human_impact_display',
            'impacted_department',
            'impacted_contact',
            'metric',
            'notes',
            'created_at',
        ]
        read_only_fields = fields


# =============================================================================
# LIST — standalone /pain-impacts/ endpoint
# =============================================================================

class PainImpactListSerializer(
    _ImpactDisplayMixin,
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Lightweight serializer for PainImpact list endpoint.

    Includes a compact pain_signal reference so callers can pivot back
    to the parent diagnosis without an extra roundtrip.
    """

    level_display        = serializers.SerializerMethodField()
    human_impact_display = serializers.SerializerMethodField()
    impacted_department  = serializers.SerializerMethodField()
    impacted_contact     = serializers.SerializerMethodField()

    # Compact reference to the parent pain
    pain_signal = serializers.SerializerMethodField()

    class Meta:
        model = PainImpact
        fields = [
            'id',
            'pain_signal',
            'level', 'level_display',
            'human_impact', 'human_impact_display',
            'impacted_department',
            'impacted_contact',
            'metric',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_pain_signal(self, obj):
        p = obj.pain_signal
        if not p:
            return None
        return {
            'id':            str(p.id),
            'canonical_key': p.canonical_key,
            'summary':       p.summary,
        }


# =============================================================================
# DETAIL — standalone /pain-impacts/{id}/ endpoint
# =============================================================================

class PainImpactDetailSerializer(PainImpactListSerializer):
    """
    Full detail serializer for single PainImpact retrieve.

    Extends the list serializer with full audit metadata — created_by,
    updated_by — so the UI can show provenance.
    """

    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    class Meta(PainImpactListSerializer.Meta):
        fields = PainImpactListSerializer.Meta.fields + [
            'created_by',
            'updated_by',
        ]
        read_only_fields = fields

    def _compact_user(self, user):
        if not user:
            return None
        return {
            'id':         str(user.id),
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'email':      user.email,
        }

    def get_created_by(self, obj):
        return self._compact_user(obj.created_by)

    def get_updated_by(self, obj):
        return self._compact_user(obj.updated_by)


# =============================================================================
# CREATE
# =============================================================================

class PainImpactCreateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Write serializer for PainImpact creation.

    Required fields:
      - pain_signal
      - level

    Conditional requirements (driven by level):
      - BUSINESS   → no impacted_department, no impacted_contact,
                     no human_impact.
      - DEPARTMENT → impacted_department required; no impacted_contact;
                     no human_impact.
      - PERSONAL   → impacted_contact required; no impacted_department;
                     human_impact optional.

    Cross-account scoping:
      - impacted_contact must belong to the same account as pain_signal.account.

    Unlike BaseSignalCreateSerializer, this does NOT route through
    SignalManager — PainImpact has no lifecycle. The view's
    perform_create() calls save(user=..., client_id=...) directly.
    """

    class Meta:
        model = PainImpact
        fields = [
            'pain_signal',
            'level',
            'impacted_department',
            'impacted_contact',
            'human_impact',
            'metric',
            'notes',
        ]
        extra_kwargs = {
            'pain_signal':         {'required': True},
            'level':               {'required': True},
            'impacted_department': {'required': False, 'allow_null': True},
            'impacted_contact':    {'required': False, 'allow_null': True},
            'human_impact':        {'required': False, 'allow_null': True},
            'metric':              {'required': False, 'allow_blank': True},
            'notes':               {'required': False, 'allow_blank': True},
        }

    # -------------------------------------------------------------------------
    # GLOBAL VALIDATION
    # -------------------------------------------------------------------------

    def validate(self, attrs):
        """
        Enforce PainImpact-specific rules.

        Mirrors the model's clean() logic but surfaces errors at the
        serializer layer for cleaner API responses.

        Rules:
          1. pain_signal required (schema-level, reinforced here for
             friendly error).
          2. level required.
          3. Level-driven field presence (BUSINESS/DEPARTMENT/PERSONAL).
          4. impacted_contact (when set) must belong to the same account
             as pain_signal.
          5. Inject client_id from JWT context.
        """
        pain_signal = attrs.get('pain_signal')
        level = attrs.get('level')
        impacted_department = attrs.get('impacted_department')
        impacted_contact = attrs.get('impacted_contact')
        human_impact = attrs.get('human_impact')

        # Rule 1
        if not pain_signal:
            raise StandardizedValidationError(
                SignalErrorMessages.IMPACT_PAIN_REQUIRED
            )

        # Rule 2
        if not level:
            raise StandardizedValidationError(
                SignalErrorMessages.IMPACT_LEVEL_REQUIRED
            )

        # Rule 3 — level-driven presence
        if level == ScopeLevel.BUSINESS:
            if impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_DEPT
                )
            if impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_CONTACT
                )
            if human_impact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_HUMAN
                )

        elif level == ScopeLevel.DEPARTMENT:
            if not impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_DEPT_REQUIRES_DEPT
                )
            if impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_DEPT_NO_CONTACT
                )
            if human_impact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_HUMAN
                )

        elif level == ScopeLevel.PERSONAL:
            if not impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_PERSONAL_REQUIRES_CONTACT
                )
            if impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_PERSONAL_NO_DEPT
                )
            # human_impact optional — no check

        # Rule 4 — cross-account scoping
        if impacted_contact and pain_signal:
            if str(impacted_contact.account_id) != str(pain_signal.account_id):
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_CONTACT_WRONG_ACCOUNT
                )

        # Rule 5 — inject client_id from context
        attrs['client_id'] = self._get_client_id_from_context()
        return attrs


# =============================================================================
# UPDATE
# =============================================================================

class PainImpactUpdateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Restricted PATCH serializer for PainImpact.

    Editable: level, impacted_department, impacted_contact,
              human_impact, metric, notes.

    Forbidden via PATCH: pain_signal. Reassigning an impact to a
    different pain changes its cluster identity — treat it as a
    delete + recreate if needed.

    Conditional validation runs against the MERGED state (instance +
    incoming PATCH). A partial PATCH changing only `level` must still
    respect the target level's field requirements using the pre-existing
    field values.

    Example: instance has level=DEPARTMENT + impacted_department=X.
    A PATCH {level: PERSONAL} is rejected: merged state is
    (PERSONAL + impacted_department=X) which violates PERSONAL rules.
    The caller must send {level: PERSONAL, impacted_department: null,
    impacted_contact: <uuid>}.
    """

    class Meta:
        model = PainImpact
        fields = [
            'level',
            'impacted_department',
            'impacted_contact',
            'human_impact',
            'metric',
            'notes',
        ]
        extra_kwargs = {
            'level':               {'required': False},
            'impacted_department': {'required': False, 'allow_null': True},
            'impacted_contact':    {'required': False, 'allow_null': True},
            'human_impact':        {'required': False, 'allow_null': True},
            'metric':              {'required': False, 'allow_blank': True},
            'notes':               {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce level-driven rules and cross-account scoping against the
        merged instance state. Partial PATCH inherits missing keys from
        self.instance.
        """
        instance = getattr(self, 'instance', None)

        def _merged(key):
            if key in attrs:
                return attrs.get(key)
            return getattr(instance, key, None) if instance else None

        level = _merged('level')
        impacted_department = _merged('impacted_department')
        impacted_contact = _merged('impacted_contact')
        human_impact = _merged('human_impact')
        pain_signal = getattr(instance, 'pain_signal', None) if instance else None

        if not level:
            raise StandardizedValidationError(
                SignalErrorMessages.IMPACT_LEVEL_REQUIRED
            )

        if level == ScopeLevel.BUSINESS:
            if impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_DEPT
                )
            if impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_CONTACT
                )
            if human_impact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_HUMAN
                )

        elif level == ScopeLevel.DEPARTMENT:
            if not impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_DEPT_REQUIRES_DEPT
                )
            if impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_DEPT_NO_CONTACT
                )
            if human_impact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_BUSINESS_NO_HUMAN
                )

        elif level == ScopeLevel.PERSONAL:
            if not impacted_contact:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_PERSONAL_REQUIRES_CONTACT
                )
            if impacted_department:
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_PERSONAL_NO_DEPT
                )

        # Cross-account scoping check — pain_signal cannot change via PATCH,
        # so we compare the (possibly new) impacted_contact against the
        # existing pain_signal.account.
        if impacted_contact and pain_signal:
            if str(impacted_contact.account_id) != str(pain_signal.account_id):
                raise StandardizedValidationError(
                    SignalErrorMessages.IMPACT_CONTACT_WRONG_ACCOUNT
                )

        return attrs