# backend/app_modules/ai_pipelines/views/last_run_view.py
"""
GET /module-ai-pipelines/last-run/?activity_id=<uuid>

Returns metadata about the most recent successful (or partial)
AIPipelineRun for a given activity.

Response (200, run found):
    {
        "last_run": {
            "last_run_at":           "2026-06-03T14:32:00Z",
            "last_run_by":           { "id": "<uuid>", "full_name": "Yacine Smk" },
            "input_hash":            "<sha256-hex-64>",
            "pipeline_type":         "TRANSCRIPT_SIGNALS",
            "status":                "SUCCESS",
            "created_signals_count": 5
        },
        "runs_by_pipeline": {
            "TRANSCRIPT_SIGNALS": { ...same shape... } | null,
            "NEXT_STEPS":         { ...same shape... } | null
        }
    }

Response (200, no run found):
    { "last_run": null, "runs_by_pipeline": { "TRANSCRIPT_SIGNALS": null, "NEXT_STEPS": null } }
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.mixins import ScopedPermission

from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import AIPipelineType
from app_modules.ai_pipelines.models import AIPipelineRun


def _serialize_run(run):
    """Serialize an AIPipelineRun into the last-run response shape."""
    if run is None:
        return None
    created_by = run.created_by
    last_run_by = None
    if created_by:
        last_run_by = {
            'id': str(created_by.id),
            'full_name': created_by.get_full_name(),
        }
    return {
        'last_run_at': (
            run.created_at.isoformat() if run.created_at else None
        ),
        'last_run_by': last_run_by,
        'input_hash': run.input_hash,
        'pipeline_type': run.pipeline_type,
        'status': run.status,
        'created_signals_count': run.created_signals_count,
        'error_message': run.error_message or '',
    }


class LastRunView(BaseAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'ai_pipelines'

    def get(self, request):
        activity_id = request.query_params.get('activity_id')
        if not activity_id:
            return Response(
                {'error': 'activity_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_id = self.get_client_id()

        try:
            activity = Activity.objects.get(
                id=activity_id,
                client_id=client_id,
            )
        except Activity.DoesNotExist:
            return Response(
                {'error': 'Activity not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        base_qs = (
            AIPipelineRun.objects
            .filter(
                client_id=client_id,
                source_activity=activity,
                status__in=('SUCCESS', 'PARTIAL'),
            )
            .select_related('created_by')
            .order_by('-created_at')
        )

        last_run = base_qs.first()

        runs_by_pipeline = {}
        for pt in AIPipelineType.values:
            runs_by_pipeline[pt] = _serialize_run(
                base_qs.filter(pipeline_type=pt).first()
            )

        latest_run_obj = (
            AIPipelineRun.objects
            .filter(
                client_id=client_id,
                source_activity=activity,
            )
            .select_related('created_by')
            .order_by('-created_at')
            .first()
        )

        return Response({
            'last_run': _serialize_run(last_run),
            'runs_by_pipeline': runs_by_pipeline,
            'latest_run': _serialize_run(latest_run_obj),
        })
