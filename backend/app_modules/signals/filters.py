# app_modules/signals/filters.py
"""
FilterSet for the Signals module.

Shared across all 3 concrete signal types (Pain, Objective, TechStack) —
the view's filter_queryset() dynamically binds SignalFilter.Meta.model to
the concrete queryset model before django-filters runs its assertion check.

Type-specific filters (what, dimension, scope_level, tech_catalog_entry,
etc.) that do not exist on a given model are silently harmless — django-filter
ignores unknown field lookups via the dynamic model binding. This is the
established pattern in this codebase.

PainImpact is NOT handled here. It has its own PainImpactFilter defined in
views/pain_impact_views.py, since impacts are a distinct resource with a
separate CRUD surface (/pain-impacts/).

Sprint TechStack — filter changes:
  REMOVED:
    - category     (TechCategory enum dropped — categorisation moved to TechCatalog)
    - satisfaction (Satisfaction enum dropped — replaced by structured lifecycle)
  ADDED (TechStackSignal):
    - tech_catalog_entry      (UUID — anchor by catalog entry)
    - usage_scope             (CSV — TEAM, DEPARTMENT, COMPANY, UNKNOWN)
    - usage_department        (UUID — department using the tool)
    - is_discontinued         (bool)
    - renewal_date_after      (date >= filter)
    - renewal_date_before     (date <= filter)
    - is_competitor           (bool, via FK traversal to TechCatalog)
    - is_integration_target   (bool, via FK traversal to TechCatalog)
  ADDED (PainSignal cross-reference):
    - related_techstack       (UUID — Pains cross-referencing a catalog entry)

Sprint 2 — filter changes (PeopleSignal sunset):
  REMOVED:
    - role            (PeopleRole enum dropped along with PeopleSignal)
    - influence_level (InfluenceLevel enum dropped along with PeopleSignal)
"""

import django_filters
from django_filters import BaseInFilter, BooleanFilter, CharFilter, DateFilter, UUIDFilter

from .models import PainSignal


class CharInFilter(BaseInFilter, CharFilter):
    """
    Filter accepting comma-separated string values.
    Example: ?status=PENDING,VALIDATED → status__in=['PENDING', 'VALIDATED']
    """
    pass


class SignalFilter(django_filters.FilterSet):
    """
    FilterSet shared across PainSignal, ObjectiveSignal, and TechStackSignal.

    Base filters (all signal types — fields live on BaseSignal):
      status, source, signal_category
      account, source_contact, source_activity, source_department,
      decision_cycle, campaign
      canonical_key

    Type-specific filters (silently ignored when field absent on model):
      what, dimension — PainSignal + ObjectiveSignal (shared canonical
                        axes since Wave A)
      scope_level     — ObjectiveSignal (Wave B — renamed from goal_level)

    Silently-absent fields on ObjectiveSignal (Wave B):
      - signal_category is shadow-overridden to None on the concrete
        ObjectiveSignal model. The `signal_category` filter declared
        here still works for Pain / TechStack; on Objective querysets,
        django-filters finds no matching field and falls back to a
        no-op (tolerated via the dynamic Meta.model rebinding in
        BaseSignalViewSet.filter_queryset()). No behavioural change
        needed here.

    Note — Pain-side fields removed in Sprint 1.6:
      pain_level, human_impact, impacted_contact no longer exist on
      PainSignal. Impact-level data now lives on PainImpact and is
      filterable through PainImpactFilter (see views/pain_impact_views.py).

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
    # TYPE-SPECIFIC — PainSignal (canonical axes only)
    # -------------------------------------------------------------------------

    what      = CharInFilter(field_name='what',      lookup_expr='in')
    dimension = CharInFilter(field_name='dimension', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — ObjectiveSignal
    # -------------------------------------------------------------------------

    scope_level = CharInFilter(field_name='scope_level', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — TechStackSignal
    # -------------------------------------------------------------------------

    category     = CharInFilter(field_name='category',     lookup_expr='in')
    satisfaction = CharInFilter(field_name='satisfaction', lookup_expr='in')

    class Meta:
        # PainSignal used as the reference model — chosen for stability:
        # it is the structural pivot of the cluster system and not slated
        # for removal. The reference model is only used to satisfy
        # django-filter's class-definition check; the view's
        # `filter_queryset()` rebinds Meta.model to the actual concrete
        # model before any filtering runs.
        #
        # `fields` is intentionally EMPTY:
        #   * Every filter in this FilterSet is declared explicitly as a
        #     class attribute above (UUIDFilter, CharInFilter, BooleanFilter,
        #     DateFilter, etc.).
        #   * `Meta.fields` is only used by django-filter to AUTO-GENERATE
        #     filters for model fields not declared explicitly. We do not
        #     want any auto-generation — we want full control over each
        #     filter's lookup_expr and field_name.
        #   * Listing field names in `Meta.fields` also triggers a
        #     model-presence check at class-definition time. Since this
        #     FilterSet is shared across multiple concrete signal models
        #     with overlapping but non-identical field sets, no single
        #     reference model would satisfy the check — hence the empty
        #     list.
        #
        # The dynamic Meta.model rebind in BaseSignalViewSet.filter_queryset()
        # ensures the FilterSet correctly targets the concrete model at
        # query time. Filters whose field_name does not resolve on the
        # actual queryset model are silently no-op, which is the desired
        # cross-type behaviour.
        model  = PainSignal
        fields = []