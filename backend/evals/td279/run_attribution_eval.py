#!/usr/bin/env python
"""
TD-279 — measure, on the REAL LLM, whether a registered contact is wrongly
given another person's description (People) or another speaker's blocker.

Standalone evaluation script. NOT part of the product: it lives outside
app_modules/, nothing imports it, it writes nothing to the database. It
reuses the production code path for everything that matters:

  * prompt rendered by the real builders: build_context_layer +
    build_people_request / build_blocker_request + PromptBuilder.assemble
    (done inside BasePipeline._call_llm) -- no patch: since B4b the
    production prompts ARE the validated "no P reference" track (no contact
    list in the context, names as written);
  * LLM call through QualificationSignalsPipeline._call_llm -- same active
    provider, model, temperature (PIPELINE_TEMPERATURES), max_tokens,
    timeout and one corrective parse retry as the pipeline;
  * contact link through the real server helper resolve_participant_by_name
    (People full_name, Blocker raised_by_name).

Only DB lookups are replaced by the test case: the tenant name, and the
contacts registered on the activity (Criminelle Husky, Finance), account
Logistix.

Variants (N calls each, default 10):
  people_V0         Logistix transcript (Criminelle registered, never speaks)
  people_WITNESS    same, with a transcript where Criminelle Husky SPEAKS
  blocker_V0        blocker stage, Logistix transcript
  blocker_WITNESS   blocker stage, witness transcript

Each call is scored on the FINAL result a run would store (link by name).

Output (one folder per run, see --out; a non-empty folder is refused):
  <variant>/call_<NN>.json   rendered system + user prompt, raw response(s),
                             parsed JSON, metrics of the call
  summary.csv / summary.md   one row per call + the per-variant recap

Usage (from backend/, with the usual .env holding OPENAI_API_KEY):
  python evals/td279/run_attribution_eval.py                 # 4 x 10 calls
  python evals/td279/run_attribution_eval.py --n 3 --only people_V0
  python evals/td279/run_attribution_eval.py --dry-run       # no API call
"""

import argparse
import csv
import datetime
import json
import os
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salescommands.settings')

import django  # noqa: E402

django.setup()

