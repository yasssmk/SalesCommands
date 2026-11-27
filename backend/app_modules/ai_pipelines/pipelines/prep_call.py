# app_modules/ai_pipelines/pipelines/prep_call.py
"""
PrepCallPipeline -- single-stage LLM pipeline that produces the Game Plan
(v2 since sprint 2 Game Plan, G10) of an upcoming Activity from its input
pack v2 (G7 / G8).

Single stage: one LLM call with the strict schema PREP_CALL_OUTLINE_SCHEMA,
one server-side validation (services/prep_call/plan_validator.py — refs
resolved against the activity's roster, no rhetoric label, no last name),
the snapshot persisted in schema_version 2 with its deal-health trace, one
sub-call audit entry.

Error handling mirrors DealHealthPipeline (single stage = no PARTIAL):

    PromptParseError after retry  -> PARSE_ERROR.
    LLMTimeoutError               -> TIMEOUT.
    LLMRateLimitError             -> LLM_ERROR.
    LLMAuthError                  -> LLM_ERROR.
    LLMProviderError (generic)    -> LLM_ERROR.

Return contract:
    .run(*, activity, target_contact, input_pack, user, client_id,
         output_kind, people) -> {
        'run':      AIPipelineRun (finalised),
        'snapshot': PrepCallSnapshot | None,
    }
"""

import hashlib
import json
import logging

from django.db import transaction

from app_modules.activities.constants import ActivityType

from .. import config as ai_config
from ..constants import (
    AIPipelineStatus,
    AIPipelineType,
    PIPELINE_TEMPERATURES,
    PREP_CALL_NOTHING_NEW_CODE,
    PREP_CALL_PROVIDER_KEYS,
    PREP_CALL_SCHEMA_V2,
    PrepCallOutputKind,
)
from ..prompts.base import PromptParseError
from ..prompts.prep_call import (
    MESSAGE_PROMPT_VERSION,
    MESSAGE_SYSTEM_PROMPT,
    PREP_CALL_MESSAGE_SCHEMA,
    build_message_request,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    build_context_layer,
    CONTEXT_VERSION,
    build_outline_request,
    OUTLINE_PROMPT_VERSION,
    PREP_CALL_OUTLINE_SCHEMA,
)
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
from ..services.llm_people import roster_last_names
from ..services.prep_call.plan_validator import validate_messages, validate_plan
from .base import BasePipeline


logger = logging.getLogger(__name__)

_STAGE_NAME = 'brief'


def check_prep_call_provider(choice, provider_config):
    """
    Load-time guard of the prep call's provider (sprint 2 Game Plan, G2 — the
    exact pattern of pipelines/deal_health.check_deal_health_provider):
    `choice` must be a key of PREP_CALL_PROVIDER_KEYS mapped to a
    PROVIDER_CONFIG entry whose provider supports a strict response schema
    (the Game Plan's two schemas, G10 / G11) AND whose API key is set (its
    REQUIRED_ENV_KEY: 'claude' needs ANTHROPIC_API_KEY). Raises ImportError so
    a misconfiguration fails at Django startup with a clear message, not at
    the first run.
    """
    key = PREP_CALL_PROVIDER_KEYS.get(choice)
    if key is None:
        raise ImportError(
            f'AI Pipelines configuration error: PREP_CALL_LLM_PROVIDER '
            f'{choice!r} is not one of {sorted(PREP_CALL_PROVIDER_KEYS)}.'
        )
    if key not in provider_config:
        raise ImportError(
            f'AI Pipelines configuration error: the prep call provider '
            f'{choice!r} maps to {key!r}, which is not in PROVIDER_CONFIG. '
            f'Available keys: {sorted(provider_config)}.'
        )
    if not provider_supports_response_schema(key):
        raise ImportError(
            f'AI Pipelines configuration error: the Game Plan sends a strict '
            f'response schema, but PREP_CALL_LLM_PROVIDER={choice!r} uses '
            f'{key!r}, whose provider does not declare SUPPORTS_RESPONSE_SCHEMA. '
            f'Keep "openai" until that provider supports Structured Outputs.'
        )
    if not provider_credentials_present(key):
        env_key = provider_required_env_key(key)
        raise ImportError(
            f'AI Pipelines configuration error: PREP_CALL_LLM_PROVIDER={choice!r} '
            f'needs the {env_key} environment variable, which is not set. Set '
            f'{env_key} in backend/salescommands/.env (backend/.env.example), or set '
            f'PREP_CALL_LLM_PROVIDER back to "openai" in ai_pipelines/config.py.'
        )
    return key


