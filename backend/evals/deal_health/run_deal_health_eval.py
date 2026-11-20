#!/usr/bin/env python
"""
Deal health — evaluate, on the REAL LLM, the format x model matrix of the
deal health diagnostic on 5 FICTITIOUS cases whose truth is written in
advance (sprint « Deal health v2 », step 7).

Standalone evaluation script. NOT part of the product: it lives outside
app_modules/, nothing imports it, and it leaves nothing in the database —
everything it creates (tenant, users, account, contacts, decision cycle and
its steps, activities, signals, stakeholders, notes, products, runs,
snapshots) is rolled back: one savepoint per call, the whole run inside one
transaction never committed (the evals/next_steps pattern).

Real path, end to end:

  * each case is SEEDED from tests/fixtures/deal_health_eval/<case>/seed.json
    by the standard paths (ActivityCreationService.create_with_entities for
    the activities, the inline decision cycle and its AUTO-CREATED steps);
    its declared step (derived from the activities) is checked before any
    call;
  * each call runs the REAL DealHealthPipeline(provider=...).run(): evidence
    builder, prompts v2.1, the strict response schema, model / effort /
    max_tokens / timeout of the PROVIDER_CONFIG entry of the matrix cell,
    the writer;
  * the matrix: format A ('sections') / B ('json') x the models of
    --models (default: openai_deal_health = gpt-5.6-terra, model X, and
    openai_deal_health_challenger, model Y). Any entry of PROVIDER_CONFIG
    whose provider supports the schema can be added — Claude with
    `--models ... claude_deal_health` once ANTHROPIC_API_KEY is set.

Truth and checks: tests/fixtures/deal_health_eval/<case>/expected.json +
evals/deal_health/scoring.py + README.md.

Output (one folder per run, see --out; a non-empty folder is refused):
  <variant>/call_<NN>.json   prompt sent, raw answer(s), parsed JSON, metrics
                             (variant = <case>__<format>__<entry>)
  summary.csv / summary.md   one row per call + the recap (eval_kit)
  report.md                  the side-by-side report: per case the outputs
                             of every cell, the checks, durations, tokens;
                             a recap table; the input caps and the timeout

Usage (from backend/, with OPENAI_API_KEY in backend/salescommands/.env):
  python evals/deal_health/run_deal_health_eval.py                 # 5 cases x 2 formats x 2 models = 20 calls
  python evals/deal_health/run_deal_health_eval.py --n 3           # 3 calls per cell
  python evals/deal_health/run_deal_health_eval.py --only technical_fit_fr
  python evals/deal_health/run_deal_health_eval.py --models openai_deal_health claude_deal_health
  python evals/deal_health/run_deal_health_eval.py --dry-run       # no API call
  python evals/deal_health/run_deal_health_eval.py --rescore evals/deal_health/out/<stamp>
"""

import argparse
import contextlib
import datetime
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
from django.utils import timezone  # noqa: E402

from app_modules.ai_pipelines import config as ai_config  # noqa: E402
from app_modules.ai_pipelines.constants import (  # noqa: E402
    AIPipelineStatus,
    DEAL_HEALTH_INPUT_FORMAT_JSON,
    DEAL_HEALTH_INPUT_FORMAT_SECTIONS,
    DEAL_HEALTH_MAX_CHARS_PER_SOURCE,
    DEAL_HEALTH_MAX_INPUT_CHARS,
    DEAL_HEALTH_TIMEOUT_S,
)
from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline  # noqa: E402
from app_modules.ai_pipelines.prompts.base import PromptBuilder, PromptParseError  # noqa: E402
from app_modules.ai_pipelines.prompts.deal_health import context_v2  # noqa: E402
from app_modules.ai_pipelines.providers import (  # noqa: E402
    get_provider,
    provider_credentials_present,
    provider_required_env_key,
    provider_supports_response_schema,
)
from app_modules.ai_pipelines.providers.base import (  # noqa: E402
    LLMCallResult,
    LLMProviderError,
    LLMTimeoutError,
)

