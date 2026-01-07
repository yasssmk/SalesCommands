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
from ..constants import DecisionStage, DecisionStepStatus

logger = get_logger(__name__)


# ============================================================================
# DECISION CYCLE VIEWSET
# ============================================================================

class DecisionCycleViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
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
        queryset = super().get_queryset()
        
        if self.action == 'list':
            queryset = queryset.select_related('account').prefetch_related('steps')
        elif self.action == 'retrieve':
            queryset = queryset.select_related('account').prefetch_related(
                'steps',
                'steps__standard_department',
                'steps__previous_step',
                'steps__contacts'
            )
        else:
            queryset = queryset.select_related('account')
        
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
        """Create a new decision cycle."""
        ctx = ctx_from_request(request)
        logger.info("decision_cycle_create_requested", extra=ctx)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='decision_cycle_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_cycle',
            target_id=str(instance.id),
            outcome='success'
        )
        
        logger.info("decision_cycle_created", extra={
            **ctx,
            'cycle_id': str(instance.id)
        })
        
        # Return full serializer
        output_serializer = DecisionCycleSerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
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
        """
        ctx = ctx_from_request(request)
        logger.info("decision_cycles_by_account_requested", extra={
            **ctx,
            'account_id': account_id
        })
        
        queryset = self.get_queryset().filter(account_id=account_id)
        serializer = DecisionCycleListSerializer(queryset, many=True)
        
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

class DecisionStepViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Decision Steps.
    
    Features:
        - Client-scoped data isolation (multi-tenant)
        - Permission-based access control
        - Linked-list ordering support
        
    Endpoints:
        - GET    /decision-steps/                     - List all steps
        - POST   /decision-steps/                     - Create step
        - GET    /decision-steps/{id}/                - Retrieve step
        - PUT    /decision-steps/{id}/                - Update step (full)
        - PATCH  /decision-steps/{id}/                - Update step (partial)
        - DELETE /decision-steps/{id}/                - Delete step
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
    ordering_fields = ['name', 'stage', 'status', 'created_at', 'updated_at']
    ordering = ['created_at']
    
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
        queryset = super().get_queryset()
        
        queryset = queryset.select_related(
            'cycle',
            'cycle__account',
            'standard_department',
            'previous_step'
        ).prefetch_related('contacts', 'next_steps')
        
        # Filter by cycle if provided
        cycle_id = self.request.query_params.get('cycle_id')
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)
        
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
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create a new decision step."""
        ctx = ctx_from_request(request)
        logger.info("decision_step_create_requested", extra=ctx)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='decision_step_create_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_step',
            target_id=str(instance.id),
            outcome='success'
        )
        
        logger.info("decision_step_created", extra={
            **ctx,
            'step_id': str(instance.id)
        })
        
        output_serializer = DecisionStepSerializer(instance)
        return Response({
            'success': True,
            'data': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
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
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete a decision step and update linked list."""
        ctx = ctx_from_request(request)
        instance = self.get_object()
        step_id = str(instance.id)
        step_name = instance.name
        
        logger.info("decision_step_delete_requested", extra={
            **ctx,
            'step_id': step_id
        })
        
        # Update linked list: connect previous to next
        previous_step = instance.previous_step
        next_steps = list(instance.next_steps.all())
        
        # Point all next steps to the previous step
        for next_step in next_steps:
            next_step.previous_step = previous_step
            next_step.save(update_fields=['previous_step'])
        
        instance.delete()
        
        # Audit log
        audit_log(
            event='decision_step_delete_success',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_step',
            target_id=step_id,
            outcome='success'
        )
        
        logger.info("decision_step_deleted", extra={
            **ctx,
            'step_id': step_id
        })
        
        return Response({
            'success': True,
            'message': 'Decision step deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """
        Update step status only.
        
        PATCH /decision-steps/{id}/status/
        Body: { "status": "VALIDATED" }
        """
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
        instance.save(user=request.user, update_fields=['status', 'updated_at', 'updated_by'])
        
        # Audit log
        audit_log(
            event='decision_step_status_update_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='decision_step',
            target_id=str(instance.id),
            fields_changed=['status'],
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
    """
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return available choices for stages and statuses."""
        ctx = ctx_from_request(request)
        logger.info("decision_cycle_choices_requested", extra=ctx)
        
        return Response({
            'success': True,
            'data': {
                'stages': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in DecisionStage.choices
                ],
                'statuses': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in DecisionStepStatus.choices
                ]
            }
        })