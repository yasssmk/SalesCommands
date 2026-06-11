# app_modules/decision_cycles/views/deal_health_snapshot_views.py
"""
DealHealthSnapshotViewSet — read-only endpoints for DealHealthSnapshot.

Snapshots are created by the deal-health pipeline (Step 5), never by
direct user request. This ViewSet exposes list, retrieve, and a
convenience ``latest`` action.

Security model mirrors DealProductViewSet: access is governed by the
parent cycle via CycleScopedMixin._resolve_parent_cycle().
"""

from django.http import Http404

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import ctx_from_request, get_logger

from permissions.mixins import ScopedPermission

from ..models import DealHealthSnapshot
from ..serializers import (
    DealHealthSnapshotListSerializer,
    DealHealthSnapshotDetailSerializer,
)
from .deal_product_views import CycleScopedMixin


logger = get_logger(__name__)


class DealHealthSnapshotViewSet(CycleScopedMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    Read-only endpoints for DealHealthSnapshot, nested under a DecisionCycle.

    Endpoints (mounted under /decision-cycles/{cycle_id}/health-snapshots/):
      GET  /                → list (all snapshots, newest first)
      GET  /{pk}/           → retrieve
      GET  /latest/         → most recent snapshot
    """

    queryset = DealHealthSnapshot.objects.all()
    entity_name = 'deal_health_snapshot'

    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'decision_cycles'

    action_policies = {
        'list':     {'crud': 'read', 'scope': 'client'},
        'retrieve': {'crud': 'read', 'scope': 'client'},
        'latest':   {'crud': 'read', 'scope': 'client'},
    }

    # =========================================================================
    # SERIALIZER ROUTING
    # =========================================================================

    def get_serializer_class(self):
        if self.action == 'list':
            return DealHealthSnapshotListSerializer
        return DealHealthSnapshotDetailSerializer

    # =========================================================================
    # QUERYSET — scoped to parent cycle
    # =========================================================================

    def get_queryset(self):
        cycle = self._resolve_parent_cycle()
        qs = DealHealthSnapshot.objects.filter(
            decision_cycle=cycle,
            client_id=cycle.client_id,
        ).order_by('-snapshot_date', '-created_at')

        if self.action in ('retrieve', 'latest'):
            qs = qs.select_related('pipeline_run')

        return qs

    # =========================================================================
    # READ-ONLY ENDPOINTS
    # =========================================================================

    def list(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        cycle = self._resolve_parent_cycle()

        logger.info('deal_health_snapshot_list_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        ctx = ctx_from_request(request)
        instance = self.get_object()

        logger.info('deal_health_snapshot_retrieved', extra={
            **ctx, 'snapshot_id': str(instance.id),
        })

        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        ctx = ctx_from_request(request)
        cycle = self._resolve_parent_cycle()

        logger.info('deal_health_snapshot_latest_requested', extra={
            **ctx, 'cycle_id': str(cycle.id),
        })

        snapshot = self.get_queryset().first()
        if not snapshot:
            return Response({
                'success': True,
                'data': None,
            })

        serializer = DealHealthSnapshotDetailSerializer(
            snapshot, context=self.get_serializer_context(),
        )
        return Response({'success': True, 'data': serializer.data})

    # =========================================================================
    # BLOCKED WRITES — snapshots are created by the pipeline only
    # =========================================================================

    def create(self, request, *args, **kwargs):
        raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)

    def update(self, request, *args, **kwargs):
        raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)

    def partial_update(self, request, *args, **kwargs):
        raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)

    def destroy(self, request, *args, **kwargs):
        raise StandardizedValidationError(CoreErrorMessages.PERMISSION_DENIED)
