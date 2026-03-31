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
from ..utils.scheduling import cumulative_delay_for_position, next_business_day

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
        from app_modules.activities.constants import ActivityStatus

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
                queryset=Activity.objects.filter(status=ActivityStatus.ON_HOLD).only('id', 'status', 'campaign_contact_id'),
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
        instance = self.get_object()
        result = instance.mark_completed(
            user=request.user,
            notes=request.data.get('notes'),
        )
        self._audit_status_change(request, instance, result)

        # Cascade: check if parent account should auto-complete/stop
        from ..services.campaign_execution_service import CampaignExecutionService
        CampaignExecutionService(
            user=request.user, client_id=self.get_client_id()
        )._check_account_completion(instance.campaign_account)

        self._invalidate_caches(self.get_client_id())

        output = CampaignContactDetailSerializer(instance, context={'request': request})
        return Response({'success': True, 'data': {
            'campaign_contact': output.data,
            'transition': result,
        }})

    @action(detail=True, methods=['post'], url_path='mark-stopped')
    @transaction.atomic
    def mark_stopped(self, request, pk=None):
        instance = self.get_object()
        reason = request.data.get('reason')
        notes = request.data.get('notes')
        combined_notes = f"Stopped: {reason}" if reason else notes
        result = instance.mark_stopped(
            user=request.user,
            notes=combined_notes,
        )
        self._audit_status_change(request, instance, result)

        # Delete open activities + cascade account — mirrors _handle_outcome()
        # terminal path. Centralised in _cancel_chain_for_contact so all
        # stop paths (manual or outcome-driven) behave identically.
        from ..services.campaign_execution_service import CampaignExecutionService
        exec_service = CampaignExecutionService(
            user=request.user, client_id=self.get_client_id(),
        )
        exec_service._cancel_chain_for_contact(instance)
        exec_service._check_account_completion(instance.campaign_account)

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

        # Transition CampaignContact to ON_HOLD so its status is consistent
        # with its activities. Without this, CampaignContact stays IN_PROGRESS
        # while all its activities are ON_HOLD (P1-5 audit fix).
        from ..constants import CampaignContactStatus
        if instance.status == CampaignContactStatus.IN_PROGRESS and activities_paused > 0:
            instance._transition_to(
                CampaignContactStatus.ON_HOLD,
                user=request.user,
                notes="Contact sequence paused manually",
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
            ).order_by('sequence_position')
        )

        if not on_hold:
            return Response({
                'success': True,
                'data': {'activities_resumed': 0},
            })

        from ..utils.scheduling import prefetch_delays

        # Single query for all delays — avoids N+1 reads in the loop.
        delays = prefetch_delays(instance.id)

        for activity in on_hold:
            cumulative_delay = cumulative_delay_for_position(
                instance.id,
                activity.sequence_position,
                prefetched=delays,
            )
            scheduled = next_business_day(today + timedelta(days=cumulative_delay))
            activity.status = ActivityStatus.PLANNED
            activity.scheduled_date = scheduled
            activity.save(update_fields=['status', 'scheduled_date', 'updated_at'])

        # Restore CampaignContact to IN_PROGRESS — mirrors pause() in reverse.
        # Without this the contact stays ON_HOLD while its activities are PLANNED.
        from ..constants import CampaignContactStatus
        if instance.status == CampaignContactStatus.ON_HOLD:
            instance._transition_to(
                CampaignContactStatus.IN_PROGRESS,
                user=request.user,
                notes="Contact sequence resumed manually",
            )

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
    
    @action(detail=True, methods=['post'], url_path='reactivate')
    @transaction.atomic
    def reactivate(self, request, pk=None):
        """
        Reactivate a COMPLETED or STOPPED contact for a new sequence cycle.
        Only valid for TARGETED campaigns.

        POST /campaigns/contacts/{id}/reactivate/

        Resets activities_generated=False so a new sequence can be generated.
        The caller (frontend) should follow up with enroll-target to generate
        new activities — or this endpoint can trigger generation directly.
        """
        from django.utils import timezone
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityStatus
        from ..constants import FINAL_CONTACT_STATES, CampaignType

        instance = self.get_object()
        client_id = self.get_client_id()

        # Guard: only TARGETED campaigns support re-enrollment
        campaign = instance.campaign_account.campaign
        if campaign.campaign_type != CampaignType.TARGETED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='reactivate (only allowed on TARGETED campaigns)'
                )
            )

        # Guard: contact must be in a final state
        if instance.status not in FINAL_CONTACT_STATES:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field=f'reactivate (contact status is {instance.status}, expected COMPLETED or STOPPED)'
                )
            )

        # Reactivate the contact (resets status + activities_generated)
        instance.reactivate(user=request.user)

        # Generate new sequence immediately
        from ..services.campaign_execution_service import CampaignExecutionService
        exec_service = CampaignExecutionService(
            user=request.user,
            client_id=client_id,
        )
        activities_created = exec_service.generate_activities_for_contact(
            campaign,
            instance.campaign_account,
            instance.contact,
        )

        audit_log(
            event='campaign_contact_reactivated',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(client_id),
            target_type='campaign_contact',
            target_id=str(instance.id),
            outcome='success',
            extra={'activities_created': activities_created},
        )

        logger.info("campaign_contact_reactivated", extra={
            'campaign_contact_id': str(instance.id),
            'activities_created': activities_created,
        })

        self._invalidate_caches(client_id)
        output = CampaignContactDetailSerializer(instance, context={'request': request})

        return Response({
            'success': True,
            'data': {
                'campaign_contact': output.data,
                'activities_created': activities_created,
            },
        })

    # ==========================================================================
    # PRIVATE HELPERS
    # ==========================================================================

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