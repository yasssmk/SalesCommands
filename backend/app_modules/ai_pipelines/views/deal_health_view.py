# app_modules/ai_pipelines/views/deal_health_view.py
"""
DealHealthRunView -- POST endpoint that triggers the deal-health
diagnostic pipeline on a DecisionCycle.

Endpoint:
    POST /module-ai-pipelines/deal-health/run/

Request:
    { "decision_cycle_id": "<uuid>" }

Response (201 Created):
    {
        "success": true,
        "data": {
            "run": { ...run summary... },
            "snapshot": { ...DealHealthSnapshotDetailSerializer... }
        }
    }

Response (502 Bad Gateway):
    {
        "success": false,
        "error": "<error_message>",
        "data": {
            "run": { ...run summary... },
            "snapshot": null
        }
    }
"""

import logging

from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication

from core.throttling import AIRateThrottle
from permissions.mixins import ScopedPermission

from app_modules.decision_cycles.serializers import (
    DealHealthSnapshotDetailSerializer,
)

from ..constants import AIPipelineStatus
from ..pipelines.deal_health import DealHealthPipeline
from ..serializers.deal_health_serializer import DealHealthRunInputSerializer


logger = logging.getLogger(__name__)


class DealHealthRunView(BaseAPIView):
    """
    POST /module-ai-pipelines/deal-health/run/

    Triggers a deal-health diagnostic pipeline and returns the snapshot.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    throttle_classes       = [AIRateThrottle]
    module                 = 'ai_pipelines'

    def post(self, request, *args, **kwargs):
        input_serializer = DealHealthRunInputSerializer(
            data=request.data,
            context={'request': request},
        )
        input_serializer.is_valid(raise_exception=True)
        validated = input_serializer.validated_data

        decision_cycle = validated['decision_cycle']
        client_id = validated['client_id']

        try:
            pipeline = DealHealthPipeline()
            result = pipeline.run(
                decision_cycle=decision_cycle,
                user=request.user,
                client_id=client_id,
            )
        except Exception:
            logger.exception(
                'deal_health_run.pipeline_hard_crash',
                extra={
                    'decision_cycle_id': str(decision_cycle.id),
                },
            )
            return Response(
                {
                    'success': False,
                    'error': 'An unexpected error occurred during the pipeline run.',
                },
                status=http_status.HTTP_502_BAD_GATEWAY,
            )

        run = result['run']
        snapshot = result.get('snapshot')

        run_data = self._serialize_run(run)

        if snapshot is not None:
            snapshot_data = DealHealthSnapshotDetailSerializer(
                snapshot,
                context={'request': request},
            ).data
        else:
            snapshot_data = None

        body = {
            'run': run_data,
            'snapshot': snapshot_data,
        }

        if run.status == AIPipelineStatus.SUCCESS:
            return Response(
                {'success': True, 'data': body},
                status=http_status.HTTP_201_CREATED,
            )

        return Response(
            {
                'success': False,
                'error': run.error_message or 'Pipeline did not succeed.',
                'data': body,
            },
            status=http_status.HTTP_502_BAD_GATEWAY,
        )

    @staticmethod
    def _serialize_run(run):
        return {
            'run_id':                str(run.id),
            'pipeline_type':         run.pipeline_type,
            'status':                run.status,
            'created_signals_count': run.created_signals_count,
            'total_tokens_used':     run.total_tokens_used,
            'total_duration_ms':     run.total_duration_ms,
            'error_message':         run.error_message or '',
            'created_at':            (
                run.created_at.isoformat() if run.created_at else None
            ),
        }
