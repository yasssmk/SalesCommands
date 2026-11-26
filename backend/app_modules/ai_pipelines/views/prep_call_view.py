# app_modules/ai_pipelines/views/prep_call_view.py
"""
PrepCallRunView — POST endpoint that triggers the prep-call tactical
brief pipeline on an Activity.

Endpoint:
    POST /module-ai-pipelines/prep-call/run/

Request:
    { "activity_id": "<uuid>" }
    (no contact_id — sprint 2 Game Plan, S2: a contact_id sent is ignored)

Response (201 Created):
    {
        "success": true,
        "data": {
            "run": { ...run summary... },
            "snapshot": { ...PrepCallSnapshotSerializer... }
        }
    }

PrepCallByActivityView — GET endpoint that returns the latest
PrepCallSnapshot for a given Activity.

Endpoint:
    GET /module-ai-pipelines/prep-call/by-activity/<uuid>/
"""

import logging

from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.error_messages import AIPipelineErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedPermissionDenied
from core.jwt_helpers import CustomJWTAuthentication
from core.throttling import AIRateThrottle
from permissions.mixins import ScopedPermission

from ..constants import (
    AIPipelineStatus,
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE,
    PREP_CALL_NOTHING_NEW_CODE,
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE,
)
from ..pipelines.prep_call import PrepCallPipeline
from ..serializers.prep_call_serializer import (
    PrepCallRunInputSerializer,
    PrepCallSnapshotSerializer,
)
from ..services.game_plan_access import (
    can_run_game_plan,
    game_plan_blocked_reason,
    game_plan_output_kind,
)
from ..services.prep_call.mode_resolver import resolve_brief_mode
from ..services.prep_call.input_pack_assembler import PrepInputPackAssembler


logger = logging.getLogger(__name__)

# The INFO message of each business rule (G3) — centralised in
# core.error_messages, as the deal health's run guards.
_BLOCKED_MESSAGES = {
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE: AIPipelineErrorMessages.PREP_CALL_TYPE_NOT_ELIGIBLE,
    PREP_CALL_ACTIVITY_CLOSED_CODE:   AIPipelineErrorMessages.PREP_CALL_ACTIVITY_CLOSED,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE: AIPipelineErrorMessages.PREP_CALL_NO_CAMPAIGN_NO_DC,
    PREP_CALL_NOTHING_NEW_CODE:       AIPipelineErrorMessages.PREP_CALL_NOTHING_NEW,   # G9
}


def _blocked_body(code, last_snapshot=None):
    """200 + the INFO code: nothing was run, nothing written (the deal
    health's _blocked_body, views/deal_health_view.py)."""
    last_at = last_snapshot.snapshot_date if last_snapshot is not None else None
    message = str(_BLOCKED_MESSAGES[code])
    if code == PREP_CALL_NOTHING_NEW_CODE:
        message = message.format(date=last_at.date().isoformat() if last_at else '')
    return {
        'success': True,
        'code':    code,
        'message': message,
        'data': {
            'run':               None,
            'snapshot':          None,
            'last_generated_at': last_at.isoformat() if last_at else None,
        },
    }


