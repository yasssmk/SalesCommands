# app_modules/ai_pipelines/views/activity_extraction_view.py
"""
ActivityExtractionView -- unified POST endpoint that orchestrates BOTH
the qualification-signals pipeline AND the next-steps pipeline on a
single transcript, in one client call.

================================================================================
Tier: T4 -- External pipeline (chained 3rd-party LLM calls).
       See core/timeout_conventions.py for the full rule set.

Key tier rules applied here:
    R1 (cost gate)    : start_op() wraps the orchestration.
    R3 (polling)      : 202 + poll_url returned when another worker
                        is already processing the same key.
    R4 (key strategy) : deterministic Idempotency-Key from frontend
                        (sha256 of activity_id + transcript).
    R6 (DB dedup)     : layer-2 lookup on AIPipelineRun.input_hash,
                        NOW filtered by pipeline_type (resolves TD-8).
================================================================================

Endpoint
--------
    POST /module-ai-pipelines/activity-extraction/run/

Request
-------
    Header:  Idempotency-Key: <sha256-hex>     (set by frontend)
    Body:    {
        "activity_id": "<uuid>",
        "transcript":  "<text>"
    }

Response shape (200 OK)
-----------------------
    {
        "success": true,
        "data": {
            "status": "SUCCESS" | "PARTIAL" | "FAILED",
            "qualification_run":    { ...run serialized..., "from_cache": bool },
            "next_steps_run":       { ...run serialized..., "from_cache": bool },
            "qualification_signals": {
                "pain":       [...],
                "objective":  [...],
                "impact":     [...],
                "tech-stack": [...],
                "blocker":    [...],
                "constraint": [...]
            },
            "next_step_signals": [...]
        }
    }

Dedup strategy (resolves TD-8)
------------------------------
Each sub-pipeline is deduped INDEPENDENTLY by
(client_id, source_activity, input_hash, pipeline_type, status).
If one sub-pipeline has a prior successful run, its cached run metadata
is returned (from_cache: true) and only the missing sub-pipeline is
executed. If BOTH have prior runs, 409 ALREADY_EXTRACTED is returned
with the cached payload of both.
"""

import hashlib
import uuid

from rest_framework import status as http_status
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

from core.throttling import AIRateThrottle
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
from app_modules.signals.serializers.constraint_serializer import (
    ConstraintSignalDetailSerializer,
)
from app_modules.signals.serializers.next_step_serializer import (
    NextStepSignalDetailSerializer,
)

from ..constants import AIPipelineType
from ..models import AIPipelineRun
from ..pipelines.transcript_signals import QualificationSignalsPipeline
from ..pipelines.next_steps import NextStepsPipeline
from ..serializers.transcript_signals_serializer import (
    TranscriptSignalsExtractInputSerializer,
)


logger = get_logger(__name__)