# Shared eval plumbing (evals/common/eval_kit.py) — one implementation, also
# used by evals/td279 and evals/next_steps.
from evals.common.eval_kit import (  # noqa: E402
    RecordingProvider,
    add_common_arguments,
    declared_models,
    load_records,
    prepare_out_dir,
    row,
    run_calls,
    write_summary,
)
from evals.deal_health import scoring  # noqa: E402


FIXTURES = BACKEND / 'tests' / 'fixtures' / 'deal_health_eval'
CASES = tuple(sorted(d.name for d in FIXTURES.iterdir() if (d / 'seed.json').exists()))
# Format A / B (amendment A5): the two renderings of the same view.
FORMATS = {DEAL_HEALTH_INPUT_FORMAT_SECTIONS: 'A', DEAL_HEALTH_INPUT_FORMAT_JSON: 'B'}
# Model X (production entry) and model Y (the declared challenger).
DEFAULT_MODELS = ('openai_deal_health', 'openai_deal_health_challenger')
SEP = '__'


def _seed(case):
    return json.loads((FIXTURES / case / 'seed.json').read_text(encoding='utf-8'))


def _expected(case):
    return json.loads((FIXTURES / case / 'expected.json').read_text(encoding='utf-8'))


def variant_name(case, fmt, model_key):
    return f'{case}{SEP}{fmt}{SEP}{model_key}'


def split_variant(name):
    case, fmt, model_key = name.split(SEP)
    return case, fmt, model_key


# =============================================================================
# SEED — one fictitious case, by the standard paths
# =============================================================================

def create_case(case):
    """Tenant, a rep and a manager, the account, then the case's activities by
    create_with_entities (the FIRST one creates the decision cycle inline,
    with its auto-created steps), the people (contact + validated People
    signal + stakeholder), the validated signals, the manager notes and the
    products. Returns (user, cycle)."""
    from app_modules.accounts.models import CompanyAccount
    from app_modules.activities.constants import ActivityStatus
    from app_modules.activities.services.activity_creation_service import ActivityCreationService
    from app_modules.activities.services.next_step_materialization import current_decision_step
    from app_modules.contacts.models import Contact
    from app_modules.decision_cycles.models import DealProduct, ManagerNote
    from app_modules.decision_cycles.services.stakeholder_service import get_or_create_contact_stakeholder
    from app_modules.product_catalog.models import ProductCatalog
    from app_modules.signals import models as signals
    from app_modules.signals.constants import SignalSource, SignalStatus
    from end_users.models import ClientAccount, User, UserRole

    seed, tag = _seed(case), uuid.uuid4().hex[:12]
    tenant = ClientAccount.objects.create(name=f'eval-deal-health-{tag}', is_b2b=True, max_users=20)

    def _user(name, **flags):
        role = UserRole.objects.create(
            client_account=tenant, name=name, is_individual=not flags,
            is_admin=False, is_manager=bool(flags.get('is_manager')),
            read=True, write=True, modify=True, can_delete=True,
        )
        return User.objects.create(email=f'eval-{name.lower()}-{tag}@eval.invalid',
                                   client_account=tenant, role=role, is_active=True)

    user, manager = _user('Rep'), _user('Manager', is_manager=True)
    account = CompanyAccount(has_buying_decision=True, **seed['account'])
    account.save(user=user, client_id=tenant.id)
    service = ActivityCreationService(user, tenant.id)
    today = timezone.now().date()
    cycle = None

    # The people first: an activity with people needs a participant (THE
    # participant rule, activities/services/participant_rules.py) — by
    # default the case's first person, else the first names of `participants`.
    contacts = {}
    for person in seed['people']:
        contact = Contact(account=account, first_name=person['first_name'],
                          last_name=person['last_name'], job_title=person['job_title'])
        contact.save(user=user, client_id=tenant.id)
        contacts[person['first_name']] = contact
    default_participant = seed['people'][0]['first_name']

    for spec in seed['activities']:
        data = {
            'account_id': str(account.id), 'title': spec['title'],
            'activity_type': spec['type'], 'status': spec['status'],
            'scheduled_date': today - datetime.timedelta(days=spec['days_ago']),
            'contact_ids': [str(contacts[name].id)
                            for name in spec.get('participants', [default_participant])],
        }
        if cycle is None:
            created = service.create_with_entities(
                activity_data=data, inline_cycle={'name': seed['cycle']['name']},
                inline_step_stage=spec['stage'])
            cycle = created['cycle']
        else:
            data.update(decision_cycle_id=str(cycle.id),
                        decision_step_id=str(cycle.steps.get(stage=spec['stage']).id))
            created = service.create_with_entities(activity_data=data)
        activity = created['activity']
        for field in ('transcript', 'outcome_notes'):
            if spec.get(field):
                setattr(activity, field, spec[field])
        if spec['status'] == ActivityStatus.COMPLETED and not activity.completed_at:
            activity.completed_at = timezone.now() - datetime.timedelta(days=spec['days_ago'])
        activity.save(user=user, client_id=tenant.id)

    for field in ('description', 'estimated_value'):
        if seed['cycle'].get(field) not in (None, ''):
            setattr(cycle, field, seed['cycle'][field])
    cycle.save(user=user, client_id=tenant.id)

    for person in seed['people']:
        contact = contacts[person['first_name']]
        signal = signals.PeopleSignal(
            account=account, decision_cycle=cycle, target_contact=contact,
            source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
            role=person['role'], confidence=1.0,
        )
        signal.save(user=user, client_id=tenant.id)
        get_or_create_contact_stakeholder(cycle, contact, user)

    models = {'pain': signals.PainSignal, 'impact': signals.ImpactSignal,
              'objective': signals.ObjectiveSignal, 'blocker': signals.BlockerSignal,
              'constraint': signals.ConstraintSignal}
    for kind, rows in (seed.get('signals') or {}).items():
        for fields in rows:
            fields = dict(fields)
            if kind in ('impact', 'objective'):
                fields.setdefault('scope_level', 'DEPARTMENT')
            signal = models[kind](account=account, decision_cycle=cycle,
                                  source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
                                  **fields)
            signal.save(user=user, client_id=tenant.id)

    for content in seed.get('manager_notes') or []:
        note = ManagerNote(decision_cycle=cycle, content=content)
        note.save(user=manager, client_id=tenant.id)

    for product in seed.get('products') or []:
        entry = ProductCatalog(name=product['name'], description=product['description'],
                               value_proposition=product['value_proposition'],
                               default_unit_price=1000)
        entry.save(user=user, client_id=tenant.id)
        DealProduct(decision_cycle=cycle, product_catalog_entry=entry,
                    quantity=product['quantity'], unit_price=1000).save(user=user, client_id=tenant.id)

    step = current_decision_step(cycle)
    declared = step.stage if step else None
    if declared != seed['declared_step']:
        sys.exit(f'{case}: the seeded declared step is {declared}, '
                 f'seed.json says {seed["declared_step"]} -- fix the activities of the seed.')
    return user, cycle


