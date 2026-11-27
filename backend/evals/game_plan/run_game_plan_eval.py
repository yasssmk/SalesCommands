#!/usr/bin/env python
"""
Game Plan — evaluate, on the REAL LLM, the models of the Game Plan (prep
call) on 6 FICTITIOUS cases whose truth is written in advance (sprint 2 Game
Plan, G13).

Standalone evaluation script. NOT part of the product: it lives outside
app_modules/, nothing imports it, and it leaves nothing in the database —
everything it creates (tenant, users, account, contacts, decision cycle and
its steps, campaign, activities, signals, stakeholders, deal-health snapshot,
seller profile, products, runs, Game Plans) is rolled back: one savepoint per
call, the whole run inside one transaction never committed (the
evals/deal_health pattern).

Real path, end to end:

  * each case is SEEDED from tests/fixtures/game_plan_eval/<case>/seed.json
    by the standard paths (ActivityCreationService.create_with_entities for
    a cycle's activities, with its auto-created steps; the stakeholder
    services for the people and a manual profile language; the ORM for a
    campaign's sequence, as tests/ai_pipelines/test_prep_call_campaign_context
    does); the prepared activity is checked eligible (G3) before any call;
  * each call runs what POST prep-call/run/ runs: the REAL
    PrepInputPackAssembler (pack v2) and PrepCallPipeline(provider=...).run()
    — prompts v2, the strict schema of the output kind (plan / message), the
    server-side validation — with the model / max_tokens / timeout / effort
    of the PROVIDER_CONFIG entry of the cell;
  * the matrix: models only, the pack v2 as it is (no format axis):
    openai_prep_call (the production entry — gpt-5.6-terra since G13b, model
    X) and openai_prep_call_challenger (gpt-4o-mini, declared for the
    evaluation only, model Y). Any entry whose provider supports the schema
    can be added — Claude with `--models ... claude_prep_call` once
    ANTHROPIC_API_KEY is set.

Truth and checks: tests/fixtures/game_plan_eval/<case>/expected.json +
evals/game_plan/scoring.py + README.md.

Output (one folder per run, see --out; a non-empty folder is refused):
  <variant>/call_<NN>.json   prompt sent, raw answer(s), parsed JSON, metrics
                             (variant = <case>__<entry>)
  summary.csv / summary.md   one row per call + the recap (eval_kit)
  report.md                  the report: per cell the checks, the PARSE_ERROR
                             causes, durations, tokens and cost; per case the
                             outputs side by side

Usage (from backend/, with OPENAI_API_KEY in backend/salescommands/.env):
  python evals/game_plan/run_game_plan_eval.py                 # 6 cases x 2 models = 12 calls
  python evals/game_plan/run_game_plan_eval.py --n 3           # 3 calls per cell
  python evals/game_plan/run_game_plan_eval.py --only trap_no_figures
  python evals/game_plan/run_game_plan_eval.py --models openai_prep_call claude_prep_call
  python evals/game_plan/run_game_plan_eval.py --dry-run       # no API call
  python evals/game_plan/run_game_plan_eval.py --rescore evals/game_plan/out/<stamp>
"""

import argparse
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
from app_modules.ai_pipelines.constants import AIPipelineStatus  # noqa: E402
from app_modules.ai_pipelines.pipelines.prep_call import PrepCallPipeline, _OUTPUTS  # noqa: E402
from app_modules.ai_pipelines.prompts.base import PromptBuilder, PromptParseError  # noqa: E402
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
from app_modules.ai_pipelines.services.game_plan_access import (  # noqa: E402
    game_plan_blocked_reason,
    game_plan_output_kind,
)
from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (  # noqa: E402
    PrepInputPackAssembler,
)

# Shared eval plumbing (evals/common/eval_kit.py) — one implementation.
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
from evals.game_plan import scoring  # noqa: E402


FIXTURES = BACKEND / 'tests' / 'fixtures' / 'game_plan_eval'
CASES = tuple(sorted(d.name for d in FIXTURES.iterdir() if (d / 'seed.json').exists()))
# Model X (the production entry, gpt-5.6-terra since G13b) and model Y (the
# challenger, gpt-4o-mini, declared for the evaluation only).
DEFAULT_MODELS = ('openai_prep_call', 'openai_prep_call_challenger')
SEP = '__'
# TD-321: gunicorn runs the web workers with --timeout 12 (backend/Procfile):
# a synchronous run longer than that is killed in production today.
GUNICORN_TIMEOUT_S = 12
# The public price per million tokens (input, output) in USD of the models
# whose price is KNOWN here — to check before deciding; a model absent from
# the table gets no estimate (« — ») unless given with --price.
PRICES_PER_MTOK = {
    'gpt-4o-mini': (0.15, 0.60),
}


