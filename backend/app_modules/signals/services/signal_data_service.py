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
"""

from core.exceptions import StandardizedValidationError
from core.error_messages import SignalErrorMessages

from ..constants import SignalStatus
from ..models import PeopleSignal, PainSignal, ObjectiveSignal, TechStackSignal


# Mapping from string key → model class.
_SIGNAL_TYPE_MAP = {
    'people':     PeopleSignal,
    'pain':       PainSignal,
    'objective':  ObjectiveSignal,
    'tech_stack': TechStackSignal,
}

# select_related paths shared across all signal types.
_BASE_RELATED = [
    'source_contact',
    'source_department',
    'validated_by',
    'decision_cycle',
    'campaign',
]

# Extra select_related per model type.
_EXTRA_RELATED = {
    'people':    ['target_contact', 'target_department'],
    'pain':      ['impacted_department'],
    'objective': ['target_contact', 'target_department'],
    'tech_stack': [],
}

# Allowlist of filters accepted by get_by_account.
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
            signal_type: 'people' | 'pain' | 'objective' | 'tech_stack' | None.
                         None returns all 4 types.
            status:      SignalStatus value to filter by (e.g. 'VALIDATED').
                         None applies no status filter.
            **filters:   Additional ORM filters (allowlisted).
                         Supported: signal_category, source_department,
                                    source, is_inferred.

        Returns:
            If signal_type given → single QuerySet for that model.
            If signal_type None  → dict with keys 'people', 'pain',
                                   'objective', 'tech_stack'.

        Raises:
            StandardizedValidationError if signal_type is invalid.
        """
        safe_filters = {k: v for k, v in filters.items() if k in _ALLOWED_FILTERS}

        def _build_qs(type_key, model_class):
            related = _BASE_RELATED + _EXTRA_RELATED.get(type_key, [])
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
            dict with keys 'people', 'pain', 'objective', 'tech_stack'.
        """
        return {
            key: model_class.objects
                .filter(source_contact_id=contact_id)
                .select_related(*(_BASE_RELATED + _EXTRA_RELATED.get(key, [])))
            for key, model_class in _SIGNAL_TYPE_MAP.items()
        }

    # =========================================================================
    # GET BY CYCLE
    # =========================================================================

    @classmethod
    def get_by_cycle(cls, cycle_id) -> dict:
        """
        Return all signals associated with a decision cycle, across all types.

        Args:
            cycle_id: UUID of the decision cycle.

        Returns:
            dict with keys 'people', 'pain', 'objective', 'tech_stack'.
        """
        return {
            key: model_class.objects
                .filter(decision_cycle_id=cycle_id)
                .select_related(*(_BASE_RELATED + _EXTRA_RELATED.get(key, [])))
            for key, model_class in _SIGNAL_TYPE_MAP.items()
        }

    # =========================================================================
    # FORMAT FOR LLM
    # =========================================================================

    @classmethod
    def format_for_llm(cls, queryset) -> list:
        """
        Format a signal queryset into a compact list for LLM prompt injection.

        Strips all technical identifiers and retains only fields meaningful
        to the LLM. Stateless — does not call CorroborationService.

        Output format per signal:
        {
            "type":       "PeopleSignal",
            "category":   "ECONOMIC",
            "summary":    "...",        # first meaningful text field found
            "contact":    "Jane Doe",   # source_contact full name or None
            "department": "IT",         # source_department display or None
            "confirmed":  1,            # always 1 in MVP for non-People types
            "date":       "2025-03-15"  # validated_at date or None
        }

        Args:
            queryset: Any QuerySet of a concrete signal model.
                      select_related('source_contact', 'source_department',
                      'validated_by') should already be applied.

        Returns:
            List of dicts, one per signal. Empty list if queryset is empty.
        """
        result = []

        for signal in queryset:
            # Contact full name
            contact_name = None
            if signal.source_contact_id and signal.source_contact:
                contact = signal.source_contact
                contact_name = (
                    f"{getattr(contact, 'first_name', '') or ''} "
                    f"{getattr(contact, 'last_name', '') or ''}"
                ).strip() or None

            # Department display name
            department_name = None
            if signal.source_department_id and signal.source_department:
                dept = signal.source_department
                department_name = (
                    dept.get_name_display()
                    if hasattr(dept, 'get_name_display')
                    else str(dept)
                )

            # Validated date as ISO date string
            date_str = None
            if signal.validated_at:
                date_str = signal.validated_at.strftime('%Y-%m-%d')

            # First meaningful text field depending on model type
            summary = (
                getattr(signal, 'summary', None)
                or getattr(signal, 'tech_name', None)
                or getattr(signal, 'notes', None)
                or ''
            )

            result.append({
                'type':       signal.__class__.__name__,
                'category':   signal.signal_category,
                'summary':    summary,
                'contact':    contact_name,
                'department': department_name,
                'confirmed':  1,
                'date':       date_str,
            })

        return result