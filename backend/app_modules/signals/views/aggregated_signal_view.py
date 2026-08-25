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
    (e.g. ?status=PENDING&status=VALIDATED). Empty = all.
  - signal_type (optional, repeatable) — restrict to these frontend type
    slugs (e.g. ?signal_type=pain&signal_type=impact). Empty = all types.
  - ordering (optional)     — one of the frontend sort keys: date-desc
    (default) / date-asc / status / type / theme.

Response envelope matches the per-type list endpoints:
  { "count": N, "next": ..., "previous": ..., "results": [ { ...signal, "signal_type": "pain" }, ... ] }
"""

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from core.exceptions import StandardizedValidationError
from permissions.mixins import ScopedPermission

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
        # Multi-valued (repeatable): restrict to these statuses (empty = all).
        status_filters    = request.query_params.getlist('status')
        # Multi-valued: restrict to these frontend type slugs (empty = all).
        requested_types   = request.query_params.getlist('signal_type')
        ordering          = request.query_params.get('ordering') or 'date-desc'

        # Exactly one scope must be given.
        scopes = (account_id, decision_cycle_id, activity_id)
        if sum(1 for s in scopes if s) != 1:
            raise StandardizedValidationError(
                "Provide exactly one of 'account_id', 'decision_cycle_id' "
                "or 'activity_id'."
            )

        # Optionally narrow to a subset of types (the Account toggle / DC
        # type chips send this). Unknown slugs are ignored.
        types = _TYPES
        if requested_types:
            wanted = set(requested_types)
            types = [t for t in _TYPES if t[0] in wanted]

        merged = []
        for slug, viewset_cls, _ser in types:
            qs = self._scoped_queryset(
                viewset_cls, request,
                account_id, decision_cycle_id, activity_id, status_filters,
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
    ):
        """
        Reuse a per-type ViewSet's get_queryset (tenant + owner scoping +
        select_related/prefetch), then narrow to the requested scope and
        status. The queryset is NOT rewritten — only filtered.
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
        return qs
