# app_modules/decision_cycles/views/views.py
"""
ViewSets for Decision Cycle module.

Follows CompanyAccountViewSet patterns for consistency.
"""

import django_filters

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Prefetch, Count, Q, Exists, OuterRef

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import (
    invalidate_tag,
    build_drf_cache_key,
    cache_get_set,
    get_permissions_version,
    _is_redis_backend,
)

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin
from permissions.scope_filter import apply_role_scope
from permissions.compat import get_auth_ctx

from app_modules.notifications.models import NotificationCategory
from app_modules.notifications.services import NotificationService

from ..models import DecisionCycle, DecisionStep, DecisionStepContact, DealProduct
from ..serializers import (
    DecisionCycleSerializer,
    DecisionCycleListSerializer,
    DecisionCycleCreateSerializer,
    DecisionCycleUpdateSerializer,
    DecisionCycleTimelineSerializer,
    DecisionStepSerializer,
    DecisionStepListSerializer,
    DecisionStepCreateSerializer,
    DecisionStepUpdateSerializer,
)
from ..constants import PipelineStep, DecisionStepStatus, CycleOutcome, TERMINAL_OUTCOMES, PIPELINE_STEPS_CONFIG
from ..config import CONFIG
from ..services import (
    annotate_cycle_state,
    annotate_deal_value,
    annotate_effective_close_date,
)
from ..services.derivation_sql import CYCLE_STATUS_ALIAS

logger = get_logger(__name__)


# ============================================================================
# DECISION CYCLE FILTERSET
# ============================================================================

# Unified status facet — one value covering BOTH vocabularies:
#   stored outcome (WON / LOST / ON_HOLD / NOT_QUALIFIED),
#   derived effective state (NOT_STARTED / IN_PROGRESS / OVERDUE / STALLED),
#   plus OPEN (outcome IS NULL).
_STATUS_OPEN = 'OPEN'
_OUTCOME_STATUS_VALUES = {
    CycleOutcome.WON, CycleOutcome.LOST, CycleOutcome.ON_HOLD, CycleOutcome.NOT_QUALIFIED,
}
_DERIVED_STATUS_VALUES = {
    DecisionStepStatus.NOT_STARTED, DecisionStepStatus.IN_PROGRESS,
    DecisionStepStatus.OVERDUE, DecisionStepStatus.STALLED,
}
_UNIFIED_STATUS_CHOICES = (
    [(_STATUS_OPEN, 'Open')]
    + [(v, v) for v in (
        CycleOutcome.WON, CycleOutcome.LOST, CycleOutcome.ON_HOLD, CycleOutcome.NOT_QUALIFIED,
    )]
    + [(v, v) for v in (
        DecisionStepStatus.NOT_STARTED, DecisionStepStatus.IN_PROGRESS,
        DecisionStepStatus.OVERDUE, DecisionStepStatus.STALLED,
    )]
)


