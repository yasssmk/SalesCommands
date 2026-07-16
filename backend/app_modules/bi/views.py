# app_modules/bi/views.py
"""
Views for the BI module — the API surface over the declarative KPI registry.

Two endpoints:
    GET  /bi/kpi/<key>/     -> one KPI
    POST /bi/kpi/batch/     -> N KPIs in one round-trip (the Home fires ~5)

Both are BaseAPIView subclasses (tenant scoping via ViewMixin, central
handle_exception). The KPI `scope` is a USER INPUT here, so it is authorized
against the caller's role via the permissions registry BEFORE compute — a rep
cannot request 'team'/'client' beyond their tier. Tenant isolation and
mine/team/client filtering are enforced inside compute by apply_role_scope.

The batch endpoint does NOT aggregate server-side (it never freezes a "Home"
shape): it runs N independent definitions, per-item errors, bounded count.
"""

from __future__ import annotations

from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Q
from django.utils import timezone

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.compat import get_auth_ctx

from . import registry
from .cache import cached_run
from permissions.owner_scope import (
    get_all_descendant_team_ids,
    get_team_member_ids,
)

from .definitions.activities import (
    build_team_todo_population,
    build_todo_population,
    todo_window_q,
)
from .presentation import (
    DEFAULT_SCOPE,
    RESERVED_QUERY_PARAMS,
    resolve_max_scope,
    resolve_period,
    scope_within,
    serialize_result,
)
from .serializers import TeamTodoRowSerializer, TodoRowSerializer

# Upper bound on batch size — the Home fires a handful; this caps abuse without
# constraining legitimate use.
MAX_BATCH = 20


def _error_detail(exc: APIException) -> str:
    """Flatten a DRF exception detail to a plain string for batch item errors."""
    detail = exc.detail
    if isinstance(detail, (list, tuple)) and detail:
        return str(detail[0])
    return str(detail)


def compute_kpi(request, *, key, scope, period_name, period_start, period_end, params):
    """Authorize + compute a single KPI, returning its serialized dict.

    Raises DRF exceptions (NotFound / ValidationError / PermissionDenied) which
    the detail view lets propagate to handle_exception, and the batch view
    catches per item.
    """
    if not key or not registry.is_registered(key):
        raise NotFound(f"Unknown KPI '{key}'")

    definition = registry.get(key)
    scope = scope or DEFAULT_SCOPE

    # 1) The KPI must permit this scope at all.
    if scope not in definition.allowed_scopes:
        raise ValidationError(
            f"scope '{scope}' not allowed for KPI '{key}' "
            f"(allowed: {list(definition.allowed_scopes)})"
        )

    # 2) SECURITY: scope is a user input — bound it by the caller's role on the
    # KPI's scope_module (same registry the viewsets use).
    max_scope = resolve_max_scope(request, definition.scope_module)
    if not scope_within(scope, max_scope):
        raise PermissionDenied(
            f"scope '{scope}' exceeds your permission on '{definition.scope_module}'"
        )

    auth_ctx = get_auth_ctx(request)

    # 3) Period parsing (bad name / malformed custom dates -> 400).
    try:
        period = resolve_period(period_name, period_start, period_end, definition, auth_ctx.client_id)
    except (ValueError, TypeError) as exc:
        raise ValidationError(str(exc))

    # 4) Compute (missing compute_fn param / disallowed scope -> ValueError -> 400).
    try:
        result = cached_run(definition, auth_ctx, scope, period, params=params or {})
    except ValueError as exc:
        raise ValidationError(str(exc))

    return serialize_result(result, definition)


