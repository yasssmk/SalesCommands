# app_modules/ai_pipelines/views/transcript_signals_view.py
"""
TranscriptSignalsExtractView -- single POST endpoint for the
transcript-based signal extraction pipeline.

================================================================================
Tier: T4 -- External pipeline (chained 3rd-party LLM calls).
       See core/timeout_conventions.py for the full rule set.

Key tier rules applied here:
    R1 (cost gate)    : start_op() wraps every pipeline.run() call.
    R3 (polling)      : 202 + poll_url returned when another worker
                        is already processing the same key.
    R4 (key strategy) : deterministic Idempotency-Key from frontend
                        (sha256 of activity_id + transcript).
    R6 (DB dedup)     : layer-2 lookup on AIPipelineRun.input_hash for
                        the "Redis TTL expired, same op retried" case.
================================================================================

Endpoint
--------
    POST /module-ai-pipelines/transcript-signals/extract/

Request
-------
    Header:  Idempotency-Key: <sha256-hex>     (set by frontend)
    Body:    {
        "activity_id": "<uuid>",
        "transcript":  "<text>"
    }

Response paths
--------------
    200 OK           Fresh extraction completed OR Redis-cached replay.
                     Body: {success: true, data: {run_id, status,
                                                  signals_by_stage, ...}}

    202 Accepted     Another worker is processing the same key.
                     Body: {poll_url, status: "running", message}
                     Header: Retry-After: <seconds>
                     Client should poll /ops/{key}/ until the run resolves.

    409 Conflict     Two flavours:
                     (a) IDEMPOTENCY_CONFLICT -- same key, different payload.
                         Should not happen with deterministic keys.
                     (b) ALREADY_EXTRACTED -- DB dedup hit on
                         AIPipelineRun.input_hash. Signals from the prior
                         run exist in the Signals tab; we do not replay
                         them here (they may have been validated/rejected
                         since).

    400 Bad Request  Input validation failure (transcript length,
                     activity not found, etc. -- see G.1).

    500 / 502 / 503  Provider-side failure or Redis-side failure
                     (handled by BaseAPIView.handle_exception).

Response envelope shape
-----------------------
Every JSON body follows the standard envelope used elsewhere in the
codebase so the frontend api wrapper unwraps consistently:

    {
        "success": <bool>,
        "data":    <object>,        # present on success, dedup, and replay
        "error":   <string>,        # present on failure paths
        "code":    <string>,        # machine-readable code on failure paths
    }

`signals_by_stage` keys are aligned with the frontend convention
("pain" / "objective" / "tech-stack" with a dash on the latter).
Internal pipeline stage key 'techstack' is translated to 'tech-stack'
once, at the response boundary.

Polling integration
-------------------
The Idempotency-Key passed in the request is what the frontend
`handleBulkTimeout` will use to poll /ops/{key}/. The Redis state
stored here via complete_op/fail_op is what /ops/{key}/ reads.
End-to-end the same key, same data, same path.

Defense-in-depth notes
----------------------
* If Redis is unavailable in dev (REQUIRE_REDIS_IDEMPOTENCY=False),
  start_op returns None and we proceed straight to layer 2 + pipeline.
  Replay protection is disabled but the request still succeeds.
* If Redis is unavailable in prod, start_op raises -> 503 via
  handle_exception. No silent corruption.
* If gunicorn kills the worker mid-pipeline (deploy SIGTERM),
  fail_op is NOT called -- the Redis op stays in 'running' state
  until TTL expires. Polling client sees 'still_running' for the
  remainder of TTL, then can retry with the same key (start_op will
  see an expired TTL = no entry, proceeds fresh).
"""

import hashlib
import logging
import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.apps_shared_methods import BaseAPIView
from core.idempotency import (
    compute_payload_hash,
    complete_op,
    fail_op,
    get_owner_from_request,
    start_op,
)
from core.jwt_helpers import CustomJWTAuthentication
from core.logging import ctx_from_request, get_logger
from core.timeout_conventions import (
    AI_PIPELINE_BACKEND_DB_DEDUP_REQUIRED,
    AI_PIPELINE_DEDUP_RUN_STATUSES,
    AI_PIPELINE_TIER,
    IDEMPOTENCY_REDIS_TTL_SECONDS,
    POLLING_ENDPOINT_PATTERN,
    POLLING_INTERVAL_SECONDS,
)