class ActivityExtractionView(BaseAPIView):
    """
    POST /module-ai-pipelines/activity-extraction/run/
    Tier: T4 (see core/timeout_conventions.py).

    Orchestrates QualificationSignalsPipeline + NextStepsPipeline
    sequentially, with independent per-pipeline DB dedup.
    """

    authentication_classes = [CustomJWTAuthentication]
    permission_classes     = [IsAuthenticated, ScopedPermission]
    throttle_classes       = [AIRateThrottle]
    module                 = 'ai_pipelines'

    # =========================================================================
    # POST
    # =========================================================================

    def post(self, request, *args, **kwargs):
        try:
            return self._handle_extract(request)
        except Exception as exc:
            return self.handle_exception(exc)

    # =========================================================================
    # ORCHESTRATOR
    # =========================================================================

    def _handle_extract(self, request):

        # -----------------------------------------------------------------
        # 1. Validate input (reuses existing serializer)
        # -----------------------------------------------------------------
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
        want_qualif = validated['run_qualification']
        want_nextsteps = validated['run_next_steps']

        log_ctx = ctx_from_request(request) if callable(ctx_from_request) else {}
        log_ctx_base = {
            **log_ctx,
            'activity_id':       str(activity.id),
            'transcript_length': len(transcript),
            'tier':              AI_PIPELINE_TIER,
            'endpoint':          'activity-extraction',
        }

        # -----------------------------------------------------------------
        # 2. Idempotency key (Layer 1 — Redis)
        # -----------------------------------------------------------------
        idempotency_key = self._extract_idempotency_key(request)
        payload_hash    = compute_payload_hash(request.data)
        owner           = get_owner_from_request(request)

        log_ctx_idemp = {
            **log_ctx_base,
            'idempotency_key_prefix': idempotency_key[:16],
        }

        try:
            existing_op = start_op(
                client_id=client_id_str,
                key=idempotency_key,
                payload_hash=payload_hash,
                owner=owner,
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except ValueError as conflict_err:
            logger.warning(
                'activity_extraction.idempotency_conflict',
                extra=log_ctx_idemp,
            )
            return Response(
                {
                    'success': False,
                    'error':   str(conflict_err),
                    'code':    'IDEMPOTENCY_CONFLICT',
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        if existing_op is not None:
            return self._respond_existing_op(
                existing_op, idempotency_key, log_ctx_idemp,
            )

        logger.info(
            'activity_extraction.started',
            extra=log_ctx_idemp,
        )

        # -----------------------------------------------------------------
        # 3. Layer 2 — per-pipeline DB dedup
        # -----------------------------------------------------------------
        input_hash = self._compute_transcript_hash(transcript)

        qualif_cached_run = None
        nextsteps_cached_run = None

        if AI_PIPELINE_BACKEND_DB_DEDUP_REQUIRED:
            if want_qualif:
                qualif_cached_run = self._find_existing_run(
                    client_id=client_id,
                    activity=activity,
                    input_hash=input_hash,
                    pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS,
                )
            if want_nextsteps:
                nextsteps_cached_run = self._find_existing_run(
                    client_id=client_id,
                    activity=activity,
                    input_hash=input_hash,
                    pipeline_type=AIPipelineType.NEXT_STEPS,
                )

        # Both requested pipelines cached → 409 ALREADY_EXTRACTED
        qualif_resolved = (not want_qualif) or (qualif_cached_run is not None)
        nextsteps_resolved = (not want_nextsteps) or (nextsteps_cached_run is not None)
        if qualif_resolved and nextsteps_resolved and (qualif_cached_run or nextsteps_cached_run):
            logger.info(
                'activity_extraction.both_cached',
                extra={
                    **log_ctx_idemp,
                    'qualif_run_id':    str(qualif_cached_run.id),
                    'nextsteps_run_id': str(nextsteps_cached_run.id),
                },
            )
            body = self._build_cached_body(
                qualif_run=qualif_cached_run,
                nextsteps_run=nextsteps_cached_run,
                request=request,
            )
            return self._complete_and_respond(
                client_id_str=client_id_str,
                key=idempotency_key,
                body=body,
                response_status=http_status.HTTP_409_CONFLICT,
                log_ctx=log_ctx_idemp,
            )

        # -----------------------------------------------------------------
        # 4. Run pipelines (only those not cached)
        # -----------------------------------------------------------------
        qualif_result = None
        nextsteps_result = None
        qualif_error = None
        nextsteps_error = None

        # --- Qualification ---
        if want_qualif and qualif_cached_run is None:
            try:
                pipeline = QualificationSignalsPipeline()
                qualif_result = pipeline.run(
                    transcript=transcript,
                    activity=activity,
                    user=request.user,
                    client_id=client_id,
                )
            except Exception as exc:
                qualif_error = exc
                logger.exception(
                    'activity_extraction.qualif_pipeline_error',
                    extra=log_ctx_idemp,
                )

        # --- Next Steps ---
        if want_nextsteps and nextsteps_cached_run is None:
            try:
                pipeline = NextStepsPipeline()
                nextsteps_result = pipeline.run(
                    transcript=transcript,
                    activity=activity,
                    user=request.user,
                    client_id=client_id,
                )
            except Exception as exc:
                nextsteps_error = exc
                logger.exception(
                    'activity_extraction.nextsteps_pipeline_error',
                    extra=log_ctx_idemp,
                )

        # -----------------------------------------------------------------
        # 5. Derive global status (strict: SUCCESS only if both are SUCCESS)
        # -----------------------------------------------------------------
        qualif_status = self._get_sub_status(qualif_cached_run, qualif_result) if want_qualif else None
        nextsteps_status = self._get_sub_status(nextsteps_cached_run, nextsteps_result) if want_nextsteps else None

        qualif_ok = (not want_qualif) or qualif_status in ('SUCCESS', 'PARTIAL')
        nextsteps_ok = (not want_nextsteps) or nextsteps_status in ('SUCCESS', 'PARTIAL')

        qualif_success = (not want_qualif) or qualif_status == 'SUCCESS'
        nextsteps_success = (not want_nextsteps) or nextsteps_status == 'SUCCESS'

        if qualif_success and nextsteps_success:
            global_status = 'SUCCESS'
        elif qualif_ok or nextsteps_ok:
            global_status = 'PARTIAL'
        else:
            global_status = 'FAILED'

        # Both fresh requested pipelines crashed → record failure + raise
        if qualif_error and nextsteps_error:
            self._record_failure(
                client_id_str, idempotency_key, qualif_error, log_ctx_idemp,
            )
            raise qualif_error

        # -----------------------------------------------------------------
        # 6. Build response
        # -----------------------------------------------------------------
        body = self._build_response_body(
            global_status=global_status,
            qualif_cached_run=qualif_cached_run,
            qualif_result=qualif_result,
            nextsteps_cached_run=nextsteps_cached_run,
            nextsteps_result=nextsteps_result,
            request=request,
        )

        logger.info(
            'activity_extraction.success',
            extra={
                **log_ctx_idemp,
                'global_status': global_status,
            },
        )

        return self._complete_and_respond(
            client_id_str=client_id_str,
            key=idempotency_key,
            body=body,
            response_status=http_status.HTTP_200_OK,
            log_ctx=log_ctx_idemp,
        )

    # =========================================================================
    # DB DEDUP (per-pipeline — resolves TD-8)
    # =========================================================================

    @staticmethod
    def _find_existing_run(*, client_id, activity, input_hash, pipeline_type):
        """
        Layer 2 dedup: look up a prior successful AIPipelineRun for a
        specific (activity, transcript, pipeline_type) combination.

        Now filters by pipeline_type — resolves TD-8.
        """
        return (
            AIPipelineRun.objects
            .filter(
                client_id=client_id,
                source_activity=activity,
                input_hash=input_hash,
                pipeline_type=pipeline_type,
                status__in=AI_PIPELINE_DEDUP_RUN_STATUSES,
            )
            .order_by('-created_at')
            .first()
        )

    # =========================================================================
    # STATUS HELPERS
    # =========================================================================

    @staticmethod
    def _get_sub_status(cached_run, fresh_result):
        """Return the AIPipelineStatus string for a sub-pipeline, or None."""
        if cached_run is not None:
            return cached_run.status
        if fresh_result is not None:
            run = fresh_result.get('run')
            return run.status if run is not None else None
        return None

    # =========================================================================
    # RESPONSE SHAPING
    # =========================================================================

    def _build_response_body(
        self,
        *,
        global_status,
        qualif_cached_run,
        qualif_result,
        nextsteps_cached_run,
        nextsteps_result,
        request,
    ):
        ser_ctx = {'request': request}

        # --- Qualification ---
        if qualif_cached_run is not None:
            qualif_run_data = self._serialize_run(qualif_cached_run, from_cache=True)
            qualif_signals = self._serialize_cached_qualif_signals(
                qualif_cached_run, ser_ctx,
            )
        elif qualif_result is not None:
            qualif_run_data = self._serialize_run(
                qualif_result['run'], from_cache=False,
            )
            qualif_signals = self._serialize_fresh_qualif_signals(
                qualif_result['signals_by_stage'], ser_ctx,
            )
        else:
            qualif_run_data = None
            qualif_signals = self._empty_qualif_signals()

        # --- Next Steps ---
        if nextsteps_cached_run is not None:
            nextsteps_run_data = self._serialize_run(
                nextsteps_cached_run, from_cache=True,
            )
            nextsteps_signals = self._serialize_cached_nextstep_signals(
                nextsteps_cached_run, ser_ctx,
            )
        elif nextsteps_result is not None:
            nextsteps_run_data = self._serialize_run(
                nextsteps_result['run'], from_cache=False,
            )
            nextsteps_signals = NextStepSignalDetailSerializer(
                nextsteps_result['signals'], many=True, context=ser_ctx,
            ).data
        else:
            nextsteps_run_data = None
            nextsteps_signals = []

        data = {
            'status':                 global_status,
            'qualification_run':      qualif_run_data,
            'next_steps_run':         nextsteps_run_data,
            'qualification_signals':  qualif_signals,
            'next_step_signals':      nextsteps_signals,
        }

        return {'success': True, 'data': data}

    def _build_cached_body(self, *, qualif_run, nextsteps_run, request):
        """
        Build 409 response body when both pipelines are already extracted.

        Note on cache replay scope (TD-11): the serialized signals are
        ALL signals matching source_activity, not only those produced by
        these specific runs. Signals created manually or by prior runs
        on different transcripts will appear here. Acceptable for MVP;
        to be resolved when adding source_run FK tracking to signals.
        """
        ser_ctx = {'request': request}
        return {
            'success': False,
            'error': (
                'Both qualification signals and next steps have already '
                'been extracted for this transcript. Existing signals are '
                'available in the Signals and Next Steps tabs.'
            ),
            'code': 'ALREADY_EXTRACTED',
            'data': {
                'status':                'SUCCESS',
                'qualification_run':     self._serialize_run(
                    qualif_run, from_cache=True,
                ),
                'next_steps_run':        self._serialize_run(
                    nextsteps_run, from_cache=True,
                ),
                'qualification_signals': self._serialize_cached_qualif_signals(
                    qualif_run, ser_ctx,
                ),
                'next_step_signals':     self._serialize_cached_nextstep_signals(
                    nextsteps_run, ser_ctx,
                ),
            },
        }

    # =========================================================================
    # SERIALIZATION HELPERS
    # =========================================================================

    @staticmethod
    def _serialize_run(run, *, from_cache):
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
            'from_cache':            from_cache,
        }

    @staticmethod
    def _serialize_fresh_qualif_signals(signals_by_stage, ser_ctx):
        return {
            'pain':       PainSignalDetailSerializer(
                signals_by_stage.get('pain', []),
                many=True, context=ser_ctx,
            ).data,
            'objective':  ObjectiveSignalDetailSerializer(
                signals_by_stage.get('objective', []),
                many=True, context=ser_ctx,
            ).data,
            'impact':     ImpactSignalDetailSerializer(
                signals_by_stage.get('impact', []),
                many=True, context=ser_ctx,
            ).data,
            'tech-stack': TechStackSignalDetailSerializer(
                signals_by_stage.get('techstack', []),
                many=True, context=ser_ctx,
            ).data,
            'blocker':    BlockerSignalDetailSerializer(
                signals_by_stage.get('blocker', []),
                many=True, context=ser_ctx,
            ).data,
            'constraint': ConstraintSignalDetailSerializer(
                signals_by_stage.get('constraint', []),
                many=True, context=ser_ctx,
            ).data,
        }

    @staticmethod
    def _serialize_cached_qualif_signals(run, ser_ctx):
        """Re-query signals from DB for a cached qualification run."""
        from app_modules.signals.models import (
            PainSignal,
            ObjectiveSignal,
            ImpactSignal,
            TechStackSignal,
            BlockerSignal,
            ConstraintSignal,
        )
        activity = run.source_activity
        if activity is None:
            return {
                'pain': [], 'objective': [], 'impact': [],
                'tech-stack': [], 'blocker': [], 'constraint': [],
            }

        pain = PainSignal.objects.filter(source_activity=activity, source_run=run)
        objective = ObjectiveSignal.objects.filter(source_activity=activity, source_run=run)
        impact = ImpactSignal.objects.filter(source_activity=activity, source_run=run)
        techstack = TechStackSignal.objects.filter(source_activity=activity, source_run=run)
        blocker = BlockerSignal.objects.filter(source_activity=activity, source_run=run)
        constraint = ConstraintSignal.objects.filter(source_activity=activity, source_run=run)

        return {
            'pain':       PainSignalDetailSerializer(
                pain, many=True, context=ser_ctx,
            ).data,
            'objective':  ObjectiveSignalDetailSerializer(
                objective, many=True, context=ser_ctx,
            ).data,
            'impact':     ImpactSignalDetailSerializer(
                impact, many=True, context=ser_ctx,
            ).data,
            'tech-stack': TechStackSignalDetailSerializer(
                techstack, many=True, context=ser_ctx,
            ).data,
            'blocker':    BlockerSignalDetailSerializer(
                blocker, many=True, context=ser_ctx,
            ).data,
            'constraint': ConstraintSignalDetailSerializer(
                constraint, many=True, context=ser_ctx,
            ).data,
        }

    @staticmethod
    def _serialize_cached_nextstep_signals(run, ser_ctx):
        """Re-query NextStepSignals from DB for a cached next-steps run."""
        from app_modules.signals.models import NextStepSignal
        activity = run.source_activity
        if activity is None:
            return []
        signals = NextStepSignal.objects.filter(source_activity=activity, source_run=run)
        return NextStepSignalDetailSerializer(
            signals, many=True, context=ser_ctx,
        ).data

    @staticmethod
    def _empty_qualif_signals():
        return {
            'pain': [], 'objective': [], 'impact': [],
            'tech-stack': [], 'blocker': [], 'constraint': [],
        }

    # =========================================================================
    # IDEMPOTENCY HELPERS (mirror of TranscriptSignalsExtractView)
    # =========================================================================

    @staticmethod
    def _extract_idempotency_key(request):
        key = (
            request.headers.get('Idempotency-Key')
            or request.META.get('HTTP_IDEMPOTENCY_KEY')
        )
        if not key:
            key = str(uuid.uuid4())
            logger.warning(
                'activity_extraction.missing_idempotency_key',
                extra={'generated_uuid_prefix': key[:16]},
            )
        return key

    def _respond_existing_op(self, op, idempotency_key, log_ctx):
        op_status = op.get('status')

        if op_status == 'succeeded':
            cached = op.get('result') or {}
            http_code = cached.get('http_status', http_status.HTTP_200_OK)
            body = cached.get('data')
            if body is None:
                body = cached
            logger.info(
                'activity_extraction.idempotency_replay_success',
                extra={**log_ctx, 'replay_http_status': http_code},
            )
            return Response(body, status=http_code)

        if op_status == 'failed':
            cached_error = op.get('error') or 'Previous attempt failed'
            logger.info(
                'activity_extraction.idempotency_replay_failed',
                extra=log_ctx,
            )
            return Response(
                {
                    'success': False,
                    'error':   cached_error,
                    'code':    'IDEMPOTENCY_REPLAY_FAILED',
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if op_status == 'running':
            poll_url = POLLING_ENDPOINT_PATTERN.format(key=idempotency_key)
            logger.info(
                'activity_extraction.already_running',
                extra={**log_ctx, 'poll_url': poll_url},
            )
            return Response(
                {
                    'poll_url': poll_url,
                    'status':   'running',
                    'message':  'Extraction already in progress for this request.',
                },
                status=http_status.HTTP_202_ACCEPTED,
                headers={'Retry-After': str(POLLING_INTERVAL_SECONDS)},
            )

        logger.error(
            'activity_extraction.unknown_op_state',
            extra={**log_ctx, 'op_status': op_status},
        )
        return Response(
            {
                'success': False,
                'error':   'Unknown operation state in idempotency store.',
                'code':    'IDEMPOTENCY_UNKNOWN_STATE',
            },
            status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def _complete_and_respond(self, client_id_str, key, body,
                              response_status, log_ctx):
        try:
            complete_op(
                client_id=client_id_str,
                key=key,
                result={
                    'http_status': response_status,
                    'data':        body,
                },
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except Exception:
            logger.exception(
                'activity_extraction.complete_op_failed',
                extra=log_ctx,
            )
        return Response(body, status=response_status)

    def _record_failure(self, client_id_str, key, exc, log_ctx):
        try:
            fail_op(
                client_id=client_id_str,
                key=key,
                error=str(exc),
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except Exception:
            logger.exception(
                'activity_extraction.fail_op_failed',
                extra=log_ctx,
            )

    @staticmethod
    def _compute_transcript_hash(transcript):
        return hashlib.sha256(transcript.encode('utf-8')).hexdigest()