check_prep_call_provider(ai_config.PREP_CALL_LLM_PROVIDER, ai_config.PROVIDER_CONFIG)


def _validate_plan_output(parsed, *, activity, input_pack, people, last_names):
    return validate_plan(
        parsed, people=people, last_names=last_names,
        has_campaign=bool(input_pack.get('campaign')),
    )


def _validate_message_output(parsed, *, activity, input_pack, people, last_names):
    return validate_messages(
        parsed, recipients=input_pack.get('recipients') or [], last_names=last_names,
        is_email=activity.activity_type == ActivityType.EMAIL,
    )


# G12 — THE single choice of what the pipeline produces, by output_kind
# (game_plan_output_kind, G3): its system prompt, its request layer, its
# strict response schema, its prompt versions and its server-side validation.
_OUTPUTS = {
    PrepCallOutputKind.PLAN: {
        'system': SYSTEM_PROMPT,
        'request': build_outline_request,
        'schema': PREP_CALL_OUTLINE_SCHEMA,
        'versions': {
            'system':  SYSTEM_PROMPT_VERSION,
            'context': CONTEXT_VERSION,
            'outline': OUTLINE_PROMPT_VERSION,
        },
        'validate': _validate_plan_output,
    },
    # G11 — the AI message: one per recipient, in ONE call.
    PrepCallOutputKind.MESSAGE: {
        'system': MESSAGE_SYSTEM_PROMPT,
        'request': build_message_request,
        'schema': PREP_CALL_MESSAGE_SCHEMA,
        'versions': {
            'system':  SYSTEM_PROMPT_VERSION,
            'context': CONTEXT_VERSION,
            'message': MESSAGE_PROMPT_VERSION,
        },
        'validate': _validate_message_output,
    },
}


