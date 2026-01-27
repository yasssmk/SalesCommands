# app_modules/activities/views/views.py
"""
ViewSets for Activity module.

Follows CompanyAccountViewSet and DecisionCycleViewSet patterns.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.utils import timezone

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

from ..models import Activity
from ..serializers import (
    ActivitySerializer,
    ActivityListSerializer,
    ActivityCreateSerializer,
    ActivityUpdateSerializer,
)
from ..constants import ActivityType, ActivityStatus, ActivityOutcome
from ..filters import ActivityFilter
from ..services.activity_creation_service import ActivityCreationService
from ..constants import ActivityType, ActivityStatus, ActivityOutcome
from ..filters import ActivityFilter

logger = get_logger(__name__)


# ============================================================================
# ACTIVITY VIEWSET
# ============================================================================

class ActivityViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Activities.

    Follows CompanyAccountViewSet and DecisionCycleViewSet patterns.
    
    Features:
        - Client-scoped data isolation (multi-tenant)
        - Permission-based access control
        - Owner scope filtering (mine/team/all)
        - Linked-list navigation (previous/next)
        
    Endpoints:
        GET    /activities/              - List activities
        POST   /activities/              - Create activity
        GET    /activities/{id}/         - Retrieve activity
        PUT    /activities/{id}/         - Update activity
        PATCH  /activities/{id}/         - Partial update
        DELETE /activities/{id}/         - Delete activity
        
        POST   /activities/{id}/complete/  - Complete activity
        POST   /activities/{id}/cancel/    - Cancel activity
        
        GET    /activities/my-activities/  - Current user's activities
        GET    /activities/by-account/     - Activities for an account
        GET    /activities/by-step/        - Activities for a decision step
        GET    /activities/overdue/        - Overdue activities
        GET    /activities/upcoming/       - Upcoming activities
    """
    
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    entity_name = 'activity'
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityFilter
    search_fields = ['title', 'description', 'call_to_action']
    ordering_fields = ['title', 'scheduled_date', 'due_date', 'status', 'created_at', 'updated_at']
    ordering = ['-scheduled_date', '-created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'activities'
    
    # Action policies for custom actions
    action_policies = {
        'complete': {
            'crud': 'update',
            'scope': 'client'
        },
        'reopen': {
            'crud': 'update',
            'scope': 'client'
        },
        'cancel': {
            'crud': 'update',
            'scope': 'client'
        },
        'create_with_entities': {
            'crud': 'create',
            'scope': 'client'
        },
        'my_activities': {
            'crud': 'read',
            'scope': 'mine'
        },
        'by_account': {
            'crud': 'read',
            'scope': 'client'
        },
        'by_step': {
            'crud': 'read',
            'scope': 'client'
        },
        'overdue': {
            'crud': 'read',
            'scope': 'client'
        },
        'upcoming': {
            'crud': 'read',
            'scope': 'client'
        },
        'unlinked_for_account': {
            'crud': 'read',
            'scope': 'client'
        }
    }
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ActivityListSerializer
        elif self.action == 'create':
            return ActivityCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ActivityUpdateSerializer
        return ActivitySerializer
    
    def get_queryset(self):
        """
        Get filtered queryset with optimized prefetching based on action.
        """
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'ActivityViewSet'
        })
        
        queryset = super().get_queryset()
        
        # Optimize based on action
        if self.action == 'list':
            # List: minimal relations for table display
            queryset = queryset.select_related(
                'account',
                'owner',
                'decision_step'
            )
        elif self.action == 'retrieve':
            # Retrieve: full relations for detail view
            queryset = queryset.select_related(
                'account',
                'owner',
                'decision_cycle',
                'decision_step',
                'previous_activity',
                'next_activity',
                'created_by',
                'updated_by'
            ).prefetch_related(
                'contacts',
                'contacts__standard_department',
                'invited_users'
            )
        else:
            # Default: moderate optimization
            queryset = queryset.select_related(
                'account',
                'owner',
                'decision_cycle',
                'decision_step'
            )
        
        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single activity.
        GET /activities/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("activity_retrieved", extra={
            **ctx,
            'activity_id': str(instance.id),
        })
        
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    def list(self, request, *args, **kwargs):
        """
        List activities with pagination.
        GET /activities/
        """
        ctx = ctx_from_request(request)
        logger.info("activities_list_requested", extra=ctx)
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            
            logger.info("activities_list_success", extra={
                **ctx,
                'count': response.data.get('count', 0)
            })
            
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

    # ==========================================================================
    # CRUD OPERATIONS
    # ==========================================================================    
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new activity.
        POST /activities/
        """
        ctx = ctx_from_request(request)
        logger.info("activity_create_requested", extra=ctx)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return full serializer for response
        output_serializer = ActivitySerializer(
            serializer.instance,
            context={'request': request}
        )
        
        return Response({
            'success': True,
            'data': output_serializer.data
        }, status=status.HTTP_201_CREATED)
    
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update an activity (full update).
        PUT /activities/{id}/
        """
        ctx = ctx_from_request(request)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        logger.info("activity_update_requested", extra={
            **ctx,
            'activity_id': str(instance.id),
            'partial': partial,
        })
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return full serializer for response
        output_serializer = ActivitySerializer(instance, context={'request': request})
        
        return Response({
            'success': True,
            'data': output_serializer.data
        })
    
    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Partial update an activity.
        PATCH /activities/{id}/
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete an activity.
        DELETE /activities/{id}/
        """
        ctx = ctx_from_request(request)
        instance = self.get_object()
        
        logger.info("activity_delete_requested", extra={
            **ctx,
            'activity_id': str(instance.id),
        })
        
        self.perform_destroy(instance)
        
        return Response({
            'success': True,
            'data': None
        }, status=status.HTTP_204_NO_CONTENT)
    
    # ==========================================================================
    # CRUD HOOKS
    # ==========================================================================

    def perform_create(self, serializer):
        """Create activity with audit logging."""
        user = self.request.user
        client_id = self.get_client_id()
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='activity_create_success',
            action='create',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='activity',
            target_id=str(instance.id),
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'activities')
        
        logger.info("activity_created", extra={
            **ctx_from_request(self.request),
            'activity_id': str(instance.id),
            'account_id': str(instance.account_id),
            'activity_type': instance.activity_type,
        })
    
    
    def perform_update(self, serializer):
        """Update activity with audit logging."""
        user = self.request.user
        client_id = self.get_client_id()
        instance = serializer.instance
        
        serializer.save()
        
        # Audit log
        audit_log(
            event='activity_update_success',
            action='update',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='activity',
            target_id=str(instance.id),
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'activities')
        
        logger.info("activity_updated", extra={
            **ctx_from_request(self.request),
            'activity_id': str(instance.id),
        })
    
    def perform_destroy(self, instance):
        """
        Delete activity with linked list cleanup and audit logging.
        """
        user = self.request.user
        client_id = self.get_client_id()
        activity_id = str(instance.id)
        account_id = str(instance.account_id)
        
        # Update linked list: connect previous to next
        if instance.previous_activity and instance.next_activity:
            instance.previous_activity.next_activity = instance.next_activity
            instance.previous_activity.save()
            instance.next_activity.previous_activity = instance.previous_activity
            instance.next_activity.save()
        elif instance.previous_activity:
            instance.previous_activity.next_activity = None
            instance.previous_activity.save()
        elif instance.next_activity:
            instance.next_activity.previous_activity = None
            instance.next_activity.save()
        
        instance.delete()
        
        # Audit log
        audit_log(
            event='activity_delete_success',
            action='delete',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='activity',
            target_id=activity_id,
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'activities')
        
        logger.info("activity_deleted", extra={
            **ctx_from_request(self.request),
            'activity_id': activity_id,
            'account_id': account_id,
        })
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def complete(self, request, pk=None):
        """
        Mark activity as completed or update outcome if already completed.
        
        POST /activities/{id}/complete/
        
        Body:
            - outcome (optional): ActivityOutcome choice
            - outcome_notes (optional): Outcome notes
        
        Behavior:
            - If not completed: completes the activity with outcome
            - If already completed: updates outcome and outcome_notes only
            - If cancelled: returns error
        """
        ctx = ctx_from_request(request)
        activity = self.get_object()
        
        logger.info("activity_complete_requested", extra={
            **ctx,
            'activity_id': str(activity.id),
            'current_status': activity.status,
        })
        
        # Cannot complete a cancelled activity
        if activity.status == ActivityStatus.CANCELLED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail='Cannot complete a cancelled activity')
            )
        
        outcome = request.data.get('outcome')
        outcome_notes = request.data.get('outcome_notes') or request.data.get('notes')  # Support both field names
        
        # Validate outcome if provided
        if outcome and outcome not in ActivityOutcome.values:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='outcome')
            )
        
        # If already completed, just update outcome fields
        if activity.status == ActivityStatus.COMPLETED:
            logger.info("activity_outcome_update", extra={
                **ctx,
                'activity_id': str(activity.id),
                'old_outcome': activity.outcome,
                'new_outcome': outcome,
            })
            
            # Update outcome fields only
            if outcome is not None:
                activity.outcome = outcome
            if outcome_notes is not None:
                activity.outcome_notes = outcome_notes
            
            activity.save(user=request.user)
            
            # Audit log
            audit_log(
                event='activity_outcome_updated',
                action='update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='activity',
                target_id=str(activity.id),
                outcome='success',
                extra={'activity_outcome': outcome}
            )
        else:
            # Complete the activity
            activity.complete(outcome=outcome, notes=outcome_notes, user=request.user)
            
            # Audit log
            audit_log(
                event='activity_complete_success',
                action='update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='activity',
                target_id=str(activity.id),
                outcome='success',
                extra={'activity_outcome': outcome}
            )
        
        # Invalidate cache
        invalidate_tag(str(self.get_client_id()), 'activities')
        
        logger.info("activity_completed", extra={
            **ctx,
            'activity_id': str(activity.id),
            'outcome': outcome,
        })
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reopen(self, request, pk=None):
        """
        Reopen a completed or cancelled activity.
        
        POST /activities/{id}/reopen/
        
        Body:
            - status (optional): Target status ('PLANNED' or 'IN_PROGRESS'), defaults to 'PLANNED'
        
        Behavior:
            - Clears outcome, outcome_notes, and completed_at
            - Sets status to PLANNED or IN_PROGRESS
            - Only works on COMPLETED or CANCELLED activities
        """
        ctx = ctx_from_request(request)
        activity = self.get_object()
        
        logger.info("activity_reopen_requested", extra={
            **ctx,
            'activity_id': str(activity.id),
            'current_status': activity.status,
        })
        
        # Can only reopen completed or cancelled activities
        if activity.status not in [ActivityStatus.COMPLETED, ActivityStatus.CANCELLED]:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(
                    detail='Only completed or cancelled activities can be reopened'
                )
            )
        
        # Get target status (default to PLANNED)
        target_status = request.data.get('status', ActivityStatus.PLANNED)
        
        # Validate target status
        valid_target_statuses = [ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS]
        if target_status not in valid_target_statuses:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f"status (must be one of: {', '.join(valid_target_statuses)})"
                )
            )
        
        old_status = activity.status
        
        # Clear outcome fields and reopen
        activity.status = target_status
        activity.outcome = None
        activity.outcome_notes = None
        activity.completed_at = None
        
        activity.save(user=request.user)
        
        # Audit log
        audit_log(
            event='activity_reopen_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='activity',
            target_id=str(activity.id),
            outcome='success',
            extra={
                'old_status': old_status,
                'new_status': target_status
            }
        )
        
        # Invalidate cache
        invalidate_tag(str(self.get_client_id()), 'activities')
        
        logger.info("activity_reopened", extra={
            **ctx,
            'activity_id': str(activity.id),
            'old_status': old_status,
            'new_status': target_status,
        })
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """
        Cancel activity.
        
        POST /activities/{id}/cancel/
        
        Body:
            - notes (optional): Cancellation reason
        """
        ctx = ctx_from_request(request)
        activity = self.get_object()
        
        logger.info("activity_cancel_requested", extra={
            **ctx,
            'activity_id': str(activity.id),
        })
        
        # Validate not already completed or cancelled
        if activity.status == ActivityStatus.COMPLETED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail='Cannot cancel a completed activity')
            )
        
        if activity.status == ActivityStatus.CANCELLED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail='Activity is already cancelled')
            )
        
        notes = request.data.get('notes')
        activity.cancel(notes=notes, user=request.user)
        
        # Audit log
        audit_log(
            event='activity_cancel_success',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='activity',
            target_id=str(activity.id),
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(self.get_client_id()), 'activities')
        
        logger.info("activity_cancelled", extra={
            **ctx,
            'activity_id': str(activity.id),
        })
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    @transaction.atomic
    def create_with_entities(self, request):
        """
        Create activity with optional inline entity creation.
        
        POST /activities/create-with-entities/
        
        Body:
            - activity: Activity data (title, activity_type, account_id, etc.)
            - inline_contact: Optional {first_name, last_name, email, ...}
            - inline_cycle: Optional {name}
            - inline_step: Optional {name, stage, expected_end}
        
        Creates entities in FK-safe order:
        1. Contact (if inline_contact provided)
        2. DecisionCycle (if inline_cycle provided)
        3. DecisionStep (if inline_step provided)
        4. Activity with all relations
        
        Returns all created entities.
        """
        ctx = ctx_from_request(request)
        
        logger.info("activity_create_with_entities_requested", extra=ctx)
        
        # Extract data from request
        activity_data = request.data.get('activity', {})
        inline_contact = request.data.get('inline_contact')
        inline_cycle = request.data.get('inline_cycle')
        inline_step = request.data.get('inline_step')
        
        # Validate activity_data exists
        if not activity_data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='activity')
            )
        
        # Create service and execute
        service = ActivityCreationService(
            user=request.user,
            client_id=self.get_client_id()
        )
        
        result = service.create_with_entities(
            activity_data=activity_data,
            inline_contact=inline_contact,
            inline_cycle=inline_cycle,
            inline_step=inline_step,
        )
        
        # Audit log
        audit_log(
            event='activity_create_with_entities_success',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='activity',
            target_id=str(result['activity'].id),
            outcome='success',
            extra={
                'inline_contact_created': result['contact'] is not None,
                'inline_cycle_created': result['cycle'] is not None,
                'inline_step_created': result['step'] is not None,
            }
        )
        
        # Invalidate caches
        client_id_str = str(self.get_client_id())
        invalidate_tag(client_id_str, 'activities')
        if result['contact']:
            invalidate_tag(client_id_str, 'contacts')
        if result['cycle'] or result['step']:
            invalidate_tag(client_id_str, 'decision_cycles')
        
        logger.info("activity_create_with_entities_success", extra={
            **ctx,
            'activity_id': str(result['activity'].id),
            'contact_id': str(result['contact'].id) if result['contact'] else None,
            'cycle_id': str(result['cycle'].id) if result['cycle'] else None,
            'step_id': str(result['step'].id) if result['step'] else None,
        })
        
        # Build response
        activity_serializer = ActivitySerializer(
            result['activity'],
            context={'request': request}
        )
        
        response_data = {
            'activity': activity_serializer.data,
            'created_entities': {
                'contact': {
                    'id': str(result['contact'].id),
                    'name': f"{result['contact'].first_name} {result['contact'].last_name}"
                } if result['contact'] else None,
                'cycle': {
                    'id': str(result['cycle'].id),
                    'name': result['cycle'].name
                } if result['cycle'] else None,
                'step': {
                    'id': str(result['step'].id),
                    'name': result['step'].name
                } if result['step'] else None,
            }
        }
        
        return Response({
            'success': True,
            'data': response_data
        }, status=status.HTTP_201_CREATED)
    
    # ==========================================================================
    # LIST ACTIONS
    # ==========================================================================
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """
        Get current user's activities.
        
        GET /activities/my-activities/
        """
        ctx = ctx_from_request(request)
        logger.info("my_activities_requested", extra=ctx)
        
        queryset = self.get_queryset().filter(owner=request.user)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    @action(detail=False, methods=['get'])
    def by_account(self, request):
        """
        Get activities for a specific account.
        
        GET /activities/by-account/?account_id={uuid}
        """
        ctx = ctx_from_request(request)
        account_id = request.query_params.get('account_id')
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='account_id')
            )
        
        logger.info("activities_by_account_requested", extra={
            **ctx,
            'account_id': account_id,
        })
        
        queryset = self.get_queryset().filter(account_id=account_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    @action(detail=False, methods=['get'])
    def by_step(self, request):
        """
        Get activities for a specific decision step.
        
        GET /activities/by-step/?step_id={uuid}
        """
        ctx = ctx_from_request(request)
        step_id = request.query_params.get('step_id')
        
        if not step_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='step_id')
            )
        
        logger.info("activities_by_step_requested", extra={
            **ctx,
            'step_id': step_id,
        })
        
        queryset = self.get_queryset().filter(decision_step_id=step_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue activities for current user.
        
        GET /activities/overdue/
        """
        ctx = ctx_from_request(request)
        logger.info("overdue_activities_requested", extra=ctx)
        
        queryset = self.get_queryset().filter(
            owner=request.user,
            status=ActivityStatus.PLANNED,
            due_date__lt=timezone.now().date()
        )
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming activities for current user.
        
        GET /activities/upcoming/
        """
        ctx = ctx_from_request(request)
        logger.info("upcoming_activities_requested", extra=ctx)
        
        queryset = self.get_queryset().filter(
            owner=request.user,
            status=ActivityStatus.PLANNED,
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date', 'scheduled_time')
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            response = self.get_paginated_response(serializer.data)
            return Response({
                'success': True,
                'data': response.data
            })
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    @action(detail=False, methods=['get'], url_path='unlinked/by-account/(?P<account_id>[^/.]+)')
    def unlinked_for_account(self, request, account_id=None):
        """
        Get activities not linked to any decision step for a specific account.
        
        GET /activities/unlinked/by-account/{account_id}/
        
        Returns activities where decision_step is NULL, useful for the
        "Link Existing Activity" feature in the pipeline timeline.
        
        Query params:
            - exclude_cancelled: bool (default: true) - Exclude cancelled activities
            - limit: int (default: 50) - Maximum results to return
        """
        ctx = ctx_from_request(request)
        logger.info("unlinked_activities_by_account_requested", extra={
            **ctx,
            'account_id': account_id
        })
        
        # Parse query params
        exclude_cancelled = request.query_params.get('exclude_cancelled', 'true').lower() == 'true'
        limit = min(int(request.query_params.get('limit', 50)), 100)  # Cap at 100
        
        # Build queryset
        queryset = self.get_queryset().filter(
            account_id=account_id,
            decision_step__isnull=True  # Not linked to any step
        ).select_related(
            'owner',
            'decision_cycle'
        ).prefetch_related(
            'contacts'
        ).order_by('-scheduled_date', '-created_at')
        
        # Optionally exclude cancelled
        if exclude_cancelled:
            from app_modules.activities.constants import ActivityStatus
            queryset = queryset.exclude(status=ActivityStatus.CANCELLED)
        
        # Limit results
        queryset = queryset[:limit]
        
        # Use list serializer for lightweight response
        serializer = ActivityListSerializer(queryset, many=True)
        
        return Response({
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })


# ============================================================================
# CHOICES VIEW
# ============================================================================

class ActivityChoicesView(APIView):
    """
    API endpoint for retrieving activity choices (types, statuses, outcomes).
    
    GET /activities/choices/
    """
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return all activity choices."""
        logger.info("activity_choices_requested", extra=ctx_from_request(request))
        
        return Response({
            'success': True,
            'data': {
                'activity_types': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in ActivityType.choices
                ],
                'statuses': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in ActivityStatus.choices
                ],
                'outcomes': [
                    {'value': choice[0], 'label': choice[1]}
                    for choice in ActivityOutcome.choices
                ]
            }
        })