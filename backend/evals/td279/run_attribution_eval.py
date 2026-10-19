#!/usr/bin/env python
"""
TD-279 — B2: measure, on the REAL LLM, how often a registered contact (P1)
is wrongly given another person's description.

Standalone evaluation script. NOT part of the product: it lives outside
app_modules/, nothing imports it, it writes nothing to the database. It
reuses the production code path for everything that matters:

  * prompt rendered by the real builders: build_context_layer +
    build_people_request / build_blocker_request + PromptBuilder.assemble
    (done inside BasePipeline._call_llm);
  * LLM call through QualificationSignalsPipeline._call_llm -- same active
    provider, model, temperature (PIPELINE_TEMPERATURES), max_tokens,
    timeout and one corrective parse retry as the pipeline.

Only the two DB lookups of the context layer are replaced by the test case
(tenant name, participant list): P1 = Criminelle Husky (Finance, no job
title), account Logistix.

Variants (N calls each, default 10):
  people_V0             people v4 / ctx v6, Logistix transcript
  people_V0_no_date     same, the "- Conversation date:" line removed
  people_WITNESS        V0 with a transcript where Criminelle Husky SPEAKS
  blocker_V0            blocker stage, Logistix transcript
  blocker_WITNESS       blocker stage, witness transcript

Output (one folder per run, see --out):
  <variant>/call_<NN>.json   rendered system + user prompt, raw response(s),
                             parsed JSON, metrics of the call
  summary.csv / summary.md   one row per call + the per-variant recap

Usage (from backend/, with the usual .env holding OPENAI_API_KEY):
  python evals/td279/run_attribution_eval.py                 # 5 x 10 calls
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
from app_modules.ai_pipelines.services.transcript_signal_extractor import (  # noqa: E402
    stated_name_matches_contact,
)


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
DATE_LINE_PREFIX = '- Conversation date:'

TRANSCRIPTS = {
    'logistix': HERE / 'transcript_logistix.txt',
    'witness': HERE / 'transcript_logistix_witness.txt',
}

# variant -> (stage, transcript key, drop the date line)
VARIANTS = {
    'people_V0':         ('people', 'logistix', False),
    'people_V0_no_date': ('people', 'logistix', True),
    'people_WITNESS':    ('people', 'witness', False),
    'blocker_V0':        ('blocker', 'logistix', False),
    'blocker_WITNESS':   ('blocker', 'witness', False),
}

REQUEST_BUILDERS = {
    'people': build_people_request,
    'blocker': build_blocker_request,
}


def _activity(tenant_name):
    """The activity of the case; the two DB lookups of the context layer are
    replaced (tenant name, participants) -- nothing is read from the DB."""
    ctx._resolve_tenant_name = lambda client_id: tenant_name
    ctx.ordered_participants = lambda activity: [CONTACT]
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


def _context(activity, stage, drop_date):
    context = ctx.build_context_layer(activity, target_stage=stage)
    if drop_date:
        lines = context.split('\n')
        kept = [line for line in lines if not line.startswith(DATE_LINE_PREFIX)]
        assert len(kept) == len(lines) - 1, 'Conversation date line not found'
        context = '\n'.join(kept)
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
                'participant_ref': 'P1', 'full_name': 'Isabelle Roux',
                'role': 'DECISION_MAKER', 'influence': 'HIGH',
                'department': 'Finance', 'notes': 'dry run',
                'source_quote': 'dry run', 'confidence': 0.9,
                'is_inferred': False,
            }]}
        else:
            content = {'signals': [{'raised_by': 'P1', 'source_quote': 'dry run'}]}
        return LLMCallResult(
            content=json.dumps(content), input_tokens=0, output_tokens=0,
            model_used='dry-run', duration_ms=0,
        )


# =============================================================================
# METRICS
# =============================================================================

def _name_class(full_name):
    if not isinstance(full_name, str) or not full_name.strip():
        return 'null'
    if stated_name_matches_contact(full_name, CONTACT):
        return 'Criminelle'
    if 'isabelle' in full_name.lower():
        return 'Isabelle Roux'
    return f'other: {full_name}'


def _criminelle_lines(transcript):
    return [line for line in transcript.splitlines() if line.startswith('Criminelle Husky:')]


def _people_metrics(signals, transcript):
    p1 = [s for s in signals if s.get('participant_ref') == 'P1']
    # Isabelle Roux as her OWN entry (not on P1).
    isabelle = any(
        s.get('participant_ref') != 'P1' and 'isabelle' in (s.get('full_name') or '').lower()
        for s in signals
    )
    first = p1[0] if p1 else {}
    name_class = _name_class(first.get('full_name')) if p1 else ''
    quote = first.get('source_quote') or ''
    return {
        'total_entries': len(signals),
        'p1_entries': len(p1),
        'p1_full_name': first.get('full_name') if p1 else '',
        'p1_name_class': name_class,
        'p1_role': first.get('role') if p1 else '',
        'p1_quote': quote,
        'p1_quote_about_isabelle': bool(p1) and 'isabelle' in quote.lower(),
        # The P1 quote is (part of) a line Criminelle Husky SAYS (witness only).
        'p1_quote_said_by_criminelle': bool(p1) and bool(quote.strip()) and any(
            quote.strip() in line for line in _criminelle_lines(transcript)
        ),
        # Would the B1 guard (b92b571) detach this P1? (name given and not the contact)
        'b1_detaches_p1': bool(p1) and name_class not in ('null', 'Criminelle'),
        'isabelle_present': isabelle,
    }


def _blocker_metrics(signals):
    return {
        'total_entries': len(signals),
        'raised_by_p1': sum(1 for s in signals if s.get('raised_by') == 'P1'),
        'raised_by_null': sum(1 for s in signals if s.get('raised_by') is None),
    }


def _signals(parsed):
    if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
        return [s for s in parsed['signals'] if isinstance(s, dict)]
    return []


# =============================================================================
# RUN
# =============================================================================

def run_variant(name, n, out_dir, provider, activity):
    stage, transcript_key, drop_date = VARIANTS[name]
    transcript = TRANSCRIPTS[transcript_key].read_text(encoding='utf-8')
    context = _context(activity, stage, drop_date)
    request = REQUEST_BUILDERS[stage](transcript)
    variant_dir = out_dir / name
    variant_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for index in range(1, n + 1):
        recorder = RecordingProvider(provider)
        pipeline = QualificationSignalsPipeline(provider=recorder)
        record = {'variant': name, 'call': index, 'stage': stage,
                  'transcript': transcript_key, 'date_line_removed': drop_date,
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
        metrics = _people_metrics(signals, transcript) if stage == 'people' else _blocker_metrics(signals)
        record['metrics'] = metrics
        (variant_dir / f'call_{index:02d}.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        rows.append({'variant': name, 'call': index, 'error': record['error'] or '', **metrics})
        print(f'{name} #{index}: {metrics}', flush=True)
    return rows


def _recap(rows):
    lines = []
    for name in VARIANTS:
        vrows = [r for r in rows if r['variant'] == name]
        if not vrows:
            continue
        n = len(vrows)
        errors = sum(1 for r in vrows if r['error'])
        if name.startswith('people'):
            p1 = sum(1 for r in vrows if r['p1_entries'])
            classes = {}
            for r in vrows:
                if r['p1_entries']:
                    classes[r['p1_name_class']] = classes.get(r['p1_name_class'], 0) + 1
            isa_quote = sum(1 for r in vrows if r['p1_quote_about_isabelle'])
            own_quote = sum(1 for r in vrows if r['p1_quote_said_by_criminelle'])
            b1 = sum(1 for r in vrows if r['b1_detaches_p1'])
            isabelle = sum(1 for r in vrows if r['isabelle_present'])
            totals = [r['total_entries'] for r in vrows]
            lines.append(
                f'| {name} | P1 émis {p1}/{n} | noms sur P1 {classes or "-"} | '
                f'citation P1 sur Isabelle {isa_quote}/{n} | citation P1 dite par Criminelle {own_quote}/{n} | B1 détache {b1}/{n} | '
                f'Isabelle (entrée propre) {isabelle}/{n} | entrées {min(totals)}-{max(totals)} | '
                f'erreurs {errors} |'
            )
        else:
            p1 = sum(r['raised_by_p1'] for r in vrows)
            total = sum(r['total_entries'] for r in vrows)
            lines.append(
                f'| {name} | raised_by=P1 {p1}/{total} blockers '
                f'(par appel : {[r["raised_by_p1"] for r in vrows]} sur '
                f'{[r["total_entries"] for r in vrows]}) | erreurs {errors} |'
            )
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
    # Never overwrite a previous run (the B2 reference outputs are kept).
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
        '# TD-279 B2 — récap\n\n'
        f'Versions : {json.dumps(QualificationSignalsPipeline.PROMPT_VERSIONS)}\n\n'
        + '\n'.join(recap) + '\n', encoding='utf-8',
    )
    print('\n'.join(recap))
    print(f'\nOutput: {out_dir}')


if __name__ == '__main__':
    main()