from app_modules.ai_pipelines.pipelines.transcript_signals import (  # noqa: E402
    QualificationSignalsPipeline,
)
from app_modules.ai_pipelines.prompts.transcript_signals import context as ctx  # noqa: E402
from app_modules.ai_pipelines.prompts.transcript_signals.blocker_v1 import (  # noqa: E402
    build_blocker_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (  # noqa: E402
    build_people_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.system import (  # noqa: E402
    SYSTEM_PROMPT,
)
from app_modules.ai_pipelines.providers import get_active_provider  # noqa: E402
from app_modules.ai_pipelines.providers.base import LLMCallResult  # noqa: E402
from app_modules.ai_pipelines.services import participant_refs  # noqa: E402


# =============================================================================
# TEST CASE (TD-279 smoke, activity 5b53de3d)
# =============================================================================

CONTACT = types.SimpleNamespace(
    first_name='Criminelle',
    last_name='Husky',
    job_title='',
    standard_department=types.SimpleNamespace(
        get_name_display=lambda: 'Finance', name='Finance',
    ),
)
CONVERSATION_DATE = '2026-10-14'

TRANSCRIPTS = {
    'logistix': HERE / 'transcript_logistix.txt',
    'witness': HERE / 'transcript_logistix_witness.txt',
}

# Speaker labels of the transcripts (the seller is Julien Moreau).
SPEAKERS = {
    'Claire': 'Claire Dubois',
    'Thomas': 'Thomas Lefèvre',
    'Criminelle': 'Criminelle Husky',
    'Julien (seller)': 'Julien Moreau',
}

# variant -> (stage, transcript key)
VARIANTS = {
    'people_V0':       ('people', 'logistix'),
    'people_WITNESS':  ('people', 'witness'),
    'blocker_V0':      ('blocker', 'logistix'),
    'blocker_WITNESS': ('blocker', 'witness'),
}

REQUEST_BUILDERS = {
    'people': build_people_request,
    'blocker': build_blocker_request,
}


def _activity(tenant_name):
    """The activity of the case; the DB lookups are replaced (tenant name,
    registered contacts) -- nothing is read from the DB."""
    ctx._resolve_tenant_name = lambda client_id: tenant_name
    participant_refs.ordered_participants = lambda activity: [CONTACT]
    return types.SimpleNamespace(
        client_id='eval',
        account=types.SimpleNamespace(
            company_name='Logistix', industry=None, classification=None,
        ),
        get_activity_type_display=lambda: 'Meeting',
        completed_at=datetime.datetime.fromisoformat(f'{CONVERSATION_DATE}T10:02:00'),
        scheduled_date=None,
        decision_cycle_id=None,
    )


def _context(activity, stage):
    context = ctx.build_context_layer(activity, target_stage=stage)
    # Context v8: the registered contacts are never sent to the LLM.
    assert 'Criminelle' not in context
    return context


# =============================================================================
# PROVIDERS
# =============================================================================

class RecordingProvider:
    """Wraps the real provider; keeps every prompt sent and raw answer."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def call(self, **kwargs):
        result = self.inner.call(**kwargs)
        self.calls.append({
            'system': kwargs.get('system'),
            'user': kwargs.get('user'),
            'model': kwargs.get('model'),
            'temperature': kwargs.get('temperature'),
            'max_tokens': kwargs.get('max_tokens'),
            'raw_response': result.content,
            'model_used': result.model_used,
            'input_tokens': result.input_tokens,
            'output_tokens': result.output_tokens,
        })
        return result


class DryRunProvider:
    """--dry-run: no API call, a fixed answer, to check the plumbing."""

    def call(self, **kwargs):
        if 'Extract PEOPLE signals' in kwargs['user']:
            content = {'signals': [{
                'full_name': 'Claire Dubois', 'role': 'CHAMPION', 'influence': 'HIGH',
                'department': 'Sales', 'notes': 'dry run',
                'source_quote': "honnêtement c'est moi qui ai poussé pour qu'on regarde votre solution",
                'confidence': 0.9, 'is_inferred': False,
            }]}
        else:
            content = {'signals': [{'raised_by_name': 'Thomas Lefèvre', 'source_quote': 'dry run'}]}
        return LLMCallResult(
            content=json.dumps(content), input_tokens=0, output_tokens=0,
            model_used='dry-run', duration_ms=0,
        )


# =============================================================================
# METRICS
# =============================================================================

def _norm(text):
    """Lowercase, whitespace collapsed, surrounding quotes / ellipsis dropped."""
    text = ' '.join(str(text or '').lower().split())
    return text.strip(' "\'«»“”.…')


def _speaker_lines(transcript, speaker):
    prefix = f'{speaker}:'
    return [_norm(line[len(prefix):]) for line in transcript.splitlines() if line.startswith(prefix)]


def _said_by(quote, transcript, speaker):
    """The quote is (a case-insensitive substring of) a line of `speaker`."""
    quote = _norm(quote)
    return bool(quote) and any(quote in line for line in _speaker_lines(transcript, speaker))


def _who(name):
    """Speaker key for a name as returned by the LLM (or 'null' / 'other')."""
    if not isinstance(name, str) or not name.strip():
        return 'null'
    for key, full in SPEAKERS.items():
        first, last = full.split()
        speaker = types.SimpleNamespace(first_name=first, last_name=last)
        if participant_refs.stated_name_matches_contact(name, speaker):
            return key
    return f'other: {name}'


def _linked(name, activity):
    """The server link of the stored result (real helper)."""
    return participant_refs.resolve_participant_by_name(name, activity) is CONTACT


def _people_metrics(signals, transcript, activity):
    linked = [s for s in signals if _linked(s.get('full_name'), activity)]
    claire = [s for s in signals if _who(s.get('full_name')) == 'Claire']
    first_claire = claire[0] if claire else {}
    claire_quote = first_claire.get('source_quote') or ''
    quote_low = claire_quote.lower()
    if not claire:
        claire_verdict = 'absente'
    elif 'marc' in quote_low or 'isabelle' in quote_low:
        claire_verdict = 'FAUX (citation Marc/Isabelle)'
    elif _said_by(claire_quote, transcript, SPEAKERS['Claire']):
        claire_verdict = 'juste (sa propre phrase)'
    else:
        claire_verdict = 'autre'
    return {
        'total_entries': len(signals),
        'linked_to_criminelle': len(linked),
        'linked_quote_said_by_criminelle': sum(
            1 for s in linked if _said_by(s.get('source_quote'), transcript, SPEAKERS['Criminelle'])
        ),
        # Isabelle's description on Criminelle (her own line naming Isabelle
        # -- "les chiffres ... pour Isabelle" -- is not counted).
        'linked_quote_about_isabelle': sum(
            1 for s in linked
            if 'isabelle' in (s.get('source_quote') or '').lower()
            and not _said_by(s.get('source_quote'), transcript, SPEAKERS['Criminelle'])
        ),
        'claire_role': first_claire.get('role') or '',
        'claire_quote': claire_quote,
        'claire_verdict': claire_verdict,
        'isabelle_present': any(
            'isabelle' in (s.get('full_name') or '').lower() and not _linked(s.get('full_name'), activity)
            for s in signals
        ),
        'seller_entries': sum(1 for s in signals if _who(s.get('full_name')) == 'Julien (seller)'),
    }


def _blocker_metrics(signals, activity):
    distribution = {}
    for s in signals:
        name = _who(s.get('raised_by_name'))
        distribution[name] = distribution.get(name, 0) + 1
    return {
        'total_entries': len(signals),
        'raised_by_distribution': json.dumps(distribution, ensure_ascii=False),
        'linked_to_criminelle': sum(1 for s in signals if _linked(s.get('raised_by_name'), activity)),
    }


def _signals(parsed):
    if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
        return [s for s in parsed['signals'] if isinstance(s, dict)]
    return []


# =============================================================================
# RUN
# =============================================================================

def run_variant(name, n, out_dir, provider, activity):
    stage, transcript_key = VARIANTS[name]
    transcript = TRANSCRIPTS[transcript_key].read_text(encoding='utf-8')
    context = _context(activity, stage)
    request = REQUEST_BUILDERS[stage](transcript)
    variant_dir = out_dir / name
    variant_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for index in range(1, n + 1):
        recorder = RecordingProvider(provider)
        pipeline = QualificationSignalsPipeline(provider=recorder)
        record = {'variant': name, 'call': index, 'stage': stage,
                  'transcript': transcript_key,
                  'prompt_versions': dict(QualificationSignalsPipeline.PROMPT_VERSIONS)}
        try:
            parsed, meta = pipeline._call_llm(
                system_prompt=SYSTEM_PROMPT, context=context, request=request,
            )
            record['meta'] = meta
            record['error'] = None
        except Exception as exc:  # parse failure twice, provider error
            parsed = None
            record['error'] = f'{type(exc).__name__}: {exc}'
        record['attempts'] = recorder.calls
        record['parsed'] = parsed
        signals = _signals(parsed)
        if stage == 'people':
            metrics = _people_metrics(signals, transcript, activity)
        else:
            metrics = _blocker_metrics(signals, activity)
        record['metrics'] = metrics
        (variant_dir / f'call_{index:02d}.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        rows.append({'variant': name, 'call': index, 'error': record['error'] or '', **metrics})
        print(f'{name} #{index}: {metrics}', flush=True)
    return rows


def _count(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _recap(rows):
    people, blockers = [], []
    for name in VARIANTS:
        vrows = [r for r in rows if r['variant'] == name]
        if not vrows:
            continue
        n = len(vrows)
        errors = sum(1 for r in vrows if r['error'])
        if VARIANTS[name][0] == 'people':
            totals = [r['total_entries'] for r in vrows]
            people.append(
                f'| {name} | '
                f'{sum(1 for r in vrows if r["linked_to_criminelle"])}/{n} | '
                f'{sum(1 for r in vrows if r["linked_quote_said_by_criminelle"])}/{n} | '
                f'{sum(1 for r in vrows if r["linked_quote_about_isabelle"])}/{n} | '
                f'{_count(r["claire_verdict"] for r in vrows)} | '
                f'{_count(r["claire_role"] or "-" for r in vrows)} | '
                f'{sum(1 for r in vrows if r["isabelle_present"])}/{n} | '
                f'{sum(1 for r in vrows if r["seller_entries"])}/{n} | '
                f'{min(totals)}-{max(totals)} | {errors} |'
            )
        else:
            distribution = {}
            for r in vrows:
                for key, value in json.loads(r['raised_by_distribution']).items():
                    distribution[key] = distribution.get(key, 0) + value
            blockers.append(
                f'| {name} | {sum(r["total_entries"] for r in vrows)} | '
                f'{sum(r["linked_to_criminelle"] for r in vrows)} | '
                f'{distribution} | {errors} |'
            )
    lines = []
    if people:
        lines += [
            '## People (appels avec ... / N)',
            '',
            '| variante | rattaché à Criminelle (final) | '
            'dont citation dite par Criminelle | dont citation sur Isabelle | '
            'entrée Claire | rôle Claire | Isabelle (entrée propre) | '
            'entrée vendeur | entrées | erreurs |',
            '|---|---|---|---|---|---|---|---|---|---|',
            *people, '',
        ]
    if blockers:
        lines += [
            '## Blocker (total des appels)',
            '',
            '| variante | blockers | rattachés à Criminelle (final) | raised_by_name | erreurs |',
            '|---|---|---|---|---|',
            *blockers, '',
        ]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--n', type=int, default=10, help='calls per variant')
    parser.add_argument('--only', nargs='*', choices=list(VARIANTS), help='subset of variants')
    parser.add_argument('--out', default=None, help='output folder')
    parser.add_argument('--tenant-name', default='SalesCommands')
    parser.add_argument('--dry-run', action='store_true', help='no API call')
    args = parser.parse_args()

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = Path(args.out) if args.out else HERE / 'out' / stamp
    # Never overwrite a previous run (the earlier reference outputs are kept).
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(f'Output folder {out_dir} is not empty -- choose another --out.')
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = DryRunProvider() if args.dry_run else get_active_provider()
    activity = _activity(args.tenant_name)

    rows = []
    for name in args.only or list(VARIANTS):
        rows.extend(run_variant(name, args.n, out_dir, provider, activity))

    fields = sorted({key for row in rows for key in row}, key=lambda k: (k not in ('variant', 'call'), k))
    with open(out_dir / 'summary.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    recap = _recap(rows)
    (out_dir / 'summary.md').write_text(
        '# TD-279 — récap\n\n'
        f'Versions : {json.dumps(QualificationSignalsPipeline.PROMPT_VERSIONS)}\n\n'
        + '\n'.join(recap) + '\n', encoding='utf-8',
    )
    print('\n'.join(recap))
    print(f'\nOutput: {out_dir}')


if __name__ == '__main__':
    main()
