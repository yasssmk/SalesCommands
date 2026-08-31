# app_modules/signals/serializers/people_serializer.py
"""
Serializers for PeopleSignal.

Stack:
  PeopleSignalListSerializer   — lightweight list view
  PeopleSignalDetailSerializer — full detail (validated_*, requested_by,
                                  source_quote, metadata, original_value
                                  on top of the list payload)
  PeopleSignalCreateSerializer — write path
  PeopleSignalUpdateSerializer — restricted PATCH

Notes:
  - The model shadow-overrides `signal_category` to None on the
    concrete PeopleSignal. Among the base serializer fields, only
    `signal_category` (and its `signal_category_display` companion)
    requires filtering — same pattern as BlockerSignalSerializer.

  - PeopleSignal does not carry canonical axes (no `what` / `dimension`)
    and does not participate in cluster aggregation. The inherited
    `canonical_key` field stays in the base fields for shape
    consistency but is always None on a PeopleSignal — see
    PeopleSignal.save().

  - `target_contact` (FK Contact) is the person playing this role;
    `target_department` (FK StandardDepartment) is the department.
    At least one must be provided (enforced in PeopleSignal.clean
    and re-surfaced in the Create serializer).

  - source_activity is required for LLM-sourced signals. MANUAL signals
    may omit it when anchored to a decision_cycle (DC-level qualification).
    Re-surfaced at the Create serializer for a clean API error payload.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import SignalSource
from ..models import PeopleSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — display + compact FK payloads
# =============================================================================

class _PeopleDisplayMixin:
    """Shared SerializerMethodField implementations for People serializers."""

    def get_role_display(self, obj):
        return obj.get_role_display() if obj.role else None

    def get_influence_display(self, obj):
        return obj.get_influence_display() if obj.influence else None

    def get_target_contact(self, obj):
        """
        Compact contact payload — keeps the frontend from issuing a
        separate /contacts/<id>/ fetch just to render the attribution
        on a people card. Returns None when the FK is not set.
        """
        contact = obj.target_contact
        if not contact:
            return None
        return {
            'id':         str(contact.id),
            'first_name': contact.first_name,
            'last_name':  contact.last_name,
            'job_title':  getattr(contact, 'job_title', None),
        }

    def get_target_department(self, obj):
        """Compact department payload. Returns None when the FK is not set."""
        dept = obj.target_department
        if not dept:
            return None
        return {
            'id':   str(dept.id),
            'name': dept.get_name_display(),
        }


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# PeopleSignal shadow-overrides `signal_category` to None on the
# concrete model. Among the base serializer fields, only signal_category
# and its signal_category_display companion need to be stripped — they
# are declared at the top level of BaseSignalListSerializer /
# BaseSignalDetailSerializer / BaseSignalCreateSerializer /
# BaseSignalUpdateSerializer. We strip them here once and reuse the
# resulting filtered lists in every Meta below — keeps the four
# serializers in sync. Same pattern as BlockerSignalSerializer.

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})


def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without People's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without People's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class PeopleSignalListSerializer(_PeopleDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for PeopleSignal list endpoints.

    Exposes the stakeholder role, influence level, target contact
    (compact payload), target department (compact payload), and notes.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    role_display       = serializers.SerializerMethodField()
    influence_display  = serializers.SerializerMethodField()
    target_contact     = serializers.SerializerMethodField()
    target_department  = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = PeopleSignal

        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            'full_name', 'full_name_normalized',
            'role', 'role_display',
            'influence', 'influence_display',
            'target_contact',
            'target_department',
            'notes',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class PeopleSignalDetailSerializer(_PeopleDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for PeopleSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    """

    role_display       = serializers.SerializerMethodField()
    influence_display  = serializers.SerializerMethodField()
    target_contact     = serializers.SerializerMethodField()
    target_department  = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = PeopleSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            'full_name', 'full_name_normalized',
            'role', 'role_display',
            'influence', 'influence_display',
            'target_contact',
            'target_department',
            'notes',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class PeopleSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for PeopleSignal creation.

    signal_type is fixed to 'people' via HiddenField (consumed by
    SignalManager.create()).

    Required:
      - account            (inherited)
      - role               — stakeholder role (PeopleRole enum)
      - source_activity OR decision_cycle (for MANUAL source)
      - source_activity    (always required for LLM-sourced signals)

    Optional:
      - influence          — perceived influence level
      - target_contact     — FK to Contact playing this role
      - target_department  — FK to StandardDepartment
      - decision_cycle     — FK, required for DC-level manual creation
      - notes              — additional context
      - source_quote, language_original, source, confidence,
        is_inferred, metadata (inherited)

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Validation (re-surfaced from PeopleSignal.clean()):
      1. source_activity required unless source=MANUAL + decision_cycle.
      2. At least one of target_contact / target_department required.
    """

    signal_type = serializers.HiddenField(default='people')

    class Meta(BaseSignalCreateSerializer.Meta):
        model = PeopleSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'full_name',
            'role',
            'influence',
            'target_contact',
            'target_department',
            'decision_cycle',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            # full_name is the raw person identity; full_name_normalized is
            # derived in save() and is NEVER writable (not a field here).
            'full_name':         {'required': False, 'allow_blank': True},
            'role':              {'required': True},
            'influence':         {'required': False, 'allow_null': True},
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'decision_cycle':    {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce People-specific contextual rules, then delegate to base.

        Rules (re-surfaced from PeopleSignal.clean()):
          1. source_activity required unless source=MANUAL with a
             decision_cycle anchor (DC-level manual qualification).
          2. At least one of target_contact / target_department / full_name
             required (a person may be identified by name alone).
        """
        if not attrs.get('source_activity'):
            source = attrs.get('source', SignalSource.MANUAL)
            if source != SignalSource.MANUAL or not attrs.get('decision_cycle'):
                raise StandardizedValidationError(
                    SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED
                )

        if (not attrs.get('target_contact')
                and not attrs.get('target_department')
                and not (attrs.get('full_name') or '').strip()):
            raise StandardizedValidationError(
                'At least one of target_contact, target_department or '
                'full_name is required.'
            )

        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class PeopleSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for PeopleSignal.

    Allowed beyond base fields (source_quote, metadata):
      - role               — stakeholder role may be corrected
      - influence          — influence assessment may be refined
      - target_contact     — attribution may be amended
      - target_department  — department may be corrected
      - notes              — free-text narrative may be refined

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Forbidden via PATCH (inherited):
      status, validated_by, validated_at, source, account,
      source_activity, decision_cycle, campaign.
    """

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = PeopleSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            'full_name',
            'role',
            'influence',
            'target_contact',
            'target_department',
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            # full_name may be corrected; full_name_normalized is derived in
            # save() and is NEVER writable (not a field here).
            'full_name':         {'required': False, 'allow_blank': True},
            'role':              {'required': False},
            'influence':         {'required': False, 'allow_null': True},
            'target_contact':    {'required': False, 'allow_null': True},
            'target_department': {'required': False, 'allow_null': True},
            'notes':             {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Identity invariant on the MERGED state (re-surfaced from
        PeopleSignal.clean(), applied to PATCH — the create serializer only
        sees the incoming payload, so the update path needs its own check).

        A PATCH must not strip the last identity: at least one of
        target_contact / target_department / full_name must remain, taking the
        incoming value when the field is in the payload, else the instance's
        current value. Raises a standard 400 (never a 500 / bare exception).
        """
        inst = self.instance

        contact = (attrs['target_contact'] if 'target_contact' in attrs
                   else inst.target_contact_id)
        dept = (attrs['target_department'] if 'target_department' in attrs
                else inst.target_department_id)
        name = attrs['full_name'] if 'full_name' in attrs else inst.full_name

        if not contact and not dept and not (name or '').strip():
            raise StandardizedValidationError(
                'A people signal must keep at least one of target_contact, '
                'target_department or full_name.'
            )

        return super().validate(attrs)
