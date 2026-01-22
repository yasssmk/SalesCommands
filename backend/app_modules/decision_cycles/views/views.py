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
from django.db.models import Prefetch

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from ..models import DecisionCycle, DecisionStep
from ..serializers import (
    DecisionCycleSerializer,
    DecisionCycleListSerializer,
    DecisionCycleCreateSerializer,
    DecisionCycleUpdateSerializer,
    DecisionStepSerializer,
    DecisionStepListSerializer,
    DecisionStepCreateSerializer,
    DecisionStepUpdateSerializer,
)
from ..constants import PipelineStep, DecisionStepStatus, PIPELINE_STEPS_CONFIG

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
    action_policies = {
        'by_account': {
            'crud': 'read',
            'scope': 'client'
        },
    }
    
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
        """Get cycles with optimized queries."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'DecisionCycleViewSet'
        })
        
        queryset = super().get_queryset()
        
        # Import Activity model for prefetch
        from app_modules.activities.models import Activity
        
        # Prefetch for activities in timeline (limited, ordered)
        activities_prefetch = Prefetch(
            'steps__activities',
            queryset=Activity.objects.select_related('owner').prefetch_related(
                'contacts'
            ).order_by('scheduled_date', 'scheduled_time', '-created_at')[:10],
            to_attr='_prefetched_timeline_activities'
        )
        
        if self.action == 'list':
            # List: include activities for pipeline timeline display
            queryset = queryset.select_related('account').prefetch_related(
                'steps',
                'steps__step_departments__department',
                'steps__activities',
                'steps__activities__contacts'
            )
        elif self.action == 'retrieve':
            # Retrieve: full data including activities for timeline
            queryset = queryset.select_related('account').prefetch_related(
                'steps',
                'steps__previous_step',
                'steps__contacts',
                'steps__step_departments__department',
                'steps__step_contacts__contact',
                'steps__activities',
                'steps__activities__owner',
                'steps__activities__contacts'
            )
        else:
            queryset = queryset.select_related('account')
        
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
        All 7 steps are created automatically in order:
        1. Qualification
        2. Technical Fit
        3. Solution Validation
        4. Business Case
        5. Closing
        6. Implementation
        7. Go Live
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
        Create all fixed pipeline steps for a new cycle.
        
        Steps are created in order with linked-list relationships.
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
        Get all decision cycles for a specific account.
        
        GET /decision-cycles/by-account/{account_id}/
        
        Returns full cycle data including steps with activities for timeline display.
        """
        ctx = ctx_from_request(request)
        logger.info("decision_cycles_by_account_requested", extra={
            **ctx,
            'account_id': account_id
        })
        
        # Import Activity model for prefetch
        from app_modules.activities.models import Activity
        
        # Build optimized queryset with activities for timeline
        queryset = self.get_queryset().filter(account_id=account_id)
        queryset = queryset.prefetch_related(
            'steps__activities',
            'steps__activities__owner',
            'steps__activities__contacts'
        )
        
        # Use full serializer to include nested steps with activities
        serializer = DecisionCycleSerializer(queryset, many=True)
        
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })


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
        """Retrieve a single decision step."""
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("decision_step_retrieved", extra={
            **ctx,
            'step_id': str(instance.id)
        })
        
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
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
            - started_at when status changes to IN_PROGRESS
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
        
        # Auto-set started_at when moving to IN_PROGRESS
        if new_status == DecisionStepStatus.IN_PROGRESS and not instance.started_at:
            instance.started_at = timezone.now()
            update_fields.append('started_at')
            fields_changed.append('started_at')
        
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