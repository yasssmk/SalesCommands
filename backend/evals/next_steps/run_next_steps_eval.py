#!/usr/bin/env python
"""
Next steps — measure, on the REAL LLM, the next steps the production
pipeline extracts from two reference transcripts (Sprint Next steps 3.0:
baseline of prompt v1 / context v5 before any prompt change).

Standalone evaluation script. NOT part of the product: it lives outside
app_modules/, nothing imports it, and it leaves nothing in the database —
everything it creates (tenant, user, account, contact, decision cycle and
its steps, conversation, run rows, next steps) is rolled back: one
savepoint per call, the whole run inside one transaction never committed.

Model: the pipeline's production entry (config.NEXT_STEPS_PROVIDER --
gpt-5.6-terra + Structured Outputs since 3.1); --model forces another
DECLARED entry. The pipeline sends its response schema whatever the model
(--model gpt-4o-mini = gpt-4o-mini WITH the schema, not the 3.0 baseline,
which had none: its run folder stays the reference); a provider without
schema support is refused before any call.

Real path, end to end:

  * the conversation is created by the standard service
    (ActivityCreationService.create_with_entities): account "Logistix", an
    inline contact, an inline decision cycle WITH ITS AUTO-CREATED STEPS
    (PIPELINE_STEPS_CONFIG), the conversation on the case's step;
  * each call runs the REAL NextStepsPipeline(provider=...).run(): context
    v5 (the Conversation date read on the transcript header, D7), request
    v1, system prompt, model / temperature / max_tokens / timeout / parse
    retry of production, safety filter and NextStepExtractor persistence;
  * the next steps scored are the rows the pipeline STORED (what the rep
    sees); the raw answer is ALWAYS recorded too.

Only one lookup is replaced: the tenant display name sent as "Seller"
(--tenant-name, default SalesCommands) — ClientAccount.name is unique, the
eval tenant gets a throw-away name.

Variants (N calls each, default 10; read rates on --n 20):
  atelier    transcript_atelier.txt  (evals/td279; 2026/10/20) — A, B,
             C_prospect, C_vendeur (+ C_suivi, informative)
  logistix   transcript_logistix.txt (evals/td279; 2026/10/14) — D

Ground truth and tolerant match rules: expected.json + README.md.

Output (one folder per run, see --out; a non-empty folder is refused):
  prompt_<variant>.txt       the prompt rendered by the production builders
                             (checked by the leak guard before any call)
  <variant>/call_<NN>.json   system + user prompt sent, raw response(s),
                             parsed JSON, stored next steps, metrics
  summary.csv / summary.md   one row per call + the recap

Usage (from backend/, with OPENAI_API_KEY in the environment):
  python evals/next_steps/run_next_steps_eval.py --n 20                    # production (Terra)
  python evals/next_steps/run_next_steps_eval.py --n 20 --model gpt-4o-mini  # 4o-mini + schema
  python evals/next_steps/run_next_steps_eval.py --n 3 --only atelier
  python evals/next_steps/run_next_steps_eval.py --dry-run      # no API call
  python evals/next_steps/run_next_steps_eval.py --rescore evals/next_steps/out/<stamp>
      # recompute the summary from the recorded answers, no API call
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salescommands.settings')

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from app_modules.activities.constants import ActivityStatus, ActivityType  # noqa: E402
from app_modules.ai_pipelines import config as ai_config  # noqa: E402
from app_modules.ai_pipelines.constants import AIPipelineStatus  # noqa: E402
from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline  # noqa: E402
from app_modules.ai_pipelines.prompts.base import PromptBuilder, PromptParseError  # noqa: E402
from app_modules.ai_pipelines.prompts.next_steps.context import build_context_layer  # noqa: E402
from app_modules.ai_pipelines.prompts.next_steps.next_steps_v1 import (  # noqa: E402
    build_next_steps_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals import context as session_ctx  # noqa: E402
from app_modules.ai_pipelines.prompts.transcript_signals.system import SYSTEM_PROMPT  # noqa: E402
from app_modules.ai_pipelines.providers import (  # noqa: E402
    get_provider,
    provider_supports_response_schema,
)
from app_modules.ai_pipelines.providers.base import (  # noqa: E402
    LLMCallResult,
    LLMProviderError,
    LLMTimeoutError,
)

# Shared eval plumbing (evals/common/eval_kit.py) — one implementation, also
# used by evals/td279.
from evals.common.eval_kit import (  # noqa: E402
    RecordingProvider,
    add_common_arguments,
    count,
    declared_models,
    load_records,
    prepare_out_dir,
    row,
    run_calls,
    timing_line,
    write_summary,
)
from evals.next_steps import scoring  # noqa: E402


EXPECTED = scoring.load_expected(HERE / 'expected.json')
CASES = EXPECTED['transcripts']
VARIANTS = tuple(CASES)                     # one variant per transcript
# The pipeline's own entry wins for its model (gpt-5.6-terra is also the
# People entry's model).
MODELS = {
    **declared_models(),
    ai_config.PROVIDER_CONFIG[ai_config.NEXT_STEPS_PROVIDER]['model']: ai_config.NEXT_STEPS_PROVIDER,
}


def _transcript(key):
    return (HERE / CASES[key]['file']).resolve().read_text(encoding='utf-8')


def _items(key):
    return [item for item in EXPECTED['items'] if item['transcript'] == key]


# =============================================================================
# TEST CASE — created through the standard services, rolled back
# =============================================================================

_real_tenant_name = session_ctx._resolve_tenant_name


def _use_tenant_name(client_id, tenant_name):
    """The "Seller" name for the eval tenant only (ClientAccount.name is
    unique: the eval tenant has a throw-away name)."""
    session_ctx._resolve_tenant_name = lambda cid: (
        tenant_name if str(cid) == str(client_id) else _real_tenant_name(cid)
    )


def _create_case(key, tenant_name):
    """Tenant, rep, account Logistix, then the case's activities by
    create_with_entities: its prior activities (COMPLETED, expected.json
    prior_activities), then the conversation with its contact. The FIRST
    activity creates the decision cycle inline (auto-created steps), the
    next ones are put on its steps."""
    from app_modules.accounts.models import CompanyAccount
    from app_modules.activities.services.activity_creation_service import (
        ActivityCreationService,
    )
    from end_users.models import ClientAccount, User, UserRole

    case, tag = CASES[key], uuid.uuid4().hex[:12]
    tenant = ClientAccount.objects.create(name=f'eval-next-steps-{tag}', is_b2b=True, max_users=20)
    role = UserRole.objects.create(
        client_account=tenant, name='Individual', is_admin=False, is_manager=False,
        is_individual=True, read=True, write=True, modify=True, can_delete=True,
    )
    user = User.objects.create(email=f'eval-{tag}@eval.invalid', client_account=tenant,
                               role=role, is_active=True)
    account = CompanyAccount(company_name='Logistix', has_buying_decision=True)
    account.save(user=user, client_id=tenant.id)
    service = ActivityCreationService(user, tenant.id)
    cycle = None

    def create(title, activity_type, date, stage, **inline):
        nonlocal cycle
        data = {'account_id': str(account.id), 'title': title, 'activity_type': activity_type,
                'status': ActivityStatus.COMPLETED, 'scheduled_date': date}
        if cycle is None:
            created = service.create_with_entities(
                activity_data=data, inline_cycle={'name': f'Logistix — {case["activity_title"]}'},
                inline_step_stage=stage, **inline)
            cycle = created['cycle']
        else:
            data.update(decision_cycle_id=str(cycle.id),
                        decision_step_id=str(cycle.steps.get(stage=stage).id))
            created = service.create_with_entities(activity_data=data, **inline)
        return created['activity']

    for prior in case.get('prior_activities', []):
        create(prior['title'], prior['activity_type'], prior['date'], prior['dc_stage'])
    activity = create(case['activity_title'], ActivityType.MEETING, case['conversation_date'],
                      case['dc_stage'], inline_contact=dict(case['contact']))
    _use_tenant_name(tenant.id, tenant_name)
    steps = list(cycle.steps.order_by('order').values_list('stage', flat=True))
    return user, activity, {
        'decision_cycle_steps': steps,
        'conversation_step': activity.decision_step.stage,
        'prior_activities': [p['title'] for p in case.get('prior_activities', [])],
    }


# =============================================================================
# PROVIDERS
# =============================================================================

def _signal(title, type_, date, quote, confidence=0.9):
    return {'suggested_title': title, 'suggested_activity_type': type_,
            'suggested_due_date': date, 'suggested_objective': 'dry run',
            'source_quote': quote, 'confidence': confidence, 'is_inferred': False}


# --dry-run answers: they exercise every metric (match, wrong date, duplicate,
# invention, speaker label at the head of a quote, safety filter). They live
# HERE, never in the prompt (the leak guard checks the prompt).
_DRY_RUN = {
    'atelier': [
        _signal('Envoyer le DPA et le rapport SOC 2', 'EMAIL', '2026-10-23',
                "Thomas Lefèvre: Envoyez-les avant vendredi, s'il vous plaît."),
        _signal('Organiser le rendez-vous sécurité avec Laurent Petit', 'MEETING', '2026-11-03',
                'Pour Laurent, privilégiez un mardi, il est en comité le reste de la semaine.'),
        _signal('Envoyer la première version du business case', 'TASK', '2026-10-30',
                'Il me faut la version finale avant le quinze novembre'),
        _signal('Transmettre le DPA à Thomas', 'EMAIL', None,
                'Je peux vous envoyer le DPA et le rapport SOC 2.'),
        _signal('Relancer Isabelle sur le budget', 'CALL', '2026-11-10',
                'Isabelle a confirmé le budget de soixante-dix mille euros.'),
        _signal('Faible confiance', 'TASK', None, 'Merci, à bientôt.', confidence=0.3),
    ],
    'logistix': [
        _signal('Rendez-vous avec Isabelle Roux (DAF) pour le business case', 'MEETING',
                '2026-12-05',
                'on devra forcément faire un rendez-vous avec Isabelle Roux, notre DAF'),
        _signal('Envoyer la documentation technique à Thomas', 'EMAIL', None,
                "Si ça ne s'intègre pas proprement, ça ne passera pas."),
    ],
}


class DryRunProvider:
    """--dry-run: no API call, a fixed answer per transcript."""

    def call(self, **kwargs):
        key = 'atelier' if 'Atelier business case' in kwargs['user'] else 'logistix'
        return LLMCallResult(
            content=json.dumps({'signals': _DRY_RUN[key]}, ensure_ascii=False),
            input_tokens=0, output_tokens=0, model_used='dry-run', duration_ms=0,
        )


# =============================================================================
# RUN
# =============================================================================

def _rendered_prompt(activity, transcript):
    """The prompt of the call, rendered by the production builders (the
    same calls as NextStepsPipeline.run)."""
    return PromptBuilder.assemble(
        system=SYSTEM_PROMPT,
        context=build_context_layer(activity, transcript),
        request=build_next_steps_request(transcript),
    )


def _leaks(system, user):
    guard = EXPECTED['leak_guard']
    return scoring.prompt_leaks(system, user, [_transcript(k) for k in VARIANTS],
                                guard['names'], guard['ngram_words'])


def _stored(signal):
    """A stored NextStepSignal, as scored (the fields of the rep's card)."""
    return {
        'id': str(signal.id),
        'suggested_title': signal.suggested_title,
        'suggested_activity_type': signal.suggested_activity_type,
        'suggested_due_date': (signal.suggested_due_date.isoformat()
                               if signal.suggested_due_date else None),
        'suggested_objective': signal.suggested_objective,
        'source_quote': signal.source_quote,
        'confidence': signal.confidence,
        'is_inferred': signal.is_inferred,
        'decision_cycle_set': signal.decision_cycle_id is not None,
        'suggested_decision_step': (signal.suggested_decision_step.stage
                                    if signal.suggested_decision_step_id else None),
        'suggested_people_names': signal.suggested_people_names,
        'suggested_internal_names': signal.suggested_internal_names,
        'suggested_topics': signal.suggested_topics,
        'suggested_success_criterion': signal.suggested_success_criterion,
        'carried_by_prospect': signal.carried_by_prospect,
    }


def _failure(run):
    """The failed run as the exception the pipeline swallowed (for the
    error type of the recap)."""
    message = f'run {run.status}: {run.error_message}'
    if run.status == AIPipelineStatus.TIMEOUT:
        return LLMTimeoutError(message)
    if run.status == AIPipelineStatus.PARSE_ERROR:
        return PromptParseError(message)
    return LLMProviderError(message)


def run_variant(key, n, out_dir, dry_run, tenant_name, forced_key=None):
    provider_key = forced_key or ai_config.NEXT_STEPS_PROVIDER
    provider = DryRunProvider() if dry_run else get_provider(provider_key)
    model = ai_config.PROVIDER_CONFIG[provider_key]['model']
    transcript = _transcript(key)
    user, activity, case_info = _create_case(key, tenant_name)

    # Leak guard BEFORE any call (point 7).
    system, user_prompt = _rendered_prompt(activity, transcript)
    (out_dir / f'prompt_{key}.txt').write_text(
        f'=== SYSTEM ===\n{system}\n\n=== USER ===\n{user_prompt}\n', encoding='utf-8')
    leaks = _leaks(system, user_prompt)
    if leaks:
        sys.exit(f'{key}: the prompt carries passages of the eval transcripts '
                 f'outside the transcript itself: {leaks}')

    base_record = {
        'transcript': key, 'provider_key': provider_key, 'model': model,
        'prompt_versions': dict(NextStepsPipeline.PROMPT_VERSIONS), **case_info,
    }

    def make_call(recorder):
        with transaction.atomic():          # one savepoint per call, rolled back
            pipeline = NextStepsPipeline(provider=recorder)
            if forced_key:
                pipeline._provider_config = ai_config.PROVIDER_CONFIG[forced_key]
            result = pipeline.run(transcript=transcript, activity=activity,
                                  user=user, client_id=activity.client_id)
            run = result['run']
            stored = [_stored(s) for s in result['signals']]
            sub_call = (run.sub_calls or [{}])[-1]
            transaction.set_rollback(True)
        if run.status != AIPipelineStatus.SUCCESS:
            raise _failure(run)
        meta = {k: sub_call.get(k) for k in (
            'attempt', 'duration_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens',
            'model_used', 'emitted_count', 'dropped_by_safety_filter')}
        # The raw answer the pipeline parsed (last attempt, same parser).
        parsed = PromptBuilder.parse_response(recorder.calls[-1]['raw_response'])
        return parsed, meta, {'persisted': stored, 'run_status': run.status}

    return run_calls(
        name=key, n=n, variant_dir=out_dir / key, base_record=base_record,
        make_recorder=lambda: RecordingProvider(provider), make_call=make_call,
        score=_score, failure_extra={'persisted': []},
    )


def _score(record):
    """The metrics of ONE recorded call, from the record only (shared by a
    run and --rescore)."""
    attempts = record.get('attempts') or []
    leaks = _leaks(attempts[0]['system'], attempts[0]['user']) if attempts else None
    return scoring.score_call(
        persisted=record.get('persisted') or [],
        parsed=record.get('parsed'),
        items=_items(record['transcript']),
        transcript=_transcript(record['transcript']),
        prompt_version=(record.get('prompt_versions') or {}).get('next_steps'),
        leaks=leaks,
    )


def rescore(out_dir):
    """
    --rescore: recompute the metrics and the summary of a run folder from
    the answers ALREADY recorded (call_NN.json) — no API call, no database.
    Writes summary_rescored.csv / .md next to the originals (kept);
    expected.json and the transcripts: the current files.
    """
    rows, models_used, versions = [], {}, {}
    for record in load_records(out_dir, VARIANTS):
        rows.append(row(record, _score(record)))
        models_used[record['variant']] = record.get('model')
        versions = versions or record.get('prompt_versions') or {}
    if not rows:
        sys.exit(f'No call_NN.json under {out_dir} -- nothing to rescore.')
    _write_summary(out_dir, rows, models_used, versions, suffix='_rescored')


# =============================================================================
# RECAP
# =============================================================================

def _rate(values, none='-'):
    """'x/y' over the non-None values (`none` when there is none)."""
    known = [v for v in values if v is not None]
    return f'{sum(1 for v in known if v)}/{len(known)}' if known else none


def _span(values):
    return f'{min(values)}-{max(values)}' if values else '-'


def _fusions(vrows):
    """'total {X<-Y: calls}' of the fusions of a variant ('0' without)."""
    detail = count(d for r in vrows for d in r['fusion_detail'].split('; ') if d)
    return f'{sum(r["fusions"] for r in vrows)} {detail}' if detail else '0'


def _recap(rows, prompt_version):
    """The recap tables; an item counts in the recall when required for the
    run's next_steps prompt version (expected.json required_from)."""
    timings, expected, noise, new_fields = [], [], [], []
    for key in VARIANTS:
        vrows = [r for r in rows if r['variant'] == key]
        if not vrows:
            continue
        n = len(vrows)
        timings.append(timing_line(key, vrows))
        required = [i for i in _items(key) if scoring.is_required(i, prompt_version)]
        for item in _items(key):
            p = item['id']
            present = [r for r in vrows if r[f'{p}_present']]
            expected.append(
                f'| {key} | {p}{"" if item in required else " (info)"} | '
                f'{len(present)}/{n} | '
                f'{_rate(r[f"{p}_type_ok"] for r in present)} | '
                f'{_rate(r[f"{p}_date_in_window"] for r in present)} | '
                f'{sum(1 for r in present if r[f"{p}_date_missing"])}/{len(present)} | '
                f'{sum(1 for r in present if r[f"{p}_matches"] > 1)}/{len(present)} | '
                f'{_rate((r[f"{p}_carried_ok"] for r in present), none="N/A")} | '
                f'{count(r[f"{p}_type"] for r in present) or "-"} | '
                f'{count(r[f"{p}_date"] or "null" for r in present) or "-"} | '
                f'{count(r[f"{p}_absorbed_by"] for r in vrows if r[f"{p}_absorbed_by"]) or "-"} |'
            )
        found = [sum(1 for i in required if r[f'{i["id"]}_present']) for r in vrows]
        noise.append(
            f'| {key} | {n} | {sum(found)}/{n * len(required)} | '
            f'{_span([r["emitted"] for r in vrows])} | {_span([r["persisted"] for r in vrows])} | '
            f'{sum(r["inventions"] for r in vrows)} ({sum(1 for r in vrows if r["inventions"])}/{n}) | '
            f'{sum(r["inventions_raw"] for r in vrows)} | '
            f'{sum(r["unmatched"] for r in vrows)} | {sum(r["duplicates"] for r in vrows)} | '
            f'{sum(r["duplicate_titles"] for r in vrows)} | '
            f'{_span([r["prompt_leaks"] for r in vrows if r["prompt_leaks"] is not None])} | '
            f'{sum(1 for r in vrows if r["error"])} | '
            f'{_fusions(vrows)} |'
        )
        for field in (*scoring.NEW_FIELDS, 'people_names_not_in_transcript'):
            column = f'new_{field}' if field in scoring.NEW_FIELDS else field
            values = [r[column] for r in vrows if r[column] is not None]
            shown = (f'{sum(values)} (sur {len(values)} appels)' if values
                     else 'N/A (ligne de base : le prompt v1 ne l\'émet pas)')
            new_fields.append(f'| {key} | {field} | {shown} |')
    return [
        '## Durées et erreurs (duration_ms = meta de l\'appel réussi ; wall_ms = '
        'horloge, appels en erreur compris)',
        '',
        '| variante | appels | duration_ms moyenne | duration_ms max | wall_ms max | '
        'erreurs par type |',
        '|---|---|---|---|---|---|',
        *timings, '',
        '## Attendus (next steps STOCKÉS ; un appel en erreur compte « absent »)',
        '',
        '| variante | attendu | présent | type correct | date dans la fenêtre | '
        'date absente | doublons | carried_by_prospect | types vus | dates vues | '
        'absorbé par (appels où il manque) |',
        '|---|---|---|---|---|---|---|---|---|---|---|',
        *expected, '',
        '## Bruit et inventions (totaux sur N appels)',
        '',
        '| variante | appels | attendus requis trouvés | émis (min-max) | stockés (min-max) | '
        'inventions stockées (appels) | inventions brutes | non appariés | doublons | '
        'titres identiques | fuites prompt | erreurs | fusions (détail) |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|',
        *noise, '',
        '## Nouveaux champs (comptés sur la réponse brute)',
        '',
        '| variante | champ | valeur |',
        '|---|---|---|',
        *new_fields, '',
    ]


def _write_summary(out_dir, rows, models_used, versions, suffix=''):
    write_summary(out_dir, rows, title='Next steps — récap', models_used=models_used,
                  versions=versions, recap=_recap(rows, versions.get('next_steps')),
                  suffix=suffix)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    add_common_arguments(
        parser, VARIANTS, MODELS,
        model_help='force a model DECLARED in ai_pipelines/config.py PROVIDER_CONFIG '
                   '(sent WITH the pipeline\'s response schema); default: the pipeline\'s production '
                   'entry (config.NEXT_STEPS_PROVIDER)',
    )
    args = parser.parse_args()
    forced_key = MODELS[args.model] if args.model else None
    if forced_key and not provider_supports_response_schema(forced_key):
        sys.exit(f'--model {args.model}: its provider does not support the response schema '
                 f'the next_steps pipeline sends.')

    if args.rescore:
        rescore(Path(args.rescore))
        return

    out_dir = prepare_out_dir(args.out, HERE)
    names = args.only or list(VARIANTS)
    model = ai_config.PROVIDER_CONFIG[forced_key or ai_config.NEXT_STEPS_PROVIDER]['model']
    rows = []
    # Everything created by the run is rolled back at the end.
    with transaction.atomic():
        for key in names:
            rows.extend(run_variant(key, args.n, out_dir, args.dry_run, args.tenant_name, forced_key))
        transaction.set_rollback(True)
    _write_summary(out_dir, rows, {name: model for name in names},
                   NextStepsPipeline.PROMPT_VERSIONS)


if __name__ == '__main__':
    main()
