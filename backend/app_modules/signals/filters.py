# app_modules/signals/filters.py
"""
FilterSet for the Signals module.

Follows ActivityFilter patterns:
  - CharInFilter for comma-separated multi-value choice fields.
  - UUIDFilter for FK relations.
  - BooleanFilter for flags.

Applied to both QualificationSignal and TechStackSignal querysets
via the view's filterset_class.
"""

import django_filters
from django_filters import BaseInFilter, CharFilter, UUIDFilter

from .models import QualificationSignal


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter accepting comma-separated string values.
    Example: ?status=PENDING,VALIDATED → status__in=['PENDING', 'VALIDATED']
    """
    pass


class SignalFilter(django_filters.FilterSet):
    """
    FilterSet shared across QualificationSignal and TechStackSignal.

    Multi-value filters (comma-separated):
      status, source, signal_category

    UUID filters:
      account, source_contact, source_department, decision_cycle, campaign

    Boolean filters:
      is_superseded, is_inferred
    """

    # -------------------------------------------------------------------------
    # MULTI-VALUE (comma-separated choices)
    # -------------------------------------------------------------------------
    status          = CharInFilter(field_name='status',          lookup_expr='in')
    source          = CharInFilter(field_name='source',          lookup_expr='in')
    signal_category = CharInFilter(field_name='signal_category', lookup_expr='in')

    # -------------------------------------------------------------------------
    # SINGLE FK — UUID
    # -------------------------------------------------------------------------
    account           = UUIDFilter(field_name='account_id')
    source_contact    = UUIDFilter(field_name='source_contact_id')
    source_department = UUIDFilter(field_name='source_department_id')
    decision_cycle    = UUIDFilter(field_name='decision_cycle_id')
    campaign          = UUIDFilter(field_name='campaign_id')

    # -------------------------------------------------------------------------
    # BOOLEAN FLAGS
    # -------------------------------------------------------------------------
    is_superseded = django_filters.BooleanFilter(field_name='is_superseded')
    is_inferred   = django_filters.BooleanFilter(field_name='is_inferred')

    class Meta:
        # Model is set to QualificationSignal as a reference — the view applies
        # this FilterSet to both QualificationSignal and TechStackSignal querysets
        # since all filter fields exist on BaseSignal.
        model  = QualificationSignal
        fields = [
            'status', 'source', 'signal_category',
            'account', 'source_contact', 'source_department',
            'decision_cycle', 'campaign',
            'is_superseded', 'is_inferred',
        ]