# =============================================================================
# DRY RUN — no API call
# =============================================================================

def _dry_answer(case, fmt):
    """A schema-valid answer built from the case's truth, through the real
    parse / write path. One cell is deliberately faulty (qualification_sparse,
    format B: an invented figure and a rep task in top_arguments) so the
    report shows red checks — the dry run proves the checks run, not that a
    model is good."""
    expected = _expected(case)
    seed = _seed(case)
    decider = expected['decision_maker']
    champion = next((p['first_name'] for p in seed['people'] if p['role'] == 'CHAMPION'), decider)
    step = expected['real_step']
    keyword = expected['missing_info']['any_of'][0]
    objection = expected['hidden_objection']['any_of'][0]
    dims = [{'key': key, 'status': 'suggested', 'evidence': f'{champion} described the need.', 'missing': ''}
            for key in scoring.DEAL_HEALTH_RESPONSE_SCHEMA['schema']['properties']['dimensions']
            ['items']['properties']['key']['enum']]
    status = {'budget': 'unknown', 'authority': 'validated', 'need': 'validated', 'timeline': 'unknown'}
    status.update(expected.get('bant') or {})
    answer = {
        'global_reading': f'{champion} carries the need; {decider} decides.',
        'dimensions': dims,
        'discovery_gaps': [],
        'levers': {'desires': [], 'value': [], 'cost': [], 'constraints': []},
        'themes': [],
        'evidence_scope': {'validated_signals_count': 1, 'note': 'Based on captured evidence.'},
        'summary': f'{champion} carries the need and {decider} decides; the {objection} point must be handled.',
        'needs_and_urgency': {'status': 'suggested', 'assessment': f'{champion} confirmed the need.',
                              'cost_of_inaction': 'Unknown'},
        'credibility': {'status': 'unclear', 'assessment': 'Unknown'},
        'fit_and_value': {'status': 'unclear', 'assessment': 'Unknown', 'requirements': [],
                          'competitive_position': 'Unknown'},
        'buying_process': {'assessment': f'{decider} decides.', 'steps': [], 'timeline': 'Unknown'},
        'bant': {letter: {'status': value, 'reason': 'Unknown' if value == 'unknown' else f'{decider} decides.'}
                 for letter, value in status.items()},
        'strategic_conclusion': f'The rep meets {decider} to clear the {objection} point, to move the deal on.',
        'levers_to_invest': [{'lever': f'{champion} as champion', 'why': 'carries the need'}],
        'objectives': {'deal': 'Unknown', 'next_activity': [f'meet {decider}']},
        'missing_info': [{'level': expected['missing_info']['level'], 'item': f'the {keyword} picture',
                          'why_it_matters': 'it decides the next step',
                          'suggested_question': f'what is the {keyword} situation?'}],
        'estimated_step': {'step': step, 'reason': 'from the evidence'},
        'top_arguments': [{'target': decider, 'arguments': [{
            'need': 'a clear return on the project', 'value': 'time saved for the team',
            'benefit': 'less manual work', 'advantage': 'automatic planning', 'feature': 'planning engine'}]}],
        'stakeholders': [],
    }
    if case == 'qualification_sparse' and fmt == DEAL_HEALTH_INPUT_FORMAT_JSON:
        answer['needs_and_urgency']['cost_of_inaction'] = 'About 15 percent of the fleet budget.'
        answer['top_arguments'][0]['arguments'][0]['need'] = 'Schedule a demo for the drivers'
    return answer