from permissions.mixins import ScopedPermission

from app_modules.signals.serializers.pain_serializer import (
    PainSignalDetailSerializer,
)
from app_modules.signals.serializers.objective_serializer import (
    ObjectiveSignalDetailSerializer,
)
from app_modules.signals.serializers.impact_serializer import (
    ImpactSignalDetailSerializer,
)
from app_modules.signals.serializers.tech_stack_serializer import (
    TechStackSignalDetailSerializer,
)
from app_modules.signals.serializers.blocker_serializer import (
    BlockerSignalDetailSerializer,
)

from ..config import TRANSCRIPT_SIGNALS_SUNSET_DATE
from ..models import AIPipelineRun
from ..pipelines.transcript_signals import QualificationSignalsPipeline
from ..serializers.transcript_signals_serializer import (
    TranscriptSignalsExtractInputSerializer,
)


logger = get_logger(__name__)


# =============================================================================
# VIEW
# =============================================================================


class TranscriptSignalsExtractView(BaseAPIView):
    """
    POST /module-ai-pipelines/transcript-signals/extract/
    Tier: T4 (see core/timeout_conventions.py).

    See module docstring for the full request / response contract.
    """

    # -------------------------------------------------------------------------
    # SECURITY (matches ActivityViewSet / ContactViewSet / TerritoryViewSet)
    # -------------------------------------------------------------------------

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    module                 = 'ai_pipelines'

    # No serializer_class / queryset / entity_name declared -- this is
    # an RPC-style action endpoint, not a resource collection.

    # =========================================================================
    # POST
    # =========================================================================

    def post(self, request, *args, **kwargs):
        """Thin wrapper: dispatch to _handle_extract, route exceptions."""
        try:
            response = self._handle_extract(request)
        except Exception as exc:
            response = self.handle_exception(exc)
        self._add_deprecation_headers(response)
        return response

    @staticmethod
    def _add_deprecation_headers(response):
        """Mark this endpoint as deprecated (TD-10). Migrate to /activity-extraction/run/."""
        response['Deprecation'] = 'true'
        response['Sunset'] = TRANSCRIPT_SIGNALS_SUNSET_DATE
        response['Link'] = (
            '</module-ai-pipelines/activity-extraction/run/>; '
            'rel="successor-version"'
        )

    # =========================================================================
    # ORCHESTRATOR
    # =========================================================================

    def _handle_extract(self, request):
        """
        Core extraction flow with 2-layer dedup.

        Each layer short-circuits the next on hit. Only a clean miss on
        BOTH layers triggers a fresh pipeline execution.
        """

        # ---------------------------------------------------------------------
        # 1. Validate input
        # ---------------------------------------------------------------------
        input_serializer = TranscriptSignalsExtractInputSerializer(
            data=request.data,
            context={'request': request},
        )
        input_serializer.is_valid(raise_exception=True)
        validated = input_serializer.validated_data

        activity   = validated['activity']
        transcript = validated['transcript']
        client_id  = validated['client_id']
        client_id_str = str(client_id)

        log_ctx = ctx_from_request(request) if callable(ctx_from_request) else {}
        log_ctx_base = {
            **log_ctx,
            'activity_id':       str(activity.id),
            'transcript_length': len(transcript),
            'tier':              AI_PIPELINE_TIER,
        }

        # ---------------------------------------------------------------------
        # 2. Resolve idempotency key
        # ---------------------------------------------------------------------
        # Tier T4 convention R4: frontend computes
        #     sha256(activity_id + transcript.trim())
        # and sends it as the Idempotency-Key header. If absent, we
        # fall back to a random UUID -- defensive only, axios always
        # injects an Idempotency-Key on POST.
        idempotency_key = self._extract_idempotency_key(request)
        payload_hash    = compute_payload_hash(request.data)
        owner           = get_owner_from_request(request)

        log_ctx_idemp = {
            **log_ctx_base,
            'idempotency_key_prefix': idempotency_key[:16],
        }

        # ---------------------------------------------------------------------
        # 3. Layer 1: Redis idempotency check
        # ---------------------------------------------------------------------
        try:
            existing_op = start_op(
                client_id=client_id_str,
                key=idempotency_key,
                payload_hash=payload_hash,
                owner=owner,
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except ValueError as conflict_err:
            # start_op raises ValueError when the same key has been used
            # with a DIFFERENT payload. With deterministic keys this
            # should not happen in normal usage -- treat as 409.
            logger.warning(
                'transcript_signals_extract.idempotency_conflict',
                extra=log_ctx_idemp,
            )
            return Response(
                {
                    'success': False,
                    'error':   str(conflict_err),
                    'code':    'IDEMPOTENCY_CONFLICT',
                },
                status=status.HTTP_409_CONFLICT,
            )

        if existing_op is not None:
            # Redis has prior state for this key + payload.
            return self._respond_existing_op(
                existing_op,
                idempotency_key,
                log_ctx_idemp,
            )

        # New operation -- Redis state is now 'running'. Any path out
        # of here MUST end in complete_op() or fail_op() so the state
        # is moved out of 'running'.
        logger.info(
            'transcript_signals_extract.started',
            extra=log_ctx_idemp,
        )

        # ---------------------------------------------------------------------
        # 4. Layer 2: DB dedup on AIPipelineRun.input_hash
        # ---------------------------------------------------------------------
        # Convention R6: catches the case where Redis TTL expired (10 min)
        # but the same logical operation is being retried.
        if AI_PIPELINE_BACKEND_DB_DEDUP_REQUIRED:
            dedup_response = self._check_db_dedup(
                client_id=client_id,
                client_id_str=client_id_str,
                activity=activity,
                transcript=transcript,
                idempotency_key=idempotency_key,
                log_ctx=log_ctx_idemp,
            )
            if dedup_response is not None:
                return dedup_response

        # ---------------------------------------------------------------------
        # 5. Run pipeline
        # ---------------------------------------------------------------------
        try:
            pipeline = QualificationSignalsPipeline()
            result = pipeline.run(
                transcript=transcript,
                activity=activity,
                user=request.user,
                client_id=client_id,
            )
        except Exception as pipeline_exc:
            # Pipeline crash (uncaught provider failure, DB outage, etc.).
            # Move Redis state out of 'running' -> 'failed' so future
            # replays within TTL surface a clean error instead of
            # spinning forever on 202.
            self._record_pipeline_failure(
                client_id_str,
                idempotency_key,
                pipeline_exc,
                log_ctx_idemp,
            )
            raise  # propagates to post() -> handle_exception -> 500

        # ---------------------------------------------------------------------
        # 6. Build response payload + cache for idempotent replay
        # ---------------------------------------------------------------------
        body = self._build_success_body(result, request)

        run = result['run']
        logger.info(
            'transcript_signals_extract.success',
            extra={
                **log_ctx_idemp,
                'run_id':                str(run.id),
                'pipeline_status':       run.status,
                'created_signals_count': run.created_signals_count,
                'total_tokens_used':     run.total_tokens_used,
                'total_duration_ms':     run.total_duration_ms,
            },
        )

        return self._complete_and_respond(
            client_id_str=client_id_str,
            key=idempotency_key,
            body=body,
            http_status=status.HTTP_200_OK,
            log_ctx=log_ctx_idemp,
        )

    # =========================================================================
    # HELPERS -- IDEMPOTENCY
    # =========================================================================

    def _extract_idempotency_key(self, request):
        """
        Read the Idempotency-Key header.

        Convention R4: T4 strategy is DETERMINISTIC. The frontend
        explicitly sets the header to sha256(activity_id + transcript).
        Falling back to a random UUID would defeat the dedup, but we
        do it defensively to keep the framework usable if a malformed
        client ever calls us without the header.
        """
        key = (
            request.headers.get('Idempotency-Key')
            or request.META.get('HTTP_IDEMPOTENCY_KEY')
        )
        if not key:
            key = str(uuid.uuid4())
            logger.warning(
                'transcript_signals_extract.missing_idempotency_key',
                extra={'generated_uuid_prefix': key[:16]},
            )
        return key

    def _respond_existing_op(self, op, idempotency_key, log_ctx):
        """
        Replay an existing Redis idempotency state.

        Possible op['status'] values:
            'succeeded' -> replay cached response body + http_status.
            'failed'    -> replay cached error.
            'running'   -> tell client to poll /ops/{key}/.
        """
        op_status = op.get('status')

        if op_status == 'succeeded':
            cached = op.get('result') or {}
            # Cache shape: {'http_status': int, 'data': <full body>}
            http_status_code = cached.get('http_status', status.HTTP_200_OK)
            body = cached.get('data')
            if body is None:
                # Tolerate older / malformed cache entries: treat the
                # raw result as the body.
                body = cached
            logger.info(
                'transcript_signals_extract.idempotency_replay_success',
                extra={**log_ctx, 'replay_http_status': http_status_code},
            )
            return Response(body, status=http_status_code)

        if op_status == 'failed':
            cached_error = op.get('error') or 'Previous attempt failed'
            logger.info(
                'transcript_signals_extract.idempotency_replay_failed',
                extra=log_ctx,
            )
            return Response(
                {
                    'success': False,
                    'error':   cached_error,
                    'code':    'IDEMPOTENCY_REPLAY_FAILED',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if op_status == 'running':
            # Another worker is processing -- send the client to the
            # polling endpoint. The axios response interceptor enriches
            # response.data with __is202 / __poll_url / __retry_after_ms;
            # the frontend handleBulkRevalidation picks it up from there.
            poll_url = POLLING_ENDPOINT_PATTERN.format(key=idempotency_key)
            logger.info(
                'transcript_signals_extract.already_running',
                extra={**log_ctx, 'poll_url': poll_url},
            )
            return Response(
                {
                    'poll_url': poll_url,
                    'status':   'running',
                    'message':  'Extraction already in progress for this request.',
                },
                status=status.HTTP_202_ACCEPTED,
                headers={'Retry-After': str(POLLING_INTERVAL_SECONDS)},
            )

        # Unknown / corrupted state -- defensive fallback.
        logger.error(
            'transcript_signals_extract.unknown_op_state',
            extra={**log_ctx, 'op_status': op_status},
        )
        return Response(
            {
                'success': False,
                'error':   'Unknown operation state in idempotency store.',
                'code':    'IDEMPOTENCY_UNKNOWN_STATE',
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def _complete_and_respond(self, client_id_str, key, body, http_status, log_ctx):
        """
        Cache the response in Redis AND return it.

        Single helper to ensure every success / dedup response path
        moves the Redis state out of 'running' to 'succeeded'. Skipping
        this would leave keys stuck in 'running' until TTL.

        Cache shape: {'http_status': int, 'data': <full response body>}.
        Matches the convention used by bulk operations elsewhere in the
        codebase (the frontend's polling helpers expect result.data to
        be the body).
        """
        try:
            complete_op(
                client_id=client_id_str,
                key=key,
                result={
                    'http_status': http_status,
                    'data':        body,
                },
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except Exception:
            # Never let a Redis hiccup break the actual response. Log
            # the failure so we notice if the idempotency store stops
            # working, and continue: the response still goes out.
            logger.exception(
                'transcript_signals_extract.complete_op_failed',
                extra=log_ctx,
            )

        return Response(body, status=http_status)

    def _record_pipeline_failure(self, client_id_str, key, exc, log_ctx):
        """
        Move Redis state from 'running' -> 'failed'. Swallow internal
        errors so we never mask the original pipeline exception.
        """
        try:
            fail_op(
                client_id=client_id_str,
                key=key,
                error=str(exc),
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except Exception:
            logger.exception(
                'transcript_signals_extract.fail_op_failed',
                extra=log_ctx,
            )

    # =========================================================================
    # HELPERS -- DB DEDUP
    # =========================================================================

    def _check_db_dedup(
        self,
        client_id,
        client_id_str,
        activity,
        transcript,
        idempotency_key,
        log_ctx,
    ):
        """
        Layer 2 dedup: look up AIPipelineRun for a prior successful
        extraction on the same (activity, transcript).

        Returns:
            None              on miss (caller proceeds with pipeline).
            Response (409)    on hit. The Redis op is also moved to
                              'succeeded' with the 409 payload cached,
                              so future replays within TTL bypass the
                              DB roundtrip entirely.

        We do NOT replay the existing run's signals -- they may have
        been validated / rejected / edited since extraction, and
        replaying would surface stale state. The 409 directs the user
        to the Signals tab instead.
        """
        input_hash = self._compute_transcript_hash(transcript)

        existing_run = (
            AIPipelineRun.objects
            .filter(
                client_id=client_id,
                source_activity=activity,
                input_hash=input_hash,
                status__in=AI_PIPELINE_DEDUP_RUN_STATUSES,
            )
            .order_by('-created_at')
            .first()
        )

        if existing_run is None:
            return None

        body = {
            'success': False,
            'error':   (
                'This transcript has already been extracted for this '
                'activity. Existing signals are available in the '
                'Signals tab.'
            ),
            'code': 'ALREADY_EXTRACTED',
            'data': {
                'run_id':                str(existing_run.id),
                'status':                existing_run.status,
                'created_at':            (
                    existing_run.created_at.isoformat()
                    if existing_run.created_at else None
                ),
                'created_signals_count': existing_run.created_signals_count,
            },
        }

        logger.info(
            'transcript_signals_extract.db_dedup_hit',
            extra={
                **log_ctx,
                'existing_run_id':     str(existing_run.id),
                'existing_run_status': existing_run.status,
            },
        )

        # Cache the 409 outcome so further calls with the same key
        # within TTL replay instantly without re-running the DB query.
        return self._complete_and_respond(
            client_id_str=client_id_str,
            key=idempotency_key,
            body=body,
            http_status=status.HTTP_409_CONFLICT,
            log_ctx=log_ctx,
        )

    @staticmethod
    def _compute_transcript_hash(transcript):
        """
        Compute the input_hash matching BasePipeline._create_run.

        Both this view (for the layer-2 dedup query) and the pipeline
        (for the AIPipelineRun.input_hash column) must produce the same
        hash from the same trimmed transcript -- otherwise the dedup
        query never matches. Keeping this logic identical to the
        pipeline's hashing is a hard correctness requirement.
        """
        return hashlib.sha256(transcript.encode('utf-8')).hexdigest()

    # =========================================================================
    # HELPERS -- RESPONSE SHAPING
    # =========================================================================

    def _build_success_body(self, pipeline_result, request):
        """
        Build the standard {success, data} envelope from a pipeline run.

        signals_by_stage keys are aligned with the frontend convention
        (SIGNAL_TYPES = ["pain", "objective", "tech-stack"] in
        frontend/src/api/signals/signals.js). The pipeline emits
        'techstack' (no dash) internally; we translate to 'tech-stack'
        once, at the response boundary.
        """
        signals_by_stage = pipeline_result['signals_by_stage']
        run = pipeline_result['run']

        ser_ctx = {'request': request}

        pain_payload = PainSignalDetailSerializer(
            signals_by_stage.get('pain', []),
            many=True,
            context=ser_ctx,
        ).data
        objective_payload = ObjectiveSignalDetailSerializer(
            signals_by_stage.get('objective', []),
            many=True,
            context=ser_ctx,
        ).data
        impact_payload = ImpactSignalDetailSerializer(
            signals_by_stage.get('impact', []),
            many=True,
            context=ser_ctx,
        ).data
        techstack_payload = TechStackSignalDetailSerializer(
            signals_by_stage.get('techstack', []),
            many=True,
            context=ser_ctx,
        ).data
        blocker_payload = BlockerSignalDetailSerializer(
            signals_by_stage.get('blocker', []),
            many=True,
            context=ser_ctx,
        ).data

        sub_calls = run.sub_calls or []
        total_emitted = sum(sub.get('emitted_count', 0) for sub in sub_calls)
        total_dropped = sum(
            sub.get('dropped_by_safety_filter', 0) for sub in sub_calls
        )

        # signals_by_stage key naming convention:
        #   - 'tech-stack' uses a dash for parity with the URL pattern
        #     /module-signals/tech-stack/ (legacy frontend convention).
        #   - 'blocker' (singular, no dash) matches the pipeline-internal
        #     stage name and the URL pattern /module-signals/blockers/
        #     stripped of its plural -- consistent with the per-signal
        #     identifier used everywhere else (SignalManager dispatch,
        #     AIPipelineRun.sub_calls[].stage).
        data = {
            'run_id':                          str(run.id),
            'status':                          run.status,
            'total_emitted':                   total_emitted,
            'total_dropped_by_safety_filter':  total_dropped,
            'created_signals_count':           run.created_signals_count,
            'signals_by_stage': {
                'pain':       pain_payload,
                'objective':  objective_payload,
                'impact':       impact_payload,
                'tech-stack': techstack_payload,
                'blocker':    blocker_payload,
            },
        }

        return {
            'success': True,
            'data':    data,
        }