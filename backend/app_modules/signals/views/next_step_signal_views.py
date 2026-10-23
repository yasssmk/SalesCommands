# app_modules/signals/views/next_step_signal_views.py
"""
NextStepSignalViewSet — CRUD + validate/reject for NextStepSignal.

Inherits all shared logic from BaseSignalViewSet. Extends get_queryset()
with the `suggested_contacts` M2M prefetch (next-step-specific
attendee surface) to avoid an N+1 on list responses that render the
compact attendees payload on each row.

Cluster cache invalidation is intentionally left at the base default
(False): NextStepSignal does not participate in the cluster model — see
the NextStepSignal model docstring and signals/cache_invalidation.py.
"""

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response

from core.logging import ctx_from_request, get_logger
from core.logging.audit import audit_log

from ..models import NextStepSignal
from ..serializers import (
    NextStepSignalListSerializer,
    NextStepSignalDetailSerializer,
    NextStepSignalCreateSerializer,
    NextStepSignalUpdateSerializer,
)
from ..serializers.next_step_serializer import _compact_activity
from ..services.next_step_link_service import (
    attach_next_step,
    link_candidates,
    link_differences,
)
from .base_views import BaseSignalViewSet


logger = get_logger(__name__)


class NextStepSignalViewSet(BaseSignalViewSet):
    """
    ViewSet for NextStepSignal.

    Endpoints (mounted under /next-steps/):
      GET    /next-steps/                  → list
      POST   /next-steps/                  → create
      GET    /next-steps/{id}/             → retrieve
      PATCH  /next-steps/{id}/             → partial_update
      PUT    /next-steps/{id}/             → update (treated as PATCH)
      DELETE /next-steps/{id}/             → destroy
      POST   /next-steps/{id}/validate/    → validate_signal
      POST   /next-steps/{id}/reject/      → reject_signal
    """

    queryset                = NextStepSignal.objects.all()
    model_label             = 'next_step_signal'
    list_serializer_class   = NextStepSignalListSerializer
    detail_serializer_class = NextStepSignalDetailSerializer
    create_serializer_class = NextStepSignalCreateSerializer
    update_serializer_class = NextStepSignalUpdateSerializer

    # NextStepSignal does not participate in cluster aggregation — keep
    # the base default (False). See NextStepSignal model docstring and
    # signals/cache_invalidation.py for the rationale.
    invalidate_cluster_tag = False

    search_fields = ['suggested_title']

    def get_queryset(self):
        """
        Extend base queryset with the NextStep-specific relations: the
        `suggested_contacts` / `suggested_people` M2M (with each People's
        contact) prefetched, the proposed step and the attached activity
        joined.

        Universally-present FKs (account, source_activity, validated_by,
        requested_by on detail) are preloaded by BaseSignalViewSet.
        `suggested_contacts` is a NextStep-specific m2m and gets
        prefetched here so the list serializer's compact attendees
        payload does not trigger an N+1 (one extra query per row
        otherwise).
        """
        qs = super().get_queryset()
        qs = qs.select_related('suggested_decision_step', 'attached_activity')
        qs = qs.prefetch_related(
            'suggested_contacts',
            'created_activities',
            'suggested_people__target_contact',
        )
        return qs

    # =========================================================================
    # LINK TO AN EXISTING ACTIVITY — candidates (Sprint Next steps 2.3)
    # =========================================================================

    @action(detail=True, methods=['get'], url_path='link-candidates')
    def link_candidates(self, request, pk=None):
        """
        GET /next-steps/{id}/link-candidates/

        The open activities of the next step's decision cycle it can be
        linked to, ranked by NEXT_STEP_LINK_RANKING
        (services/next_step_link_service.py), each with the values of the
        ranking criteria AND its `differences` with the next step (2.4 — a
        difference belongs to a (next step, activity) pair and the candidates
        are exactly the valid link targets, so one call gives the UI the
        list and every differences screen, nothing to recompute); the first
        one is the "link" proposal. get_object() keeps the tenant scope
        (another tenant → 404).
        """
        signal = self.get_object()
        candidates = [
            {
                **_compact_activity(activity),
                'decision_step': (
                    {'id': str(activity.decision_step.id),
                     'name': activity.decision_step.name}
                    if activity.decision_step_id else None
                ),
                'shared_people_count': criteria['shared_people'],
                'same_step':           criteria['same_step'],
                'same_type':           criteria['same_type'],
                'date_distance_days':  criteria['date_distance_days'],
                'differences':         link_differences(signal, activity),
            }
            for activity, criteria in link_candidates(signal)
        ]
        return Response({
            'success': True,
            'data': {
                'proposed_activity_id': candidates[0]['id'] if candidates else None,
                'candidates':           candidates,
            },
        })

    @action(detail=True, methods=['post'], url_path='attach-activity')
    @transaction.atomic
    def attach_activity(self, request, pk=None):
        """
        POST /next-steps/{id}/attach-activity/  {activity_id, updates}

        Link the next step to an existing candidate activity, applying the
        changes the rep chose on the differences screen — all in this one
        transaction, the signal validated last
        (services/next_step_link_service.attach_next_step).
        """
        ctx    = ctx_from_request(request)
        signal = self.get_object()

        logger.info(f"{self.model_label}_attach_requested", extra={
            **ctx, 'signal_id': str(signal.id),
        })

        updates = request.data.get('updates') or {}
        updated = attach_next_step(
            signal, request.data.get('activity_id'), updates, request,
        )

        audit_log(
            event=f'{self.model_label}_attached',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type=self.model_label,
            target_id=str(updated.id),
            fields_changed=['attached_activity', 'status', 'validated_by', 'validated_at'],
            outcome='success',
            extra={
                'activity_id':      str(updated.attached_activity_id),
                'activity_updates': sorted(updates) if isinstance(updates, dict) else [],
            },
        )

        output = self.detail_serializer_class(updated, context={'request': request})
        return Response({'success': True, 'data': output.data})

