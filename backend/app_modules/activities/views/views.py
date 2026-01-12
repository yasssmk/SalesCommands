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
from core.logging import get_logger

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import Activity
from ..serializers import (
    ActivitySerializer,
    ActivityListSerializer,
    ActivityCreateSerializer,
    ActivityUpdateSerializer,
)
from ..constants import ActivityType, ActivityStatus, ActivityOutcome
from ..filters import ActivityFilter

logger = get_logger(__name__)


# ============================================================================
# ACTIVITY VIEWSET
# ============================================================================

class ActivityViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing Activities.
    
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
    
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    
    queryset = Activity.objects.all()
    module = 'activities'
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ActivityFilter
    search_fields = ['title', 'description', 'call_to_action']
    ordering_fields = ['title', 'scheduled_date', 'due_date', 'status', 'created_at', 'updated_at']
    ordering = ['-scheduled_date', '-created_at']
    
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
        Get filtered queryset with optimized prefetching.
        """
        queryset = super().get_queryset()
        
        # Optimize with select_related and prefetch_related
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
            'contacts'
        )
        
        return queryset
    
    # ==========================================================================
    # CRUD OVERRIDES
    # ==========================================================================
    
    def perform_create(self, serializer):
        """Create with audit fields."""
        serializer.save()
    
    def perform_update(self, serializer):
        """Update with audit fields."""
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Delete activity and clean up linked list references.
        """
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
    
    # ==========================================================================
    # CUSTOM ACTIONS
    # ==========================================================================
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Mark activity as completed.
        
        POST /activities/{id}/complete/
        
        Body:
            - outcome (optional): ActivityOutcome choice
            - notes (optional): Outcome notes
        """
        activity = self.get_object()
        
        # Validate not already completed
        if activity.status == ActivityStatus.COMPLETED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail='Activity is already completed')
            )
        
        if activity.status == ActivityStatus.CANCELLED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail='Cannot complete a cancelled activity')
            )
        
        outcome = request.data.get('outcome')
        notes = request.data.get('notes')
        
        # Validate outcome if provided
        if outcome and outcome not in ActivityOutcome.values:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='outcome')
            )
        
        activity.complete(outcome=outcome, notes=notes, user=request.user)
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel activity.
        
        POST /activities/{id}/cancel/
        
        Body:
            - notes (optional): Cancellation reason
        """
        activity = self.get_object()
        
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
        
        serializer = ActivitySerializer(activity, context={'request': request})
        return Response(serializer.data)
    
    # ==========================================================================
    # LIST ACTIONS
    # ==========================================================================
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """
        Get current user's activities.
        
        GET /activities/my-activities/
        """
        queryset = self.get_queryset().filter(owner=request.user)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_account(self, request):
        """
        Get activities for a specific account.
        
        GET /activities/by-account/?account_id={uuid}
        """
        account_id = request.query_params.get('account_id')
        
        if not account_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='account_id')
            )
        
        queryset = self.get_queryset().filter(account_id=account_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_step(self, request):
        """
        Get activities for a specific decision step.
        
        GET /activities/by-step/?step_id={uuid}
        """
        step_id = request.query_params.get('step_id')
        
        if not step_id:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='step_id')
            )
        
        queryset = self.get_queryset().filter(decision_step_id=step_id)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Get overdue activities for current user.
        
        GET /activities/overdue/
        """
        today = timezone.now().date()
        
        queryset = self.get_queryset().filter(
            owner=request.user,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS],
            due_date__lt=today
        ).order_by('due_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Get upcoming activities for current user.
        
        GET /activities/upcoming/?days=7
        """
        days = int(request.query_params.get('days', 7))
        today = timezone.now().date()
        end_date = today + timezone.timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            owner=request.user,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS],
            scheduled_date__gte=today,
            scheduled_date__lte=end_date
        ).order_by('scheduled_date', 'scheduled_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActivityListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


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
        return Response({
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
        })