def _seed(case):
    return json.loads((FIXTURES / case / 'seed.json').read_text(encoding='utf-8'))


def _expected(case):
    return json.loads((FIXTURES / case / 'expected.json').read_text(encoding='utf-8'))


def variant_name(case, model_key):
    return f'{case}{SEP}{model_key}'


# =============================================================================
# SEED — one fictitious case, by the standard paths
# =============================================================================

def _tenant_and_rep():
    from end_users.models import ClientAccount, User, UserRole
    tag = uuid.uuid4().hex[:12]
    tenant = ClientAccount.objects.create(name=f'eval-game-plan-{tag}', is_b2b=True, max_users=20)
    role = UserRole.objects.create(
        client_account=tenant, name='Rep', is_individual=True, is_admin=False, is_manager=False,
        read=True, write=True, modify=True, can_delete=True,
    )
    user = User.objects.create(email=f'eval-rep-{tag}@eval.invalid', client_account=tenant,
                               role=role, is_active=True)
    return tenant, user


def _contacts(seed, account, user, tenant):
    from app_modules.contacts.models import Contact
    contacts = {}
    for person in seed['people']:
        contact = Contact(account=account, first_name=person['first_name'],
                          last_name=person['last_name'], job_title=person['job_title'],
                          department=person.get('department') or '')
        contact.save(user=user, client_id=tenant.id)
        contacts[f"{person['first_name']} {person['last_name']}"] = contact
    return contacts


def _contact_of(contacts, name):
    """A participant of the seed: « Nadia » or « Marc Dupont » (homonyms)."""
    found = [c for full, c in contacts.items() if full == name or full.split(' ')[0] == name]
    if len(found) != 1:
        sys.exit(f'seed: participant {name!r} matches {len(found)} people -- use the full name.')
    return found[0]


def _seller_profile(seed, user, tenant):
    from app_modules.product_catalog.models import SellerProfile
    if seed.get('seller_profile'):
        SellerProfile(**seed['seller_profile']).save(user=user, client_id=tenant.id)