class PrepCallRunView(BaseAPIView):
    """
    POST /module-ai-pipelines/prep-call/run/

    Triggers a prep-call brief pipeline and returns the snapshot.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    throttle_classes       = [AIRateThrottle]
    module                 = 'ai_pipelines'

    def post(self, request, *args, **kwargs):
        input_serializer = PrepCallRunInputSerializer(
            data=request.data,
            context={'request': request},
        )
        input_serializer.is_valid(raise_exception=True)
        validated = input_serializer.validated_data

        activity = validated['activity']
        client_id = validated['client_id']
        # No contact received any more (S2, C2-11 / TD-325): the people of the
        # brief come from the activity itself (Game Plan roster, sub-step G4).
        target_contact = None

        # G3 — who may generate: a real 403, before anything else.
        if not can_run_game_plan(request, activity):
            logger.info('prep_call_run.permission_denied',
                        extra={'activity_id': str(activity.id)})
            raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)

        # G3 — the business rules: 200 + an INFO code, nothing run.
        blocked = game_plan_blocked_reason(activity)
        if blocked:
            logger.info('prep_call_run.blocked',
                        extra={'activity_id': str(activity.id), 'code': blocked})
            return Response(_blocked_body(blocked), status=http_status.HTTP_200_OK)

        # Idempotence layer 1 (Redis) intentionally omitted — matches
        # DealHealth pattern. Layer 2 (DB hash dedup in the pipeline)
        # prevents duplicate snapshots.
        assembler = PrepInputPackAssembler()
        maturity_snapshot = assembler.build_maturity_snapshot(
            activity.decision_cycle,
        )
        brief_mode = resolve_brief_mode(maturity_snapshot)

        input_pack = assembler.build(
            activity=activity,
            target_contact=target_contact,
            brief_mode=brief_mode,
        )

        try:
            pipeline = PrepCallPipeline()
            result = pipeline.run(
                activity=activity,
                target_contact=target_contact,
                brief_mode=brief_mode,
                input_pack=input_pack,
                user=request.user,
                client_id=client_id,
                output_kind=game_plan_output_kind(activity),
            )
        except Exception:
            logger.exception(
                'prep_call_run.pipeline_hard_crash',
                extra={
                    'activity_id': str(activity.id),
                },
            )
            return Response(
                {
                    'success': False,
                    'error': 'An unexpected error occurred during the pipeline run.',
                },
                status=http_status.HTTP_502_BAD_GATEWAY,
            )

        # G9 — nothing new since the last Game Plan: 200 + INFO, after the
        # permission (403) and the business rules of G3 (INFO) above.
        if result.get('blocked'):
            logger.info('prep_call_run.blocked',
                        extra={'activity_id': str(activity.id), 'code': result['blocked']})
            return Response(_blocked_body(result['blocked'], result.get('last_snapshot')),
                            status=http_status.HTTP_200_OK)

        run = result['run']
        snapshot = result.get('snapshot')

        run_data = self._serialize_run(run)

        if snapshot is not None:
            snapshot_data = PrepCallSnapshotSerializer(
                snapshot,
                context={'request': request},
            ).data
        else:
            snapshot_data = None

        body = {
            'run': run_data,
            'snapshot': snapshot_data,
        }

        if run and run.status == AIPipelineStatus.SUCCESS:
            return Response(
                {'success': True, 'data': body},
                status=http_status.HTTP_201_CREATED,
            )

        return Response(
            {
                'success': False,
                'error': (
                    run.error_message if run else 'Pipeline did not succeed.'
                ) or 'Pipeline did not succeed.',
                'data': body,
            },
            status=http_status.HTTP_502_BAD_GATEWAY,
        )

    @staticmethod
    def _serialize_run(run):
        if not run:
            return None
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


class PrepCallByActivityView(BaseAPIView):
    """
    GET /module-ai-pipelines/prep-call/by-activity/<uuid>/

    Returns the latest PrepCallSnapshot for the given Activity.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'ai_pipelines'

    def get(self, request, activity_id, *args, **kwargs):
        from app_modules.activities.models import Activity
        from ..models import PrepCallSnapshot

        client_id = request.user.client_id

        try:
            activity = Activity.objects.get(
                id=activity_id, client_id=client_id,
            )
        except Activity.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Activity not found.'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        snapshot = (
            PrepCallSnapshot.objects
            .filter(activity=activity, client_id=client_id)
            .select_related('pipeline_run')
            .order_by('-snapshot_date', '-created_at')
            .first()
        )

        if not snapshot:
            return Response(
                {'success': True, 'data': None},
            )

        serializer = PrepCallSnapshotSerializer(
            snapshot,
            context={'request': request},
        )
        return Response({'success': True, 'data': serializer.data})
