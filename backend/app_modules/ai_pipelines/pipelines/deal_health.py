# app_modules/ai_pipelines/pipelines/deal_health.py
"""
DealHealthPipeline -- single-stage LLM pipeline that produces a
structured diagnostic snapshot of a DecisionCycle from validated
signals.

Single stage: one LLM call, one structural validation + snapshot
persistence, one sub-call audit entry.

Error handling mirrors NextStepsPipeline (single stage = no PARTIAL):

    PromptParseError after retry  -> PARSE_ERROR.
    LLMTimeoutError               -> TIMEOUT.
    LLMRateLimitError             -> LLM_ERROR.
    LLMAuthError                  -> LLM_ERROR.
    LLMProviderError (generic)    -> LLM_ERROR.

Return contract:
    .run(*, decision_cycle, user, client_id) -> {
        'run':      AIPipelineRun (finalised) | None,
        'snapshot': DealHealthSnapshot | None,
        'blocked':  None | DEAL_HEALTH_CYCLE_CLOSED_CODE
                         | DEAL_HEALTH_NO_NEW_SOURCES_CODE,
        'last_snapshot': DealHealthSnapshot | None,   # when blocked
    }

Run guards (sprint « Deal health v2 », step 6, amendment A10) — business
rules, checked BEFORE any run row or LLM call (blocked: run and snapshot are
None):
    the cycle is closed (DEAL_HEALTH_CLOSED_OUTCOMES: won, lost, not
    qualified — ON_HOLD is not, 6c)              -> CYCLE_CLOSED;
    a previous snapshot exists, the sources cursor (step 3b) finds no
    changed source and the static context's fingerprint is the same (6c)
                                                 -> NO_NEW_SOURCES.

Sprint « Deal health v2 », step 5: the « manager / coach » diagnostic v2
(prompts system_v2 / context_v2 / diagnostic_v2), sent with its strict
Structured Outputs schema to the deal health's OWN PROVIDER_CONFIG entry
(config.DEAL_HEALTH_LLM_PROVIDER -> DEAL_HEALTH_PROVIDER_KEYS, the
NextStepsPipeline pattern). The writer validates and persists the v2
snapshot, then the stakeholder profiles go through
stakeholder_service.apply_ai_profile only. The deal's step is never changed.
"""

import json

from .. import config as ai_config
from ..constants import (
    AIPipelineStatus,
    AIPipelineType,
    DEAL_HEALTH_CYCLE_CLOSED_CODE,
    DEAL_HEALTH_NO_NEW_SOURCES_CODE,
    DEAL_HEALTH_PROVIDER_KEYS,
    PIPELINE_TEMPERATURES,
)
from ..prompts.base import PromptParseError
from ..prompts.deal_health.context_v2 import (
    CONTEXT_VERSION,
    build_context_layer,
)
from ..prompts.deal_health.diagnostic_v2 import (
    DEAL_HEALTH_RESPONSE_SCHEMA,
    DIAGNOSTIC_PROMPT_VERSION,
    build_diagnostic_request,
)
from ..prompts.deal_health.system_v2 import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from ..providers import (
    get_provider,
    provider_credentials_present,
    provider_required_env_key,
    provider_supports_response_schema,
)
from ..providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .base import BasePipeline

from app_modules.decision_cycles.constants import (
    DEAL_HEALTH_CLOSED_OUTCOMES,
    DEAL_HEALTH_SCHEMA_V2,
)

from django.db import transaction


_STAGE_NAME = 'diagnostic'


def check_deal_health_provider(choice, provider_config):
    """
    Load-time guard of the deal health's provider (amendment A11, the
    pipelines/next_steps.check_next_steps_provider pattern): `choice` must be
    a key of DEAL_HEALTH_PROVIDER_KEYS mapped to a PROVIDER_CONFIG entry whose
    provider supports a strict response schema AND whose API key is set
    (its REQUIRED_ENV_KEY — sub-step 5b: 'claude' needs ANTHROPIC_API_KEY).
    Raises ImportError so a misconfiguration fails at Django startup with a
    clear message, not at the first run.
    """
    key = DEAL_HEALTH_PROVIDER_KEYS.get(choice)
    if key is None:
        raise ImportError(
            f'AI Pipelines configuration error: DEAL_HEALTH_LLM_PROVIDER '
            f'{choice!r} is not one of {sorted(DEAL_HEALTH_PROVIDER_KEYS)}.'
        )
    if key not in provider_config:
        raise ImportError(
            f'AI Pipelines configuration error: the deal health provider '
            f'{choice!r} maps to {key!r}, which is not in PROVIDER_CONFIG. '
            f'Available keys: {sorted(provider_config)}.'
        )
    if not provider_supports_response_schema(key):
        raise ImportError(
            f'AI Pipelines configuration error: the deal health sends a strict '
            f'response schema, but DEAL_HEALTH_LLM_PROVIDER={choice!r} uses '
            f'{key!r}, whose provider does not declare SUPPORTS_RESPONSE_SCHEMA. '
            f'Keep "openai" until that provider supports Structured Outputs.'
        )
    if not provider_credentials_present(key):
        env_key = provider_required_env_key(key)
        raise ImportError(
            f'AI Pipelines configuration error: DEAL_HEALTH_LLM_PROVIDER={choice!r} '
            f'needs the {env_key} environment variable, which is not set. Set '
            f'{env_key} in backend/salescommands/.env (backend/.env.example), or set '
            f'DEAL_HEALTH_LLM_PROVIDER back to "openai" in ai_pipelines/config.py.'
        )
    return key