def _cycle_case(seed, tenant, user, account, contacts):
    """The activities by create_with_entities (the first creates the cycle
    inline, with its auto-created steps), the people (validated People signal
    + stakeholder, a manual profile language), the stakeholders without
    contact, the signals, the products, the deal-health snapshot."""
    from app_modules.activities.constants import ActivityStatus
    from app_modules.activities.services.activity_creation_service import ActivityCreationService
    from app_modules.decision_cycles.constants import PROFILE_COMMUNICATION_LANGUAGE
    from app_modules.decision_cycles.models import DealHealthSnapshot, DealProduct, Stakeholder
    from app_modules.decision_cycles.services.stakeholder_service import (
        apply_manual_profile,
        get_or_create_contact_stakeholder,
    )
    from app_modules.product_catalog.models import ProductCatalog
    from app_modules.signals import models as signals
    from app_modules.signals.constants import SignalSource, SignalStatus

    service = ActivityCreationService(user, tenant.id)
    today = timezone.now().date()
    cycle, prepared = None, None
    for spec in seed['activities']:
        data = {
            'account_id': str(account.id), 'title': spec['title'],
            'activity_type': spec['type'], 'status': spec['status'],
            'scheduled_date': today - datetime.timedelta(days=spec['days_ago']),
            'contact_ids': [str(_contact_of(contacts, n).id) for n in spec['participants']],
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
        for field in ('outcome_notes', 'description'):
            if spec.get(field):
                setattr(activity, field, spec[field])
        if spec['status'] == ActivityStatus.COMPLETED and not activity.completed_at:
            activity.completed_at = timezone.now() - datetime.timedelta(days=spec['days_ago'])
        activity.save(user=user, client_id=tenant.id)
        if spec.get('prepare'):
            prepared = activity

    cycle.description = seed['cycle'].get('description') or ''
    cycle.save(user=user, client_id=tenant.id)

    for person in seed['people']:
        if person.get('stakeholder') is False:
            continue
        contact = contacts[f"{person['first_name']} {person['last_name']}"]
        if person.get('role'):
            signals.PeopleSignal(
                account=account, decision_cycle=cycle, target_contact=contact,
                source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
                role=person['role'], confidence=1.0,
            ).save(user=user, client_id=tenant.id)
        stakeholder = get_or_create_contact_stakeholder(cycle, contact, user)
        if person.get('language'):
            apply_manual_profile(stakeholder, PROFILE_COMMUNICATION_LANGUAGE, person['language'], user)

    for spec in seed.get('stakeholders_without_contact') or []:
        stakeholder = Stakeholder(decision_cycle=cycle, full_name=spec['full_name'])
        stakeholder.save(user=user, client_id=tenant.id)
        if spec.get('on_prepared_activity'):
            prepared.stakeholders.add(stakeholder)

    kinds = {'pain': signals.PainSignal, 'impact': signals.ImpactSignal,
             'objective': signals.ObjectiveSignal, 'blocker': signals.BlockerSignal,
             'constraint': signals.ConstraintSignal}
    for kind, rows in (seed.get('signals') or {}).items():
        for fields in rows:
            fields = dict(fields)
            if kind in ('impact', 'objective'):
                fields.setdefault('scope_level', 'DEPARTMENT')
            kinds[kind](account=account, decision_cycle=cycle, source=SignalSource.MANUAL,
                        status=SignalStatus.VALIDATED, **fields).save(user=user, client_id=tenant.id)

    for product in seed.get('products') or []:
        entry = ProductCatalog(name=product['name'], description=product['description'],
                               value_proposition=product['value_proposition'], default_unit_price=1000)
        entry.save(user=user, client_id=tenant.id)
        DealProduct(decision_cycle=cycle, product_catalog_entry=entry,
                    quantity=product['quantity'], unit_price=1000).save(user=user, client_id=tenant.id)

    if seed.get('deal_health'):
        from app_modules.decision_cycles.constants import DEAL_HEALTH_SCHEMA_V2
        DealHealthSnapshot(decision_cycle=cycle, diagnostic=seed['deal_health'],
                           schema_version=DEAL_HEALTH_SCHEMA_V2,
                           snapshot_date=timezone.now()).save(user=user, client_id=tenant.id)
    return prepared


def _campaign_case(seed, tenant, user, account, contacts):
    """A campaign's sequence without decision cycle — by the ORM, the shape
    campaign_execution_service gives it (campaign, campaign account and
    contact, the activities with their sequence position and the campaign
    objective as call_to_action)."""
    from app_modules.activities.constants import ActivityStatus
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact

    spec = seed['campaign']
    today = timezone.now().date()
    campaign = Campaign(name=spec['name'], campaign_type=CampaignType.OUTBOUND, owner=user,
                        activity_objective=spec['activity_objective'],
                        planned_start_date=today - datetime.timedelta(days=10),
                        planned_end_date=today + datetime.timedelta(days=30))
    campaign.save(user=user, client_id=tenant.id)
    ca = CampaignAccount(campaign=campaign, account=account, status='IN_PROGRESS')
    ca.save(user=user, client_id=tenant.id)
    contact = _contact_of(contacts, spec['contact'])
    cc = CampaignContact(campaign_account=ca, contact=contact, status='IN_PROGRESS',
                         objective=spec['contact_objective'])
    cc.save(user=user, client_id=tenant.id)
    prepared = None
    for position, step in enumerate(spec['sequence'], start=1):
        done = step['status'] == ActivityStatus.COMPLETED
        activity = Activity(
            title=f'Step {position}', activity_type=step['type'], status=step['status'],
            outcome=step.get('outcome'), outcome_notes=step.get('notes') or '',
            account=account, owner=user, campaign=campaign, campaign_account=ca,
            campaign_contact=cc, sequence_position=position,
            scheduled_date=today - datetime.timedelta(days=step['days_ago']),
            completed_at=(timezone.now() - datetime.timedelta(days=step['days_ago'])) if done else None,
            call_to_action=spec['activity_objective'],
        )
        activity.save(user=user, client_id=tenant.id)
        activity.contacts.add(contact)
        if step.get('prepare'):
            prepared = activity
    return prepared


def create_case(case):
    """The case's tenant, rep, account, people, seller profile and its cycle
    or campaign. Returns (user, the activity to prepare) — checked eligible."""
    from app_modules.accounts.models import CompanyAccount

    seed = _seed(case)
    tenant, user = _tenant_and_rep()
    account = CompanyAccount(has_buying_decision=True, **seed['account'])
    account.save(user=user, client_id=tenant.id)
    contacts = _contacts(seed, account, user, tenant)
    _seller_profile(seed, user, tenant)
    prepared = (_campaign_case if seed.get('campaign') else _cycle_case)(seed, tenant, user, account, contacts)
    prepared.refresh_from_db()
    blocked = game_plan_blocked_reason(prepared)
    if blocked:
        sys.exit(f'{case}: the prepared activity is not eligible ({blocked}) -- fix the seed.')
    if game_plan_output_kind(prepared) != _expected(case)['output_kind']:
        sys.exit(f'{case}: the prepared activity is a {game_plan_output_kind(prepared)}, '
                 f'expected.json says {_expected(case)["output_kind"]}.')
    return user, prepared


# =============================================================================
# DRY RUN — no API call
# =============================================================================

def _dry_plan(case, expected):
    """A valid plan built from the case's truth."""
    first = expected['participants'][0]
    keyword = (expected.get('dh_missing_any_of') or ['budget'])[0]
    answer = {
        'context': f'{first} carries the need; this conversation moves the deal on.',
        'objective': {'plans': [
            {'label': 'A', 'goal': 'Agree on the next step.', 'success_criteria': 'A date is set.'},
            {'label': 'B', 'goal': 'Learn who decides.', 'success_criteria': 'The decider is named.'},
        ]},
        'client_expectations': ['A clear view of how the planning would work.'],
        'opening': {'objective': 'Agree on the next step.', 'time': 'Ask for the time they have.',
                    'client_agenda': 'Ask what they want from the call.',
                    'our_agenda': 'Their planning today, then the next step.',
                    'expected_outcome': 'A next step accepted.'},
        'discovery': {
            'missing_info': [{'item': f'The {keyword} point', 'question': f'Where does the {keyword} stand?'}],
            'conviction': {
                'needs_and_urgency': {'reading': 'The need is stated.', 'question': 'What if nothing changes?'},
                'credibility': {'reading': 'Unknown.', 'question': 'What proof would you need?'},
                'fit_and_value': {'reading': 'Unknown.', 'question': 'Which step hurts most?'},
            },
        },
        'argumentation': [{'ref': ref, 'arguments': [{'benefit': 'A calmer week.',
                                                       'advantage': 'No manual rework.',
                                                       'feature': 'The planning engine.'}]}
                          for ref in expected['participants']],
        'closing': {'next_step': 'Book the next meeting.', 'with_whom': first,
                    'when': 'Two dates next week.', 'keep_control': 'Send the invitation today.'},
        'product_pitch': [],
        'participants': [{'ref': ref, 'angle': 'Their own words first.'} for ref in expected['participants']],
        'campaign_diagnostic': (
            {'reading': 'Two calls without answer.', 'next_move': 'Leave a short voicemail, then email.'}
            if expected['campaign_diagnostic'] else None
        ),
    }
    return answer


def _dry_messages(expected):
    channel_subject = 'Our next step' if expected['channel'] == 'EMAIL' else None
    return {'messages': [
        {'ref': ref, 'language': language, 'subject': channel_subject,
         'body': f'Hello {ref}, shall we book a short call next week?'}
        for ref, language in expected['languages'].items()
    ]}


def _dry_answer(case, model_key):
    """A valid answer built from the case's truth, through the real parse /
    validate path. Two cells are deliberately faulty, to show red checks:
      * trap_no_figures · openai_prep_call_challenger: an INVENTED figure (the RED
        RUBAN fault, with numbers no date can hold: « 37 % … 430 hours »);
      * demo_end_of_cycle · openai_prep_call: « the price » written as
        a common word — the server refuses it (Sarah's last name is Price): a
        PARSE_ERROR counted as a FALSE rejection."""
    expected = _expected(case)
    if expected['output_kind'] == 'MESSAGE':
        return _dry_messages(expected)
    answer = _dry_plan(case, expected)
    if case == 'trap_no_figures' and model_key == 'openai_prep_call_challenger':
        answer['context'] = ('Reducing IT maintenance by 37 % saves 430 hours a year: '
                             'lead with it.')
    if case == 'demo_end_of_cycle' and model_key == 'openai_prep_call':
        answer['client_expectations'] = ['See the price of the solution on their own data.']
    return answer


class DryRunProvider:
    """--dry-run: no API call; a fixed answer per cell."""

    def __init__(self, case, model_key):
        self.case, self.model_key = case, model_key

    def call(self, **kwargs):
        return LLMCallResult(
            content=json.dumps(_dry_answer(self.case, self.model_key), ensure_ascii=False),
            input_tokens=0, output_tokens=0, model_used='dry-run', duration_ms=0,
        )


# =============================================================================
# RUN
# =============================================================================

def _failure(run):
    message = f'run {run.status}: {run.error_message}'
    if run.status == AIPipelineStatus.TIMEOUT:
        return LLMTimeoutError(message)
    if run.status == AIPipelineStatus.PARSE_ERROR:
        return PromptParseError(message)
    return LLMProviderError(message)


def run_cell(case, model_key, n, out_dir, dry_run, user, activity):
    provider = DryRunProvider(case, model_key) if dry_run else get_provider(model_key)
    model = ai_config.PROVIDER_CONFIG[model_key]['model']
    name = variant_name(case, model_key)
    kind = game_plan_output_kind(activity)
    base_record = {'case': case, 'provider_key': model_key, 'model': model,
                   'output_kind': str(kind), 'prompt_versions': dict(_OUTPUTS[kind]['versions'])}

    def make_call(recorder):
        with transaction.atomic():          # one savepoint per call, rolled back
            assembler = PrepInputPackAssembler()
            input_pack = assembler.build(activity=activity)
            pipeline = PrepCallPipeline(provider=recorder)
            pipeline._provider_key = model_key
            pipeline._provider_config = ai_config.PROVIDER_CONFIG[model_key]
            result = pipeline.run(
                activity=activity, target_contact=None, input_pack=input_pack, user=user,
                client_id=activity.client_id, output_kind=kind, people=assembler.people,
            )
            run = result['run']
            if run is None:                 # « nothing new » (G9) — never on a fresh seed
                raise LLMProviderError(f'blocked: {result.get("blocked")}')
            sub_call = (run.sub_calls or [{}])[-1]
            transaction.set_rollback(True)
        if run.status != AIPipelineStatus.SUCCESS:
            raise _failure(run)
        meta = {k: sub_call.get(k) for k in (
            'attempt', 'duration_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens',
            'model_used', 'persist_counts')}
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
    first = attempts[0] if attempts else {}
    meta = dict(record.get('meta') or {})
    if not meta and attempts:               # a refused answer: the provider's own counts
        meta = {'input_tokens': attempts[-1].get('input_tokens'),
                'output_tokens': attempts[-1].get('output_tokens')}
    return scoring.score_call(
        parsed=record.get('parsed'),
        prompt=f"{first.get('system') or ''}\n{first.get('user') or ''}",
        user_prompt=first.get('user') or '',
        expected=_expected(record['case']), meta=meta,
        error_type=record.get('error_type'), error=record.get('error'),
        raw_answer=attempts[-1].get('raw_response') if attempts else None,
    )


# =============================================================================
# REPORT
# =============================================================================

def _mark(value):
    return {True: '✅', False: '❌', None: '—'}[value]


def _short(text, limit):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _cost(record, prices):
    """The estimated cost of one call in USD, or None (no price known)."""
    price = prices.get(record.get('model'))
    metrics = record['metrics']
    if price is None or metrics.get('input_tokens') is None:
        return None
    return ((metrics.get('input_tokens') or 0) * price[0]
            + (metrics.get('output_tokens') or 0) * price[1]) / 1_000_000


def write_report(out_dir, records, prices=None, suffix=''):
    """report<suffix>.md: the recap per cell, then per case side by side."""
    prices = {**PRICES_PER_MTOK, **(prices or {})}
    cells = sorted({r['provider_key'] for r in records})
    cases = sorted({r['case'] for r in records})
    # The model each cell RAN on, as recorded — not today's config (a
    # --rescore of a run made before an entry changed stays right, G13b).
    model_of = {r['provider_key']: r.get('model') for r in records}

    def rate(recs, key):
        values = [scoring.checks(r['metrics'])[key] for r in recs]
        values = [v for v in values if v is not None]
        return f'{sum(1 for v in values if v)}/{len(values)}' if values else '—'

    lines = [
        '# Game Plan — évaluation des modèles',
        '',
        f'Cas : {len(cases)} (fictifs) · appels : {len(records)} · '
        f'timeout gunicorn (TD-321) : {GUNICORN_TIMEOUT_S} s',
        '',
        '## Récapitulatif (par modèle : contrôles réussis sur les appels où ils s’appliquent)',
        '',
        '| Modèle | ' + ' | '.join(label for _k, label in scoring.CHECK_LABELS)
        + ' | PARSE_ERROR (rhétorique / nom / faux rejet / structure) | durée moy. (s) '
          '| durée max (s) | > 12 s | tokens moy. (in/out) | coût estimé ($) | erreurs |',
        '|' + '---|' * (len(scoring.CHECK_LABELS) + 8),
    ]
    for model_key in cells:
        recs = [r for r in records if r['provider_key'] == model_key]
        durations = [r['metrics'].get('duration_ms') for r in recs if r['metrics'].get('duration_ms') is not None]
        ins = [r['metrics'].get('input_tokens') or 0 for r in recs if r['metrics'].get('input_tokens') is not None]
        outs = [r['metrics'].get('output_tokens') or 0 for r in recs if r['metrics'].get('output_tokens') is not None]
        causes = [r['metrics'].get('parse_error_cause') for r in recs]
        costs = [_cost(r, prices) for r in recs]
        errors = [r['metrics'].get('error_type') for r in recs if r['metrics'].get('error_type')]
        lines.append(
            f'| {model_of[model_key]} (`{model_key}`) | '
            + ' | '.join(rate(recs, key) for key, _label in scoring.CHECK_LABELS)
            + ' | ' + ' / '.join(str(causes.count(c)) for c in scoring.PARSE_CAUSES)
            + f' ({sum(1 for c in causes if c)}/{len(recs)})'
            f' | {round(sum(durations) / len(durations) / 1000, 1) if durations else "—"}'
            f' | {round(max(durations) / 1000, 1) if durations else "—"}'
            f' | {sum(1 for d in durations if d > GUNICORN_TIMEOUT_S * 1000)}'
            f' | {round(sum(ins) / len(ins)) if ins else "—"} / {round(sum(outs) / len(outs)) if outs else "—"}'
            f' | {round(sum(costs), 4) if costs and None not in costs else "—"}'
            f' | {", ".join(errors) or "—"} |')

    lines += ['', '## Appels (durée, tokens, coût)', '',
              '| Appel | durée (s) | tokens in / out | coût estimé ($) | erreur |', '|---|---|---|---|---|']
    for record in records:
        metrics = record['metrics']
        cost = _cost(record, prices)
        lines.append(
            f'| {record["variant"]} #{record["call"]} '
            f'| {round((metrics.get("duration_ms") or 0) / 1000, 1)} '
            f'| {metrics.get("input_tokens") or 0} / {metrics.get("output_tokens") or 0} '
            f'| {round(cost, 5) if cost is not None else "—"} '
            f'| {metrics.get("parse_error_cause") or metrics.get("error_type") or "—"} |')

    for case in cases:
        expected = _expected(case)
        case_recs = [[r for r in records if r['case'] == case and r['provider_key'] == m] for m in cells]
        lines += ['', f'## Cas `{case}`', '', _seed(case).get('description', ''), '',
                  f'Attendu : {expected["output_kind"]}'
                  + (f' · participants {", ".join(expected["participants"])}' if expected.get('participants') else '')
                  + (f' · langues {json.dumps(expected["languages"], ensure_ascii=False)}' if expected.get('languages') else '')
                  + (' · campaign_diagnostic attendu' if expected.get('campaign_diagnostic') else '')
                  + (' · **piège : rien ne doit être inventé**' if expected.get('trap') else ''),
                  '',
                  '| Contrôle | ' + ' | '.join(model_of[m] for m in cells) + ' |',
                  '|---|' + '---|' * len(cells)]
        for key, label in scoring.CHECK_LABELS:
            lines.append(f'| {label} | ' + ' | '.join(
                (_mark(scoring.checks(recs[0]['metrics'])[key]) if len(recs) == 1 else rate(recs, key))
                if recs else '—' for recs in case_recs) + ' |')
        lines.append('')
        for model_key, recs in zip(cells, case_recs):
            if not recs:
                continue
            record = recs[0]
            parsed, metrics = record.get('parsed') or {}, record['metrics']
            lines += [f'### {model_of[model_key]} — appel 1', '']
            if not parsed:
                lines += [f'Erreur ({metrics.get("parse_error_cause") or metrics.get("error_type")}) : '
                          f'`{_short(record.get("error"), 300)}`', '']
                continue
            findings = {k: metrics.get(k) for k in (
                'schema_errors', 'last_names_in_output', 'invented_numbers', 'invented_names',
                'rhetoric_labels', 'participants_without_angle', 'opening_missing',
                'wrong_languages') if metrics.get(k)}
            if expected['output_kind'] == 'MESSAGE':
                for message in parsed.get('messages') or []:
                    lines.append(f'- **{message.get("ref")}** ({message.get("language")}) — '
                                 f'{_short(message.get("subject"), 80) or "sans subject"} : '
                                 f'{_short(message.get("body"), 300)}')
            else:
                plans = '; '.join(f'{p.get("label")}: {p.get("goal")}'
                                  for p in (parsed.get('objective') or {}).get('plans') or [])
                angles = '; '.join(f'{p.get("ref")}: {p.get("angle")}' for p in parsed.get('participants') or [])
                lines += [
                    f'- **Contexte** : {_short(parsed.get("context"), 300)}',
                    f'- **Plans** : {_short(plans, 300)}',
                    f'- **Angles** : {_short(angles, 400) or "—"}',
                    f'- **Closing** : {_short((parsed.get("closing") or {}).get("next_step"), 200)}',
                    f'- **campaign_diagnostic** : {_short(json.dumps(parsed.get("campaign_diagnostic"), ensure_ascii=False), 200)}',
                ]
            lines += [f'- **Constats** : {json.dumps(findings, ensure_ascii=False) if findings else "aucun"}', '']
    path = out_dir / f'report{suffix}.md'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def _recap(rows):
    return [f'Appels : {len(rows)} · rapport : report.md']


def _parse_prices(values):
    """--price gpt-5.6-terra=1.25,10 -> {'gpt-5.6-terra': (1.25, 10.0)}."""
    prices = {}
    for value in values or []:
        model, _sep, pair = value.partition('=')
        try:
            prices[model] = tuple(float(x) for x in pair.split(','))
            assert len(prices[model]) == 2
        except (ValueError, AssertionError):
            sys.exit(f'--price {value}: expected MODEL=INPUT,OUTPUT (USD per million tokens).')
    return prices


def rescore(out_dir, prices=None):
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
    write_summary(out_dir, rows, title='Game Plan — récap (rescored)',
                  models_used={r['variant']: r.get('model') for r in records},
                  versions={r['output_kind']: r.get('prompt_versions') for r in records},
                  recap=_recap(rows), suffix='_rescored')
    print(f'Report: {write_report(out_dir, records, prices, suffix="_rescored")}')


# =============================================================================
# MAIN
# =============================================================================

def check_models(model_keys, dry_run):
    """Every entry exists, supports the response schema and, for a real run,
    has its API key (the prep call's own load-time rules)."""
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
                        help='PROVIDER_CONFIG entries (default: model X openai_prep_call, '
                             'model Y openai_prep_call_challenger)')
    parser.add_argument('--price', nargs='*', metavar='MODEL=IN,OUT',
                        help='USD per million tokens of a model, for the cost estimate')
    args = parser.parse_args(argv)
    prices = _parse_prices(args.price)

    if args.rescore:
        rescore(Path(args.rescore), prices)
        return None

    model_keys = [declared_models()[args.model]] if args.model else args.models
    check_models(model_keys, args.dry_run)
    out_dir = prepare_out_dir(args.out, HERE)
    cases = args.only or list(CASES)

    rows = []
    with transaction.atomic():              # everything is rolled back at the end
        for case in cases:
            user, activity = create_case(case)
            for model_key in model_keys:
                rows.extend(run_cell(case, model_key, args.n, out_dir, args.dry_run, user, activity))
        transaction.set_rollback(True)

    records = list(load_records(out_dir, sorted(p.name for p in out_dir.iterdir() if p.is_dir())))
    write_summary(out_dir, rows, title='Game Plan — récap',
                  models_used={variant_name(c, m): ai_config.PROVIDER_CONFIG[m]['model']
                               for c in cases for m in model_keys},
                  versions={str(k): v['versions'] for k, v in _OUTPUTS.items()}, recap=_recap(rows))
    report = write_report(out_dir, records, prices)
    print(f'Report: {report}')
    return out_dir


if __name__ == '__main__':
    main()
