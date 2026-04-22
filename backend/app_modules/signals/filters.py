# app_modules/signals/filters.py
"""
FilterSet for the Signals module.

Shared across all 4 signal types — the view's filter_queryset() dynamically
binds SignalFilter.Meta.model to the concrete queryset model before
django-filters runs its assertion check.

Type-specific filters (role, pain_level, etc.) that do not exist on a given
model are silently harmless — Django filter ignores unknown field lookups
via the dynamic binding. This is the established pattern in this codebase.
"""

import django_filters
from django_filters import BaseInFilter, CharFilter, UUIDFilter

from .models import PeopleSignal


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter accepting comma-separated string values.
    Example: ?status=PENDING,VALIDATED → status__in=['PENDING', 'VALIDATED']
    """
    pass


class SignalFilter(django_filters.FilterSet):
    """
    FilterSet shared across PeopleSignal, PainSignal, ObjectiveSignal,
    and TechStackSignal.

    Base filters (all signal types — fields live on BaseSignal):
      status, source, signal_category
      account, source_contact, source_activity, source_department,
      decision_cycle, campaign
      canonical_key

    Type-specific filters (silently ignored when field absent on model):
      role, influence_level         — PeopleSignal
      what, dimension, human_impact — PainSignal (canonical + orthogonal axes)
      pain_level                    — PainSignal
      category                      — TechStackSignal (PainCategory removed
                                       — this filter key now applies to
                                       TechStackSignal only)
      goal_level                    — ObjectiveSignal
      satisfaction                  — TechStackSignal

    Note:
      When the refactored SignalClusterService (Sprint 2) groups Pain signals
      by canonical_key, callers can also filter directly by what/dimension
      to narrow cluster lookups.
    """

    # -------------------------------------------------------------------------
    # BASE — all signal types
    # -------------------------------------------------------------------------

    status          = CharInFilter(field_name='status',          lookup_expr='in')
    source          = CharInFilter(field_name='source',          lookup_expr='in')
    signal_category = CharInFilter(field_name='signal_category', lookup_expr='in')

    # canonical_key uses the shared CharInFilter (comma-separated list).
    # This is safe for the current canonical schemas which never contain
    # commas:
    #     "pain:OPS:TIME"
    #     "people:<uuid>:CHAMPION"
    # If a future signal type introduces commas inside canonical_key
    # (free-text matching, localized labels, etc.), switch this filter to an
    # exact CharFilter or implement a JSON/array-aware lookup — the comma
    # delimiter would otherwise split a legitimate key into two halves.
    canonical_key   = CharInFilter(field_name='canonical_key',   lookup_expr='in')

    account          = UUIDFilter(field_name='account_id')
    source_contact   = UUIDFilter(field_name='source_contact_id')
    source_activity  = UUIDFilter(field_name='source_activity_id')
    source_department = UUIDFilter(field_name='source_department_id')
    decision_cycle   = UUIDFilter(field_name='decision_cycle_id')
    campaign         = UUIDFilter(field_name='campaign_id')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — PeopleSignal
    # -------------------------------------------------------------------------

    role            = CharInFilter(field_name='role',            lookup_expr='in')
    influence_level = CharInFilter(field_name='influence_level', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — PainSignal (canonical + orthogonal axes)
    # -------------------------------------------------------------------------

    what         = CharInFilter(field_name='what',         lookup_expr='in')
    dimension    = CharInFilter(field_name='dimension',    lookup_expr='in')
    human_impact = CharInFilter(field_name='human_impact', lookup_expr='in')
    pain_level   = CharInFilter(field_name='pain_level',   lookup_expr='in')
    impacted_contact = UUIDFilter(field_name='impacted_contact_id')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — TechStackSignal
    # -------------------------------------------------------------------------

    category = CharInFilter(field_name='category', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — ObjectiveSignal
    # -------------------------------------------------------------------------

    goal_level = CharInFilter(field_name='goal_level', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — TechStackSignal
    # -------------------------------------------------------------------------

    satisfaction = CharInFilter(field_name='satisfaction', lookup_expr='in')

    class Meta:
        # PeopleSignal used as reference model — the view's filter_queryset()
        # rebinds Meta.model to the correct concrete model before the
        # django-filters assertion runs.
        model  = PeopleSignal
        fields = [
            # Base — all types
            'status', 'source', 'signal_category', 'canonical_key',
            'account', 'source_contact', 'source_activity',
            'source_department', 'decision_cycle', 'campaign',
            # PeopleSignal
            'role', 'influence_level',
            # PainSignal — canonical + orthogonal axes
            'what', 'dimension', 'human_impact',
            'pain_level', 'impacted_contact',
            # ObjectiveSignal
            'goal_level',
            # TechStackSignal
            'category', 'satisfaction',
        ]