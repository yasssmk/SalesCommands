# app_modules/ai_pipelines/views/prep_call_view.py
"""
PrepCallRunView — POST endpoint that triggers the prep-call tactical
brief pipeline on an Activity.

Endpoint:
    POST /module-ai-pipelines/prep-call/run/

Request:
    Header: Idempotency-Key: <deterministic key from the front> (G12, optional:
            without one the run goes on as before)
    { "activity_id": "<uuid>", "language_overrides": [...] (G11, optional) }
    (no contact_id — sprint 2 Game Plan, S2: a contact_id sent is ignored)

Response (200 OK + an INFO code): a business rule (G3 / G9 / G11) — nothing run.
Response (202 Accepted): the same Idempotency-Key is already running (G12).
Response (409 Conflict): the same Idempotency-Key with another payload (G12).

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
from core.exceptions import StandardizedPermissionDenied, StandardizedValidationError
from core.timeout_conventions import IDEMPOTENCY_REDIS_TTL_SECONDS
from core.jwt_helpers import CustomJWTAuthentication
from core.throttling import AIRateThrottle
from permissions.mixins import ScopedPermission

from ..constants import (
    AIPipelineStatus,
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_MESSAGE_RECIPIENTS_MAX,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE,
    PREP_CALL_NO_RECIPIENT_CODE,
    PREP_CALL_NOTHING_NEW_CODE,
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE,
    PrepCallOutputKind,
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
from ..services.prep_call.input_pack_assembler import PrepInputPackAssembler
from .run_idempotency import IdempotentRun


logger = logging.getLogger(__name__)

# The INFO message of each business rule (G3) — centralised in
# core.error_messages, as the deal health's run guards.
_BLOCKED_MESSAGES = {
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE: AIPipelineErrorMessages.PREP_CALL_TYPE_NOT_ELIGIBLE,
    PREP_CALL_ACTIVITY_CLOSED_CODE:   AIPipelineErrorMessages.PREP_CALL_ACTIVITY_CLOSED,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE: AIPipelineErrorMessages.PREP_CALL_NO_CAMPAIGN_NO_DC,
    PREP_CALL_NOTHING_NEW_CODE:       AIPipelineErrorMessages.PREP_CALL_NOTHING_NEW,   # G9
    PREP_CALL_NO_RECIPIENT_CODE:      AIPipelineErrorMessages.PREP_CALL_NO_RECIPIENT,  # G11
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

        # G12 — Layer 1: Redis idempotency (TD-50), the deal health's
        # mechanics (views/run_idempotency.py), AFTER the 403 and before any
        # rule, read or LLM call: the same key while running -> 202, once
        # answered -> replayed (a success for IDEMPOTENCY_REDIS_TTL_SECONDS, an
        # INFO / a failure for AI_RUN_SHORT_REPLAY_TTL_SECONDS). No key: a
        # random one — the run goes on as before (no 400).
        log_ctx = {'activity_id': str(activity.id)}
        idem = IdempotentRun(
            request, client_id, event='prep_call_run',
            running_message='A Game Plan is already being generated for this activity.',
            log_ctx=log_ctx,
        )
        replay = idem.start()
        if replay is not None:
            return replay
        try:
            return self._run(request, idem, activity, client_id, target_contact,
                             validated.get('language_overrides'), log_ctx)
        except StandardizedValidationError as exc:
            # The standard 400 (G11: an override to an unknown recipient) —
            # answered and replayed briefly, never left « running ».
            response = self.handle_exception(exc)
            return idem.respond_short(response.data, response.status_code)
        except Exception as exc:
            idem.record_failure(exc)
            raise

    def _run(self, request, idem, activity, client_id, target_contact, language_overrides, log_ctx):
        """The rules, then the generation — every answer recorded by `idem`."""
        # G3 — the business rules: 200 + an INFO code, nothing run.
        blocked = game_plan_blocked_reason(activity)
        if blocked:
            logger.info('prep_call_run.blocked', extra={**log_ctx, 'code': blocked})
            return idem.respond_short(_blocked_body(blocked), http_status.HTTP_200_OK)

        # Layer 2 — the DB hash dedup in the pipeline (G9: nothing new).
        # G10: no brief mode (the mode resolver and its extra deal-health
        # read are gone): the pack reads the latest snapshot ONCE.
        # G11: the languages chosen for an AI message — the recipient is
        # resolved by the roster here (an unknown one: a standard 400).
        assembler = PrepInputPackAssembler()
        input_pack = assembler.build(
            activity=activity,
            target_contact=target_contact,
            language_overrides=language_overrides,
        )

        # G11 (Q2) — an AI message needs a participant with a contact: a
        # business rule, 200 + INFO, nothing run.
        if input_pack.get('recipients') == []:
            logger.info('prep_call_run.blocked', extra={**log_ctx, 'code': PREP_CALL_NO_RECIPIENT_CODE})
            return idem.respond_short(_blocked_body(PREP_CALL_NO_RECIPIENT_CODE), http_status.HTTP_200_OK)

        try:
            pipeline = PrepCallPipeline()
            result = pipeline.run(
                activity=activity,
                target_contact=target_contact,
                input_pack=input_pack,
                user=request.user,
                client_id=client_id,
                output_kind=game_plan_output_kind(activity),
                people=assembler.people,
            )
        except Exception as exc:
            logger.exception('prep_call_run.pipeline_hard_crash', extra=log_ctx)
            idem.record_failure(exc)
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
            logger.info('prep_call_run.blocked', extra={**log_ctx, 'code': result['blocked']})
            return idem.respond_short(
                _blocked_body(result['blocked'], result.get('last_snapshot')),
                http_status.HTTP_200_OK,
            )

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
            return idem.respond(
                {'success': True, 'data': body},
                http_status.HTTP_201_CREATED,
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )

        return idem.respond_short(
            {
                'success': False,
                'error': (
                    run.error_message if run else 'Pipeline did not succeed.'
                ) or 'Pipeline did not succeed.',
                'data': body,
            },
            http_status.HTTP_502_BAD_GATEWAY,
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

    Returns the latest PrepCallSnapshot for the given Activity. Without any
    Game Plan yet: data null and `game_plan_freshness` (G14) — the deal
    health's freshness of the activity's cycle ({applies, has_new_info,
    last_analysis_at, reasons}), or null for an activity without cycle.
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
            # G14 — before the activity's FIRST Game Plan only: the banner
            # predicate (the deal health's freshness of its cycle; None for
            # an activity without cycle). The display comes with the UI step.
            from ..services.game_plan_freshness import game_plan_freshness
            return Response(
                {'success': True, 'data': None,
                 'game_plan_freshness': game_plan_freshness(activity)},
            )

        serializer = PrepCallSnapshotSerializer(
            snapshot,
            context={'request': request},
        )
        return Response({'success': True, 'data': serializer.data})


class PrepCallMessageLanguagesView(BaseAPIView):
    """
    GET /module-ai-pipelines/prep-call/message-languages/<uuid>/

    Sprint 2 Game Plan, G11 — the languages preview of an AI message, BEFORE
    the generation: per recipient {ref, first_name, language, source}
    (services/prep_call/message_language — Q2 / Q3 / Q7). Who may see it:
    who may generate (can_run_game_plan, a real 403). [] for an activity that
    is not an email / a LinkedIn message.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'ai_pipelines'
    http_method_names      = ['get', 'head', 'options']

    def get(self, request, activity_id, *args, **kwargs):
        from app_modules.activities.models import Activity
        from ..services.llm_people import activity_roster
        from ..services.prep_call.message_language import message_recipients

        activity = (
            Activity.objects.select_related('decision_cycle', 'account')
            .filter(id=activity_id, client_id=request.user.client_id).first()
        )
        if activity is None:
            return Response(
                {'success': False, 'error': str(AIPipelineErrorMessages.ACTIVITY_NOT_FOUND)},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        if not can_run_game_plan(request, activity):
            raise StandardizedPermissionDenied(CoreErrorMessages.PERMISSION_DENIED)

        recipients, omitted = [], 0
        if game_plan_output_kind(activity) == PrepCallOutputKind.MESSAGE:
            recipients, omitted = message_recipients(activity_roster(activity))
        return Response({
            'success': True,
            'data': {
                'recipients': [
                    {key: r[key] for key in ('ref', 'first_name', 'language', 'source')}
                    for r in recipients
                ],
                'max_recipients': PREP_CALL_MESSAGE_RECIPIENTS_MAX,
                'omitted_count': omitted,
            },
        })
