# app_modules/signals/serializers/tech_stack_serializer.py
"""
Serializers for TechStackSignal.

Stack:
  TechStackSignalListSerializer   — lightweight list view
  TechStackSignalDetailSerializer — full detail (validated_*, requested_by,
                                    source_quote, metadata, original_value
                                    on top of the list payload)
  TechStackSignalCreateSerializer — write path with conditional rules
  TechStackSignalUpdateSerializer — restricted PATCH, merged-state checks

Notes:
  - The model shadow-overrides `decision_cycle`, `campaign`, and
    `signal_category` to None on the concrete TechStackSignal — see
    app_modules/signals/models/tech_stack_signal.py docstring for the
    rationale of each. Of these three, only `signal_category` (and its
    `signal_category_display` companion) is declared at the top level
    of the base serializers, so it is the only one that requires
    filtering. decision_cycle and campaign are no longer top-level
    fields on the base — they live inside the `source_context` block
    produced by SignalSourceSerializer, which already handles the
    shadow-override at runtime via getattr() fallback.

  - source_contact and source_department were previously shadow-overridden
    too. Both were retired from BaseSignal entirely during the
    standardisation refactor — there is nothing left to strip for them
    at the serializer level.

  - Tech identity is free text: `tech_name` is required on Create and
    stays editable. `tech_name_normalized` is derived by model.save()
    and is read-only everywhere — it is never accepted from the API.
    TechStack is not clustered, so canonical_key is never set.

  - Qualification: is_competitor / is_integration / is_to_replace are
    three independent booleans, default False, writable on both Create
    and Update.

  - Usage: usage_scope is the SCALE (TEAM/COMPANY/UNKNOWN); the WHO is the
    multi-department M2M usage_departments, written as a list of
    StandardDepartment ids and independent of usage_scope. The legacy
    single FK usage_department has been dropped.

  - Conditional rule (mirror of TechStackSignal.clean()):
      is_discontinued = True    → discontinued_date REQUIRED
      is_discontinued = False   → discontinued_date FORBIDDEN
    Enforced strict in Create, merged-state in Update.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from app_modules.core_modules.models import StandardDepartment

from ..models import TechStackSignal
from .base_serializer import (
    BaseSignalCreateSerializer,
    BaseSignalDetailSerializer,
    BaseSignalListSerializer,
    BaseSignalUpdateSerializer,
)


# =============================================================================
# HELPERS — display methods + conditional validation
# =============================================================================
#
# List and Detail share the read shape for usage_scope and the
# usage_departments list. A small mixin keeps both serializers aligned when
# the schema evolves. tech_name / tech_name_normalized and the three
# qualification booleans are plain model fields — no method needed.
#
# Conditional validation helpers are shared by Create (strict) and
# Update (merged-state) — same pattern as ObjectiveSignal / ImpactSignal.
# =============================================================================


class _TechStackDisplayMixin:
    """Shared SerializerMethodField implementations for TechStack serializers."""

    def get_usage_scope_display(self, obj):
        return obj.get_usage_scope_display() if obj.usage_scope else None

    def get_usage_departments(self, obj):
        """
        Compact list of the departments that USE this tool (multi-department).

        Returns a list of {id, name} payloads, one entry per linked
        StandardDepartment. Empty list when none are designated.

        N+1-safe: reads obj.usage_departments.all(), which the ViewSet
        prefetches (prefetch_related('usage_departments')), so iterating
        the manager here fires no per-row query. `.all()` (not a filtered
        queryset) is required to hit the prefetched cache.
        """
        return [
            {
                'id':   str(d.id),
                'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
            }
            for d in obj.usage_departments.all()
        ]


def _validate_discontinuation_consistency(is_discontinued, discontinued_date):
    """
    Enforce is_discontinued ↔ discontinued_date coherence.

    Mirror of TechStackSignal.clean() rule 2. Called by Create (strict)
    and Update (merged-state).

    Rules:
      is_discontinued = True  → discontinued_date REQUIRED
      is_discontinued = False → discontinued_date FORBIDDEN

    Note: bool(is_discontinued) is used so that a missing key in a
    PATCH payload (None on the merged value) doesn't accidentally land
    in the True branch.
    """
    if is_discontinued:
        if not discontinued_date:
            raise StandardizedValidationError({
                'discontinued_date': SignalErrorMessages.TECHSTACK_DISCONTINUED_REQUIRES_DATE,
            })
    else:
        if discontinued_date:
            raise StandardizedValidationError({
                'discontinued_date': SignalErrorMessages.TECHSTACK_DISCONTINUED_DATE_WITHOUT_FLAG,
            })


# =============================================================================
# BASE FIELD STRIP
# =============================================================================
# TechStackSignal shadow-overrides `signal_category` to None on the
# concrete model (see app_modules/signals/models/tech_stack_signal.py
# docstring). Among the base serializer fields, only signal_category
# and its signal_category_display companion need to be stripped — they
# are declared at the top level of BaseSignalListSerializer /
# BaseSignalDetailSerializer / BaseSignalCreateSerializer /
# BaseSignalUpdateSerializer. We strip them here once and reuse the
# resulting filtered lists in every Meta below — keeps the four
# serializers in sync.
#
# Other shadow-overrides on the model (decision_cycle, campaign):
#   These are not declared at the top level of the base serializers
#   post-standardisation refactor — they are exposed exclusively
#   through the `source_context` block produced by
#   SignalSourceSerializer, which handles the runtime fallback via
#   getattr() (returns None when the attribute is absent at the
#   concrete-class level). No strip needed here.
#
# Retired shadow-overrides (source_contact, source_department):
#   Both fields were removed from BaseSignal entirely during the
#   standardisation refactor — they are no longer declared anywhere
#   in the base serializers. Nothing to strip.
# =============================================================================

_SHADOW_OVERRIDDEN_FIELDS = frozenset({
    'signal_category',
    'signal_category_display',
})

def _strip_shadow_fields(field_list):
    """Return a copy of `field_list` without TechStack's shadow-overridden fields."""
    return [f for f in field_list if f not in _SHADOW_OVERRIDDEN_FIELDS]


