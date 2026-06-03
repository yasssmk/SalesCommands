# backend/app_modules/ai_pipelines/views/last_run_view.py
"""
GET /module-ai-pipelines/last-run/?activity_id=<uuid>

Returns metadata about the most recent successful (or partial)
AIPipelineRun for a given activity. Used by the frontend Notes Tab
to display "Last analyzed on …" captions and to detect content-level
dedup before opening the extraction modal.

Response (200, run found):
    {
        "last_run_at":              "2026-06-03T14:32:00Z",
        "last_run_by": {
            "id":        "<uuid>",
            "full_name": "Yacine Smk"
        },
        "input_hash":               "<sha256-hex-64>",
        "pipeline_type":            "TRANSCRIPT_SIGNALS",
        "status":                   "SUCCESS",
        "created_signals_count":    5
    }

Response (200, no run found):
    { "last_run": null }
"""

from rest_framework import status
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.jwt_helpers import CustomJWTAuthentication
from permissions.mixins import ScopedPermission

from app_modules.activities.models import Activity
from app_modules.ai_pipelines.models import AIPipelineRun


class LastRunView(BaseAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [ScopedPermission]

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

        run = (
            AIPipelineRun.objects
            .filter(
                client_id=client_id,
                source_activity=activity,
                status__in=('SUCCESS', 'PARTIAL'),
            )
            .select_related('created_by')
            .order_by('-created_at')
            .first()
        )

        if run is None:
            return Response({'last_run': None})

        created_by = run.created_by
        last_run_by = None
        if created_by:
            last_run_by = {
                'id': str(created_by.id),
                'full_name': created_by.get_full_name(),
            }

        return Response({
            'last_run': {
                'last_run_at': (
                    run.created_at.isoformat() if run.created_at else None
                ),
                'last_run_by': last_run_by,
                'input_hash': run.input_hash,
                'pipeline_type': run.pipeline_type,
                'status': run.status,
                'created_signals_count': run.created_signals_count,
            },
        })
