# app_modules/signals/views/aggregated_signal_view.py
"""
GET /module-signals/all/

One aggregated, paginated, mixed list of ALL signal types for a single
scope (an account OR a decision cycle). Assembles the 8 existing per-type
querysets rather than reinventing them:

  - each type's ViewSet.get_queryset() is reused verbatim, so the same
    tenant scoping (ScopedQuerysetMixin) + owner scoping + select_related /
    prefetch_related the per-type list endpoints use are applied here too;
  - the rows are merged into one Python list, sorted by created_at DESC
    (id as a stable secondary key to avoid pagination drift on equal
    timestamps), and paginated with the project-standard paginator (which
    paginates a plain list just like a queryset);
  - each item is serialized by its own type's List serializer via a small
    dispatcher, and a `signal_type` field is injected on every item (the
    per-type serializers never expose the type on read — it is implied by
    the URL on the per-type endpoints, so the aggregated list must add it).

`signal_type` uses the frontend slugs (pain / objective / impact /
tech-stack / blockers / next-steps / people / constraints) so the unified
SignalLine can read it straight off each item.

Query params:
  - account_id        (UUID) — signals for the account across its cycles
  - decision_cycle_id (UUID) — signals for that decision cycle only
  - activity_id       (UUID) — signals whose source_activity is that activity
  Exactly ONE scope is required; none or several → 400 business error.
  - status (optional, repeatable) — restrict to these statuses
    (e.g. ?status=PENDING&status=VALIDATED). Omitted = the actionable default
    (PENDING + VALIDATED); REJECTED is returned only when explicitly requested.
  - signal_type (optional, repeatable) — restrict to these frontend type
    slugs (e.g. ?signal_type=pain&signal_type=impact). Empty = all types.
  - ordering (optional)     — one of the frontend sort keys: date-desc
    (default) / date-asc / status / type / theme.
  - department (optional)   — StandardDepartment id; only signals whose
    target_department matches. Types without target_department (tech-stack /
    blockers / next-steps) are EXCLUDED when this filter is active.
  - contact (optional)      — Contact UUID; only signals whose source_activity
    includes that contact. Applies to all types.
  - scope (optional)        — scope_level (BUSINESS / DEPARTMENT / PERSONAL);
    only signals with that scope_level. Types without scope_level (people /
    constraints / tech-stack / blockers / next-steps) are EXCLUDED when active.
  Field-specific filters combine with the others (AND). Invalid values → 400.

Response envelope matches the per-type list endpoints:
  { "count": N, "next": ..., "previous": ..., "results": [ { ...signal, "signal_type": "pain" }, ... ] }
"""

import uuid

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.exceptions import StandardizedValidationError
from permissions.mixins import ScopedPermission
from app_modules.signals.constants import DEFAULT_LIST_STATUSES, ScopeLevel

from app_modules.signals.serializers import (
    PainSignalListSerializer,
    ObjectiveSignalListSerializer,
    ImpactSignalListSerializer,
    TechStackSignalListSerializer,
    BlockerSignalListSerializer,
    NextStepSignalListSerializer,
    PeopleSignalListSerializer,
    ConstraintSignalListSerializer,
)
from .pain_signal_views import PainSignalViewSet
from .objective_signal_views import ObjectiveSignalViewSet
from .impact_signal_views import ImpactSignalViewSet
from .tech_stack_signal_views import TechStackSignalViewSet
from .blocker_signal_views import BlockerSignalViewSet
from .next_step_signal_views import NextStepSignalViewSet
from .people_signal_views import PeopleSignalViewSet
from .constraint_signal_views import ConstraintSignalViewSet


# (frontend slug, ViewSet class, List serializer) — the slug is what the
# SignalLine / SignalTypeChip components key off, so it must match the
# frontend vocabulary, NOT the backend create-time HiddenField values.
_TYPES = (
    ('pain',        PainSignalViewSet,        PainSignalListSerializer),
    ('objective',   ObjectiveSignalViewSet,   ObjectiveSignalListSerializer),
    ('impact',      ImpactSignalViewSet,      ImpactSignalListSerializer),
    ('tech-stack',  TechStackSignalViewSet,   TechStackSignalListSerializer),
    ('blockers',    BlockerSignalViewSet,     BlockerSignalListSerializer),
    ('next-steps',  NextStepSignalViewSet,    NextStepSignalListSerializer),
    ('people',      PeopleSignalViewSet,      PeopleSignalListSerializer),
    ('constraints', ConstraintSignalViewSet,  ConstraintSignalListSerializer),
)

