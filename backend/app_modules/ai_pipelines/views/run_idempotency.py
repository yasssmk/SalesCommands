# app_modules/ai_pipelines/views/run_idempotency.py
"""
Layer 1 of an AI run endpoint — Redis idempotency (TD-50), the
core/idempotency.py pattern (start_op / complete_op / fail_op) shared by the
deal health (views/deal_health_view.py, where it was written — sprint « Deal
health v2 », step 6) and the Game Plan (views/prep_call_view.py, sprint 2
Game Plan, G12). Extracted unchanged from DealHealthRunView, its log events
kept by `event` ('deal_health_run' / 'prep_call_run').

  * the front's deterministic Idempotency-Key; without one, a random key —
    the run goes on as before (no 400);
  * the same key and payload while running -> 202 + poll_url; once answered
    -> the answer replayed (no 2nd LLM call); the same key with another
    payload -> 409 IDEMPOTENCY_CONFLICT;
  * a success is kept IDEMPOTENCY_REDIS_TTL_SECONDS; an INFO answer or a
    failure only AI_RUN_SHORT_REPLAY_TTL_SECONDS (a double click, a second
    tab — the rule is evaluated again on the next click);
  * without Redis in dev, the run goes on (core/idempotency.py
    _check_redis_available).
"""

import logging
import uuid

from rest_framework import status as http_status
from rest_framework.response import Response

from core.idempotency import (
    compute_payload_hash,
    complete_op,
    fail_op,
    get_owner_from_request,
    start_op,
)
from core.timeout_conventions import (
    IDEMPOTENCY_REDIS_TTL_SECONDS,
    POLLING_ENDPOINT_PATTERN,
    POLLING_INTERVAL_SECONDS,
)

from ..constants import AI_RUN_SHORT_REPLAY_TTL_SECONDS


logger = logging.getLogger(__name__)

__all__ = ['IdempotentRun']


class IdempotentRun:
    """
    One idempotent POST of an AI run.

    Usage:
        idem = IdempotentRun(request, client_id, event='prep_call_run',
                             running_message='...', log_ctx=log_ctx)
        replay = idem.start()
        if replay is not None:
            return replay                      # 409 / 202 / the replayed answer
        ...
        return idem.respond(body, status, ttl=...)
    """

    def __init__(self, request, client_id, *, event, running_message, log_ctx):
        self.request = request
        self.client_id_str = str(client_id)
        self.event = event
        self.running_message = running_message
        self.log_ctx = log_ctx
        self.key = self._extract_idempotency_key(request, event)
        log_ctx['idempotency_key_prefix'] = self.key[:16]

    def start(self):
        """None: a new operation, run it. Else the Response to return."""
        try:
            existing_op = start_op(
                client_id=self.client_id_str,
                key=self.key,
                payload_hash=compute_payload_hash(self.request.data),
                owner=get_owner_from_request(self.request),
                ttl=IDEMPOTENCY_REDIS_TTL_SECONDS,
            )
        except ValueError as conflict_err:
            logger.warning(f'{self.event}.idempotency_conflict', extra=self.log_ctx)
            return Response(
                {
                    'success': False,
                    'error':   str(conflict_err),
                    'code':    'IDEMPOTENCY_CONFLICT',
                },
                status=http_status.HTTP_409_CONFLICT,
            )
        if existing_op is not None:
            return self._respond_existing_op(existing_op)
        return None

    def respond(self, body, response_status, *, ttl):
        """Record the answer for the replays, then return it."""
        try:
            complete_op(
                client_id=self.client_id_str,
                key=self.key,
                result={'http_status': response_status, 'data': body},
                ttl=ttl,
            )
        except Exception:
            logger.exception(f'{self.event}.complete_op_failed', extra=self.log_ctx)
        return Response(body, status=response_status)

    def respond_short(self, body, response_status):
        """An INFO answer or a failure: replayed only a short time."""
        return self.respond(body, response_status, ttl=AI_RUN_SHORT_REPLAY_TTL_SECONDS)

    def record_failure(self, exc):
        try:
            fail_op(
                client_id=self.client_id_str,
                key=self.key,
                error=str(exc),
                ttl=AI_RUN_SHORT_REPLAY_TTL_SECONDS,
            )
        except Exception:
            logger.exception(f'{self.event}.fail_op_failed', extra=self.log_ctx)

    # =========================================================================
    # INTERNALS (activity_extraction_view.py:607-705)
    # =========================================================================

    @staticmethod
    def _extract_idempotency_key(request, event):
        key = (
            request.headers.get('Idempotency-Key')
            or request.META.get('HTTP_IDEMPOTENCY_KEY')
        )
        if not key:
            key = str(uuid.uuid4())
            logger.warning(
                f'{event}.missing_idempotency_key',
                extra={'generated_uuid_prefix': key[:16]},
            )
        return key

    def _respond_existing_op(self, op):
        op_status = op.get('status')

        if op_status == 'succeeded':
            cached = op.get('result') or {}
            http_code = cached.get('http_status', http_status.HTTP_200_OK)
            body = cached.get('data')
            if body is None:
                body = cached
            logger.info(
                f'{self.event}.idempotency_replay',
                extra={**self.log_ctx, 'replay_http_status': http_code},
            )
            return Response(body, status=http_code)

        if op_status == 'failed':
            logger.info(f'{self.event}.idempotency_replay_failed', extra=self.log_ctx)
            return Response(
                {
                    'success': False,
                    'error':   op.get('error') or 'Previous attempt failed',
                    'code':    'IDEMPOTENCY_REPLAY_FAILED',
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if op_status == 'running':
            poll_url = POLLING_ENDPOINT_PATTERN.format(key=self.key)
            logger.info(
                f'{self.event}.already_running',
                extra={**self.log_ctx, 'poll_url': poll_url},
            )
            return Response(
                {
                    'poll_url': poll_url,
                    'status':   'running',
                    'message':  self.running_message,
                },
                status=http_status.HTTP_202_ACCEPTED,
                headers={'Retry-After': str(POLLING_INTERVAL_SECONDS)},
            )

        logger.error(
            f'{self.event}.unknown_op_state',
            extra={**self.log_ctx, 'op_status': op_status},
        )
        return Response(
            {
                'success': False,
                'error':   'Unknown operation state in idempotency store.',
                'code':    'IDEMPOTENCY_UNKNOWN_STATE',
            },
            status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