class DryRunProvider:
    """--dry-run: no API call; the answer of the case read on the prompt."""

    def __init__(self, case, fmt):
        self.case, self.fmt = case, fmt

    def call(self, **kwargs):
        return LLMCallResult(
            content=json.dumps(_dry_answer(self.case, self.fmt), ensure_ascii=False),
            input_tokens=0, output_tokens=0, model_used='dry-run', duration_ms=0,
        )


# =============================================================================
# RUN
# =============================================================================

@contextlib.contextmanager
def _input_format(fmt):
    """The format of the cell, for this call only (the module global the
    context builder reads — constants.DEAL_HEALTH_INPUT_FORMAT)."""
    previous = context_v2.DEAL_HEALTH_INPUT_FORMAT
    context_v2.DEAL_HEALTH_INPUT_FORMAT = fmt
    try:
        yield
    finally:
        context_v2.DEAL_HEALTH_INPUT_FORMAT = previous


def _failure(run):
    message = f'run {run.status}: {run.error_message}'
    if run.status == AIPipelineStatus.TIMEOUT:
        return LLMTimeoutError(message)
    if run.status == AIPipelineStatus.PARSE_ERROR:
        return PromptParseError(message)
    return LLMProviderError(message)


def run_cell(case, fmt, model_key, n, out_dir, dry_run, user, cycle):
    provider = DryRunProvider(case, fmt) if dry_run else get_provider(model_key)
    model = ai_config.PROVIDER_CONFIG[model_key]['model']
    name = variant_name(case, fmt, model_key)
    base_record = {'case': case, 'format': fmt, 'format_label': FORMATS[fmt],
                   'provider_key': model_key, 'model': model,
                   'prompt_versions': dict(DealHealthPipeline.PROMPT_VERSIONS)}

    def make_call(recorder):
        with transaction.atomic():          # one savepoint per call, rolled back
            with _input_format(fmt):
                pipeline = DealHealthPipeline(provider=recorder)
                pipeline._provider_key = model_key
                pipeline._provider_config = ai_config.PROVIDER_CONFIG[model_key]
                result = pipeline.run(decision_cycle=cycle, user=user, client_id=cycle.client_id)
            run = result['run']
            if run is None:                 # a run guard (A10) — never on a fresh seed
                raise LLMProviderError(f'blocked: {result.get("blocked")}')
            sub_call = (run.sub_calls or [{}])[-1]
            transaction.set_rollback(True)
        if run.status != AIPipelineStatus.SUCCESS:
            raise _failure(run)
        meta = {k: sub_call.get(k) for k in (
            'attempt', 'duration_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens',
            'model_used', 'input_truncation', 'persist_counts')}
        parsed = PromptBuilder.parse_response(recorder.calls[-1]['raw_response'])
        return parsed, meta, {'run_status': run.status}

    return run_calls(
        name=name, n=n, variant_dir=out_dir / name, base_record=base_record,
        make_recorder=lambda: RecordingProvider(provider), make_call=make_call,
        score=score_record,
    )