_SERIALIZER_BY_SLUG = {slug: ser for slug, _vs, ser in _TYPES}

# Field-capability sets (frontend slugs). A field-specific filter (department /
# scope) excludes the types that do not carry the field — a tech signal has no
# target_department, so filtering by department must not return it.
#   target_department FK : pain / objective / impact / people / constraints
#   scope_level          : pain / objective / impact  ONLY
# (people and constraints carry target_department but NOT scope_level.)
_HAS_DEPARTMENT = {'pain', 'objective', 'impact', 'people', 'constraints'}
_HAS_SCOPE = {'pain', 'objective', 'impact'}

# Sort vocabularies — mirror the frontend SignalsSortSelect keys so the
# `ordering` param maps 1:1 to the UI control.
_STATUS_ORDER = {'PENDING': 0, 'VALIDATED': 1, 'REJECTED': 2}
_TYPE_ORDER = ('pain', 'objective', 'impact', 'tech-stack', 'blockers')


def _theme_key(obj):
    what = getattr(obj, 'what', None)
    dimension = getattr(obj, 'dimension', None)
    if what and dimension:
        return f"{obj.get_what_display()} × {obj.get_dimension_display()}".lower()
    return 'zzz'  # themeless types sort last, matching the flat view


def _sort_merged(merged, ordering):
    """
    Sort the merged cross-type list. Base order is created_at DESC with id as
    a stable secondary key (deterministic across page boundaries); the other
    keys re-order that base with a stable sort so ties stay newest-first.
    """
    merged.sort(key=lambda o: (o.created_at, o.id), reverse=True)

    if ordering == 'date-asc':
        merged.reverse()
    elif ordering == 'status':
        merged.sort(key=lambda o: _STATUS_ORDER.get(o.status, 3))
    elif ordering == 'type':
        merged.sort(
            key=lambda o: _TYPE_ORDER.index(o._signal_type)
            if o._signal_type in _TYPE_ORDER else 99
        )
    elif ordering == 'theme':
        merged.sort(key=_theme_key)
    # 'date-desc' (default): base order already applied.


class AggregatedSignalSerializer(serializers.BaseSerializer):
    """
    Dispatcher: routes each merged item to its own type's List serializer
    (so every type keeps the exact field shape its per-type endpoint
    returns) and stamps `signal_type` on the output.

    The item's slug is read from the transient `_signal_type` attribute the
    view tags each object with during the merge.
    """

    def to_representation(self, instance):
        slug = instance._signal_type
        serializer_cls = _SERIALIZER_BY_SLUG[slug]
        data = serializer_cls(instance, context=self.context).data
        data['signal_type'] = slug
        return data


