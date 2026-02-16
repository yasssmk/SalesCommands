# app_modules/decision_cycles/views/views.py
"""
ViewSets for Decision Cycle module.

Follows CompanyAccountViewSet patterns for consistency.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Prefetch, Count, Q

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

from ..models import DecisionCycle, DecisionStep
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

logger = get_logger(__name__)


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
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'account': ['exact'],
        'is_active': ['exact'],
    }
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'is_active', 'created_at', 'updated_at']
    ordering = ['-is_active', '-updated_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'
    
    # Action policies
    # Action policies
    action_policies = {
        'by_account': {
            'crud': 'read',
            'scope': 'client'
        }
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
            # List: minimal data for table display (no activities, no deep nesting)
            queryset = queryset.select_related('account', 'owner').prefetch_related(
                Prefetch(
                    'steps',
                    queryset=DecisionStep.objects.only(
                        'id', 'cycle_id', 'name', 'stage', 'status', 'order'
                    ).order_by('order')
                )
            )
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
            
            queryset = queryset.select_related('account', 'owner').prefetch_related(
                Prefetch(
                    'steps',
                    queryset=DecisionStep.objects.select_related('previous_step').order_by('order')
                ),
                activities_prefetch
            )
        else:
            # Create/Update/Delete: minimal - just account and owner
            queryset = queryset.select_related('account', 'owner')
        
        # Apply owner scope filter (mine/team/all)
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
                status=DecisionStepStatus.NOT_STARTED,
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
        queryset = DecisionCycle.objects.filter(
            client_id=self.get_client_id(),
            account_id=account_id
        ).select_related(
            'account', 'owner', 'updated_by'
        ).annotate(
            _annotated_steps_count=Count('steps', distinct=True),
            _annotated_validated_steps_count=Count(
                'steps',
                filter=Q(steps__status='VALIDATED'),
                distinct=True
            )
        ).prefetch_related(
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
        'status': ['exact'],
    }
    search_fields = ['name', 'description', 'stakeholder']
    ordering_fields = ['name', 'stage', 'status', 'order', 'created_at', 'updated_at']
    ordering = ['order', 'created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'
    
    # Action policies
    action_policies = {
        'update_status': {
            'crud': 'update',
            'scope': 'client'
        },
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
    
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """
        Update step status only.

        PATCH /decision-steps/{id}/status/
        Body: { "status": "VALIDATED" }

        Auto-sets:
            - start_date when status changes to IN_PROGRESS
            - completed_at when status changes to VALIDATED or REJECTED
        """
        from django.utils import timezone
        
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        new_status = request.data.get('status')
        if not new_status:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Status')
            )
        
        valid_statuses = [choice[0] for choice in DecisionStepStatus.choices]
        if new_status not in valid_statuses:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Status')
            )
        
        old_status = instance.status
        instance.status = new_status
        
        # Track which fields changed
        update_fields = ['status', 'updated_at', 'updated_by']
        fields_changed = ['status']
        
        # Auto-set start_date when moving to IN_PROGRESS
        if new_status == DecisionStepStatus.IN_PROGRESS and not instance.start_date:
            instance.start_date = timezone.now()
            update_fields.append('start_date')
            fields_changed.append('start_date')
        
        # Auto-set completed_at when VALIDATED or REJECTED
        if new_status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
            if not instance.completed_at:
                instance.completed_at = timezone.now()
                update_fields.append('completed_at')
                fields_changed.append('completed_at')
        elif old_status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
            # If reverting from terminal status, clear completed_at
            instance.completed_at = None
            update_fields.append('completed_at')
            fields_changed.append('completed_at')
        
        instance.save(user=request.user, update_fields=update_fields)
        
        # Audit log
        audit_log(
            event='decision_step_status_update_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_step',
            target_id=str(instance.id),
            fields_changed=fields_changed,
            outcome='success'
        )
        
        logger.info("decision_step_status_updated", extra={
            **ctx,
            'step_id': str(instance.id),
            'old_status': old_status,
            'new_status': new_status
        })
        
        serializer = DecisionStepSerializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })

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