def score_record(record):
    """The metrics of ONE recorded call, from the record only (a run and --rescore)."""
    attempts = record.get('attempts') or []
    prompt = (f"{attempts[0].get('system') or ''}\n{attempts[0].get('user') or ''}"
              if attempts else '')
    return scoring.score_call(
        parsed=record.get('parsed'), prompt=prompt, expected=_expected(record['case']),
        meta=record.get('meta'), error_type=record.get('error_type'),
    )


# =============================================================================
# REPORT — side by side
# =============================================================================

def _mark(value):
    return {True: '✅', False: '❌', None: '—'}[value]


def _short(text, limit):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _thousands(number):
    """50000 -> '50 000' (the report is in French)."""
    return f'{number:,}'.replace(',', ' ')


def _cell_label(fmt, model_key):
    return f'{FORMATS[fmt]} · {ai_config.PROVIDER_CONFIG[model_key]["model"]}'


def write_report(out_dir, records, suffix=''):
    """report<suffix>.md: the recap table, then per case the cells side by side."""
    by_cell = {}
    for record in records:
        by_cell.setdefault(record['variant'], []).append(record)
    cells = sorted({(r['format'], r['provider_key']) for r in records},
                   key=lambda c: (c[0] != DEAL_HEALTH_INPUT_FORMAT_SECTIONS, c[1]))
    cases = sorted({r['case'] for r in records})
    versions = next((r.get('prompt_versions') for r in records), {})

    def rate(recs, key):
        values = [scoring.checks(r['metrics'])[key] for r in recs]
        passed = sum(1 for v in values if v)
        return f'{passed}/{len(values)}'

    lines = [
        '# Deal health — évaluation format × modèle',
        '',
        f'Prompts : {json.dumps(versions)} · cas : {len(cases)} (fictifs) · '
        f'appels : {len(records)}',
        '',
        '## Récapitulatif (par cellule : contrôles réussis sur les appels)',
        '',
        '| Cellule | ' + ' | '.join(label for _k, label in scoring.CHECK_LABELS)
        + ' | durée moy. (s) | durée max (s) | tokens moy. (in/out) | erreurs |',
        '|' + '---|' * (len(scoring.CHECK_LABELS) + 5),
    ]
    for fmt, model_key in cells:
        recs = [r for r in records if r['format'] == fmt and r['provider_key'] == model_key]
        durations = [r['metrics'].get('duration_ms') for r in recs if r['metrics'].get('duration_ms') is not None]
        ins = [r['metrics'].get('input_tokens') or 0 for r in recs if r['metrics'].get('answered')]
        outs = [r['metrics'].get('output_tokens') or 0 for r in recs if r['metrics'].get('answered')]
        errors = [r['metrics'].get('error_type') for r in recs if r['metrics'].get('error_type')]
        lines.append(
            f'| {_cell_label(fmt, model_key)} | '
            + ' | '.join(rate(recs, key) for key, _label in scoring.CHECK_LABELS)
            + f' | {round(sum(durations) / len(durations) / 1000, 1) if durations else "—"}'
            f' | {round(max(durations) / 1000, 1) if durations else "—"}'
            f' | {round(sum(ins) / len(ins)) if ins else "—"} / {round(sum(outs) / len(outs)) if outs else "—"}'
            f' | {", ".join(errors) or "—"} |')

    truncated = [r for r in records if r['metrics'].get('input_truncated')]
    timeouts = [r for r in records if r['metrics'].get('error_type') == 'timeout']
    all_durations = [r['metrics'].get('duration_ms') or 0 for r in records]
    longest_prompt = max((r['metrics'].get('prompt_chars') or 0) for r in records)
    lines += [
        '',
        '## Plafonds et délai',
        '',
        f'- Plafonds d’entrée : {_thousands(DEAL_HEALTH_MAX_CHARS_PER_SOURCE)} caractères par source, '
        f'{_thousands(DEAL_HEALTH_MAX_INPUT_CHARS)} au total — atteints : '
        f'{"oui, " + str(len(truncated)) + " appel(s) tronqué(s)" if truncated else "non"} '
        f'(prompt le plus long : {_thousands(longest_prompt)} caractères).',
        f'- Délai : {DEAL_HEALTH_TIMEOUT_S} s — atteint : '
        f'{"oui, " + str(len(timeouts)) + " timeout(s)" if timeouts else "non"} '
        f'(durée max : {round(max(all_durations) / 1000, 1) if all_durations else 0} s).',
    ]

    for case in cases:
        expected = _expected(case)
        lines += ['', f'## Cas `{case}`', '',
                  f'{_seed(case).get("description", "")}',
                  '',
                  f'Attendu : étape réelle **{expected["real_step"]}** · info manquante '
                  f'**{expected["missing_info"]["level"]}** ({", ".join(expected["missing_info"]["any_of"])}) · '
                  f'objection cachée : {expected["hidden_objection"]["description"]} · décideur : '
                  f'**{expected["decision_maker"]}**',
                  '',
                  '| Contrôle | ' + ' | '.join(_cell_label(f, m) for f, m in cells) + ' |',
                  '|---|' + '---|' * len(cells)]
        case_cells = [by_cell.get(variant_name(case, f, m), []) for f, m in cells]
        for key, label in scoring.CHECK_LABELS:
            lines.append(f'| {label} | ' + ' | '.join(
                (_mark(scoring.checks(recs[0]['metrics'])[key]) if len(recs) == 1 else rate(recs, key))
                if recs else '—' for recs in case_cells) + ' |')
        for key, label in (('objection_found', 'objection cachée vue'),
                           ('decision_maker_found', 'décideur nommé'), ('bant_ok', 'BANT attendu')):
            lines.append(f'| {label} (info) | ' + ' | '.join(
                _mark(recs[0]['metrics'].get(key)) if recs else '—' for recs in case_cells) + ' |')
        lines.append('| étape estimée | ' + ' | '.join(
            str(recs[0]['metrics'].get('estimated_step') or '—') if recs else '—' for recs in case_cells) + ' |')
        lines.append('| durée (s) / tokens in·out | ' + ' | '.join(
            (f'{round((recs[0]["metrics"].get("duration_ms") or 0) / 1000, 1)} / '
             f'{recs[0]["metrics"].get("input_tokens") or 0}·{recs[0]["metrics"].get("output_tokens") or 0}')
            if recs else '—' for recs in case_cells) + ' |')
        lines.append('')
        for (fmt, model_key), recs in zip(cells, case_cells):
            if not recs:
                continue
            record = recs[0]
            parsed, metrics = record.get('parsed') or {}, record['metrics']
            lines += [f'### {_cell_label(fmt, model_key)} — appel 1', '']
            if not parsed:
                lines += [f'Erreur : `{record.get("error")}`', '']
                continue
            arguments = '; '.join(
                f'{t.get("target")}: {a.get("need")} → {a.get("value")}'
                for t in parsed.get('top_arguments') or [] for a in t.get('arguments') or [])
            missing = '; '.join(f'{m.get("level")}: {m.get("item")}' for m in parsed.get('missing_info') or [])
            findings = {k: metrics.get(k) for k in (
                'schema_errors', 'last_names_in_output', 'invented_numbers', 'invented_names',
                'guardrail_leaks', 'rhetoric_labels', 'rep_tasks_in_top_arguments') if metrics.get(k)}
            lines += [
                f'- **Résumé** : {_short(parsed.get("summary"), 300)}',
                f'- **Plan d’action** : {_short(parsed.get("strategic_conclusion"), 600)}',
                f'- **Arguments** : {_short(arguments, 400) or "—"}',
                f'- **Info manquante** : {_short(missing, 400) or "—"}',
                f'- **Étape estimée** : {(parsed.get("estimated_step") or {}).get("step")} — '
                f'{_short((parsed.get("estimated_step") or {}).get("reason"), 200)}',
                f'- **Constats** : {json.dumps(findings, ensure_ascii=False) if findings else "aucun"}',
                '',
            ]
    path = out_dir / f'report{suffix}.md'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def _recap(rows):
    return [f'Appels : {len(rows)} · rapport côte à côte : report.md']