class AggregatedSignalListView(BaseAPIView):
    """
    Read-only aggregated signals list for one scope. Mirrors the per-type
    signal endpoints' auth / permission / pagination for consistency.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'signals'

    def get(self, request):
        account_id        = request.query_params.get('account_id')
        decision_cycle_id = request.query_params.get('decision_cycle_id')
        activity_id       = request.query_params.get('activity_id')
        # Multi-valued (repeatable): restrict to these statuses. When OMITTED,
        # default to the actionable set (PENDING + VALIDATED) — REJECTED is
        # excluded unless explicitly requested. Same default the cluster
        # (grouped) path uses via SignalClusterService._member_statuses, sourced
        # from the shared DEFAULT_LIST_STATUSES so the two cannot drift.
        status_filters    = (
            request.query_params.getlist('status') or list(DEFAULT_LIST_STATUSES)
        )
        # Multi-valued: restrict to these frontend type slugs (empty = all).
        requested_types   = request.query_params.getlist('signal_type')
        ordering          = request.query_params.get('ordering') or 'date-desc'
        # Field-specific filters (each optional). department + scope only apply
        # to the types that carry the field; contact applies to all types via
        # source_activity.contacts.
        department        = request.query_params.get('department')
        contact           = request.query_params.get('contact')
        scope             = request.query_params.get('scope')

        # Exactly one scope must be given.
        scopes = (account_id, decision_cycle_id, activity_id)
        if sum(1 for s in scopes if s) != 1:
            raise StandardizedValidationError(
                "Provide exactly one of 'account_id', 'decision_cycle_id' "
                "or 'activity_id'."
            )

        # Validate the scope id is a well-formed UUID up front. A malformed
        # value would otherwise raise a ValueError inside the ORM filter and
        # surface as a raw 500; this keeps it a clean business 400 through the
        # standard exception handler.
        scope_value = account_id or decision_cycle_id or activity_id
        try:
            uuid.UUID(str(scope_value))
        except (ValueError, TypeError, AttributeError):
            raise StandardizedValidationError(
                "The scope id must be a valid UUID."
            )

        # Validate the field-specific filter values so a bad value is a clean
        # 400 business error, never a raw 500 from the ORM.
        department_id = None
        if department:
            try:
                department_id = int(department)
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    "The 'department' filter must be a valid department id."
                )
        contact_id = None
        if contact:
            try:
                contact_id = str(uuid.UUID(str(contact)))
            except (ValueError, TypeError, AttributeError):
                raise StandardizedValidationError(
                    "The 'contact' filter must be a valid UUID."
                )
        if scope and scope not in ScopeLevel.values:
            raise StandardizedValidationError(
                "The 'scope' filter must be one of: "
                + ", ".join(ScopeLevel.values) + "."
            )

        # Optionally narrow to a subset of types (the type filter sends this).
        # Unknown slugs are ignored.
        types = _TYPES
        if requested_types:
            wanted = set(requested_types)
            types = [t for t in _TYPES if t[0] in wanted]

        # A field-specific filter excludes the types that do not carry the
        # field (a tech signal has no target_department / scope_level).
        if department_id is not None:
            types = [t for t in types if t[0] in _HAS_DEPARTMENT]
        if scope:
            types = [t for t in types if t[0] in _HAS_SCOPE]

        merged = []
        for slug, viewset_cls, _ser in types:
            qs = self._scoped_queryset(
                viewset_cls, request,
                account_id, decision_cycle_id, activity_id, status_filters,
                department_id, contact_id, scope,
            )
            for obj in qs:
                obj._signal_type = slug
                merged.append(obj)

        _sort_merged(merged, ordering)

        page = self.paginate_queryset(merged)
        serializer = AggregatedSignalSerializer(
            page, many=True, context={'request': request},
        )
        return self.get_paginated_response(serializer.data)

    def _scoped_queryset(
        self, viewset_cls, request,
        account_id, decision_cycle_id, activity_id, status_filters,
        department_id=None, contact_id=None, scope=None,
    ):
        """
        Reuse a per-type ViewSet's get_queryset (tenant + owner scoping +
        select_related/prefetch), then narrow to the requested scope, status
        and field-specific filters. The queryset is NOT rewritten — only
        filtered. department_id / scope are only ever passed for types that
        carry the field (the caller pre-filters the type list).
        """
        vs = viewset_cls()
        vs.request      = request
        vs.action       = 'list'
        vs.args         = ()
        vs.kwargs       = {}
        vs.format_kwarg = None

        qs = vs.get_queryset()
        if account_id:
            qs = qs.filter(account_id=account_id)
        elif decision_cycle_id:
            qs = qs.filter(decision_cycle_id=decision_cycle_id)
        else:
            qs = qs.filter(source_activity_id=activity_id)
        if status_filters:
            qs = qs.filter(status__in=status_filters)
        if department_id is not None:
            qs = qs.filter(target_department_id=department_id)
        if scope:
            qs = qs.filter(scope_level=scope)
        if contact_id:
            # A signal whose origin activity includes this contact. The m2m
            # filter matches each signal at most once (single-value), so no
            # duplicates are introduced. contacts are already prefetched.
            qs = qs.filter(source_activity__contacts=contact_id)
        return qs
