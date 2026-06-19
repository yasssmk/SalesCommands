# app_modules/ai_pipelines/pipelines/prep_call.py
"""
PrepCallPipeline -- single-stage LLM pipeline that produces a
structured tactical brief for an upcoming Activity from validated
signals and the last DealHealthSnapshot.

Single stage: one LLM call, one structural validation + snapshot
persistence, one sub-call audit entry.

Error handling mirrors DealHealthPipeline (single stage = no PARTIAL):

    PromptParseError after retry  -> PARSE_ERROR.
    LLMTimeoutError               -> TIMEOUT.
    LLMRateLimitError             -> LLM_ERROR.
    LLMAuthError                  -> LLM_ERROR.
    LLMProviderError (generic)    -> LLM_ERROR.

Return contract:
    .run(*, activity, target_contact, brief_mode, input_pack,
         user, client_id) -> {
        'run':      AIPipelineRun (finalised),
        'snapshot': PrepCallSnapshot | None,
    }
"""

import hashlib
import json
import logging

from django.db import transaction

from ..constants import AIPipelineStatus, AIPipelineType, PIPELINE_TEMPERATURES
from ..prompts.base import PromptParseError
from ..prompts.prep_call import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    build_context_layer,
    CONTEXT_VERSION,
    build_brief_request,
    BRIEF_PROMPT_VERSION,
)
from ..providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .base import BasePipeline


logger = logging.getLogger(__name__)

_STAGE_NAME = 'brief'


class PrepCallPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.PREP_CALL

    PROMPT_VERSIONS = {
        'system':  SYSTEM_PROMPT_VERSION,
        'context': CONTEXT_VERSION,
        'brief':   BRIEF_PROMPT_VERSION,
    }

    TEMPERATURE = PIPELINE_TEMPERATURES[AIPipelineType.PREP_CALL]

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, activity, target_contact, brief_mode, input_pack,
            user, client_id):
        """
        Execute the single-stage prep-call brief pipeline.

        Args:
            activity:       Activity instance.
            target_contact: Contact instance or None.
            brief_mode:     str — resolved brief mode.
            input_pack:     dict — assembled input pack.
            user:           end_users.User — the rep who triggered the run.
            client_id:      UUID — tenant scope.

        Returns:
            dict: {
                'run':      AIPipelineRun (finalised),
                'snapshot': PrepCallSnapshot | None,
            }
        """
        input_text = json.dumps(input_pack, default=str)
        input_hash = self._compute_idempotence_hash(
            input_pack=input_pack,
            brief_mode=brief_mode,
            target_contact=target_contact,
        )

        existing = self._find_existing_snapshot(input_hash, activity)
        if existing:
            logger.info(
                'prep_call_dedup_hit',
                extra={
                    'activity_id': str(activity.id),
                    'input_hash': input_hash,
                    'event': 'ai_pipeline_dedup',
                },
            )
            return existing

        try:
            with transaction.atomic():
                run = self._create_run(
                    user=user,
                    client_id=client_id,
                    source_activity=activity,
                    source_decision_cycle=activity.decision_cycle,
                    input_text=input_text,
                )

                try:
                    context_layer = build_context_layer(input_pack, brief_mode)
                    request_layer = build_brief_request(input_pack, brief_mode)

                    parsed, sub_call_meta = self._call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        context=context_layer,
                        request=request_layer,
                    )

                    self._validate_brief(parsed)

                    snapshot = self._persist_snapshot(
                        parsed=parsed,
                        activity=activity,
                        target_contact=target_contact,
                        brief_mode=brief_mode,
                        input_hash=input_hash,
                        run=run,
                        user=user,
                        client_id=client_id,
                    )

                    self._log_sub_call(
                        run,
                        stage=_STAGE_NAME,
                        sub_call_meta=sub_call_meta,
                        parsed=parsed,
                        error=None,
                        dropped_count=0,
                    )

                except LLMTimeoutError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.TIMEOUT,
                        error_label='timeout',
                        exc=exc,
                    )
                except LLMRateLimitError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='rate_limit',
                        exc=exc,
                    )
                except LLMAuthError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='auth_error',
                        exc=exc,
                    )
                except PromptParseError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.PARSE_ERROR,
                        error_label='parse_error',
                        exc=exc,
                    )
                except LLMProviderError as exc:
                    return self._finalize_failure(
                        run,
                        status=AIPipelineStatus.LLM_ERROR,
                        error_label='provider_error',
                        exc=exc,
                    )

                final_run = self._finalize_run(
                    run,
                    status=AIPipelineStatus.SUCCESS,
                    created_signals_count=0,
                    error_message='',
                )
            return {'run': final_run, 'snapshot': snapshot}

        except Exception as exc:
            self._finalize_run(
                run,
                status=AIPipelineStatus.LLM_ERROR,
                created_signals_count=0,
                error_message=f'hard crash: {str(exc)[:1000]}',
            )
            raise

    # =========================================================================
    # IDEMPOTENCE — DB dedup (layer 2)
    # =========================================================================

    @staticmethod
    def _compute_idempotence_hash(*, input_pack, brief_mode, target_contact):
        """
        SHA-256 of deterministic input components for DB-layer dedup.

        Components (sorted for stability):
        - validated signal count
        - last DealHealthSnapshot date (or "none")
        - target_contact id (or "none")
        - current step name (or "none")
        - brief_mode
        """
        parts = []

        scope = input_pack.get('evidence_scope', {})
        parts.append(f"signals:{scope.get('validated_signals_count', 0)}")

        ctx = input_pack.get('prep_context', {})
        parts.append(
            f"snapshot_date:{ctx.get('last_deal_health_snapshot_date') or 'none'}"
        )
        parts.append(
            f"contact:{str(target_contact.id) if target_contact else 'none'}"
        )
        parts.append(f"step:{ctx.get('current_step') or 'none'}")
        parts.append(f"mode:{brief_mode}")

        # Maturity dimensions for finer-grained dedup
        maturity = input_pack.get('maturity_snapshot')
        if maturity:
            dim_str = ','.join(
                f"{d['key']}={d['status']}"
                for d in maturity.get('dimensions', [])
            )
            parts.append(f"dims:{dim_str}")
        else:
            parts.append('dims:none')

        composite = '|'.join(sorted(parts))
        return hashlib.sha256(composite.encode('utf-8')).hexdigest()

    @staticmethod
    def _find_existing_snapshot(input_hash, activity):
        """
        Check if a PrepCallSnapshot with this hash already exists.

        Returns the cached result dict or None.
        """
        from ..models import PrepCallSnapshot

        snapshot = (
            PrepCallSnapshot.objects
            .filter(activity=activity, input_hash=input_hash)
            .select_related('pipeline_run')
            .order_by('-snapshot_date')
            .first()
        )
        if not snapshot:
            return None

        return {
            'run': snapshot.pipeline_run,
            'snapshot': snapshot,
        }

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    @staticmethod
    def _persist_snapshot(*, parsed, activity, target_contact, brief_mode,
                          input_hash, run, user, client_id):
        from ..models import PrepCallSnapshot

        snapshot = PrepCallSnapshot(
            activity=activity,
            pipeline_run=run,
            target_contact=target_contact,
            brief_mode=brief_mode,
            brief=parsed,
            input_hash=input_hash,
        )
        snapshot.save(user=user, client_id=client_id)

        logger.info(
            'prep_call_snapshot_created',
            extra={
                'snapshot_id': str(snapshot.id),
                'activity_id': str(activity.id),
                'run_id': str(run.id),
                'brief_mode': brief_mode,
                'event': 'ai_pipeline_persist',
            },
        )

        return snapshot

    # =========================================================================
    # STRUCTURAL VALIDATION
    # =========================================================================

    @staticmethod
    def _validate_brief(parsed):
        if not isinstance(parsed, dict):
            raise PromptParseError(
                'Brief must be a JSON object.'
            )

        if not isinstance(parsed.get('context'), str):
            raise PromptParseError(
                'Missing or invalid "context" (expected string).'
            )

        objectives = parsed.get('objectives')
        if not isinstance(objectives, list) or not objectives:
            raise PromptParseError(
                'Missing or invalid "objectives" (expected non-empty list).'
            )
        for obj in objectives:
            if not isinstance(obj, dict):
                raise PromptParseError(
                    'Each objective must be a JSON object.'
                )
            if obj.get('rank') not in ('primary', 'secondary'):
                raise PromptParseError(
                    f'Invalid objective rank: "{obj.get("rank")}". '
                    f'Expected "primary" or "secondary".'
                )

        rhetoric = parsed.get('rhetoric')
        if not isinstance(rhetoric, dict):
            raise PromptParseError(
                'Missing or invalid "rhetoric" (expected object).'
            )
        for field in ('register', 'key_argument', 'tangible_reformulation', 'proof'):
            if not isinstance(rhetoric.get(field), str):
                raise PromptParseError(
                    f'Missing or invalid "rhetoric.{field}" (expected string).'
                )

        gaps = parsed.get('gaps')
        if not isinstance(gaps, list):
            raise PromptParseError(
                'Missing or invalid "gaps" (expected list).'
            )
        for gap in gaps:
            if not isinstance(gap, dict):
                raise PromptParseError(
                    'Each gap must be a JSON object.'
                )
            if gap.get('strategy') not in ('DIRECT', 'ELICITATION'):
                raise PromptParseError(
                    f'Invalid gap strategy: "{gap.get("strategy")}". '
                    f'Expected "DIRECT" or "ELICITATION".'
                )

        next_step = parsed.get('next_step')
        if not isinstance(next_step, dict):
            raise PromptParseError(
                'Missing or invalid "next_step" (expected object).'
            )
        for field in ('what', 'with_whom', 'when'):
            if not isinstance(next_step.get(field), str):
                raise PromptParseError(
                    f'Missing or invalid "next_step.{field}" (expected string).'
                )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _finalize_failure(self, run, *, status, error_label, exc):
        error_message = f'{error_label}: {exc}'
        self._log_sub_call(
            run,
            stage=_STAGE_NAME,
            sub_call_meta=None,
            parsed=None,
            error=error_message,
            dropped_count=0,
        )
        final_run = self._finalize_run(
            run,
            status=status,
            created_signals_count=0,
            error_message=error_message,
        )
        return {'run': final_run, 'snapshot': None}
