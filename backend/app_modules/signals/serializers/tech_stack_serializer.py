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

Sprint TechStack notes:
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

  - Cluster identity is driven by tech_catalog_entry FK. canonical_key
    is recomputed by model.save() from the FK and is never writable
    via the serializer — same stance as Pain/Objective with their
    canonical axes (what × dimension).

  - Conditional rules (mirror of TechStackSignal.clean()):
      tech_catalog_entry required (Create + Update treat the FK as
        immutable on Update — repointing a signal to a different tool
        changes its cluster identity, which should be a delete +
        recreate flow).
      usage_scope = DEPARTMENT  → usage_department REQUIRED
      usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}
                                → usage_department FORBIDDEN
      is_discontinued = True    → discontinued_date REQUIRED
      is_discontinued = False   → discontinued_date FORBIDDEN
    Enforced strict in Create. Enforced merged-state in Update — same
    pattern as ObjectiveSignal scope and PainImpact level.
"""

from rest_framework import serializers

from core.error_messages import SignalErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import UsageScope
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
# List and Detail share the read shape for tech_catalog_entry, usage_scope,
# and usage_department. A small mixin keeps both serializers aligned
# when the schema evolves.
#
# Conditional validation helpers are shared by Create (strict) and
# Update (merged-state) — same pattern as ObjectiveSignal / PainImpact.
# =============================================================================


class _TechStackDisplayMixin:
    """Shared SerializerMethodField implementations for TechStack serializers."""

    def get_usage_scope_display(self, obj):
        return obj.get_usage_scope_display() if obj.usage_scope else None

    def get_tech_catalog_entry(self, obj):
        """
        Compact catalog payload — keeps the frontend from issuing a
        separate /tech-catalog/<id>/ fetch just to render the tool name
        on a signal card.
        """
        entry = obj.tech_catalog_entry
        if not entry:
            return None
        return {
            'id':                    str(entry.id),
            'company_name':          entry.company_name,
            'product_name':          entry.product_name,
            'is_competitor':         entry.is_competitor,
            'is_integration_target': entry.is_integration_target,
        }

    def get_usage_department(self, obj):

        d = obj.usage_department
        if not d:
            return None
        return {
            'id':   str(d.id),
            'name': d.get_name_display() if hasattr(d, 'get_name_display') else str(d),
        }


def _validate_scope_consistency(usage_scope, usage_department):
    """
    Enforce usage_scope ↔ usage_department coherence.

    Mirror of TechStackSignal.clean() rule 2. Called by Create (strict)
    and Update (merged-state). Raises StandardizedValidationError on
    the first offending field for a clean API error payload.

    Rules:
      usage_scope = DEPARTMENT
        → usage_department REQUIRED (else 400)
      usage_scope ∈ {TEAM, COMPANY, UNKNOWN, None}
        → usage_department FORBIDDEN (else 400)
    """
    if usage_scope == UsageScope.DEPARTMENT:
        if not usage_department:
            raise StandardizedValidationError({
                'usage_department': SignalErrorMessages.TECHSTACK_DEPT_REQUIRES_DEPT,
            })
    else:
        # Covers TEAM, COMPANY, UNKNOWN, and None.
        if usage_department:
            raise StandardizedValidationError({
                'usage_department': SignalErrorMessages.TECHSTACK_DEPT_OUTSIDE_SCOPE,
            })


def _validate_discontinuation_consistency(is_discontinued, discontinued_date):
    """
    Enforce is_discontinued ↔ discontinued_date coherence.

    Mirror of TechStackSignal.clean() rule 3. Called by Create (strict)
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
      - Catalog anchor (compact tech_catalog_entry payload)
      - Usage scope + usage_department (when DEPARTMENT)
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

    # Catalog + scope + dept compact payloads
    tech_catalog_entry  = serializers.SerializerMethodField()
    usage_scope_display = serializers.SerializerMethodField()
    usage_department    = serializers.SerializerMethodField()

    class Meta(BaseSignalListSerializer.Meta):
        model = TechStackSignal

        # Strip shadow-overridden fields from inherited list.
        _base_fields = _strip_shadow_fields(BaseSignalListSerializer.Meta.fields)

        fields = _base_fields + [
            # Catalog anchor (drives canonical_key)
            'tech_catalog_entry',
            # Scope axis (conditional dept)
            'usage_scope', 'usage_scope_display',
            'usage_department',
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

    tech_catalog_entry  = serializers.SerializerMethodField()
    usage_scope_display = serializers.SerializerMethodField()
    usage_department    = serializers.SerializerMethodField()

    class Meta(BaseSignalDetailSerializer.Meta):
        model = TechStackSignal

        _base_fields = _strip_shadow_fields(BaseSignalDetailSerializer.Meta.fields)

        fields = _base_fields + [
            # Catalog anchor
            'tech_catalog_entry',
            # Scope axis
            'usage_scope', 'usage_scope_display',
            'usage_department',
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
      - tech_catalog_entry   (catalog FK — drives canonical_key)

    Optional:
      - source_activity (left optional — TechStack is not as strictly
                         conversation-anchored as Pain; an external
                         research signal may carry no activity)
      - usage_scope, usage_department (conditional)
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

    class Meta(BaseSignalCreateSerializer.Meta):
        model = TechStackSignal

        _base_fields       = _strip_shadow_fields(BaseSignalCreateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalCreateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            # Catalog anchor (required)
            'tech_catalog_entry',
            # Scope axis
            'usage_scope',
            'usage_department',
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
            'tech_catalog_entry': {'required': True},
            'usage_scope':        {'required': False, 'allow_null': True},
            'usage_department':   {'required': False, 'allow_null': True},
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
          1. tech_catalog_entry presence (defense in depth — extra_kwargs
             marks it required, but the explicit check yields a typed
             error message via SignalErrorMessages).
          2. Scope ↔ usage_department coherence (strict — Create has
             no instance state to merge against).
          3. Discontinuation ↔ discontinued_date coherence (strict).
          4. super().validate() — base injects client_id from JWT
             context. The previous cross-account source_contact check
             is gone (the field was retired from BaseSignal during
             the standardisation refactor).
        """

        # Rule 1: catalog FK presence
        if not attrs.get('tech_catalog_entry'):
            raise StandardizedValidationError({
                'tech_catalog_entry': SignalErrorMessages.TECHSTACK_CATALOG_ENTRY_REQUIRED,
            })

        # Rule 2: scope ↔ department coherence (strict)
        _validate_scope_consistency(
            usage_scope=attrs.get('usage_scope'),
            usage_department=attrs.get('usage_department'),
        )

        # Rule 3: discontinuation ↔ date coherence (strict)
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
      - usage_scope, usage_department  (conditional pair)
      - usage_start_year, renewal_date, cost_description
      - is_discontinued, discontinued_date  (conditional pair)
      - notes

    NOT writable:
      - tech_catalog_entry (immutable post-creation — repointing a signal
        to a different tool changes its cluster identity. The proper
        flow is: delete the signal and create a new one against the
        correct catalog entry. Surfacing this constraint at the
        serializer level prevents silent corruption of cluster stats.)
      - canonical_key (auto-derived by model.save() from the FK)

    Merged-state validation:
      A partial PATCH that touches `usage_scope`, `usage_department`,
      `is_discontinued`, or `discontinued_date` triggers the matching
      consistency check against the merged (instance + payload) state.
      Same pattern as ObjectiveSignalUpdateSerializer.

    Examples:
      Switching usage_scope=DEPARTMENT to usage_scope=COMPANY:
        PATCH { usage_scope: 'COMPANY' }
          → rejected (current usage_department still set, violates the
                       "outside scope = forbidden" rule).
        PATCH { usage_scope: 'COMPANY', usage_department: null }
          → accepted.

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

    class Meta(BaseSignalUpdateSerializer.Meta):
        model = TechStackSignal

        _base_fields       = _strip_shadow_fields(BaseSignalUpdateSerializer.Meta.fields)
        _base_extra_kwargs = _strip_shadow_extra_kwargs(BaseSignalUpdateSerializer.Meta.extra_kwargs)

        fields = _base_fields + [
            # Scope axis (conditional pair)
            'usage_scope',
            'usage_department',
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
            'usage_scope':        {'required': False, 'allow_null': True},
            'usage_department':   {'required': False, 'allow_null': True},
            'usage_start_year':   {'required': False, 'allow_null': True},
            'renewal_date':       {'required': False, 'allow_null': True},
            'cost_description':   {'required': False, 'allow_blank': True},
            'is_discontinued':    {'required': False},
            'discontinued_date':  {'required': False, 'allow_null': True},
            'notes':              {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        """
        Merged-state coherence check on partial payloads.

        Two independent conditional pairs:
          A. usage_scope ↔ usage_department
          B. is_discontinued ↔ discontinued_date

        Each pair is checked only when at least one of its members is
        in the payload — otherwise the instance is already valid and
        nothing changed for that pair. This avoids spurious 400s on
        unrelated PATCHes (e.g. a notes-only update).
        """
        instance = self.instance

        # --- Pair A: scope coherence ---
        touched_scope_fields = any(
            field in attrs
            for field in ('usage_scope', 'usage_department')
        )

        if touched_scope_fields and instance is not None:
            merged_scope = (
                attrs['usage_scope']
                if 'usage_scope' in attrs
                else instance.usage_scope
            )
            merged_department = (
                attrs['usage_department']
                if 'usage_department' in attrs
                else instance.usage_department
            )
            _validate_scope_consistency(
                usage_scope=merged_scope,
                usage_department=merged_department,
            )

        # --- Pair B: discontinuation coherence ---
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