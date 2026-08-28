# app_modules/signals/services/signal_data_service.py

"""
SignalDataService — read-only signal queries and LLM formatting.

Provides optimised querysets for the 4 concrete signal types (Pain,
Objective, Impact, TechStack) and compact LLM-ready formatting. No
state mutation — all writes go through SignalManager.

Public API:
  get_by_account(account_id, signal_type, status, **filters)
  get_by_contact(contact_id)
  format_for_llm(queryset)

Standardisation refactor notes
------------------------------
source_contact and source_department were retired from BaseSignal
during the standardisation refactor. The "TechStack-style" join
strategy that previously applied only to TechStack is now
generalised to every signal type:

  - get_by_contact: ALL signal types are matched by
    source_activity__contacts (contacts who PARTICIPATED in the source
    conversation). Single uniform code path, no per-type branching.
  - format_for_llm: contact name is derived from
    source_activity.contacts.first() across all types — consistent
    with the standardised `source_context` block exposed by the
    serializers.

decision_cycle / campaign remain direct FKs on Pain and Objective
(populated by SignalManager._propagate_activity_context from
source_activity at create time). See Q1 architectural decision.

TechStackSignal still shadow-overrides decision_cycle, campaign, and
signal_category. The per-type _RELATED_BY_TYPE map remains the single
source of truth for select_related preloading per concrete model.
"""

from core.exceptions import StandardizedValidationError
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus
from ..models import PainSignal, ObjectiveSignal, ImpactSignal, TechStackSignal


# Mapping from string key → model class.
_SIGNAL_TYPE_MAP = {
    'pain':       PainSignal,
    'objective':  ObjectiveSignal,
    'impact':     ImpactSignal,
    'tech_stack': TechStackSignal,
}

# select_related paths PER signal type.
#
# Each list contains only FKs that ACTUALLY exist on the concrete model.
# Extending this dict is the single point of truth when a model gains or
# loses a relation that benefits from select_related preloading.
#
# source_activity is preloaded for all 3 types because:
#   - The standardisation refactor derives the contact set from
#     source_activity.contacts (m2m). Without source_activity in
#     select_related, every signal access through that path triggers
#     an extra query.
#   - format_for_llm walks source_activity.contacts.first() per signal
#     to compose the LLM contact name.
#
# Note: source_activity.contacts is a m2m and requires
# prefetch_related('source_activity__contacts') to be efficient — that
# prefetch lives at the view layer (PHASE E) since it's a per-action
# concern, not a default per-type optimisation.
_RELATED_BY_TYPE = {
    'pain': [
        'source_activity',
        'validated_by',
        'decision_cycle',
        'campaign',
    ],
    'objective': [
        'source_activity',
        'validated_by',
        'decision_cycle',
        'campaign',
        'target_contact',
        'target_department',
    ],
    # ImpactSignal — same base FK surface as Pain/Objective (no
    # Impact-specific FK). Impact-specific data (impact_type,
    # scope_level, metric_text, human_impact) are scalar fields
    # requiring no relational preload.
    'impact': [
        'source_activity',
        'validated_by',
        'decision_cycle',
        'campaign',
    ],
    # TechStackSignal narrow surface — shadow-overrides decision_cycle,
    # campaign, and signal_category. (source_contact / source_department
    # were retired from BaseSignal entirely during the standardisation
    # refactor — they are not "shadow-overridden", they simply do not
    # exist on any signal type anymore.)
    'tech_stack': [
        'source_activity',
        'validated_by',
        # usage_department (single FK) retired -- WHO the tool serves is now
        # the multi-department M2M usage_departments, preloaded via
        # _PREFETCH_BY_TYPE below (M2M can't ride select_related).
    ],
}

# prefetch_related paths PER signal type (M2M / reverse relations, which
# cannot ride select_related). Applied alongside _RELATED_BY_TYPE on every
# queryset this service builds so multi-valued relations stay N+1-safe.
_PREFETCH_BY_TYPE = {
    'tech_stack': [
        'usage_departments',   # WHO uses the tool (multi-department).
    ],
}