def _strip_shadow_extra_kwargs(extra_kwargs):
    """Return a copy of `extra_kwargs` without TechStack's shadow-overridden fields."""
    return {
        k: v for k, v in extra_kwargs.items()
        if k not in _SHADOW_OVERRIDDEN_FIELDS
    }


# =============================================================================
# LIST
# =============================================================================

class TechStackSignalListSerializer(_TechStackDisplayMixin, BaseSignalListSerializer):
    """
    Lightweight serializer for TechStackSignal list endpoints.

    Exposes:
      - Tech identity (tech_name + the derived normalised key)
      - Qualification booleans
      - Usage scope (scale) + usage_departments (multi-department list)
      - Lifecycle quick view: usage_start_year, renewal_date,
        is_discontinued, discontinued_date
      - cost_description (optional but useful at-a-glance)

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).
    The standardised `source_context` block is inherited as-is from
    the base; SignalSourceSerializer handles the shadow-overridden
    decision_cycle / campaign at runtime by falling back to
    source_activity.decision_cycle / .campaign.
    """

    # Scope (scale) + the multi-department usage list (who USES the tool).
    usage_scope_display = serializers.SerializerMethodField()
    usage_departments   = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = TechStackSignal

        # Strip shadow-overridden fields from inherited list.
        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            # Tech identity (raw + derived key)
            'tech_name',
            'tech_name_normalized',
            # Qualification (independent booleans)
            'is_competitor',
            'is_integration',
            'is_to_replace',
            # Usage scale
            'usage_scope', 'usage_scope_display',
            # Multi-department usage (who USES the tool)
            'usage_departments',
            # Lifecycle stats
            'usage_start_year',
            'renewal_date',
            'cost_description',
            'is_discontinued',
            'discontinued_date',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL
# =============================================================================

class TechStackSignalDetailSerializer(_TechStackDisplayMixin, BaseSignalDetailSerializer):
    """
    Full detail serializer for TechStackSignal retrieve endpoints.

    Inherits validated_at / validated_by / requested_by / source_quote /
    metadata / original_value from BaseSignalDetailSerializer. Adds
    notes on top of the list payload.

    signal_category / signal_category_display are stripped from
    inherited fields (model shadow-overrides signal_category to None).

    Note (history):
      Earlier versions also stripped source_contact / source_department
      / decision_cycle / campaign. Following the standardisation refactor:
        - source_contact / source_department were removed from
          BaseSignal entirely.
        - decision_cycle / campaign moved out of the top-level
          serializer fields and into the standardised `source_context`
          block (produced by SignalSourceSerializer with getattr()
          fallback for shadow-overridden cases).
      None of these four fields require explicit stripping anymore.

      An older note mentioned `get_decision_cycle` / `get_campaign`
      methods on BaseSignalDetailSerializer that would error out on
      shadow-overridden FKs — these methods were removed; the
      fallback now lives in SignalSourceSerializer.
    """

    usage_scope_display = serializers.SerializerMethodField()
    # Multi-department usage (who USES the tool) — compact list payload.
    usage_departments   = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = TechStackSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            # Tech identity (raw + derived key)
            'tech_name',
            'tech_name_normalized',
            # Qualification (independent booleans)
            'is_competitor',
            'is_integration',
            'is_to_replace',
            # Usage scale
            'usage_scope', 'usage_scope_display',
            # Multi-department usage (who USES the tool)
            'usage_departments',
            # Lifecycle stats
            'usage_start_year',
            'renewal_date',
            'cost_description',
            'is_discontinued',
            'discontinued_date',
            # Narrative
            'notes',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE
# =============================================================================

class TechStackSignalCreateSerializer(BaseSignalCreateSerializer):
    """
    Write serializer for TechStackSignal creation.

    signal_type is fixed to 'tech_stack' via HiddenField (consumed by
    SignalManager.create() — same identifier across all layers
    including SignalDataService._SIGNAL_TYPE_MAP).

    Required:
      - account              (inherited from BaseSignalCreateSerializer)
      - tech_name            (free text; the tool's identity)

    Optional:
      - source_activity (left optional — TechStack is not as strictly
                         conversation-anchored as Pain; an external
                         research signal may carry no activity)
      - usage_scope (scale) + usage_departments (multi-department M2M)
      - usage_start_year, renewal_date, cost_description
      - is_discontinued, discontinued_date (conditional)
      - notes
      - source_quote, language_original, source, confidence,
        is_inferred, metadata (inherited)

    Strict validation on the conditional pairs — see helpers above.

    Stripped from BaseSignalCreateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Note: source_contact / source_department / decision_cycle / campaign
    were previously stripped here too. Following the standardisation
    refactor:
      - source_contact / source_department were removed from
        BaseSignal entirely.
      - decision_cycle / campaign were removed from the Create
        serializer (auto-populated by SignalManager from
        source_activity at create time — never accepted from the API).
    None of these four fields appear in the base Create fields anymore.
    """

    signal_type = serializers.HiddenField(default='tech_stack')

    # WHO uses the tool — multi-department M2M, written as a list of
    # StandardDepartment ids. PrimaryKeyRelatedField(many=True) validates
    # each id against the vocabulary and hands SignalManager.create a list
    # of instances, which it applies via .set() after the row is saved
    # (M2M can't be set pre-save). Same write shape as the DecisionStep /
    # CampaignAccount department M2M. Optional — [] means nobody designated.
    usage_departments = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=StandardDepartment.objects.all(),
    )

    class Meta(BaseSignalCreateSerializer.Meta):
        model = TechStackSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            # Tech identity (raw; the normalised key is derived in save())
            'tech_name',
            # Qualification (independent booleans)
            'is_competitor',
            'is_integration',
            'is_to_replace',
            # Usage scale + who (multi-department)
            'usage_scope',
            'usage_departments',
            # Lifecycle stats
            'usage_start_year',
            'renewal_date',
            'cost_description',
            # Discontinuation
            'is_discontinued',
            'discontinued_date',
            # Narrative
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'tech_name':          {'required': True, 'allow_blank': False},
            'is_competitor':      {'required': False},
            'is_integration':     {'required': False},
            'is_to_replace':      {'required': False},
            'usage_scope':        {'required': False, 'allow_null': True},
            'usage_start_year':   {'required': False, 'allow_null': True},
            'renewal_date':       {'required': False, 'allow_null': True},
            'cost_description':   {'required': False, 'allow_blank': True},
            'is_discontinued':    {'required': False},
            'discontinued_date':  {'required': False, 'allow_null': True},
            'notes':              {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Enforce TechStack-specific rules, then delegate to base.

        Order matters:
          1. tech_name presence (defense in depth — extra_kwargs marks
             it required, but the explicit check also rejects a
             whitespace-only name, which allow_blank=False alone would
             let through).
          2. Discontinuation ↔ discontinued_date coherence (strict).
          3. super().validate() — base injects client_id from JWT
             context.

        usage_departments carries no conditional rule: the multi-department
        M2M is independent of usage_scope (the WHO is orthogonal to the
        SCALE), so any combination is valid.
        """

        # Rule 1: tech_name presence (rejects whitespace-only too)
        if not (attrs.get('tech_name') or '').strip():
            raise StandardizedValidationError({
                'tech_name': SignalErrorMessages.TECHSTACK_NAME_REQUIRED,
            })

        # Rule 2: discontinuation ↔ date coherence (strict)
        _validate_discontinuation_consistency(
            is_discontinued=attrs.get('is_discontinued', False),
            discontinued_date=attrs.get('discontinued_date'),
        )

        # Delegate to base for client_id injection.
        return super().validate(attrs)


# =============================================================================
# UPDATE
# =============================================================================

class TechStackSignalUpdateSerializer(BaseSignalUpdateSerializer):
    """
    Restricted PATCH serializer for TechStackSignal.

    Allowed beyond inherited base fields:
      - tech_name  (correcting what the LLM heard is a normal edit)
      - is_competitor, is_integration, is_to_replace
      - usage_scope  (scale) + usage_departments (multi-department M2M,
        list of StandardDepartment ids; replaces .set())
      - usage_start_year, renewal_date, cost_description
      - is_discontinued, discontinued_date  (conditional pair)
      - notes

    tech_name is editable at any status. It is free text, not an
    identifier: a rep fixing "Sales force" to "Salesforce" is correcting
    a transcription, not repointing the signal at a different tool. The
    normalised key follows automatically on save(), so the corrected
    signal regroups with its peers immediately. Blanking it is refused —
    a nameless tech observation cannot be displayed or grouped.

    S10 note: this serializer previously guarded a `tech_catalog_entry`
    FK that was settable only while PENDING and locked once VALIDATED
    (TECHSTACK_CATALOG_ENTRY_LOCKED). The catalogue is gone; there is no
    identifier left to lock.

    NOT writable:
      - tech_name_normalized (derived in save(); read-only by contract)
      - canonical_key (TechStack is not clustered; never set)

    Merged-state validation:
      A partial PATCH that touches `is_discontinued` or `discontinued_date`
      triggers the discontinuation consistency check against the merged
      (instance + payload) state. usage_departments carries no conditional
      rule (independent of usage_scope), so a PATCH may set it freely.

    Examples:
      Reassigning the using departments:
        PATCH { usage_departments: [7, 5] }  → replaces the M2M set.
        PATCH { usage_departments: [] }      → clears it.

      Marking discontinued without a date:
        PATCH { is_discontinued: true }
          → rejected (missing discontinued_date).
        PATCH { is_discontinued: true, discontinued_date: '2026-06-30' }
          → accepted.

    Stripped from BaseSignalUpdateSerializer.Meta.fields:
      signal_category — the model shadow-overrides it to None.

    Note: source_contact / source_department were previously stripped
    here too. They were removed from BaseSignal entirely during the
    standardisation refactor — they no longer appear in the base
    Update fields, so no strip is needed.
    """

    # WHO uses the tool — multi-department M2M, written as a list of
    # StandardDepartment ids (same shape as Create). Applied via .set() by
    # SignalManager.edit after the row is loaded.
    usage_departments = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=StandardDepartment.objects.all(),
    )

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = TechStackSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            # Tech identity (raw; normalised key follows in save())
            'tech_name',
            # Qualification (independent booleans)
            'is_competitor',
            'is_integration',
            'is_to_replace',
            # Usage scale + who (multi-department)
            'usage_scope',
            'usage_departments',
            # Lifecycle stats
            'usage_start_year',
            'renewal_date',
            'cost_description',
            # Discontinuation (conditional pair)
            'is_discontinued',
            'discontinued_date',
            # Narrative
            'notes',
        ]
        extra_kwargs = {
            **_base_extra_kwargs,
            'tech_name':          {'required': False, 'allow_blank': False},
            'is_competitor':      {'required': False},
            'is_integration':     {'required': False},
            'is_to_replace':      {'required': False},
            'usage_scope':        {'required': False, 'allow_null': True},
            'usage_start_year':   {'required': False, 'allow_null': True},
            'renewal_date':       {'required': False, 'allow_null': True},
            'cost_description':   {'required': False, 'allow_blank': True},
            'is_discontinued':    {'required': False},
            'discontinued_date':  {'required': False, 'allow_null': True},
            'notes':              {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Reject a blanked tech_name, then run the merged-state coherence
        checks on partial payloads.

        tech_name:
          Editable at any status (see class docstring), but never
          blankable — allow_blank=False catches '', and the explicit
          check below also catches a whitespace-only value, which would
          otherwise normalise to an empty grouping key.

        One conditional pair remains:
          is_discontinued ↔ discontinued_date

        It is checked only when at least one of its members is in the
        payload — otherwise the instance is already valid and nothing
        changed for that pair. This avoids spurious 400s on unrelated
        PATCHes (e.g. a notes-only update). usage_departments is
        unconditional (independent of usage_scope) and needs no check.
        """
        instance = self.instance

        # --- tech_name may be corrected, never blanked ---
        if 'tech_name' in attrs and not (attrs['tech_name'] or '').strip():
            raise StandardizedValidationError({
                'tech_name': SignalErrorMessages.TECHSTACK_NAME_REQUIRED,
            })

        # --- discontinuation coherence ---
        touched_disc_fields = any(
            field in attrs
            for field in ('is_discontinued', 'discontinued_date')
        )

        if touched_disc_fields and instance is not None:
            merged_is_discontinued = (
                attrs['is_discontinued']
                if 'is_discontinued' in attrs
                else instance.is_discontinued
            )
            merged_discontinued_date = (
                attrs['discontinued_date']
                if 'discontinued_date' in attrs
                else instance.discontinued_date
            )
            _validate_discontinuation_consistency(
                is_discontinued=merged_is_discontinued,
                discontinued_date=merged_discontinued_date,
            )

        return super().validate(attrs)