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

from collections import defaultdict

from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Case, CharField, Q, Value, When
from django.db.models.functions import Coalesce, Concat
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


def authorize_and_resolve(
    request, *, key, scope, period_name, period_start, period_end, fiscal_cache=None
):
    """Authorize a KPI request and resolve its scope + period, WITHOUT computing.

    Returns (definition, scope, period, auth_ctx). Raises DRF exceptions
    (NotFound / ValidationError / PermissionDenied) which the detail view lets
    propagate to handle_exception, and the batch view catches per item.

    ``fiscal_cache`` is an optional per-request memo passed through to
    resolve_period so a batch fetches the tenant's fiscal config once, not once
    per spec.
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
        period = resolve_period(
            period_name, period_start, period_end, definition, auth_ctx.client_id,
            fiscal_cache=fiscal_cache,
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(str(exc))

    return definition, scope, period, auth_ctx


def compute_kpi(request, *, key, scope, period_name, period_start, period_end, params,
                fiscal_cache=None):
    """Authorize + compute a single KPI, returning its serialized dict."""
    definition, scope, period, auth_ctx = authorize_and_resolve(
        request, key=key, scope=scope, period_name=period_name,
        period_start=period_start, period_end=period_end, fiscal_cache=fiscal_cache,
    )

    # Compute (missing compute_fn param / disallowed scope -> ValueError -> 400).
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

        # Per-request memo: N specs of the same tenant fetch the fiscal config once.
        fiscal_cache = {}
        # results is pre-sized and written by ORIGINAL index, so results[i] always
        # matches requests[i] whether the spec is an error, a per-spec compute, or
        # part of a bulk group (reassembled by index below).
        results = [None] * len(specs)
        # (key, scope, period) -> [(index, params)] for KPIs exposing a bulk hook.
        bulk_groups = defaultdict(list)
        bulk_defs = {}
        auth_ctx = None

        for i, spec in enumerate(specs):
            spec = spec or {}
            key = spec.get('key')
            try:
                definition, scope, period, auth_ctx = authorize_and_resolve(
                    request,
                    key=key,
                    scope=spec.get('scope'),
                    period_name=spec.get('period'),
                    period_start=spec.get('period_start'),
                    period_end=spec.get('period_end'),
                    fiscal_cache=fiscal_cache,
                )
            except APIException as exc:
                results[i] = {'key': key, 'error': _error_detail(exc), 'status': exc.status_code}
                continue

            params = spec.get('params') or {}
            if definition.bulk_compute_fn is not None:
                group_key = (definition.key, scope, period)
                bulk_groups[group_key].append((i, params))
                bulk_defs[group_key] = definition
            else:
                # Per-spec path — behaviour unchanged for every non-bulk KPI.
                try:
                    result = cached_run(definition, auth_ctx, scope, period, params=params)
                    results[i] = serialize_result(result, definition)
                except ValueError as exc:
                    results[i] = {'key': key, 'error': str(exc), 'status': 400}

        # Bulk path — one grouped compute per (key, scope, period), then scatter
        # the aligned results back to their original indices.
        for group_key, items in bulk_groups.items():
            definition = bulk_defs[group_key]
            _, scope, period = group_key
            params_list = [p for (_, p) in items]
            bulk_results = definition.bulk_compute_fn(
                definition, auth_ctx, scope, period, params_list
            )
            for (i, _), res in zip(items, bulk_results):
                if isinstance(res, APIException):
                    results[i] = {'key': definition.key,
                                  'error': _error_detail(res), 'status': res.status_code}
                elif isinstance(res, Exception):
                    # e.g. a ValueError for a missing required param — mapped to a
                    # 400 exactly like the per-spec ValueError -> ValidationError.
                    results[i] = {'key': definition.key, 'error': str(res), 'status': 400}
                else:
                    results[i] = serialize_result(res, definition)

        return Response({'success': True, 'data': {'results': results}})


# Server-side ordering for the todo lists — STRICT whitelist mapping a public
# ordering name to its queryset field (annotation-aware: effective_date is the
# COALESCE annotation). The default (no param) stays effective_date asc so the
# overdue rows lead — the Home's motivation framing. An out-of-whitelist field is
# a 400, never a silent fallback.
TODO_ORDERING_FIELDS = {
    'effective_date': '_effective_date',
    'due_date': 'due_date',
    'title': 'title',
    'activity_type': 'activity_type',
    'account__company_name': 'account__company_name',
    'owner__last_name': 'owner__last_name',       # manager Person column
    'owner__team__name': 'owner__team__name',     # manager Team column
    # Context = the activity's decision cycle OR campaign (an activity has one or
    # the other). Both are order-by-only annotations added by
    # _annotate_todo_context: _context_name = COALESCE(dc.name, campaign.name),
    # _context_kind = which of the two.
    'context_name': '_context_name',
    'context_kind': '_context_kind',
}


def _annotate_todo_context(queryset):
    """Annotate the context (decision cycle / campaign) sort fields — order-by
    only, not serialized. Uses the joins already in select_related, so no extra
    query. `_context_kind` is '' when the activity has neither."""
    return queryset.annotate(
        _context_name=Coalesce('decision_cycle__name', 'campaign__name'),
        _context_kind=Case(
            When(decision_cycle__isnull=False, then=Value('decision_cycle')),
            When(campaign__isnull=False, then=Value('campaign')),
            default=Value(''),
            output_field=CharField(),
        ),
    )


def _apply_todo_search(queryset, search, include_team=False):
    """Server-side search over the row's VISIBLE names: activity title, account
    company name, OWNER (the full name "First Last" as shown, AND the email
    fallback the column shows when no name is set), and the row's context name
    (decision cycle OR campaign — the "Name" column). include_team also matches
    the owner's team name; it is opt-in because only the MANAGER table shows a
    Team column (the rep table has none). Blank/None is a no-op.

    Owner is matched on the CONCATENATED full name (annotated), not first/last
    separately: a user searches what the Owner column DISPLAYS ("Fabien Roux"),
    which no single field contains. Concat matches that exactly in one SQL pass —
    unlike a token split, which would false-positive ("Fabien Martin" + "Pierre
    Roux" both matching "Fabien Roux").

    All terms are to-one joins (account, owner, decision_cycle, campaign,
    owner__team), so the OR filter adds no row multiplication (no .distinct())
    and the accessed fields are already in the callers' select_related — no N+1.
    """
    search = (search or '').strip()
    if not search:
        return queryset

    # Annotate the displayed owner name ("First Last"); Coalesce nulls to '' so a
    # name-less owner is a harmless " " (never a spurious match).
    queryset = queryset.annotate(
        _owner_full_name=Concat(
            Coalesce('owner__first_name', Value('')),
            Value(' '),
            Coalesce('owner__last_name', Value('')),
            output_field=CharField(),
        ),
    )
    q = (
        Q(title__icontains=search)
        | Q(account__company_name__icontains=search)
        | Q(_owner_full_name__icontains=search)      # the full name as displayed
        | Q(owner__email__icontains=search)          # the email fallback the column shows
        | Q(decision_cycle__name__icontains=search)
        | Q(campaign__name__icontains=search)
    )
    if include_team:
        q |= Q(owner__team__name__icontains=search)
    return queryset.filter(q)


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
        queryset = _annotate_todo_context(queryset)
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

        # Window narrowing — the same rolling predicate the tiles use, so a tile's
        # count equals this endpoint's row count for that window (parity with the
        # todo_team_windows KPI, exactly as /bi/todo/ pairs with todo_my_windows).
        # Absent window -> whole population (todo_window_q returns an empty Q).
        window = request.query_params.get('window')
        queryset = queryset.filter(todo_window_q(window, timezone.now().date()))

        # owner__team so the serializer's Team column resolves without a per-row
        # lookup (owner__team implies the owner join too).
        queryset = queryset.select_related('owner__team', 'account', 'decision_cycle', 'campaign')
        queryset = _annotate_todo_context(queryset)
        # include_team: the manager table has a Team column, so its name is searchable.
        queryset = _apply_todo_search(queryset, request.query_params.get('search'), include_team=True)
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