# Allowlist of filters accepted by get_by_account.
#
# Note on cross-type validity:
#   - 'signal_category' does NOT exist on TechStackSignal nor on
#     ObjectiveSignal (both shadow-override it). Passing it with
#     signal_type='tech_stack' or 'objective' will raise a FieldError.
#     This is by design — the allowlist is generic, model surface
#     enforces what applies. Callers must respect each model's
#     documented surface.
#
# Removed during the standardisation refactor:
#   - 'source_department' — the field was retired from BaseSignal
#     entirely; it no longer exists on any signal type.
_ALLOWED_FILTERS = {
    'signal_category',
    'source',
    'is_inferred',
}


class SignalDataService:
    """
    Stateless read service for signal data retrieval and LLM formatting.

    All methods are classmethods — no instance needed.
    No writes, no business logic — pure query and formatting.
    """

    # =========================================================================
    # GET BY ACCOUNT
    # =========================================================================

    @classmethod
    def get_by_account(
        cls,
        account_id,
        signal_type: str = None,
        status: str = None,
        **filters,
    ):
        """
        Return signals for a given account, optionally filtered.

        Args:
            account_id:  UUID of the account.
            signal_type: 'pain' | 'objective' | 'impact' | 'tech_stack' | None.
                         None returns all 4 types.
            status:      SignalStatus value to filter by (e.g. 'VALIDATED').
                         None applies no status filter.
            **filters:   Additional ORM filters (allowlisted).
                         Supported: signal_category, source, is_inferred.

        Returns:
            If signal_type given → single QuerySet for that model.
            If signal_type None  → dict with keys 'pain', 'objective',
                                   'impact', 'tech_stack'.

        Raises:
            StandardizedValidationError if signal_type is invalid.

        Cross-type filter notes:
          - signal_category does not exist on ObjectiveSignal nor on
            TechStackSignal (both shadow-override it). Passing it with
            those signal_type values raises a FieldError. Callers
            querying Objective / TechStack should restrict themselves
            to 'source' and 'is_inferred' filters.
          - source_department was retired from BaseSignal during the
            standardisation refactor and is no longer accepted in the
            allowlist (any caller still passing it gets it silently
            stripped by the safe_filters comprehension).
        """

        safe_filters = {k: v for k, v in filters.items() if k in _ALLOWED_FILTERS}

        def _build_qs(type_key, model_class):
            related = _RELATED_BY_TYPE.get(type_key, [])
            prefetch = _PREFETCH_BY_TYPE.get(type_key, [])
            qs = (
                model_class.objects
                .filter(account_id=account_id)
                # Exclude out-of-taxonomy-domain signals (COST-bug guard): a
                # flagged signal must not feed downstream (incl. LLM context).
                .filter(is_domain_valid=True)
                .select_related(*related)
                .prefetch_related(*prefetch)
            )
            if status:
                qs = qs.filter(status=status)
            if safe_filters:
                qs = qs.filter(**safe_filters)
            return qs

        if signal_type:
            model_class = _SIGNAL_TYPE_MAP.get(signal_type)
            if not model_class:
                raise StandardizedValidationError(
                    SignalErrorMessages.INVALID_SIGNAL_TYPE.format(
                        signal_type=signal_type
                    )
                )
            return _build_qs(signal_type, model_class)

        return {
            key: _build_qs(key, model_class)
            for key, model_class in _SIGNAL_TYPE_MAP.items()
        }

    # =========================================================================
    # GET BY CONTACT
    # =========================================================================

    @classmethod
    def get_by_contact(cls, contact_id) -> dict:
        """
        Return all signals associated with a contact, across all types.

        Args:
            contact_id: UUID of the contact.

        Returns:
            dict with keys 'pain', 'objective', 'impact', 'tech_stack'.

        Standardisation refactor — uniformised semantics
        ------------------------------------------------
        All signal types are now matched by source_activity.contacts:

            source_activity__contacts__id = contact_id

        This is a single uniform code path replacing the previous
        per-type branching. The previous Pain / Objective semantics
        (direct source_contact FK on the model = "this contact
        REPORTED the signal") is gone with the field removal.

        New semantics across all types:
          "Signal whose source conversation included this contact"

        Stricter than the previous direct FK lookup — Pain / Objective
        signals without source_activity are excluded from the result.
        For Pain this is irrelevant in practice (source_activity is
        required at clean()). For Objective and TechStack,
        source_activity is optional and signals without one are simply
        not surfaced by this method — by design.

        distinct() is required because the JOIN on the m2m
        (source_activity.contacts) can yield duplicate rows when a
        contact participates in multiple activities tied to the same
        signal — defensive even though the current single-value
        filter does not in practice trigger duplicates.
        """
        result = {}
        for key, model_class in _SIGNAL_TYPE_MAP.items():
            related = _RELATED_BY_TYPE.get(key, [])
            prefetch = _PREFETCH_BY_TYPE.get(key, [])
            qs = (
                model_class.objects
                .filter(source_activity__contacts__id=contact_id)
                # Exclude out-of-taxonomy-domain signals (COST-bug guard).
                .filter(is_domain_valid=True)
                .select_related(*related)
                .prefetch_related(*prefetch)
                .distinct()
            )
            result[key] = qs
        return result

    # =========================================================================
    # FORMAT FOR LLM
    # =========================================================================

    @classmethod
    def format_for_llm(cls, queryset) -> list:
        """
        Format a signal queryset into a compact list for LLM prompt injection.

        Strips all technical identifiers and retains only fields meaningful
        to the LLM. Stateless — pure read-and-format, no service
        dependencies.

        Output format per signal (common across all 4 types):
        {
            "type":       "PainSignal",     # class name for LLM disambiguation
            "category":   "ECONOMIC",       # signal_category — None on
                                            # Objective / Impact / TechStack
                                            # (shadow-overridden)
            "summary":    "...",            # type-appropriate text excerpt
            "contact":    "Jane Doe",       # first contact of source_activity, or None
            "department": "IT",             # usage_departments (joined) for TechStack only,
                                            # None for Pain / Objective / Impact
            "confirmed":  1,                # always 1 in MVP
            "date":       "2025-03-15"      # validated_at date or None
        }

        Standardisation refactor changes
        --------------------------------
        - signal_category : None for TechStack and Objective (both
                            shadow-override it on the model).
        - summary         : Pain / Objective use signal.summary (or
                            notes fallback). TechStack composes
                            "<company> <product>" from
                            tech_name plus notes when set.
        - contact         : Now uniformly derived from
                            source_activity.contacts.first() across
                            all 3 types. Previous per-type branching
                            (Pain / Objective via source_contact FK)
                            is gone — the field was retired from the
                            model.
        - department      : TechStack-only (usage_departments, "the
                            department USING the tool"). None for
                            Pain / Objective — source_department was
                            retired from BaseSignal and no
                            replacement is provided at this layer.
                            If a deeper department surface is needed
                            for Pain or Objective later, derive it
                            from related ImpactSignal data or
                            target_department (Objective) at the call
                            site.

        Args:
            queryset: Any QuerySet of a concrete signal model.
                      The corresponding entry in _RELATED_BY_TYPE should
                      already be applied via select_related at the
                      caller (or use get_by_account to get an optimised
                      queryset for free).

        Returns:
            List of dicts, one per signal. Empty list if queryset is empty.
        """
        result = []

        for signal in queryset:
            is_tech_stack = isinstance(signal, TechStackSignal)

            # ---- Category ----
            # TechStack has no signal_category (shadow-override).
            category = None if is_tech_stack else signal.signal_category

            # ---- Contact name ----
            contact_name = cls._extract_contact_name(signal, is_tech_stack)

            # ---- Department display ----
            department_name = cls._extract_department_name(signal, is_tech_stack)

            # ---- Summary text ----
            summary = cls._extract_summary(signal, is_tech_stack)

            # ---- Validated date ----
            date_str = None
            if signal.validated_at:
                date_str = signal.validated_at.strftime('%Y-%m-%d')

            result.append({
                'type':       signal.__class__.__name__,
                'category':   category,
                'summary':    summary,
                'contact':    contact_name,
                'department': department_name,
                'confirmed':  1,
                'date':       date_str,
            })

        return result

    # =========================================================================
    # PRIVATE HELPERS — format_for_llm
    # =========================================================================

    @staticmethod
    def _extract_contact_name(signal, is_tech_stack: bool):
        """
        Resolve a contact display name for the LLM payload.

        Uniform across all signal types (Pain / Objective / TechStack):
        first contact of source_activity, or None if the activity is
        unset or has no contacts.

        Standardisation refactor note:
          The previous Pain / Objective path read signal.source_contact
          directly; the field was retired from BaseSignal during the
          standardisation refactor. All types now share the activity-
          derived path — same code surface as the cluster service and
          the standardised `source_context` block on the serializers.

        The `is_tech_stack` flag is kept in the signature for caller
        symmetry with _extract_department_name and _extract_summary,
        but it is no longer consulted here.
        """
        # Unused param kept for caller-symmetry (see docstring).
        del is_tech_stack

        if not signal.source_activity_id or not signal.source_activity:
            return None
        try:
            # source_activity.contacts is m2m; we take the first for a
            # compact LLM display, not an authoritative representation.
            # The Pre-Call Game Plan pipeline can always re-fetch full
            # activity details when needed.
            first_contact = signal.source_activity.contacts.first()
        except Exception:
            return None
        if not first_contact:
            return None
        return SignalDataService._format_contact_name(first_contact)

    @staticmethod
    def _format_contact_name(contact):
        """Resolve 'first_name last_name' or None."""
        name = (
            f"{getattr(contact, 'first_name', '') or ''} "
            f"{getattr(contact, 'last_name', '') or ''}"
        ).strip()
        return name or None

    @staticmethod
    def _extract_department_name(signal, is_tech_stack: bool):
        """
        Resolve a department display name for the LLM payload.

        TechStack:           usage_departments — the department(s) USING
                             the tool (multi-department M2M). Reads every
                             designated department and joins their display
                             names with ", " so the single "department"
                             string in the payload reflects the full set
                             (mono -> multi kept in the same key shape:
                             "Marketing", or "Sales, Marketing", or None
                             when no department is designated).
        Pain / Objective:    None. source_department was retired from
                             BaseSignal during the standardisation
                             refactor and no replacement is provided
                             at this layer. If a deeper department
                             surface is needed, derive it from
                             related ImpactSignal data or
                             target_department (Objective) at the call
                             site, not here.

        Reads signal.usage_departments.all(); callers preload it via
        _PREFETCH_BY_TYPE so this stays N+1-safe.
        """
        if not is_tech_stack:
            return None

        names = [
            d.get_name_display() if hasattr(d, 'get_name_display') else str(d)
            for d in signal.usage_departments.all()
        ]
        if not names:
            return None

        return ', '.join(names)

    @staticmethod
    def _extract_summary(signal, is_tech_stack: bool):
        """
        Resolve the summary text shown to the LLM.

        Pain / Objective : `summary` field.
        TechStack        : `tech_name` (the raw tool name as observed),
                           optionally suffixed with notes when set.

                           S10: this used to compose
                           "<company> <product>" from the catalogue FK.
                           The extractor no longer populates that FK, so
                           reading it would return '' on every extracted
                           signal and blank the tool name out of every
                           LLM-facing payload built from this service.
        """
        if is_tech_stack:
            parts = []
            tool_label = (getattr(signal, 'tech_name', '') or '').strip()
            if tool_label:
                parts.append(tool_label)
            notes = (getattr(signal, 'notes', '') or '').strip()
            if notes:
                parts.append(notes)
            return ' — '.join(parts) if parts else ''

        # Non-TechStack path — same fallback chain as before.
        return (
            getattr(signal, 'summary', None)
            or getattr(signal, 'notes', None)
            or ''
        )