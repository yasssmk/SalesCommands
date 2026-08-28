# app_modules/signals/filters.py
"""
FilterSet for the Signals module.

Shared across all 4 concrete signal types (Pain, Objective, Impact,
TechStack) — the view's filter_queryset() dynamically binds
SignalFilter.Meta.model to the concrete queryset model before
django-filters runs its assertion check.

Type-specific filters (what, dimension, scope_level, impact_type,
human_impact, usage_scope, etc.) that do not exist on a given
model are silently harmless — django-filter ignores unknown field
lookups via the dynamic model binding. This is the established
pattern in this codebase.

Shared canonical axes (Pain + Objective + Impact):
  - what       (SignalWhat enum)
  - dimension  (SignalDimension enum)
  - scope_level (ScopeLevel enum — also on TechStack via usage_scope,
                 distinct concept)

Filter inventory by signal type
-------------------------------
  Pain:       what, dimension, scope_level
  Objective:  what, dimension, scope_level
  Impact:     what, dimension, scope_level, impact_type, human_impact
  TechStack:  tech_name_normalized, usage_scope, usage_departments,
              is_discontinued, renewal_date_*, is_competitor,
              is_integration_target

Universal:
  status, source, signal_category, account, source_activity,
  decision_cycle, campaign, canonical_key, source_contact
  (decision_cycle / campaign / signal_category are shadow-overridden
   to None on TechStack — those filters are no-op on TechStack
   querysets.)

Source contact resolution
-------------------------
`source_contact` traverses source_activity.contacts (m2m). The direct
source_contact_id FK was retired from BaseSignal during the
standardisation refactor — contacts who participated in the source
conversation remain queryable through the activity. API surface is
unchanged for callers — `?source_contact=<uuid>` keeps returning
signals associated with that contact, just resolved through a
different path.
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
    FilterSet shared across PainSignal, ObjectiveSignal, ImpactSignal,
    and TechStackSignal.

    Base filters (all signal types — fields live on BaseSignal):
      status, source, signal_category
      account, source_activity, decision_cycle, campaign
      canonical_key

    Derived filters (traverse source_activity to reach related entities):
      source_contact — filters via source_activity.contacts (m2m).
                       Returns signals whose source_activity has the
                       given contact as a participant. Replaces the
                       previous direct source_contact_id FK filter
                       (the field was retired during the standardisation
                       refactor). API surface unchanged.

    Type-specific filters (silently ignored when field absent on model):
      what, dimension — PainSignal + ObjectiveSignal + ImpactSignal
                        (shared canonical axes)
      scope_level     — ObjectiveSignal

    Silently-absent fields on ObjectiveSignal:
      - signal_category is shadow-overridden to None on the concrete
        ObjectiveSignal model. The `signal_category` filter declared
        here still works for Pain / TechStack; on Objective querysets,
        django-filters finds no matching field and falls back to a
        no-op (tolerated via the dynamic Meta.model rebinding in
        BaseSignalViewSet.filter_queryset()). No behavioural change
        needed here.

    Silently-absent fields on TechStackSignal:
      - decision_cycle, campaign are shadow-overridden to None on the
        concrete TechStackSignal model (they are not deal-scoped — see
        the model docstring for the rationale). The `decision_cycle`
        and `campaign` filters declared here are silently no-op on
        TechStack querysets.

    Note:
      When SignalClusterService groups Pain signals by canonical_key,
      callers can also filter directly by what/dimension to narrow
      cluster lookups.
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
    # If a future signal type introduces commas inside canonical_key
    # (free-text matching, localized labels, etc.), switch this filter to an
    # exact CharFilter or implement a JSON/array-aware lookup — the comma
    # delimiter would otherwise split a legitimate key into two halves.
    canonical_key   = CharInFilter(field_name='canonical_key',   lookup_expr='in')

    account         = UUIDFilter(field_name='account_id')
    source_activity = UUIDFilter(field_name='source_activity_id')
    decision_cycle  = UUIDFilter(field_name='decision_cycle_id')
    campaign        = UUIDFilter(field_name='campaign_id')

    # source_contact — repointed during the standardisation refactor.
    # The direct source_contact_id FK was retired from BaseSignal. To
    # preserve API surface compatibility (?source_contact=<uuid> on the
    # signal listing endpoints), we now traverse source_activity.contacts
    # (m2m). distinct=True is required because a contact may appear on
    # multiple activities, which would otherwise duplicate signal rows
    # in the result set.
    #
    # Behaviour by signal type:
    #   - Pain        : source_activity is required → filter is exact.
    #   - Objective   : source_activity is optional → signals without
    #                   activity are excluded from the filtered set.
    #   - TechStack   : source_activity is optional → same.
    source_contact  = UUIDFilter(
        field_name='source_activity__contacts',
        distinct=True,
    )

   # -------------------------------------------------------------------------
    # CANONICAL AXES — shared by Pain, Objective, Impact
    # -------------------------------------------------------------------------
    #
    # what / dimension form the canonical_key for all three qualification
    # signal types. TechStack signals have no what/dimension axes
    # (TechStack is identified by tech_name instead) — these
    # filters are silently no-op on TechStack querysets.

    what      = CharInFilter(field_name='what',      lookup_expr='in')
    dimension = CharInFilter(field_name='dimension', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — ObjectiveSignal + ImpactSignal
    # -------------------------------------------------------------------------
    #
    # scope_level is shared between Objective and Impact — both store
    # the field directly on the model. Pain also stores scope_level
    # (PainSignal.scope_level, default=BUSINESS), so this filter applies
    # to Pain too.

    scope_level = CharInFilter(field_name='scope_level', lookup_expr='in')

    # -------------------------------------------------------------------------
    # TYPE-SPECIFIC — ImpactSignal
    # -------------------------------------------------------------------------
    #
    # impact_type  — nature of the impact (FINANCIAL, TIME, HUMAN, ...)
    # human_impact — optional human dimension (FRUSTRATION, OVERLOAD, ...)
    #                Multiple values via CSV: ?human_impact=FRUSTRATION,STRESS

    impact_type  = CharInFilter(field_name='impact_type',  lookup_expr='in')
    human_impact = CharInFilter(field_name='human_impact', lookup_expr='in')

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