def rescore(out_dir):
    """--rescore: recompute the metrics, the summary and the report from the
    answers ALREADY recorded — no API call, no database."""
    variants = sorted(p.name for p in out_dir.iterdir() if p.is_dir() and SEP in p.name)
    records = []
    for record in load_records(out_dir, variants):
        record['metrics'] = score_record(record)
        records.append(record)
    if not records:
        sys.exit(f'No call_NN.json under {out_dir} -- nothing to rescore.')
    rows = [row(r, r['metrics']) for r in records]
    write_summary(out_dir, rows, title='Deal health — récap (rescored)',
                  models_used={r['variant']: r.get('model') for r in records},
                  versions=records[0].get('prompt_versions') or {}, recap=_recap(rows),
                  suffix='_rescored')
    print(f'Report: {write_report(out_dir, records, suffix="_rescored")}')


# =============================================================================
# MAIN
# =============================================================================

def check_models(model_keys, dry_run):
    """Every matrix entry exists, supports the response schema and, for a
    real run, has its API key (the deal health's own load-time rules)."""
    for key in model_keys:
        if key not in ai_config.PROVIDER_CONFIG:
            sys.exit(f'--models {key}: not a PROVIDER_CONFIG entry '
                     f'({", ".join(sorted(ai_config.PROVIDER_CONFIG))}).')
        if not provider_supports_response_schema(key):
            sys.exit(f'--models {key}: its provider does not support the response schema.')
        if not dry_run and not provider_credentials_present(key):
            sys.exit(f'--models {key}: {provider_required_env_key(key)} is not set.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    add_common_arguments(
        parser, CASES, declared_models(),
        model_help='one model DECLARED in ai_pipelines/config.py instead of the --models matrix',
    )
    parser.set_defaults(n=1)
    parser.add_argument('--models', nargs='+', default=list(DEFAULT_MODELS),
                        help='PROVIDER_CONFIG entries of the matrix (default: model X '
                             'openai_deal_health, model Y openai_deal_health_challenger)')
    parser.add_argument('--formats', nargs='+', choices=list(FORMATS), default=list(FORMATS),
                        help='input formats: sections (A), json (B)')
    args = parser.parse_args(argv)

    if args.rescore:
        rescore(Path(args.rescore))
        return None

    model_keys = [declared_models()[args.model]] if args.model else args.models
    check_models(model_keys, args.dry_run)
    out_dir = prepare_out_dir(args.out, HERE)
    cases = args.only or list(CASES)

    rows = []
    with transaction.atomic():              # everything is rolled back at the end
        for case in cases:
            user, cycle = create_case(case)
            for fmt in args.formats:
                for model_key in model_keys:
                    rows.extend(run_cell(case, fmt, model_key, args.n, out_dir,
                                         args.dry_run, user, cycle))
        transaction.set_rollback(True)

    records = list(load_records(out_dir, sorted(p.name for p in out_dir.iterdir() if p.is_dir())))
    write_summary(out_dir, rows, title='Deal health — récap',
                  models_used={variant_name(c, f, m): ai_config.PROVIDER_CONFIG[m]['model']
                               for c in cases for f in args.formats for m in model_keys},
                  versions=DealHealthPipeline.PROMPT_VERSIONS, recap=_recap(rows))
    report = write_report(out_dir, records)
    print(f'Report: {report}')
    return out_dir


if __name__ == '__main__':
    main()