class KPIDetailView(BaseAPIView):
    """
    GET /bi/kpi/<key>/?scope=&period=&<extra params> -> one KPI.

    Query params: `scope` (mine|team|client, default mine), `period`
    (default|fiscal_year|all|custom + period_start/period_end). Any other query
    param (cycle_id, campaign_id, territory_id, quota_id, ...) is forwarded to
    the KPI as a compute_fn param.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'kpi'

    def get(self, request, key):
        params = {
            k: v for k, v in request.query_params.items()
            if k not in RESERVED_QUERY_PARAMS
        }
        data = compute_kpi(
            request,
            key=key,
            scope=request.query_params.get('scope'),
            period_name=request.query_params.get('period'),
            period_start=request.query_params.get('period_start'),
            period_end=request.query_params.get('period_end'),
            params=params,
        )
        return Response({'success': True, 'data': data})


class KPIBatchView(BaseAPIView):
    """
    POST /bi/kpi/batch/ -> run several KPIs in one round-trip.

    Body: {"requests": [{"key", "scope"?, "period"?, "period_start"?,
    "period_end"?, "params"?}, ...]}.

    Does NOT aggregate: returns {"results": [<kpi dict> | {"key","error","status"}]}
    in request order. One failing item never fails the batch — its error is
    reported inline and the others still run.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'kpi'

    def post(self, request):
        specs = request.data.get('requests')
        if not isinstance(specs, list):
            raise ValidationError("Body must be {'requests': [ ... ]}")
        if len(specs) > MAX_BATCH:
            raise ValidationError(f"Batch too large: {len(specs)} requests (max {MAX_BATCH})")

        results = []
        for spec in specs:
            spec = spec or {}
            key = spec.get('key')
            try:
                results.append(compute_kpi(
                    request,
                    key=key,
                    scope=spec.get('scope'),
                    period_name=spec.get('period'),
                    period_start=spec.get('period_start'),
                    period_end=spec.get('period_end'),
                    params=spec.get('params'),
                ))
            except APIException as exc:
                results.append({
                    'key': key,
                    'error': _error_detail(exc),
                    'status': exc.status_code,
                })

        return Response({'success': True, 'data': {'results': results}})


# Server-side ordering for the todo lists — STRICT whitelist mapping a public
# ordering name to its queryset field (annotation-aware: effective_date is the
# COALESCE annotation). The default (no param) stays effective_date asc so the
# overdue rows lead — the Home's motivation framing. An out-of-whitelist field is
# a 400, never a silent fallback.
TODO_ORDERING_FIELDS = {
    'effective_date': '_effective_date',
    'account__company_name': 'account__company_name',
    'owner__last_name': 'owner__last_name',
    'due_date': 'due_date',
}


def _apply_todo_search(queryset, search):
    """Server-side search over the row's visible names: activity title, account
    company name, owner first/last name. Blank/None is a no-op."""
    search = (search or '').strip()
    if not search:
        return queryset
    return queryset.filter(
        Q(title__icontains=search)
        | Q(account__company_name__icontains=search)
        | Q(owner__first_name__icontains=search)
        | Q(owner__last_name__icontains=search)
    )


def _apply_todo_ordering(queryset, ordering):
    """Map a whitelisted `ordering` param (comma-separated, '-' prefix = desc) to
    order_by, always tie-broken by id. No param -> effective_date asc (overdue
    first, unchanged). A field outside TODO_ORDERING_FIELDS raises 400 — strict
    rejection, never a silent fallback."""
    ordering = (ordering or '').strip()
    if not ordering:
        return queryset.order_by('_effective_date', 'id')

    order_by = []
    for term in ordering.split(','):
        term = term.strip()
        if not term:
            continue
        desc = term.startswith('-')
        name = term[1:] if desc else term
        field = TODO_ORDERING_FIELDS.get(name)
        if field is None:
            raise ValidationError(f"Cannot order by '{name}'")
        order_by.append(f'-{field}' if desc else field)

    if not order_by:
        return queryset.order_by('_effective_date', 'id')
    order_by.append('id')
    return queryset.order_by(*order_by)