class DecisionCycleFilterSet(django_filters.FilterSet):
    """
    Filterset for the decision-cycle list.

    Narrows WITHIN the already tenant- and role-scoped queryset (get_queryset);
    it never widens scope. To-many facets (contact, product) use isolated
    correlated Exists subqueries, never a join + distinct that fan-out would
    skew. `team` matches the EXACT team (owner__team_id), no hierarchy descent —
    the descent is owner_scope=team's job, a separate mechanism (mirror of
    CampaignFilterSet.filter_team).
    """

    # Exact FK facets (nullable FKs: a positive value only narrows; absence
    # leaves owner-less / campaign-less cycles in place — no orphan drop).
    account = django_filters.UUIDFilter(field_name='account_id')
    owner = django_filters.UUIDFilter(field_name='owner_id')
    source_campaign = django_filters.UUIDFilter(field_name='source_campaign_id')
    is_active = django_filters.BooleanFilter(field_name='is_active')

    # Backward-compat raw outcome facets (kept until the frontend switches to
    # the unified `status` in the next sub-step; additive, independent params).
    outcome = django_filters.CharFilter(field_name='outcome')
    outcome__isnull = django_filters.BooleanFilter(
        field_name='outcome', lookup_expr='isnull'
    )

    # Unified effective-status facet.
    status = django_filters.ChoiceFilter(
        method='filter_status', choices=_UNIFIED_STATUS_CHOICES
    )

    # Exact team (no descent), mirror of CampaignFilterSet.filter_team.
    team = django_filters.CharFilter(method='filter_team')

    # To-many facets via isolated Exists.
    contact = django_filters.UUIDFilter(method='filter_contact')
    product = django_filters.UUIDFilter(method='filter_product')

    class Meta:
        model = DecisionCycle
        fields = []  # every facet declared explicitly above

    def filter_status(self, queryset, name, value):
        """
        Filter on the EFFECTIVE status.

        - OPEN                              → outcome IS NULL
        - WON / LOST / ON_HOLD / NOT_QUALIFIED → outcome = value (exact, so
          NOT_QUALIFIED stays distinct from LOST — the 1b annotation collapses
          NOT_QUALIFIED into LOST for display, but the filter keeps them apart)
        - NOT_STARTED / IN_PROGRESS / OVERDUE / STALLED → the derived state,
          which only exists on open cycles, read from the 1b cycle-state
          annotation (present on the list queryset)
        """
        if not value:
            return queryset
        if value == _STATUS_OPEN:
            return queryset.filter(outcome__isnull=True)
        if value in _OUTCOME_STATUS_VALUES:
            return queryset.filter(outcome=value)
        if value in _DERIVED_STATUS_VALUES:
            return queryset.filter(
                outcome__isnull=True, **{CYCLE_STATUS_ALIAS: value}
            )
        return queryset

    def filter_team(self, queryset, name, value):
        """Cycles whose owner belongs to the given team — exact team, no descent."""
        if not value:
            return queryset
        return queryset.filter(owner__team_id=value)

    def filter_contact(self, queryset, name, value):
        """
        Cycles where the contact is involved — UNION of the two provenances:
        attached to a step (steps__contacts) OR present on one of the cycle's
        step activities (steps__activities__contacts). Same semantics as the
        all_contacts model property. Isolated Exists per provenance, so the
        to-many joins never multiply the outer cycle rows.
        """
        if not value:
            return queryset
        from app_modules.activities.models import Activity

        on_step = DecisionStepContact.objects.filter(
            step__cycle_id=OuterRef('pk'), contact_id=value,
        )
        on_activity = Activity.objects.filter(
            decision_step__cycle_id=OuterRef('pk'), contacts__id=value,
        )
        return queryset.filter(Exists(on_step) | Exists(on_activity))

    def filter_product(self, queryset, name, value):
        """Cycles carrying the given catalog product on a deal line (isolated Exists)."""
        if not value:
            return queryset
        lines = DealProduct.objects.filter(
            decision_cycle_id=OuterRef('pk'), product_catalog_entry_id=value,
        )
        return queryset.filter(Exists(lines))


# ============================================================================
# DECISION CYCLE VIEWSET
# ============================================================================

class DecisionCycleViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Decision Cycles.
    
    Features:
        - Client-scoped data isolation (multi-tenant)
        - Permission-based access control
        - Structured logging + SOC 2 audit trail
        
    Endpoints:
        - GET    /decision-cycles/                    - List all cycles
        - POST   /decision-cycles/                    - Create cycle
        - GET    /decision-cycles/{id}/               - Retrieve cycle
        - PUT    /decision-cycles/{id}/               - Update cycle (full)
        - PATCH  /decision-cycles/{id}/               - Update cycle (partial)
        - DELETE /decision-cycles/{id}/               - Delete cycle
        - GET    /decision-cycles/by-account/{id}/    - Get cycles for account
    """
    
    queryset = DecisionCycle.objects.all()
    serializer_class = DecisionCycleSerializer
    entity_name = 'decision_cycle'
    
    # Filtering — filterset + ordering + search read from the module CONFIG
    # (single source of truth, config/settings.py). The base queryset is
    # tenant/owner-scoped upstream, so every facet narrows WITHIN scope.
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = DecisionCycleFilterSet
    search_fields = CONFIG.filters.dc_search_fields
    ordering_fields = CONFIG.filters.dc_ordering_fields
    ordering = CONFIG.filters.default_dc_ordering
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'
    
    # Action policies
    action_policies = {
        'by_account': {
            'crud': 'read',
            'scope': 'client',
        },
        'people': {
            'crud': 'read',
            'scope': 'client',
        },
        'readiness': {
            'crud': 'read',
            'scope': 'client',
        },
    }

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _invalidate_cycle_caches(self, client_id):
        """
        Invalidate all decision-cycle-related caches and cross-module dependencies.

        When a cycle changes, we must invalidate:
        - Decision cycle cache (list, detail, timeline views)
        - Activity cache (activity status may change from auto-cancel)
        - Account cache (workspace stats depend on cycle data)
        """
        client_id_str = str(client_id)
        invalidate_tag(client_id_str, 'decision_cycles')
        invalidate_tag(client_id_str, 'activities')
        invalidate_tag(client_id_str, 'accounts')

        logger.info('cache_invalidation_cycle', extra={
            'event': 'cache_invalidation',
            'client_id': client_id_str,
            'tags': ['decision_cycles', 'activities', 'accounts'],
        })

    
    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'list':
            return DecisionCycleListSerializer
        elif self.action == 'create':
            return DecisionCycleCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DecisionCycleUpdateSerializer
        return DecisionCycleSerializer
    
    def get_queryset(self):
        """Get cycles with optimized queries based on action."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'DecisionCycleViewSet'
        })
        
        queryset = super().get_queryset()
        
        if self.action == 'list':
            # List: minimal data for table display (no activities, no deep nesting).
            # owner__team so DecisionCycleListSerializer.get_team resolves the
            # owner's team without a per-row lookup (the manager DC block's Team
            # line). owner__team implies the owner join too.
            #
            # annotate_cycle_state adds the 1b cycle-state annotations (effective
            # status, current step name/stage/order, validated/total/stalled
            # counts). They serve the list serializer (killing the TD-90 N+1: the
            # two count properties are now single isolated subqueries, not one/two
            # queries PER cycle) AND back the unified `status` filter and the
            # stage/status ordering. This annotation lives ONLY on the list branch
            # — the only branch that reaches filter_queryset (OrderingFilter would
            # otherwise raise FieldError for a missing annotation). The steps
            # prefetch is gone: the serializer reads the counts from annotations,
            # nothing consumes the prefetched steps anymore.
            # annotate_deal_value adds the product roll-up (_deal_value) the
            # Amount column reads and sorts on — one correlated subquery per
            # row, so total_deal_value costs the serializer nothing and the
            # list stays query-bounded.
            queryset = annotate_effective_close_date(annotate_deal_value(
                annotate_cycle_state(
                    queryset.select_related('account', 'owner', 'owner__team')
                )
            ))
        elif self.action == 'retrieve':
            # Retrieve: full step data with limited activities for detail view
            from app_modules.activities.models import Activity
            
            activities_prefetch = Prefetch(
                'steps__activities',
                queryset=Activity.objects.select_related('owner').only(
                    'id', 'title', 'activity_type', 'status', 'outcome',
                    'scheduled_date', 'due_date', 'owner_id',
                    'decision_step_id', 'created_at'
                ).order_by('-scheduled_date', '-created_at')[:15]
            )
            
            # annotate_deal_value carries the product roll-up (_deal_value) that
            # DecisionCycleSerializer.total_deal_value reads — one correlated
            # subquery on the single row being retrieved, instead of the extra
            # query the model property would otherwise issue. Same annotation,
            # same formula as the list branch above.
            queryset = annotate_effective_close_date(annotate_deal_value(
                queryset.select_related('account', 'owner').prefetch_related(
                    Prefetch(
                        'steps',
                        queryset=DecisionStep.objects.select_related('previous_step').order_by('order')
                    ),
                    activities_prefetch
                )
            ))
        else:
            # Create/Update/Delete: minimal - just account and owner
            queryset = queryset.select_related('account', 'owner')

        # Apply owner scope filter (mine/team/all).
        #
        # For owner_scope=mine AND team we deliberately DIVERGE from the shared
        # OwnerScopeMixin (which matches owner_id only) and reuse the SAME
        # primitive the BI layer uses — apply_role_scope — so the list's scope ==
        # the KPI's scope: owner (+ team members) OR account-owner (C6). Without
        # this, a cycle an SDR posted on a caller's / team member's account
        # (which they can already read via C6, and which dc_cycle_state resolves)
        # is silently dropped from the list — the asymmetry that hid an AE's deals
        # on the Home (mine) and hid a team member's SDR-posted deals from the
        # manager block (team). C6 terms are to-one joins, so no .distinct() is
        # needed, and this runs BEFORE the DjangoFilterBackend/pagination so the
        # count is correct. Diverting team also aligns the ROOTS with the KPI
        # (teams managed via manager_id, not just the caller's own team_id).
        # all / absent stay on the mixin, unchanged (zero blast radius on the 8
        # other ViewSets that share it).
        owner_scope = self.request.query_params.get('owner_scope')
        if owner_scope in ('mine', 'team'):
            ctx = get_auth_ctx(self.request)
            queryset = apply_role_scope(
                queryset, module='decision_cycles', scope=owner_scope, auth_ctx=ctx
            )
        else:
            queryset = self.apply_owner_scope_filter(queryset)

        return queryset
    
    # ==========================================================================
    # CRUD OVERRIDES
    # ==========================================================================
    
    def list(self, request, *args, **kwargs):
        """List decision cycles with pagination."""
        ctx = ctx_from_request(request)
        logger.info("decision_cycles_list_requested", extra=ctx)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single decision cycle with steps."""
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("decision_cycle_retrieved", extra={
            **ctx,
            'cycle_id': str(instance.id)
        })
        
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new decision cycle with AUTO-CREATED pipeline steps.
        
        Pipeline steps are fixed and cannot be created manually by users.
        5 steps are created automatically in order:
        1. Qualification
        2. Technical Fit
        3. Solution Validation
        4. Business Case
        5. Closing
        """

        ctx = ctx_from_request(request)
        logger.info("decision_cycle_create_requested", extra=ctx)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the cycle
        cycle = serializer.save()
        
        # Auto-create all pipeline steps
        self._create_pipeline_steps(cycle, request.user)
        
        # Audit log
        audit_log(
            event='decision_cycle_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=str(cycle.id),
            outcome='success'
        )
        
        logger.info("decision_cycle_created_with_steps", extra={
            **ctx,
            'cycle_id': str(cycle.id),
            'steps_created': len(PIPELINE_STEPS_CONFIG)
        })
        
        # Return full cycle with steps
        self._invalidate_cycle_caches(str(self.get_client_id()))

        # Notify the account owner that a new decision cycle was created on
        # their account. The self-notify (creator == account owner) and
        # owner-None guards live in NotificationService.emit(). Primitives are
        # captured outside the commit closure.
        account = cycle.account
        account_owner_id = account.account_owner_id
        company_name = account.company_name
        account_id = cycle.account_id
        cycle_id = cycle.id
        client_id = cycle.client_id
        actor = request.user
        actor_name = actor.get_full_name() or actor.email

        def _emit_owner_notification():
            NotificationService.emit(
                client_id=client_id,
                recipient=account_owner_id,
                actor=actor,
                category=NotificationCategory.DECISION_CYCLE_CREATED,
                title=f"{actor_name} created a Decision Cycle on {company_name}",
                related_object_type='decision_cycle',
                related_object_id=cycle_id,
                payload={'account_id': str(account_id), 'cycle_id': str(cycle_id)},
            )

        transaction.on_commit(_emit_owner_notification)

        output_serializer = DecisionCycleSerializer(cycle)
        return Response({
            'success': True,
            'data': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def _create_pipeline_steps(self, cycle, user):
        """
        Create fixed pipeline steps for a new cycle (5 steps).
        
        Steps are created in order with linked-list relationships.
        IMPLEMENTATION and GO_LIVE kept in PipelineStep enum for backward
        compatibility but are NOT auto-created for new cycles.
        """
        previous_step = None
        
        for config in PIPELINE_STEPS_CONFIG:
            step = DecisionStep(
                cycle=cycle,
                client_id=cycle.client_id,
                name=config['step'].label,  # Use the label from PipelineStep
                stage=config['step'].value,
                order=config['order'],
                previous_step=previous_step,
                # expected_end will be set by user later
                expected_end=None,
                created_by=user,
                updated_by=user,
            )
            step.save(user=user)
            
            logger.debug("pipeline_step_created", extra={
                'cycle_id': str(cycle.id),
                'step_id': str(step.id),
                'stage': config['step'].value,
                'order': config['order']
            })
            
            previous_step = step
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update a decision cycle."""
        ctx = ctx_from_request(request)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info("decision_cycle_update_requested", extra={
            **ctx,
            'cycle_id': str(instance.id)
        })
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='decision_cycle_update_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=str(instance.id),
            fields_changed=list(serializer.validated_data.keys()),
            outcome='success'
        )
        
        logger.info("decision_cycle_updated", extra={
            **ctx,
            'cycle_id': str(instance.id)
        })

        self._invalidate_cycle_caches(str(self.get_client_id()))

        output_serializer = DecisionCycleSerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        })
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete a decision cycle."""
        ctx = ctx_from_request(request)
        instance = self.get_object()
        cycle_id = str(instance.id)
        cycle_name = instance.name

        
        logger.info("decision_cycle_delete_requested", extra={
            **ctx,
            'cycle_id': cycle_id
        })
        
        instance.delete()
        
        # Audit log
        audit_log(
            event='decision_cycle_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=cycle_id,
            outcome='success'
        )
        
        logger.info("decision_cycle_deleted", extra={
            **ctx,
            'cycle_id': cycle_id
        })

        self._invalidate_cycle_caches(str(self.get_client_id()))

        return Response({
            'success': True,
            'message': 'Decision cycle deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=False, methods=['get'], url_path='by-account/(?P<account_id>[^/.]+)')
    def by_account(self, request, account_id=None):
        """
        Get all decision cycles for a specific account with Redis caching.
        
        GET /decision-cycles/by-account/{account_id}/
        
        Cache: 60s, tag 'decision_cycles', keyed by account_id + user.
        
        Returns cycle data including steps with activities for timeline display.
        
        PERFORMANCE OPTIMIZED:
        - Uses DecisionCycleTimelineSerializer (no expensive model properties)
        - Annotations for counts (single query vs N+1)
        - Limited activity prefetch (max 5 per step)
        - No completeness_score, is_stalled computation for list view
        - Prefetched activity contacts + departments for aggregation (zero extra queries in serializer)
        
        SQL BUDGET: ~5 queries total regardless of step/activity count:
        1. Cycles (with annotations)
        2. Steps (with annotation)
        3. Activities (with select_related owner, prefetch contacts)
        4. Activity contacts (with select_related standard_department)
        5. Step contacts + Step departments (to_attr prefetch)
        """
        ctx = ctx_from_request(request)
        logger.info("decision_cycles_by_account_requested", extra={
            **ctx,
            'account_id': account_id
        })
        
        if not _is_redis_backend():
            return Response(self._produce_by_account(request, account_id, ctx))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='decision_cycles_by_account',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            extra=str(account_id),
            tag_namespace='decision_cycles',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_by_account(request, account_id, ctx),
            ttl=60,
            tag=(client_id, 'decision_cycles'),
        )
        
        return Response(cached_data)
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def close(self, request, pk=None):
        """
        Close a decision cycle with an explicit outcome.

        POST /decision-cycles/{id}/close/

        Payload:
            outcome: WON | LOST | ON_HOLD | NOT_QUALIFIED  (required)
            outcome_notes: str  (required for ON_HOLD, optional otherwise)
            hold_until: date    (required for ON_HOLD only)

        Behavior:
            WON / LOST / NOT_QUALIFIED → auto-cancel all PLANNED activities
            ON_HOLD → keep PLANNED activities (deal paused, not dead)
        """
        from django.utils import timezone as tz
        from app_modules.activities.constants import ActivityStatus

        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("decision_cycle_close_requested", extra={
            **ctx,
            'cycle_id': str(instance.id),
        })

        # --- Validate payload ---
        outcome = request.data.get('outcome')
        outcome_notes = (request.data.get('outcome_notes') or '').strip() or None
        hold_until = request.data.get('hold_until')

        if not outcome:
            raise StandardizedValidationError("outcome is required.")

        valid_outcomes = [c.value for c in CycleOutcome]
        if outcome not in valid_outcomes:
            raise StandardizedValidationError(
                f"outcome must be one of: {', '.join(valid_outcomes)}"
            )

        # Already closed guard
        if instance.outcome is not None:
            raise StandardizedValidationError(
                f"Cycle is already closed as {instance.outcome}. Reopen it first."
            )

        # ON_HOLD specific validation
        if outcome == CycleOutcome.ON_HOLD:
            if not outcome_notes:
                raise StandardizedValidationError(
                    "outcome_notes is required when outcome is ON_HOLD."
                )
            if not hold_until:
                raise StandardizedValidationError(
                    "hold_until date is required when outcome is ON_HOLD."
                )
            # hold_until must not be in the past
            from datetime import date as date_type
            try:
                parsed_hold = (
                    hold_until if isinstance(hold_until, date_type)
                    else tz.datetime.strptime(hold_until, '%Y-%m-%d').date()
                )
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    "hold_until must be a valid date."
                )
            if parsed_hold < tz.now().date():
                raise StandardizedValidationError(
                    "hold_until date cannot be in the past."
                )

        # --- Apply outcome ---
        instance.outcome = outcome
        instance.outcome_date = tz.now().date()
        instance.outcome_notes = outcome_notes
        instance.hold_until = hold_until if outcome == CycleOutcome.ON_HOLD else None
        instance.save(user=request.user)

        # --- Terminal outcomes: auto-cancel PLANNED activities ---
        cancelled_count = 0
        if outcome in TERMINAL_OUTCOMES:
            from app_modules.activities.models import Activity

            planned_activities = Activity.objects.filter(
                decision_step__cycle=instance,
                status=ActivityStatus.PLANNED,
            )
            cancelled_count = planned_activities.count()
            planned_activities.update(
                status=ActivityStatus.CANCELLED,
                updated_by=request.user,
            )

        # --- WON: a PROSPECT account becomes a CLIENT (new logo) on first win. ---
        # A server-side EFFECT of the win, not a user edit. Only a PROSPECT is
        # converted: an account already CLIENT (e.g. imported from the client's
        # existing base) is never recounted as a new logo. Idempotent — the
        # timestamp is set once and never overwritten, so a second won cycle on
        # the same account changes nothing.
        became_client = False
        if outcome == CycleOutcome.WON:
            from app_modules.accounts.models import AccountType

            account = instance.account
            if account.type == AccountType.PROSPECT:
                account.type = AccountType.CLIENT
                if account.became_client_at is None:
                    account.became_client_at = tz.now()
                account.save(user=request.user)
                became_client = True

        # Audit log
        audit_log(
            event='decision_cycle_close_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=str(instance.id),
            outcome='success',
             extra={
                'cycle_outcome': outcome,
                'cancelled_activities': cancelled_count,
                'account_became_client': became_client,
            },
        )

        # Invalidate caches (cycles + activities + accounts)
        self._invalidate_cycle_caches(self.get_client_id())

        logger.info("decision_cycle_closed", extra={
            **ctx,
            'cycle_id': str(instance.id),
            'outcome': outcome,
            'cancelled_activities': cancelled_count,
        })

        serializer = DecisionCycleSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data,
            'meta': {
                'cancelled_activities_count': cancelled_count,
            },
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reopen(self, request, pk=None):
        """
        Reopen a closed decision cycle.

        POST /decision-cycles/{id}/reopen/

        Behavior:
            - Clears outcome, outcome_date, outcome_notes, hold_until
            - Does NOT auto-restore cancelled activities
            - Cycle status re-derives from step data
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info("decision_cycle_reopen_requested", extra={
            **ctx,
            'cycle_id': str(instance.id),
        })

        # Guard: must be closed
        if instance.outcome is None:
            raise StandardizedValidationError(
                "Cycle is not closed. Nothing to reopen."
            )

        previous_outcome = instance.outcome

        # Clear outcome fields
        instance.outcome = None
        instance.outcome_date = None
        instance.outcome_notes = None
        instance.hold_until = None
        instance.save(user=request.user)

        # Audit log
        audit_log(
            event='decision_cycle_reopen_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=str(instance.id),
            outcome='success',
             extra={
                'previous_outcome': previous_outcome,
            },
        )

        # Invalidate caches (cycles + activities + accounts)
        self._invalidate_cycle_caches(self.get_client_id())

        logger.info("decision_cycle_reopened", extra={
            **ctx,
            'cycle_id': str(instance.id),
            'previous_outcome': previous_outcome,
        })

        serializer = DecisionCycleSerializer(instance, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data,
        })

    @action(detail=True, methods=['get'], url_path='people')
    def people(self, request, pk=None):
        """
        Consolidated people view for a decision cycle.

        GET /decision-cycles/{id}/people/

        Returns qualified (with PeopleSignal) and unqualified contacts,
        grouped by department.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info('decision_cycle_people_requested', extra={
            **ctx, 'cycle_id': str(instance.id),
        })

        from ..services import PeopleConsolidationService
        service = PeopleConsolidationService()
        result = service.consolidate(instance)

        return Response({'success': True, 'data': result})

    @action(detail=True, methods=['get'], url_path='readiness')
    def readiness(self, request, pk=None):
        """
        Readiness score for a decision cycle.

        GET /decision-cycles/{id}/readiness/

        Returns a deterministic score (0-100) indicating whether the cycle
        has enough validated evidence for a useful Deal Health diagnostic.
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info('decision_cycle_readiness_requested', extra={
            **ctx, 'cycle_id': str(instance.id),
        })

        from ..services import ReadinessScoreService
        service = ReadinessScoreService()
        result = service.calculate(instance)

        return Response({'success': True, 'data': result})

    def _produce_by_account(self, request, account_id, ctx):
        """Produce by_account data dict (cache-friendly, no Response wrapper)."""
        # Import models for prefetch
        from app_modules.activities.models import Activity
        from ..models import DecisionStepContact, DecisionStepDepartment
        
        # Build optimized steps queryset with activity count annotation
        # + to_attr prefetch for manual contacts/departments (used by timeline serializer)
        steps_queryset = DecisionStep.objects.annotate(
            activities_count=Count('activities')
        ).prefetch_related(
            Prefetch(
                'step_contacts',
                queryset=DecisionStepContact.objects.select_related('contact'),
                to_attr='_prefetched_step_contacts'
            ),
            Prefetch(
                'step_departments',
                queryset=DecisionStepDepartment.objects.select_related('department'),
                to_attr='_prefetched_step_departments'
            ),
        ).order_by('order')
        
        # Build activities prefetch with contacts + departments for aggregation
        # contacts prefetched with standard_department for department aggregation
        activities_prefetch = Prefetch(
            'steps__activities',
            queryset=Activity.objects.select_related(
                'owner'
            ).prefetch_related(
                Prefetch(
                    'contacts',
                    queryset=Activity.contacts.field.related_model.objects.select_related(
                        'standard_department'
                    ).only(
                        'id', 'first_name', 'last_name', 'email',
                        'job_title', 'standard_department_id'
                    )
                )
            ).only(
                'id', 'title', 'activity_type', 'status', 'outcome',
                'scheduled_date', 'scheduled_time', 'due_date', 'completed_at',
                'owner_id', 'decision_step_id', 'created_at'
            ).order_by('-scheduled_date', '-created_at')
        )
        
        # Build cycle queryset with annotations
        # NOTE: Use different names to avoid conflict with model @property
        # annotate_deal_value carries the product roll-up (_deal_value) that
        # DecisionCycleTimelineSerializer.total_deal_value reads — an ISOLATED
        # correlated subquery per row, so it neither fans out against the steps
        # Count above nor costs one query per cycle. It is what the DC workspace
        # header and the Products tab display.
        queryset = annotate_effective_close_date(annotate_deal_value(DecisionCycle.objects.filter(
            client_id=self.get_client_id(),
            account_id=account_id
        ).select_related(
            'account', 'owner', 'updated_by'
        ).annotate(
            _annotated_steps_count=Count('steps', distinct=True),
            # NOTE: validated_steps_count is now DERIVED (bulk context) in the
            # timeline serializer — the stored-column annotation was stale (~0).
        ))).prefetch_related(
            Prefetch('steps', queryset=steps_queryset),
            activities_prefetch
        ).order_by('-is_active', '-updated_at')

        # =====================================================================
        # BULK SERVICE COMPUTATION
        # Results are injected into serializer context so serializers read
        # from dicts instead of recomputing per instance.
        # =====================================================================
        cycles = list(queryset)

        # Collect all prefetched steps across all cycles
        all_steps = []
        for cycle in cycles:
            cycle_steps = getattr(cycle, '_prefetched_objects_cache', {}).get('steps', [])
            all_steps.extend(cycle_steps)

        # Bulk step aggregation (contacts count, departments, effective dates)
        from ..services import (
            StepAggregationService,
            StepStatusDerivationService,
            CycleAggregationService,
        )

        step_aggregations = StepAggregationService().get_bulk_aggregation(all_steps)

        # Bulk status derivation (derived_status, color — replaces manual status)
        step_derived_statuses = StepStatusDerivationService().derive_bulk(all_steps)

        # Bulk cycle summaries (cycle_status, progress, stalled_steps_count, is_at_risk)
        cycle_summaries = CycleAggregationService().get_bulk_summaries(
            cycles,
            step_derived_statuses=step_derived_statuses,
        )

        logger.debug("by_account_bulk_services_computed", extra={
            **ctx,
            'account_id': account_id,
            'cycles_count': len(cycles),
            'steps_count': len(all_steps),
        })

        # Use timeline-optimized serializer with pre-computed context
        serializer = DecisionCycleTimelineSerializer(
            cycles,
            many=True,
            context={
                'request': request,
                'step_aggregations': step_aggregations,
                'step_derived_statuses': step_derived_statuses,
                'cycle_summaries': cycle_summaries,
            }
        )

        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(cycles)
            }
        }


# ============================================================================
# DECISION STEP VIEWSET
# ============================================================================

class DecisionStepViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Decision Steps (Pipeline Stages).
    
    IMPORTANT: Steps are AUTO-CREATED when a Decision Cycle is created.
    Users CANNOT create or delete steps manually - they are fixed pipeline stages.
    Users CAN only:
        - View steps
        - Update step details (name, expected_end, stakeholder, etc.)
        - Add activities within steps
    
    Features:
        - Client-scoped data isolation (multi-tenant)
        - Permission-based access control
        - Fixed pipeline structure (7 stages)
        
    Endpoints:
        - GET    /decision-steps/                     - List all steps
        - POST   /decision-steps/                     - BLOCKED (auto-created)
        - GET    /decision-steps/{id}/                - Retrieve step
        - PUT    /decision-steps/{id}/                - Update step details
        - PATCH  /decision-steps/{id}/                - Partial update
        - DELETE /decision-steps/{id}/                - BLOCKED (fixed structure)
        - PATCH  /decision-steps/{id}/status/         - Update step status
    """
    
    queryset = DecisionStep.objects.all()
    serializer_class = DecisionStepSerializer
    entity_name = 'decision_step'
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'cycle': ['exact'],
        'stage': ['exact'],
    }
    search_fields = ['name', 'description', 'stakeholder']
    ordering_fields = ['name', 'stage', 'order', 'created_at', 'updated_at']
    ordering = ['order', 'created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'
    
    # Action policies
    action_policies = {
        'by_cycle': {
            'crud': 'read',
            'scope': 'client'
        },
    }
    
    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'list':
            return DecisionStepListSerializer
        elif self.action == 'create':
            return DecisionStepCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DecisionStepUpdateSerializer
        return DecisionStepSerializer
    
    def get_queryset(self):
        """Get steps with optimized queries."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'DecisionStepViewSet'
        })
        
        queryset = super().get_queryset()
        
        queryset = queryset.select_related(
            'cycle',
            'cycle__account',
            'previous_step'
        ).prefetch_related(
            'contacts',
            'next_steps',
            'step_departments__department',
            'step_contacts__contact'
        )
        
        # Filter by cycle if provided
        cycle_id = self.request.query_params.get('cycle_id')
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)
        
        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)
        
        return queryset
    
    # ==========================================================================
    # CRUD OVERRIDES
    # ==========================================================================
    
    def list(self, request, *args, **kwargs):
        """List decision steps with pagination."""
        ctx = ctx_from_request(request)
        logger.info("decision_steps_list_requested", extra=ctx)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single decision step with Redis caching.
        
        GET /decision-cycles/steps/{id}/
        
        Cache: 60s, tag 'decision_cycles', keyed by step pk.
        
        Note: DecisionStepSerializer triggers multiple DB queries per step
        (derived_status, completeness_score, aggregated_contacts, etc.).
        Caching avoids re-executing these on repeated navigation.
        """
        ctx = ctx_from_request(request)
        pk = kwargs.get('pk')
        
        logger.info("decision_step_retrieved", extra={
            **ctx,
            'step_id': str(pk)
        })
        
        if not _is_redis_backend():
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'success': True,
                'data': serializer.data
            })
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='decision_step_detail',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            extra=str(pk),
            tag_namespace='decision_cycles',
        )
        
        def producer():
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return {
                'success': True,
                'data': serializer.data
            }
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'decision_cycles'),
        )
        
        return Response(cached_data)
    
    def create(self, request, *args, **kwargs):
            """
            BLOCKED: Pipeline steps cannot be created manually.
            
            Steps are auto-created when a Decision Cycle is created.
            Users can only add activities within existing steps.
            """
            ctx = ctx_from_request(request)
            logger.warning("decision_step_manual_create_blocked", extra=ctx)
            
            raise StandardizedValidationError(
                CoreErrorMessages.PERMISSION_DENIED
            )

    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update a decision step."""
        ctx = ctx_from_request(request)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info("decision_step_update_requested", extra={
            **ctx,
            'step_id': str(instance.id)
        })
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='decision_step_update_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_step',
            target_id=str(instance.id),
            fields_changed=list(serializer.validated_data.keys()),
            outcome='success'
        )
        
        logger.info("decision_step_updated", extra={
            **ctx,
            'step_id': str(instance.id)
        })
        
        output_serializer = DecisionStepSerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        BLOCKED: Pipeline steps cannot be deleted manually.
        
        Steps are fixed pipeline stages. To remove a step's content,
        delete the activities within it instead.
        """
        ctx = ctx_from_request(request)
        logger.warning("decision_step_manual_delete_blocked", extra=ctx)
        
        raise StandardizedValidationError(
            CoreErrorMessages.PERMISSION_DENIED
        )
    
    
# ============================================================================
# CHOICES VIEW
# ============================================================================

class DecisionCycleChoicesView(APIView):
    """
    API view for retrieving Decision Cycle choices.
    
    GET /decision-cycles/choices/
    
    Returns:
        - pipeline_steps: Fixed pipeline steps with order and config
        - statuses: Available step statuses
    """
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return available choices for pipeline steps and statuses."""
        ctx = ctx_from_request(request)
        logger.info("decision_cycle_choices_requested", extra=ctx)
        
        # Build pipeline steps with full configuration
        pipeline_steps = []
        for config in PIPELINE_STEPS_CONFIG:
            pipeline_steps.append({
                'value': config['step'].value,
                'label': config['step'].label,
                'order': config['order'],
                'activity_optional': config['activity_optional'],
                'description': config['description'],
            })
        
        return Response({
            'success': True,
            'data': {
                # New: Full pipeline step configuration
                'pipeline_steps': pipeline_steps,
                
                # Legacy alias for backward compatibility
                'stages': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in PipelineStep.choices
                ],
                
                # Step statuses
                'statuses': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in DecisionStepStatus.choices
                ]
            }
        })