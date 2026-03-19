# app_modules/campaigns/views/campaign_contact_views.py
"""
CampaignContactViewSet — state machine actions per contact within a campaign.

Follows CampaignAccountViewSet patterns:
    - BaseAPIView + ScopedQuerysetMixin
    - Response({'success': True, 'data': ...})
    - Redis cache invalidation
    - Structured logging + SOC 2 audit trail
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin

from ..models import CampaignContact
from ..serializers import (
    CampaignContactListSerializer,
    CampaignContactDetailSerializer,
    CampaignContactSerializer,
)

logger = get_logger(__name__)


class CampaignContactViewSet(ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing per-contact state within a campaign.

    Routes:
        GET    /campaign-contacts/                         list
        POST   /campaign-contacts/                         create
        GET    /campaign-contacts/{id}/                    retrieve
        PUT    /campaign-contacts/{id}/                    update
        DELETE /campaign-contacts/{id}/                    destroy
        POST   /campaign-contacts/{id}/start-progress/     PENDING → IN_PROGRESS
        POST   /campaign-contacts/{id}/request-callback/   IN_PROGRESS → CALLBACK_PENDING
        POST   /campaign-contacts/{id}/resume-callback/    CALLBACK_PENDING → IN_PROGRESS (cancel pause)
        POST   /campaign-contacts/{id}/mark-completed/     → COMPLETED
        POST   /campaign-contacts/{id}/mark-stopped/       → STOPPED
    """

    queryset = CampaignContact.objects.all()
    serializer_class = CampaignContactSerializer
    entity_name = 'campaign_contact'

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]

    module = 'campaigns'
    action_policies = {
        'list':             'read',
        'retrieve':         'read',
        'create':           'write',
        'update':           'write',
        'partial_update':   'write',
        'destroy':          'delete',
        'start_progress':   'write',
        'request_callback': 'write',
        'resume_callback':  'write',
        'mark_completed':   'write',
        'mark_stopped':     'write',
        'pause':            'write',
        'resume':           'write',
    }

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['campaign_account', 'status', 'contact']
    ordering_fields = ['created_at', 'status']
    ordering = ['created_at']

    def get_queryset(self):
        from django.db.models import Prefetch
        from app_modules.activities.models import Activity

        qs = CampaignContact.objects.filter(
            client_id=self.get_client_id(),
        ).select_related(
            'contact',
            'contact__standard_department',
            'campaign_account',
            'campaign_account__account',
        ).prefetch_related(
            Prefetch(
                'activities',
                queryset=Activity.objects.filter(status='ON_HOLD').only('id', 'status', 'campaign_contact_id'),
            )
        )

        campaign_id = self.request.query_params.get('campaign')
        if campaign_id:
            qs = qs.filter(campaign_account__campaign_id=campaign_id)

        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CampaignContactDetailSerializer
        if self.action == 'list':
            return CampaignContactListSerializer
        return CampaignContactSerializer

    # ==========================================================================
    # STANDARD CRUD
    # ==========================================================================

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = CampaignContactListSerializer(
            qs, many=True, context={'request': request}
        )
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = CampaignContactDetailSerializer(
            instance, context={'request': request}
        )
        return Response({'success': True, 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = CampaignContactSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        audit_log(
            event='campaign_contact_created',
            action='create',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_contact',
            target_id=str(instance.id),
            outcome='success',
        )
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response(
            {'success': True, 'data': output.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        from django.utils import timezone
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        instance = self.get_object()
        instance_id = str(instance.id)
        client_id = self.get_client_id()

        # Cancel PLANNED + ON_HOLD activities — keep COMPLETED/CANCELLED untouched
        cancelled_count = Activity.objects.filter(
            campaign_contact=instance,
            status__in=[ActivityStatus.PLANNED, ActivityStatus.ON_HOLD],
            client_id=client_id,
        ).update(
            status=ActivityStatus.CANCELLED,
            outcome_notes='Target removed from campaign',
            updated_at=timezone.now(),
        )

        instance.delete()

        audit_log(
            event='campaign_contact_deleted',
            action='delete',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_contact',
            target_id=instance_id,
            outcome='success',
            extra={'activities_cancelled': cancelled_count},
        )
        self._invalidate_caches(client_id)
        return Response({'success': True, 'data': None}, status=status.HTTP_204_NO_CONTENT)

    # ==========================================================================
    # STATE MACHINE ACTIONS
    # ==========================================================================

    @action(detail=True, methods=['post'], url_path='start-progress')
    @transaction.atomic
    def start_progress(self, request, pk=None):
        """
        PENDING → IN_PROGRESS.
        POST /campaign-contacts/{id}/start-progress/
        """
        instance = self.get_object()
        result = instance.start_progress(user=request.user)
        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})

    @action(detail=True, methods=['post'], url_path='request-callback')
    @transaction.atomic
    def request_callback(self, request, pk=None):
        """
        IN_PROGRESS → CALLBACK_PENDING.
        POST /campaign-contacts/{id}/request-callback/

        Body:
            - callback_date: date (YYYY-MM-DD, required)
            - notes: str (optional)
        """
        instance = self.get_object()
        callback_date = request.data.get('callback_date')
        notes = request.data.get('notes')

        if not callback_date:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='callback_date')
            )

        result = instance.request_callback(
            callback_date=callback_date,
            user=request.user,
            notes=notes,
        )
        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})

    @action(detail=True, methods=['post'], url_path='resume-callback')
    @transaction.atomic
    def resume_callback(self, request, pk=None):
        """
        CALLBACK_PENDING → IN_PROGRESS (cancel pause).
        POST /campaign-contacts/{id}/resume-callback/
        """
        instance = self.get_object()
        result = instance.resume_from_callback(
            user=request.user,
            notes=request.data.get('notes'),
        )
        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})

    @action(detail=True, methods=['post'], url_path='mark-completed')
    @transaction.atomic
    def mark_completed(self, request, pk=None):
        """
        → COMPLETED.
        POST /campaign-contacts/{id}/mark-completed/
        """
        instance = self.get_object()
        result = instance.mark_completed(
            user=request.user,
            notes=request.data.get('notes'),
        )
        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})

    @action(detail=True, methods=['post'], url_path='mark-stopped')
    @transaction.atomic
    def mark_stopped(self, request, pk=None):
        """
        Any non-final → STOPPED.
        POST /campaign-contacts/{id}/mark-stopped/

        Body:
            - reason: str (optional)
            - notes: str (optional)
        """
        instance = self.get_object()
        reason = request.data.get('reason')
        notes = request.data.get('notes')
        combined_notes = f"Stopped: {reason}" if reason else notes
        result = instance.mark_stopped(
            user=request.user,
            notes=combined_notes,
        )
        self._audit_status_change(request, instance, result)
        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})
    
    @action(detail=True, methods=['post'], url_path='pause')
    @transaction.atomic
    def pause(self, request, pk=None):
        """
        Pause a contact's sequence: PLANNED activities → ON_HOLD.
        Contact remains visible in playlist (Upcoming section, end of list).

        POST /campaigns/contacts/{id}/pause/
        """
        from django.utils import timezone
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        instance = self.get_object()
        client_id = self.get_client_id()

        activities_paused = Activity.objects.filter(
            campaign_contact=instance,
            status=ActivityStatus.PLANNED,
            client_id=client_id,
        ).update(
            status=ActivityStatus.ON_HOLD,
            updated_at=timezone.now(),
        )

        audit_log(
            event='campaign_contact_paused',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_contact',
            target_id=str(instance.id),
            outcome='success',
            extra={'activities_paused': activities_paused},
        )

        logger.info("campaign_contact_paused", extra={
            'campaign_contact_id': str(instance.id),
            'activities_paused': activities_paused,
        })

        self._invalidate_caches(self.get_client_id())
        output = CampaignContactDetailSerializer(instance, context={'request': request})

        return Response({
            'success': True,
            'data': {
                'campaign_contact': output.data,
                'activities_paused': activities_paused,
            },
        })

    @action(detail=True, methods=['post'], url_path='resume')
    @transaction.atomic
    def resume(self, request, pk=None):
        """
        Resume a contact's sequence: ON_HOLD activities → PLANNED.
        Dates recalculated from today using cumulative min_delay_days.

        POST /campaigns/contacts/{id}/resume/
        """
        from datetime import timedelta
        from django.utils import timezone
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus

        instance = self.get_object()
        client_id = self.get_client_id()
        today = timezone.now().date()

        on_hold = list(
            Activity.objects.filter(
                campaign_contact=instance,
                status=ActivityStatus.ON_HOLD,
                client_id=client_id,
            ).select_related('previous_activity').order_by('sequence_position')
        )

        if not on_hold:
            return Response({
                'success': True,
                'data': {'activities_resumed': 0},
            })

        by_id = {a.id: a for a in on_hold}

        for activity in on_hold:
            cumulative_delay = self._cumulative_delay_from_root(activity, by_id)
            if cumulative_delay > 0:
                scheduled = self._next_business_day(
                    today + timedelta(days=cumulative_delay)
                )
            else:
                scheduled = self._next_business_day(today)

            activity.status = ActivityStatus.PLANNED
            activity.scheduled_date = scheduled
            activity.save(update_fields=['status', 'scheduled_date', 'updated_at'])

        audit_log(
            event='campaign_contact_resumed',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_contact',
            target_id=str(instance.id),
            outcome='success',
            extra={'activities_resumed': len(on_hold)},
        )

        logger.info("campaign_contact_resumed", extra={
            'campaign_contact_id': str(instance.id),
            'activities_resumed': len(on_hold),
        })

        self._invalidate_caches(self.get_client_id())
        output = CampaignContactDetailSerializer(instance, context={'request': request})
        
        return Response({
            'success': True,
            'data': {
                'campaign_contact': output.data,
                'activities_resumed': len(on_hold),
            },
        })

    # ==========================================================================
    # PRIVATE HELPERS
    # ==========================================================================

    def _next_business_day(self, date):
        """Advance date past weekends."""
        from datetime import timedelta
        while date.weekday() >= 5:
            date += timedelta(days=1)
        return date

    def _cumulative_delay_from_root(self, activity, by_id, _visited=None):
        """Walk previous_activity chain summing min_delay_days."""
        if _visited is None:
            _visited = set()
        if activity.id in _visited:
            return 0
        _visited.add(activity.id)
        prev = activity.previous_activity
        if prev is None:
            return 0
        prev_delay = self._cumulative_delay_from_root(prev, by_id, _visited)
        return prev_delay + (activity.min_delay_days or 0)

    def _audit_status_change(self, request, instance, result):
        audit_log(
            event='campaign_contact_status_changed',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='campaign_contact',
            target_id=str(instance.id),
            outcome='success',
            extra=result,
        )

    def _invalidate_caches(self, client_id):
        invalidate_tag(str(client_id), 'campaigns')
        invalidate_tag(str(client_id), 'activities')