check_deal_health_provider(ai_config.DEAL_HEALTH_LLM_PROVIDER, ai_config.PROVIDER_CONFIG)


class DealHealthPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.DEAL_HEALTH

    PROMPT_VERSIONS = {
        'system':     SYSTEM_PROMPT_VERSION,
        'context':    CONTEXT_VERSION,
        'diagnostic': DIAGNOSTIC_PROMPT_VERSION,
    }

    TEMPERATURE = PIPELINE_TEMPERATURES[AIPipelineType.DEAL_HEALTH]

    def __init__(self, provider=None):
        super().__init__(provider=provider)
        # The deal health's own entry (step 5) — call AND run row (the
        # NextStepsPipeline.__init__ pattern).
        self._provider_key = DEAL_HEALTH_PROVIDER_KEYS[ai_config.DEAL_HEALTH_LLM_PROVIDER]
        self._provider_config = ai_config.PROVIDER_CONFIG[self._provider_key]
        if not self._provider_injected:
            self.provider = get_provider(self._provider_key)

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, decision_cycle, user, client_id):
        """
        Execute the single-stage deal-health diagnostic pipeline.

        Args:
            decision_cycle: DecisionCycle instance.
            user:           end_users.User -- the rep who triggered the run.
            client_id:      UUID -- tenant scope.

        Returns:
            dict: {
                'run':      AIPipelineRun (finalised),
                'snapshot': DealHealthSnapshot | None,
            }
        """
        from ..services.deal_health_evidence_builder import DealHealthEvidenceBuilder
        from ..services.deal_health_writer import DealHealthWriter

        # A10 — a closed cycle (won, lost, not qualified) is not analysed
        # again; its last diagnostic stays readable. 6c (PO): ON_HOLD is a
        # pause, the usual « nothing new » guard applies.
        if getattr(decision_cycle, 'outcome', None) in DEAL_HEALTH_CLOSED_OUTCOMES:
            return self._blocked(
                DEAL_HEALTH_CYCLE_CLOSED_CODE,
                DealHealthEvidenceBuilder.latest_snapshot(decision_cycle),
            )

        builder = DealHealthEvidenceBuilder()
        pack = builder.build(decision_cycle)

        # A10 — nothing changed since the last snapshot (sources and static
        # context): no LLM call.
        previous = getattr(builder, 'previous_snapshot', None)
        if previous is not None and not builder.has_new_sources(decision_cycle, previous):
            return self._blocked(DEAL_HEALTH_NO_NEW_SOURCES_CODE, previous)

        # The input bounds applied (step 3b) — traced on success AND failure.
        self._pack_truncation = pack.get('truncation') if isinstance(pack, dict) else None
        input_text = json.dumps(pack, default=str)

        try:
            with transaction.atomic():
                run = self._create_run(
                    user=user,
                    client_id=client_id,
                    source_activity=None,
                    source_decision_cycle=decision_cycle,
                    input_text=input_text,
                )

                try:
                    context_layer = build_context_layer(pack)
                    request_layer = build_diagnostic_request(pack)

                    parsed, sub_call_meta = self._call_llm(
                        system_prompt=SYSTEM_PROMPT,
                        context=context_layer,
                        request=request_layer,
                        response_schema=DEAL_HEALTH_RESPONSE_SCHEMA,
                    )

                    current_step = (pack.get('cycle') or {}).get('current_step') or {}
                    writer = DealHealthWriter()
                    snapshot = writer.write(
                        parsed=parsed,
                        decision_cycle=decision_cycle,
                        run=run,
                        user=user,
                        client_id=client_id,
                        declared_step=current_step.get('stage'),
                        prompt_versions=self.PROMPT_VERSIONS,
                        sources_cursor=pack.get('sources_cursor'),
                        schema_version=DEAL_HEALTH_SCHEMA_V2,
                    )
                    # The stakeholder profiles — validated with the answer,
                    # written by apply_ai_profile only; a label is resolved
                    # server side against the prompt's own roster.
                    profile_counts = writer.apply_profiles(
                        parsed=parsed,
                        decision_cycle=decision_cycle,
                        run=run,
                        roster=getattr(builder, 'roster', None),
                    )

                    self._log_sub_call(
                        run,
                        stage=_STAGE_NAME,
                        sub_call_meta=sub_call_meta,
                        parsed=parsed,
                        error=None,
                        dropped_count=0,
                        input_truncation=pack.get('truncation'),
                        persist_counts=profile_counts,
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
    # HELPERS
    # =========================================================================

    @staticmethod
    def _blocked(code, last_snapshot):
        """A run stopped by a business rule (A10): nothing written."""
        return {'run': None, 'snapshot': None, 'blocked': code,
                'last_snapshot': last_snapshot}

    def _finalize_failure(self, run, *, status, error_label, exc):
        """
        Log a failed sub-call entry, finalise the run, and return the
        canonical empty-snapshot envelope.
        """
        error_message = f'{error_label}: {exc}'
        self._log_sub_call(
            run,
            stage=_STAGE_NAME,
            sub_call_meta=None,
            parsed=None,
            error=error_message,
            dropped_count=0,
            input_truncation=self._pack_truncation,
        )
        final_run = self._finalize_run(
            run,
            status=status,
            created_signals_count=0,
            error_message=error_message,
        )
        return {'run': final_run, 'snapshot': None}
