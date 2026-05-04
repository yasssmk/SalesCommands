# app_modules/signals/services/signal_data_service.py
"""
SignalDataService — read-only signal queries and LLM formatting.

Provides optimised querysets for all 4 signal types and compact
LLM-ready formatting. No state mutation — all writes go through
SignalManager.

Public API:
  get_by_account(account_id, signal_type, status, **filters)
  get_by_contact(contact_id)
  get_by_cycle(cycle_id)
  format_for_llm(queryset)

Sprint TechStack notes
----------------------
TechStackSignal shadow-overrides 5 inherited BaseSignal fields:
  source_contact, source_department, decision_cycle, campaign,
  signal_category.

The previous shared `_BASE_RELATED` list assumed all signal types
carry the full BaseSignal field set — it broke silently (or loudly)
on TechStack. We now keep an EXPLICIT per-type select_related list in
_RELATED_BY_TYPE to make the model's narrow surface visible at the
call site.

Likewise, get_by_contact and get_by_cycle now route TechStack queries
via source_activity (the only deal/contact context TechStack carries
indirectly):
  - get_by_contact: TechStack signals are matched by
    source_activity__contacts (contacts who PARTICIPATED in the
    activity), not by source_contact.
  - get_by_cycle:   TechStack signals are matched by
    source_activity__decision_cycle, not by decision_cycle.
This mirrors the cluster service's filtering strategy (Phase 6.2).
"""
from core.exceptions import StandardizedValidationError
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus
from ..models import PainSignal, ObjectiveSignal, TechStackSignal


# Mapping from string key → model class.
_SIGNAL_TYPE_MAP = {
    'pain':       PainSignal,
    'objective':  ObjectiveSignal,
    'tech_stack': TechStackSignal,
}

# select_related paths PER signal type.
#
# Sprint TechStack: we replaced the legacy _BASE_RELATED + _EXTRA_RELATED
# split with a single explicit per-type list. The previous _BASE_RELATED
# silently assumed every signal carries source_contact / source_department
# / decision_cycle / campaign — false on TechStack since the catalog-FK
# refactor (those fields are shadow-overridden to None on the model).
#
# Each list contains only FKs that ACTUALLY exist on the concrete model.
# Extending this dict is the single point of truth when a model gains or
# loses a relation that benefits from select_related preloading.
_RELATED_BY_TYPE = {
    'pain': [
        'source_contact',
        'source_department',
        'validated_by',
        'decision_cycle',
        'campaign',
        # PainSignal does not declare impacted_department on the model
        # itself — it lives on PainImpact (see PainImpact model). The
        # legacy _EXTRA_RELATED['pain'] = ['impacted_department'] was
        # therefore inert. Removed here for accuracy.
        # Cross-reference TechCatalog (Sprint TechStack):
        'related_techstack',
    ],
    'objective': [
        'source_contact',
        'source_department',
        'validated_by',
        'decision_cycle',
        'campaign',
        'target_contact',
        'target_department',
    ],
    # TechStackSignal narrow surface — shadow-overrides remove
    # source_contact, source_department, decision_cycle, campaign, and
    # signal_category. Only validated_by survives from the audit set.
    'tech_stack': [
        'validated_by',
        'source_activity',     # Used as deal/contact-context join path.
        'tech_catalog_entry',  # Drives canonical_key + display payload.
        'usage_department',    # Often null but cheap to prefetch.
    ],
}

