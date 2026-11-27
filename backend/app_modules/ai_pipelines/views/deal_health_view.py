# app_modules/ai_pipelines/views/deal_health_view.py
"""
DealHealthRunView -- POST endpoint that triggers the deal-health
diagnostic pipeline on a DecisionCycle.

Endpoint:
    POST /module-ai-pipelines/deal-health/run/

Request:
    Header: Idempotency-Key: <sha256-hex> (front: sha256(cycleId::latestSnapshotId))
    { "decision_cycle_id": "<uuid>" }

Response (201 Created):
    {
        "success": true,
        "data": {
            "run": { ...run summary... },
            "snapshot": { ...DealHealthSnapshotDetailSerializer... }
        }
    }

Response (200 OK, a run guard — A10, step 6): no LLM call, no snapshot
    { "success": true, "code": "DEAL_HEALTH_NO_NEW_SOURCES" |
      "DEAL_HEALTH_CYCLE_CLOSED", "message": "<INFO>",
      "data": { "run": null, "snapshot": null, "last_analysis_at": "<iso>" } }

Response (202 Accepted): the same Idempotency-Key is already running.
Response (409 Conflict): the same Idempotency-Key with another payload.
Response (403 Forbidden): not an admin, a manager nor the cycle's owner (6b).

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
from core.error_messages import AIPipelineErrorMessages, CoreErrorMessages
from core.exceptions import StandardizedPermissionDenied
from core.jwt_helpers import CustomJWTAuthentication
from core.timeout_conventions import IDEMPOTENCY_REDIS_TTL_SECONDS

from core.throttling import AIRateThrottle
from permissions.mixins import ScopedPermission

from app_modules.decision_cycles.serializers import (
    DealHealthSnapshotDetailSerializer,
)
from app_modules.decision_cycles.services.deal_health_access import can_run_deal_health

from ..constants import (
    AIPipelineStatus,
    DEAL_HEALTH_CYCLE_CLOSED_CODE,
    DEAL_HEALTH_NO_NEW_SOURCES_CODE,
)
from ..pipelines.deal_health import DealHealthPipeline
from ..serializers.deal_health_serializer import DealHealthRunInputSerializer
from .run_idempotency import IdempotentRun


logger = logging.getLogger(__name__)

# The INFO message of each run guard (A10) — centralised in
# core/error_messages.py.
_BLOCKED_MESSAGES = {
    DEAL_HEALTH_NO_NEW_SOURCES_CODE: AIPipelineErrorMessages.DEAL_HEALTH_NO_NEW_SOURCES,
    DEAL_HEALTH_CYCLE_CLOSED_CODE:   AIPipelineErrorMessages.DEAL_HEALTH_CYCLE_CLOSED,
}


class DealHealthRunView(BaseAPIView):
    """
    POST /module-ai-pipelines/deal-health/run/

    Triggers a deal-health diagnostic pipeline and returns the snapshot.

    Step 6 (sprint « Deal health v2 »):
      Layer 1 — Redis (TD-50), the core/idempotency.py pattern of
        activity_extraction_view.py: the front's deterministic
        Idempotency-Key (sha256(cycleId::latestSnapshotId)) — the same key
        and payload while running → 202 + poll_url; once answered → the
        answer replayed (no 2nd LLM call); the same key with another payload
        → 409 IDEMPOTENCY_CONFLICT. Without Redis in dev, the run goes on
        (core/idempotency.py _check_redis_available).
      Layer 2 — the run guards (A10, DealHealthPipeline): 200 + an INFO
        code, no LLM call, no snapshot.
    6b: who may run it — decision_cycles/services/deal_health_access.py
      can_run_deal_health (admin, manager, the cycle's owner), else 403.
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
        client_id_str = str(client_id)
        log_ctx = {'decision_cycle_id': str(decision_cycle.id)}

        # 6b (PO decision n° 6): only an admin, a manager or the cycle's owner
        # runs a deal health — the central predicate, the standard refusal
        # (403), before any idempotency record or LLM call.
        if not can_run_deal_health(request, decision_cycle):
            logger.info('deal_health_run.permission_denied', extra=log_ctx)
            raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)

        # -----------------------------------------------------------------
        # Layer 1 — Redis idempotency (activity_extraction_view.py:208-242)
        # -----------------------------------------------------------------
        # (views/run_idempotency.py — shared with the Game Plan since G12.)
        idem = IdempotentRun(
            request, client_id_str, event='deal_health_run',
            running_message='A deal health analysis is already in progress for this deal.',
            log_ctx=log_ctx,
        )
        replay = idem.start()
        if replay is not None:
            return replay

        # -----------------------------------------------------------------
        # The run (its guards first — DealHealthPipeline, A10)
        # -----------------------------------------------------------------
        try:
            pipeline = DealHealthPipeline()
            result = pipeline.run(
                decision_cycle=decision_cycle,
                user=request.user,
                client_id=client_id,
            )
        except Exception as exc:
            logger.exception('deal_health_run.pipeline_hard_crash', extra=log_ctx)
            idem.record_failure(exc)
            return Response(
                {
                    'success': False,
                    'error': 'An unexpected error occurred during the pipeline run.',
                },
                status=http_status.HTTP_502_BAD_GATEWAY,
            )

        blocked = result.get('blocked')
        if blocked:
            logger.info('deal_health_run.blocked', extra={**log_ctx, 'code': blocked})
            return idem.respond_short(
                self._blocked_body(blocked, result.get('last_snapshot')),
                http_status.HTTP_200_OK,
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
            return idem.respond(
                {'success': True, 'data': body},
                http_status.HTTP_201_CREATED,
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )

        return idem.respond_short(
            {
                'success': False,
                'error': run.error_message or 'Pipeline did not succeed.',
                'data': body,
            },
            http_status.HTTP_502_BAD_GATEWAY,
        )

    # =========================================================================
    # RUN GUARDS (A10)
    # =========================================================================

    @staticmethod
    def _blocked_body(code, last_snapshot):
        """200 + the INFO code: nothing was run, nothing written."""
        last_at = last_snapshot.snapshot_date if last_snapshot is not None else None
        message = _BLOCKED_MESSAGES[code]
        if code == DEAL_HEALTH_NO_NEW_SOURCES_CODE:
            message = str(message).format(
                date=last_at.date().isoformat() if last_at else '',
            )
        return {
            'success': True,
            'code':    code,
            'message': str(message),
            'data': {
                'run':              None,
                'snapshot':         None,
                'last_analysis_at': last_at.isoformat() if last_at else None,
            },
        }

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
