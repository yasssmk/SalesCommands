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
from core.error_messages import CoreErrorMessages, ActivityErrorMessages
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
from ..constants import NoNextStepReason

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

    # ==========================================================================
    # CACHE HELPERS
    # ==========================================================================

    def _invalidate_activity_caches(self, client_id):
        """
        Invalidate all activity-related caches and cross-module dependencies.

        When an activity changes, we must invalidate:
        - Activity cache (list, detail, filtered views)
        - Account cache (workspace stats, activities_count)
        - Decision cycle cache (timeline: activities per step)
        """
        client_id_str = str(client_id)
        invalidate_tag(client_id_str, 'activities')
        invalidate_tag(client_id_str, 'accounts')
        invalidate_tag(client_id_str, 'decision_cycles')

        logger.info('cache_invalidation_activity', extra={
            'event': 'cache_invalidation',
            'client_id': client_id_str,
            'tags': ['activities', 'accounts', 'decision_cycles'],
        })
    
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
        Retrieve a single activity with Redis caching.
        GET /activities/{id}/
        
        Cache: 60s, tag 'activities', keyed by activity pk.
        """
        ctx = ctx_from_request(request)
        pk = kwargs.get('pk')
        
        # Skip cache if no Redis
        if not _is_redis_backend():
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
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activity_detail',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            extra=str(pk),
            tag_namespace='activities',
        )
        
        def producer():
            instance = self.get_object()
            serializer = ActivitySerializer(instance, context={'request': request})
            return {
                'success': True,
                'data': serializer.data
            }
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        logger.info("activity_retrieved", extra={
            **ctx,
            'activity_id': str(pk),
        })
        
        return Response(cached_data)
    
    def list(self, request, *args, **kwargs):
        """
        List activities with pagination and Redis caching.
        GET /activities/
        
        Cache: 60s, tag 'activities', includes query_string for filter uniqueness.
        """
        ctx = ctx_from_request(request)
        logger.info("activities_list_requested", extra=ctx)
        
        # Skip cache if no Redis
        if not _is_redis_backend():
            return self._list_uncached(request, ctx)
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_list',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        def producer():
            return self._list_uncached_data(request)
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        logger.info("activities_list_success", extra={
            **ctx,
            'count': cached_data.get('data', {}).get('count', '-') if isinstance(cached_data.get('data'), dict) else '-',
        })
        
        return Response(cached_data)
    
    def _list_uncached(self, request, ctx):
        """Fallback list without cache (FileBasedCache or Redis down)."""
        data = self._list_uncached_data(request)
        
        logger.info("activities_list_success", extra={
            **ctx,
            'count': data.get('data', {}).get('count', '-') if isinstance(data.get('data'), dict) else '-',
        })
        
        return Response(data)
    
    def _list_uncached_data(self, request):
        """Produce list data dict (cache-friendly, no Response object)."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = self.get_serializer(queryset, many=True)
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }

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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(client_id)
        
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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(client_id)
        
        logger.info("activity_updated", extra={
            **ctx_from_request(self.request),
            'activity_id': str(instance.id),
        })
    
    def perform_destroy(self, instance):
        """
        Delete activity with linked list cleanup and audit logging.
        
        Uses direct database updates to avoid unique constraint violations
        on OneToOneField (next_activity_id, previous_activity_id).
        
        Strategy:
            1. Capture adjacent activity IDs before any modification
            2. Clear links on the instance being deleted (breaks the chain)
            3. Reconnect adjacent activities
            4. Delete the instance
        """
        user = self.request.user
        client_id = self.get_client_id()
        activity_id = str(instance.id)
        account_id = str(instance.account_id)
        
        # Capture adjacent activity IDs before modification
        previous_id = instance.previous_activity_id
        next_id = instance.next_activity_id
        
        # Step 1: Clear links on the instance being deleted
        # This releases the unique constraint on next_activity_id and previous_activity_id
        Activity.objects.filter(id=instance.id).update(
            previous_activity=None,
            next_activity=None
        )
        
        # Step 2: Reconnect adjacent activities
        if previous_id and next_id:
            # Chain: A → [B] → C  becomes  A → C
            Activity.objects.filter(id=previous_id).update(next_activity=next_id)
            Activity.objects.filter(id=next_id).update(previous_activity=previous_id)
        elif previous_id:
            # Chain: A → [B]  becomes  A (end)
            Activity.objects.filter(id=previous_id).update(next_activity=None)
        elif next_id:
            # Chain: [B] → C  becomes  C (start)
            Activity.objects.filter(id=next_id).update(previous_activity=None)
        
        # Step 3: Delete the instance
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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(client_id)
        
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
        
        Note: Cycle-level close (WON/LOST/ON_HOLD) is handled by
        DecisionCycleViewSet.close(), not here.
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
                ActivityErrorMessages.CANNOT_COMPLETE_CANCELLED
            )
        
        outcome = request.data.get('outcome')
        outcome_notes = request.data.get('outcome_notes') or request.data.get('notes')
        
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
            
            if outcome is not None:
                activity.outcome = outcome
            if outcome_notes is not None:
                activity.outcome_notes = outcome_notes
            
            activity.save(user=request.user)
            
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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(self.get_client_id())
        
        logger.info("activity_completed", extra={
            **ctx,
            'activity_id': str(activity.id),
            'outcome': outcome,
        })
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response({
            'success': True,
            'data': serializer.data,
        })
    
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def reopen(self, request, pk=None):
        """
        Reopen a completed or cancelled activity.
        
        POST /activities/{id}/reopen/
        
        Behavior:
            - Clears outcome, outcome_notes, and completed_at
            - Sets status back to PLANNED
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
                ActivityErrorMessages.CANNOT_REOPEN
            )
        
        # Cannot reopen activity if parent cycle is closed
        if (
            hasattr(activity, 'decision_step')
            and activity.decision_step_id
            and activity.decision_step.cycle
            and activity.decision_step.cycle.outcome is not None
        ):
            raise StandardizedValidationError(
                ActivityErrorMessages.CANNOT_REOPEN_CLOSED_CYCLE
            )
        
        old_status = activity.status
        
        # Clear outcome fields and reopen as PLANNED
        activity.status = ActivityStatus.PLANNED
        activity.outcome = None
        activity.outcome_notes = None
        activity.completed_at = None
        
        activity.save(user=request.user)
        target_status = activity.status
        
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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(self.get_client_id())
        
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
                ActivityErrorMessages.CANNOT_CANCEL_COMPLETED
            )
        
        if activity.status == ActivityStatus.CANCELLED:
            raise StandardizedValidationError(
                ActivityErrorMessages.ALREADY_CANCELLED
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
        
        # Invalidate caches (activities + cross-module)
        self._invalidate_activity_caches(self.get_client_id())
        
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
        inline_step_stage = request.data.get('inline_step_stage')
        
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
            inline_step_stage=inline_step_stage,
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
        
        # Invalidate caches (activities + accounts + decision_cycles)
        self._invalidate_activity_caches(self.get_client_id())
        # Additional: contacts cache only if inline contact was created
        if result['contact']:
            invalidate_tag(str(self.get_client_id()), 'contacts')
        
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
        
        # Build created_entities with detailed info
        created_entities = {}

        if result['contact']:
            created_entities['contact'] = {
                'id': str(result['contact'].id),
                'first_name': result['contact'].first_name,
                'last_name': result['contact'].last_name,
                'full_name': f"{result['contact'].first_name} {result['contact'].last_name}",
                'email': result['contact'].email,
                'phone_number': str(result['contact'].phone_number) if result['contact'].phone_number else None,
                'job_title': result['contact'].job_title,
            }

        if result['cycle']:
            created_entities['cycle'] = {
                'id': str(result['cycle'].id),
                'name': result['cycle'].name,
                'is_active': result['cycle'].is_active,
                'steps_count': result['cycle'].steps.count(),
            }

        if result['step']:
            created_entities['step'] = {
                'id': str(result['step'].id),
                'name': result['step'].name,
                'stage': result['step'].stage,
                'order': result['step'].order,
            }

        # Build summary
        entities_created = []
        if result['contact']:
            entities_created.append('contact')
        if result['cycle']:
            entities_created.append('cycle')

        response_data = {
            'activity': activity_serializer.data,
            'created_entities': created_entities if created_entities else None,
            'summary': {
                'entities_created': entities_created,
                'has_inline_creations': len(entities_created) > 0,
                'step_auto_assigned': result['cycle'] is not None,  # Step was auto-assigned if cycle was inline
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
        Get current user's activities with Redis caching.
        
        GET /activities/my-activities/
        
        Cache: 60s, tag 'activities', scoped by user_id + query_string.
        """
        ctx = ctx_from_request(request)
        logger.info("my_activities_requested", extra=ctx)
        
        if not _is_redis_backend():
            return Response(self._produce_my_activities(request))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_my',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_my_activities(request),
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_my_activities(self, request):
        """Produce my_activities data dict (cache-friendly)."""
        queryset = self.get_queryset().filter(owner=request.user)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }
    
    @action(detail=False, methods=['get'])
    def by_account(self, request):
        """
        Get activities for a specific account with Redis caching.
        
        GET /activities/by-account/?account_id={uuid}
        
        Cache: 60s, tag 'activities', account_id included via query_string hash.
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
        
        if not _is_redis_backend():
            return Response(self._produce_by_account(request, account_id))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_by_account',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_by_account(request, account_id),
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_by_account(self, request, account_id):
        """Produce by_account data dict (cache-friendly)."""
        queryset = self.get_queryset().filter(account_id=account_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }
    
    @action(detail=False, methods=['get'])
    def by_step(self, request):
        """
        Get activities for a specific decision step with Redis caching.
        
        GET /activities/by-step/?step_id={uuid}
        
        Cache: 60s, tag 'activities', step_id included via query_string hash.
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
        
        if not _is_redis_backend():
            return Response(self._produce_by_step(request, step_id))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_by_step',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_by_step(request, step_id),
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_by_step(self, request, step_id):
        """Produce by_step data dict (cache-friendly)."""
        queryset = self.get_queryset().filter(decision_step_id=step_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue activities for current user with Redis caching.
        
        GET /activities/overdue/
        
        Cache: 30s (time-dependent: results change as time passes).
        """
        ctx = ctx_from_request(request)
        logger.info("overdue_activities_requested", extra=ctx)
        
        if not _is_redis_backend():
            return Response(self._produce_overdue(request))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_overdue',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_overdue(request),
            ttl=30,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_overdue(self, request):
        """Produce overdue data dict (cache-friendly)."""
        queryset = self.get_queryset().filter(
            owner=request.user,
            status=ActivityStatus.PLANNED,
            due_date__lt=timezone.now().date()
        )
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming activities for current user with Redis caching.
        
        GET /activities/upcoming/
        
        Cache: 30s (time-dependent: results change as time passes).
        """
        ctx = ctx_from_request(request)
        logger.info("upcoming_activities_requested", extra=ctx)
        
        if not _is_redis_backend():
            return Response(self._produce_upcoming(request))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_upcoming',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_upcoming(request),
            ttl=30,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_upcoming(self, request):
        """Produce upcoming data dict (cache-friendly)."""
        queryset = self.get_queryset().filter(
            owner=request.user,
            status=ActivityStatus.PLANNED,
            scheduled_date__gte=timezone.now().date()
        ).order_by('scheduled_date', 'scheduled_time')
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return {
                'success': True,
                'data': {
                    'results': serializer.data,
                    'count': self.paginator.page.paginator.count,
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                }
            }
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }
    
    @action(detail=False, methods=['get'], url_path='unlinked/by-account/(?P<account_id>[^/.]+)')
    def unlinked_for_account(self, request, account_id=None):
        """
        Get activities not linked to any decision step for a specific account.
        
        GET /activities/unlinked/by-account/{account_id}/
        
        Cache: 60s, tag 'activities', keyed by account_id + query params.
        
        Query params:
            - exclude_cancelled: bool (default: true) - Exclude cancelled activities
            - limit: int (default: 50) - Maximum results to return
        """
        ctx = ctx_from_request(request)
        logger.info("unlinked_activities_by_account_requested", extra={
            **ctx,
            'account_id': account_id
        })
        
        if not _is_redis_backend():
            return Response(self._produce_unlinked_for_account(request, account_id))
        
        client_id = self.get_client_id()
        cache_key = build_drf_cache_key(
            namespace='activities_unlinked',
            client_id=client_id,
            user_id=request.user.id,
            perm_version=get_permissions_version(),
            query_string=request.META.get('QUERY_STRING', ''),
            extra=str(account_id),
            tag_namespace='activities',
        )
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=lambda: self._produce_unlinked_for_account(request, account_id),
            ttl=60,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    def _produce_unlinked_for_account(self, request, account_id):
        """Produce unlinked_for_account data dict (cache-friendly)."""
        # Parse query params
        exclude_cancelled = request.query_params.get('exclude_cancelled', 'true').lower() == 'true'
        limit = min(int(request.query_params.get('limit', 50)), 100)
        
        # Build queryset
        queryset = self.get_queryset().filter(
            account_id=account_id,
            decision_step__isnull=True
        ).select_related(
            'owner',
            'decision_cycle'
        ).prefetch_related(
            'contacts'
        ).order_by('-scheduled_date', '-created_at')
        
        # Optionally exclude cancelled
        if exclude_cancelled:
            queryset = queryset.exclude(status=ActivityStatus.CANCELLED)
        
        # Limit results
        queryset = queryset[:limit]
        
        serializer = ActivityListSerializer(queryset, many=True)
        
        return {
            'success': True,
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        }


# ============================================================================
# CHOICES VIEW
# ============================================================================

class ActivityChoicesView(APIView):
    """
    API endpoint for retrieving activity choices (types, statuses, outcomes).
    
    GET /activities/choices/
    
    Cache: 300s (5 minutes) - Static enum data, only changes on redeploy.
    """
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return all activity choices with Redis caching."""
        logger.info("activity_choices_requested", extra=ctx_from_request(request))
        
        client_id = getattr(request.user, 'client_account_id', None)
        
        # Skip cache if no Redis or no tenant context
        if not _is_redis_backend() or not client_id:
            return Response({
                'success': True,
                'data': self._build_choices_data()
            })
        
        cache_key = build_drf_cache_key(
            namespace='activity_choices',
            client_id=client_id,
            perm_version=get_permissions_version(),
            tag_namespace='activities',
        )
        
        def producer():
            return {
                'success': True,
                'data': self._build_choices_data()
            }
        
        cached_data = cache_get_set(
            key=cache_key,
            producer=producer,
            ttl=300,
            tag=(client_id, 'activities'),
        )
        
        return Response(cached_data)
    
    @staticmethod
    def _build_choices_data():
        """Build choices dict from enums. Extracted for cache producer reuse."""
        return {
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
            ],
        }