class PrepCallPipeline(BasePipeline):
    """
    See module docstring for the full pipeline contract and lifecycle.
    """

    PIPELINE_TYPE = AIPipelineType.PREP_CALL

    # The plan's layers (BasePipeline requires them); a run takes the ones of
    # its output kind (_OUTPUTS).
    PROMPT_VERSIONS = _OUTPUTS[PrepCallOutputKind.PLAN]['versions']

    TEMPERATURE = PIPELINE_TEMPERATURES[AIPipelineType.PREP_CALL]

    def __init__(self, provider=None):
        super().__init__(provider=provider)
        # The prep call's own entry (G2) — call AND run row (the
        # DealHealthPipeline.__init__ pattern; the run's provider since G1).
        self._provider_key = PREP_CALL_PROVIDER_KEYS[ai_config.PREP_CALL_LLM_PROVIDER]
        self._provider_config = ai_config.PROVIDER_CONFIG[self._provider_key]
        if not self._provider_injected:
            self.provider = get_provider(self._provider_key)

    # =========================================================================
    # MAIN ENTRY
    # =========================================================================

    def run(self, *, activity, target_contact, input_pack,
            user, client_id, output_kind=PrepCallOutputKind.PLAN, people=None):
        """
        Execute the single-stage Game Plan pipeline.

        Args:
            activity:       Activity instance.
            target_contact: Contact instance or None.
            input_pack:     dict — assembled input pack.
            user:           end_users.User — the rep who triggered the run.
            client_id:      UUID — tenant scope.
            output_kind:    PrepCallOutputKind — PLAN (a conversation) or
                            MESSAGE (an email / a LinkedIn message, G3).
            people:         ActivityRoster the pack's labels come from
                            (PrepInputPackAssembler.people) — the refs the
                            Game Plan writes back are resolved against it;
                            None: every ref is dropped.

        Returns:
            dict: {
                'run':      AIPipelineRun (finalised),
                'snapshot': PrepCallSnapshot | None,
            }
            or, nothing new since the last Game Plan (G9):
            {'run': None, 'snapshot': None,
             'blocked': PREP_CALL_NOTHING_NEW_CODE, 'last_snapshot': ...}
        """
        input_text = json.dumps(input_pack, default=str)
        input_hash = self._compute_idempotence_hash(
            input_pack=input_pack,
            target_contact=target_contact,
        )

        # G9 (PO decision Q1) — regenerate only when the inputs changed since
        # the activity's LAST Game Plan (the hash v2, G7); otherwise an INFO,
        # no run, no LLM call (the deal health's _blocked(NO_NEW_SOURCES)
        # pattern). The first generation of an activity is never blocked.
        last = self._last_snapshot(activity)
        if last is not None and last.input_hash == input_hash:
            logger.info(
                'prep_call_nothing_new',
                extra={
                    'activity_id': str(activity.id),
                    'input_hash': input_hash,
                    'event': 'ai_pipeline_blocked',
                },
            )
            return self._blocked(PREP_CALL_NOTHING_NEW_CODE, last)

        # G12 — the ONE choice by output_kind: a conversation -> the plan, an
        # email / a LinkedIn message -> the messages (G11).
        output = _OUTPUTS[output_kind]
        self.PROMPT_VERSIONS = output['versions']

        # Bound before the try: a crash inside _create_run leaves no run to
        # finalise (S4 — was an UnboundLocalError hiding the original error).
        run = None
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
                    context_layer = build_context_layer(input_pack)
                    request_layer = output['request'](input_pack)

                    parsed, sub_call_meta = self._call_llm(
                        system_prompt=output['system'],
                        context=context_layer,
                        request=request_layer,
                        response_schema=output['schema'],
                    )

                    # G10 / G11 — validated server side (the deal health v2
                    # writer's pattern): a refusal is a PromptParseError,
                    # nothing is written.
                    last_names = (
                        roster_last_names(people.roster, client_id)
                        if people is not None else frozenset()
                    )
                    plan, ref_counts = output['validate'](
                        parsed, activity=activity, input_pack=input_pack,
                        people=people, last_names=last_names,
                    )

                    snapshot = self._persist_snapshot(
                        plan=plan,
                        activity=activity,
                        target_contact=target_contact,
                        input_pack=input_pack,
                        input_hash=input_hash,
                        run=run,
                        user=user,
                        client_id=client_id,
                        output_kind=output_kind,
                    )

                    self._log_sub_call(
                        run,
                        stage=_STAGE_NAME,
                        sub_call_meta=sub_call_meta,
                        parsed=parsed,
                        error=None,
                        dropped_count=(
                            len(ref_counts['unknown_refs']) + len(ref_counts['ambiguous_refs'])
                            + len(ref_counts.get('wrong_language_refs', []))
                        ),
                        persist_counts=ref_counts,
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
            self._finalize_hard_crash(run, exc)
            raise

    # =========================================================================
    # IDEMPOTENCE — DB dedup (layer 2)
    # =========================================================================

    @staticmethod
    def _compute_idempotence_hash(*, input_pack, target_contact):
        """
        SHA-256 of deterministic input components for DB-layer dedup.

        Components (sorted for stability):
        - validated signal count
        - last DealHealthSnapshot date (or "none")
        - target_contact id (or "none")
        - current step name (or "none")
        - the output schema version (G10: v2 — no brief mode any more)
        - the pack v2's inputs (G7, _pack_v2_fingerprint)
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
        parts.append(f"schema:{PREP_CALL_SCHEMA_V2}")

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

        # G7 — the input pack v2: what the Game Plan reads changes the hash.
        parts.append(f"v2:{PrepCallPipeline._pack_v2_fingerprint(input_pack)}")

        composite = '|'.join(sorted(parts))
        return hashlib.sha256(composite.encode('utf-8')).hexdigest()

    @staticmethod
    def _pack_v2_fingerprint(input_pack):
        """sha256 of the pack v2's inputs (G7): the activity's content, the
        participants' identities (sorted — the server-side ids, not the
        labels), the deal-health snapshot read, the seller profile's update
        date, the deal's products, the previous activities' notes, the
        campaign block (G8)."""
        participants = sorted(
            f"{p.get('contact_id') or ''}:{p.get('stakeholder_id') or ''}"
            for p in input_pack.get('participants') or []
        )
        deal_health = input_pack.get('deal_health') or {}
        seller = input_pack.get('seller_profile') or {}
        deal = input_pack.get('deal') or {}
        canonical = json.dumps({
            'activity': input_pack.get('activity'),
            'participants': participants,
            'deal_health_snapshot': deal_health.get('snapshot_id'),
            'seller_profile_updated_at': seller.get('updated_at'),
            'products': sorted(
                (json.dumps(p, sort_keys=True, default=str) for p in deal.get('products') or []),
            ),
            'previous_activities': input_pack.get('previous_activities') or [],
            'campaign': input_pack.get('campaign'),               # G8
            # G11: the recipients and their language (overrides included) —
            # only for an AI message, so a plan's hash is unchanged.
            **({'recipients': [
                f"{r['contact_id']}:{r['language']}:{r['source']}"
                for r in input_pack['recipients']
            ]} if input_pack.get('recipients') is not None else {}),
        }, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @staticmethod
    def _last_snapshot(activity):
        """The activity's last Game Plan, or None (its first generation)."""
        from ..models import PrepCallSnapshot

        return (
            PrepCallSnapshot.objects
            .filter(activity=activity)
            .order_by('-snapshot_date', '-id')
            .first()
        )

    @staticmethod
    def _blocked(code, last_snapshot):
        """Nothing run, nothing written — the deal health's shape
        (pipelines/deal_health.py _blocked)."""
        return {'run': None, 'snapshot': None, 'blocked': code,
                'last_snapshot': last_snapshot}

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    @staticmethod
    def _persist_snapshot(*, plan, activity, target_contact, input_pack,
                          input_hash, run, user, client_id,
                          output_kind=PrepCallOutputKind.PLAN):
        """The Game Plan v2 (schema_version 2, no brief_mode) with the trace
        of the deal-health snapshot it read (G2 columns): the pack's
        deal_health block — read inside the tenant by the canonical reader
        (DealHealthEvidenceBuilder.latest_snapshot, S3), never received."""
        from ..models import PrepCallSnapshot

        deal_health = input_pack.get('deal_health') or {}
        snapshot = PrepCallSnapshot(
            activity=activity,
            pipeline_run=run,
            target_contact=target_contact,
            brief=plan,
            input_hash=input_hash,
            output_kind=output_kind,
            schema_version=PREP_CALL_SCHEMA_V2,
            deal_health_snapshot_id=deal_health.get('snapshot_id'),
            deal_health_schema_version=deal_health.get('schema_version'),
        )
        snapshot.save(user=user, client_id=client_id)

        logger.info(
            'prep_call_snapshot_created',
            extra={
                'snapshot_id': str(snapshot.id),
                'activity_id': str(activity.id),
                'run_id': str(run.id),
                'schema_version': PREP_CALL_SCHEMA_V2,
                'event': 'ai_pipeline_persist',
            },
        )

        return snapshot

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