# Allowlist of filters accepted by get_by_account.
#
# Note on cross-type validity:
#   - 'signal_category' and 'source_department' do NOT exist on
#     TechStackSignal (shadow-overridden). Passing them with
#     signal_type='tech_stack' will raise a FieldError. This is by
#     design — the allowlist is generic, model surface enforces what
#     applies. Callers must respect each model's documented surface.
_ALLOWED_FILTERS = {
    'signal_category',
    'source_department',
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
            signal_type: 'pain' | 'objective' | 'tech_stack' | None.
                         None returns all 3 types.
            status:      SignalStatus value to filter by (e.g. 'VALIDATED').
                         None applies no status filter.
            **filters:   Additional ORM filters (allowlisted).
                         Supported: signal_category, source_department,
                                    source, is_inferred.

        Returns:
            If signal_type given → single QuerySet for that model.
            If signal_type None  → dict with keys 'pain', 'objective',
                                   'tech_stack'.

        Raises:
            StandardizedValidationError if signal_type is invalid.

        Sprint TechStack note:
          Passing signal_category / source_department in filters with
          signal_type='tech_stack' will raise a FieldError. Those fields
          do not exist on TechStackSignal — see _RELATED_BY_TYPE
          docstring for the full list of shadow-overridden fields.
          Callers querying TechStack should restrict themselves to
          'source' and 'is_inferred' filters.
        """

        safe_filters = {k: v for k, v in filters.items() if k in _ALLOWED_FILTERS}

        def _build_qs(type_key, model_class):
            related = _RELATED_BY_TYPE.get(type_key, [])
            qs = (
                model_class.objects
                .filter(account_id=account_id)
                .select_related(*related)
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
        Return all signals where source_contact matches, across all types.

        Args:
            contact_id: UUID of the contact.

        Returns:
            dict with keys 'pain', 'objective', 'tech_stack'.

        TechStack semantics
        -------------------
        TechStackSignal has no source_contact FK (shadow-overridden —
        a tool's existence at an account is account-level, not
        per-contact). For TechStack, this method matches signals where
        the source Activity included the given contact:

            source_activity__contacts__id = contact_id

        Semantic shift:
          Pain / Objective → "this contact REPORTED the signal"
          TechStack        → "this contact PARTICIPATED in a
                              conversation where the tool was
                              mentioned"

        Both are useful for the question "what does this contact know
        about?" — the per-type semantics simply reflect each model's
        relationship to its origin.
        """
        result = {}
        for key, model_class in _SIGNAL_TYPE_MAP.items():
            related = _RELATED_BY_TYPE.get(key, [])
            if key == 'tech_stack':
                # No source_contact FK on TechStack — traverse
                # source_activity.contacts instead. distinct() is needed
                # because the JOIN on the m2m yields one row per contact
                # match (which is fine here — there's only one filter
                # value — but stays defensive in case the helper is
                # later called with multi-value filtering).
                qs = (
                    model_class.objects
                    .filter(source_activity__contacts__id=contact_id)
                    .select_related(*related)
                    .distinct()
                )
            else:
                qs = (
                    model_class.objects
                    .filter(source_contact_id=contact_id)
                    .select_related(*related)
                )
            result[key] = qs
        return result

    # =========================================================================
    # GET BY CYCLE
    # =========================================================================

    @classmethod
    @classmethod
    def get_by_cycle(cls, cycle_id) -> dict:
        """
        Return all signals associated with a decision cycle, across all types.

        Args:
            cycle_id: UUID of the decision cycle.

        Returns:
            dict with keys 'pain', 'objective', 'tech_stack'.

        TechStack semantics
        -------------------
        TechStackSignal has no decision_cycle FK (shadow-overridden —
        a tool's existence at an account is account-level, not
        deal-level). For TechStack, this method matches signals where
        the source Activity belongs to the given decision cycle:

            source_activity__decision_cycle_id = cycle_id

        Mirror of the cluster service's filtering strategy — see
        SignalClusterService._fetch_techstack_signals (Phase 6.2)
        for the same join path.

        Signals with source_activity=NULL are excluded for TechStack
        when filtering by cycle (no Activity → no DC context to match
        on). This matches the INNER JOIN semantics through nullable FKs.
        """
        result = {}
        for key, model_class in _SIGNAL_TYPE_MAP.items():
            related = _RELATED_BY_TYPE.get(key, [])
            if key == 'tech_stack':
                # No direct decision_cycle FK on TechStack — traverse
                # source_activity.decision_cycle instead. Same strategy
                # as SignalClusterService Phase 6.2.
                qs = (
                    model_class.objects
                    .filter(source_activity__decision_cycle_id=cycle_id)
                    .select_related(*related)
                )
            else:
                qs = (
                    model_class.objects
                    .filter(decision_cycle_id=cycle_id)
                    .select_related(*related)
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
        to the LLM. Stateless — does not call CorroborationService.

        Output format per signal (common across all 4 types):
        {
            "type":       "PeopleSignal",  # class name for LLM disambiguation
            "category":   "ECONOMIC",       # signal_category or None for TechStack
            "summary":    "...",            # type-appropriate text excerpt
            "contact":    "Jane Doe",       # source_contact OR (for TechStack)
                                            # first activity contact, or None
            "department": "IT",             # source_department OR (for TechStack)
                                            # usage_department, or None
            "confirmed":  1,                # always 1 in MVP for non-People types
            "date":       "2025-03-15"      # validated_at date or None
        }

        Sprint TechStack changes
        ------------------------
        TechStackSignal has shadow-overridden source_contact,
        source_department, signal_category. The legacy implementation
        accessed these unconditionally and broke when iterating over
        TechStack. This method now branches per-type to safely emit
        the same shape:

          - signal_category : None for TechStack (no such field)
          - summary         : tech_catalog_entry display + notes for
                              TechStack instead of looking for a
                              non-existent `tech_name` attribute
          - contact         : first contact of source_activity for
                              TechStack (when set), else None
          - department      : usage_department for TechStack (when set),
                              else None — note this is "department
                              USING the tool", not "department who
                              MENTIONED the tool"

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

        Pain / Objective / People: source_contact.
        TechStack:                  first contact of source_activity
                                    (best-effort — the activity's
                                    participants are the closest
                                    "who reported this" approximation
                                    available given the shadow-override).
        """
        if is_tech_stack:
            if not signal.source_activity_id or not signal.source_activity:
                return None
            try:
                # source_activity.contacts is m2m; we take the first
                # for a compact LLM display, not an authoritative
                # representation. The Pre-Call Game Plan pipeline can
                # always re-fetch full activity details when needed.
                first_contact = signal.source_activity.contacts.first()
            except Exception:
                return None
            if not first_contact:
                return None
            return SignalDataService._format_contact_name(first_contact)

        # Non-TechStack path — direct source_contact FK.
        if not signal.source_contact_id:
            return None
        contact = signal.source_contact
        if not contact:
            return None
        return SignalDataService._format_contact_name(contact)

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

        Pain / Objective / People: source_department.
        TechStack:                  usage_department — note semantic
                                    shift: "department USING the tool"
                                    rather than "department who
                                    MENTIONED it". This is the most
                                    informative department available
                                    for TechStack.
        """
        if is_tech_stack:
            if not signal.usage_department_id:
                return None
            dept = signal.usage_department
        else:
            if not signal.source_department_id:
                return None
            dept = signal.source_department

        if not dept:
            return None

        return (
            dept.get_name_display()
            if hasattr(dept, 'get_name_display')
            else str(dept)
        )

    @staticmethod
    def _extract_summary(signal, is_tech_stack: bool):
        """
        Resolve the summary text shown to the LLM.

        Pain / Objective : `summary` field.
        People           : falls back to `notes` (no canonical summary
                           field on PeopleSignal).
        TechStack        : "<company> <product>" from tech_catalog_entry,
                           optionally suffixed with notes when set.
                           Replaces the legacy `tech_name` lookup that
                           became obsolete with the catalog FK refactor.
        """
        if is_tech_stack:
            parts = []
            entry = signal.tech_catalog_entry if signal.tech_catalog_entry_id else None
            if entry:
                tool_label = (
                    f"{entry.company_name or ''} "
                    f"{entry.product_name or ''}"
                ).strip()
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