class TodoListView(BaseAPIView):
    """
    GET /bi/todo/?scope=&window= -> the ROWS of the todo population, paginated.

    Reads the SAME build_todo_population + todo_window_q as the todo_my_windows
    count KPI, so a window's tile count equals its row count by construction.
    scope is bounded by role (same invariant as the KPI endpoint); rows are
    sorted by effective_date (COALESCE(due_date, scheduled_date)) — the field the
    windows are defined on, so an activity with no due_date but scheduled today
    sorts with today, not into the nulls.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'todo'

    def get(self, request):
        scope = request.query_params.get('scope') or DEFAULT_SCOPE

        # SECURITY: scope is a user input — bound it by the caller's role on the
        # activities module (same invariant as the KPI endpoint).
        max_scope = resolve_max_scope(request, 'activities')
        if not scope_within(scope, max_scope):
            raise PermissionDenied(f"scope '{scope}' exceeds your permission on 'activities'")

        auth_ctx = get_auth_ctx(request)
        window = request.query_params.get('window')

        queryset = (
            build_todo_population(auth_ctx, scope)
            .filter(todo_window_q(window, timezone.now().date()))
            .select_related('owner', 'account', 'decision_cycle', 'campaign')
        )
        queryset = _apply_todo_search(queryset, request.query_params.get('search'))
        queryset = _apply_todo_ordering(queryset, request.query_params.get('ordering'))

        page = self.paginate_queryset(queryset)
        serializer = TodoRowSerializer(page, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': self.paginator.page.paginator.count,
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
            },
        })


class TeamTodoListView(BaseAPIView):
    """
    GET /bi/todo/team/?scope=&team=&owner= -> the MANAGER view's team todo ROWS,
    paginated.

    Reads the SAME population as the todo_team_by_owner COUNT KPI
    (build_team_todo_population: open activities, role-scoped, NO personal
    invited-accepted union), so a person's row count here equals their bucket in
    that KPI by construction. `scope` is a USER INPUT and is bounded by the
    caller's role on 'activities' exactly as the other BI endpoints; it defaults
    to 'team' (this IS the team view).

    Optional narrowing — UX only, never widening, both applied INSIDE the role
    scope:
      - team=<id>: restrict to the members of that team AND its sub-teams
        (get_all_descendant_team_ids -> get_team_member_ids -> owner_id__in). A
        team OUTSIDE the caller's managed hierarchy yields ZERO rows: the role
        scope has already excluded its members, so the intersection is empty.
      - owner=<id>: restrict to a single person — the per-person drill-down
        behind clicking a name in the manager's per-owner breakdown.

    Rows sort by effective_date (COALESCE(due_date, scheduled_date)), the same
    field the todo windows are defined on.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    entity_name = 'todo'

    def get(self, request):
        scope = request.query_params.get('scope') or 'team'

        # SECURITY: scope is a user input — bound it by the caller's role on the
        # activities module (same invariant as the other BI endpoints).
        max_scope = resolve_max_scope(request, 'activities')
        if not scope_within(scope, max_scope):
            raise PermissionDenied(f"scope '{scope}' exceeds your permission on 'activities'")

        auth_ctx = get_auth_ctx(request)

        queryset = build_team_todo_population(auth_ctx, scope)

        # UX narrowing — a team subtree and/or a single owner, always INSIDE the
        # role scope (an out-of-hierarchy team intersects the scope to empty).
        team_id = request.query_params.get('team')
        if team_id:
            team_ids = get_all_descendant_team_ids([team_id], auth_ctx.client_id)
            member_ids = get_team_member_ids(team_ids, auth_ctx.client_id)
            queryset = queryset.filter(owner_id__in=member_ids)

        owner_id = request.query_params.get('owner')
        if owner_id:
            queryset = queryset.filter(owner_id=owner_id)

        # owner__team so the serializer's Team column resolves without a per-row
        # lookup (owner__team implies the owner join too).
        queryset = queryset.select_related('owner__team', 'account', 'decision_cycle', 'campaign')
        queryset = _apply_todo_search(queryset, request.query_params.get('search'))
        queryset = _apply_todo_ordering(queryset, request.query_params.get('ordering'))

        page = self.paginate_queryset(queryset)
        serializer = TeamTodoRowSerializer(page, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': self.paginator.page.paginator.count,
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
            },
        })
