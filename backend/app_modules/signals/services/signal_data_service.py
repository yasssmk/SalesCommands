# app_modules/signals/services/signal_data_service.py
"""
SignalDataService — read-only signal queries.

Provides optimised querysets and LLM-ready formatting.
No state mutation here — all writes go through SignalManager.

Public API:
  get_by_account(account_id, signal_type, status, **filters)
  get_by_contact(contact_id)
  get_by_cycle(cycle_id)
  format_for_llm(queryset)
"""

from ..constants import SignalStatus
from ..models import QualificationSignal, TechStackSignal


# Mapping from string key → model class, used by get_by_account.
_SIGNAL_TYPE_MAP = {
    'qualification': QualificationSignal,
    'tech_stack':    TechStackSignal,
}

# select_related paths shared across all public query methods.
_BASE_RELATED = [
    'source_contact',
    'source_department',
    'validated_by',
    'merged_into',
    'decision_cycle',
    'campaign',
]


class SignalDataService:
    """
    Stateless read service for signal data retrieval and formatting.

    All methods are classmethods — no instance needed.
    No writes, no business logic — pure query + formatting.
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
            signal_type: 'qualification' | 'tech_stack' | None (both).
            status:      SignalStatus value to filter by (e.g. 'VALIDATED').
                         Accepts None (no status filter).
            **filters:   Additional ORM filters applied to all querysets.
                         Supported keys: signal_category, source_department,
                         source, is_superseded.

        Returns:
            If signal_type is given → single QuerySet for that model.
            If signal_type is None  → list of two QuerySets
                                      [qualification_qs, tech_stack_qs].

        Notes:
            Callers that need a single iterable from both types should
            iterate over each queryset in the returned list. Django does not
            support cross-table union with heterogeneous models in a single
            QuerySet without raw SQL — returning separate querysets is the
            correct approach for this architecture.
        """
        # Allowlist of filters to prevent arbitrary field injection
        _allowed_filters = {
            'signal_category',
            'source_department',
            'source',
            'is_superseded',
        }
        safe_filters = {k: v for k, v in filters.items() if k in _allowed_filters}

        def _build_qs(model_class):
            qs = model_class.objects.filter(
                account_id=account_id
            ).select_related(*_BASE_RELATED)

            if status:
                qs = qs.filter(status=status)

            if safe_filters:
                qs = qs.filter(**safe_filters)

            return qs

        if signal_type:
            model_class = _SIGNAL_TYPE_MAP.get(signal_type)
            if not model_class:
                from core.exceptions import StandardizedValidationError
                from core.error_messages import CoreErrorMessages
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='signal_type')
                )
            return _build_qs(model_class)

        # Both types — return list of querysets
        return [
            _build_qs(QualificationSignal),
            _build_qs(TechStackSignal),
        ]

    # =========================================================================
    # GET BY CONTACT
    # =========================================================================

    @classmethod
    def get_by_contact(cls, contact_id):
        """
        Return all signals where source_contact matches, across all types.

        Args:
            contact_id: UUID of the contact.

        Returns:
            dict with keys 'qualification' and 'tech_stack',
            each holding the corresponding QuerySet.
        """
        kwargs = {'source_contact_id': contact_id}
        return {
            'qualification': QualificationSignal.objects.filter(
                **kwargs
            ).select_related(*_BASE_RELATED),
            'tech_stack': TechStackSignal.objects.filter(
                **kwargs
            ).select_related(*_BASE_RELATED),
        }

    # =========================================================================
    # GET BY CYCLE
    # =========================================================================

    @classmethod
    def get_by_cycle(cls, cycle_id):
        """
        Return all signals associated with a decision cycle, across all types.

        Args:
            cycle_id: UUID of the decision cycle.

        Returns:
            dict with keys 'qualification' and 'tech_stack',
            each holding the corresponding QuerySet.
        """
        kwargs = {'decision_cycle_id': cycle_id}
        return {
            'qualification': QualificationSignal.objects.filter(
                **kwargs
            ).select_related(*_BASE_RELATED),
            'tech_stack': TechStackSignal.objects.filter(
                **kwargs
            ).select_related(*_BASE_RELATED),
        }

    # =========================================================================
    # FORMAT FOR LLM
    # =========================================================================

    @classmethod
    def format_for_llm(cls, queryset) -> list:
        """
        Format a signal queryset into a compact list for LLM prompt injection.

        Strips all technical identifiers (id, FK ids) and retains only
        the fields meaningful to the model:

        Output format per signal:
        {
            "field":     "pain_point",
            "value":     "...",
            "category":  "ECONOMIC",
            "contact":   "CTO",          # full name or None
            "department": "IT",          # department display name or None
            "confirmed": 2,              # confirmation_count
            "date":      "2025-03-15"    # last_confirmed_at date
        }

        Args:
            queryset: Any QuerySet of QualificationSignal or TechStackSignal.
                      select_related('source_contact', 'source_department')
                      should already be applied for performance.

        Returns:
            List of dicts, one per signal. Empty list if queryset is empty.
        """
        result = []

        for signal in queryset:
            # Contact full name — None if no contact linked
            contact_name = None
            if signal.source_contact_id and signal.source_contact:
                contact = signal.source_contact
                contact_name = (
                    f"{getattr(contact, 'first_name', '') or ''} "
                    f"{getattr(contact, 'last_name', '') or ''}"
                ).strip() or None

            # Department display name — None if no department linked
            department_name = None
            if signal.source_department_id and signal.source_department:
                dept = signal.source_department
                # StandardDepartment exposes get_name_display()
                department_name = (
                    dept.get_name_display()
                    if hasattr(dept, 'get_name_display')
                    else str(dept)
                )

            # Date as ISO date string (date only, not datetime)
            date_str = None
            if signal.last_confirmed_at:
                date_str = signal.last_confirmed_at.strftime('%Y-%m-%d')

            result.append({
                'field':      signal.field_name,
                'value':      signal.value,
                'category':   signal.signal_category,
                'contact':    contact_name,
                'department': department_name,
                'confirmed':  signal.confirmation_count,
                'date':       date_str,
            })

        return result