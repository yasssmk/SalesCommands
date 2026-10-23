# backend/evals/common/eval_kit.py
"""
Shared plumbing of the evaluation scripts under backend/evals/ (td279,
next_steps). NOT product code: nothing in app_modules/ imports it.

One implementation, imported by every script (no diverging copies):

  * RecordingProvider    — wraps the real provider, keeps every prompt sent
                           and every RAW answer (always recorded);
  * error_type           — the kind of a failed call, for the recap;
  * declared_models      — the --model choices: only the models declared in
                           ai_pipelines/config.py PROVIDER_CONFIG;
  * add_common_arguments — --n / --only / --out / --tenant-name / --dry-run /
                           --rescore / --model;
  * prepare_out_dir      — a run never overwrites a previous one;
  * run_calls            — the N-calls loop: call, time, catch, record
                           <variant>/call_NN.json, score;
  * load_records         — the recorded calls of a run folder (--rescore);
  * row / count / timing_line / write_summary — the summary.csv / .md.

Django must be set up by the calling script before it imports this module.
"""

import csv
import datetime
import json
import sys
import time
from pathlib import Path


# =============================================================================
# PROVIDER
# =============================================================================

class RecordingProvider:
    """Wraps the real provider; keeps every prompt sent and raw answer — a
    call that raises (timeout, provider error) is kept too, with its error,
    then the exception goes on."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def call(self, **kwargs):
        sent = {
            'system': kwargs.get('system'),
            'user': kwargs.get('user'),
            'model': kwargs.get('model'),
            'temperature': kwargs.get('temperature'),
            'max_tokens': kwargs.get('max_tokens'),
            'reasoning_effort': kwargs.get('reasoning_effort'),
            'response_schema': (kwargs.get('response_schema') or {}).get('name'),
        }
        try:
            result = self.inner.call(**kwargs)
        except Exception as exc:
            self.calls.append({**sent, 'raw_response': None,
                               'error': f'{type(exc).__name__}: {exc}'})
            raise
        self.calls.append({
            **sent,
            'raw_response': result.content,
            'model_used': result.model_used,
            'input_tokens': result.input_tokens,
            'output_tokens': result.output_tokens,
        })
        return result


def error_type(exc):
    """The kind of a failed call, for the recap (messages of providers/)."""
    from app_modules.ai_pipelines.prompts.base import PromptParseError
    from app_modules.ai_pipelines.providers.base import (
        LLMProviderError,
        LLMTimeoutError,
    )

    if isinstance(exc, LLMTimeoutError):
        return 'timeout'
    if isinstance(exc, PromptParseError):
        return 'parsing'
    if isinstance(exc, LLMProviderError):
        if 'truncated' in str(exc):
            return 'troncature'
        if 'refused' in str(exc):
            return 'refus'
        return 'provider'
    return type(exc).__name__


def declared_models():
    """--model choices: ONLY the models declared in the repo config (never
    invented) -> PROVIDER_CONFIG key. A model declared by several entries
    maps to the FIRST one (gpt-5.6-terra -> openai_people, as before
    openai_next_steps existed); a script may prefer its own entry."""
    from app_modules.ai_pipelines import config as ai_config
    models = {}
    for key, cfg in ai_config.PROVIDER_CONFIG.items():
        models.setdefault(cfg['model'], key)
    return models


# =============================================================================
# CLI + OUTPUT FOLDER
# =============================================================================

def add_common_arguments(parser, variants, models, model_help):
    parser.add_argument('--n', type=int, default=10, help='calls per variant')
    parser.add_argument('--only', nargs='*', choices=list(variants), help='subset of variants')
    parser.add_argument('--out', default=None, help='output folder')
    parser.add_argument('--tenant-name', default='SalesCommands')
    parser.add_argument('--dry-run', action='store_true', help='no API call')
    parser.add_argument(
        '--rescore', metavar='OUT_DIR', default=None,
        help='recompute the summary of an existing run folder from its recorded '
             'raw answers (no API call); writes summary_rescored.csv / .md',
    )
    parser.add_argument('--model', choices=sorted(models), help=model_help)


def prepare_out_dir(out_arg, here):
    """The run folder: --out, else <here>/out/<stamp>. A non-empty folder is
    refused — the earlier reference outputs are kept."""
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out_dir = Path(out_arg) if out_arg else here / 'out' / stamp
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(f'Output folder {out_dir} is not empty -- choose another --out.')
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


# =============================================================================
# THE N-CALLS LOOP
# =============================================================================

def run_calls(*, name, n, variant_dir, base_record, make_recorder, make_call,
              score, failure_extra=None):
    """
    Run `make_call` N times and record each call in
    <variant_dir>/call_NN.json — raw answers ALWAYS kept.

    make_call(recorder) -> (parsed, meta, extra): extra keys are added to the
    record (e.g. the persisted rows); on an exception the call is recorded as
    an error, with `failure_extra` as its extra keys. score(record) -> the
    metrics of the call, from the record only (shared with --rescore).
    Returns the summary rows.
    """
    variant_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(1, n + 1):
        recorder = make_recorder()
        record = {'variant': name, 'call': index, **base_record}
        started = time.monotonic()
        try:
            parsed, meta, extra = make_call(recorder)
            record['meta'] = meta
            record['error'] = None
            record['error_type'] = None
        except Exception as exc:  # parse failure twice, provider error
            parsed, extra = None, dict(failure_extra or {})
            record['error'] = f'{type(exc).__name__}: {exc}'
            record['error_type'] = error_type(exc)
        record['wall_ms'] = int((time.monotonic() - started) * 1000)
        record['attempts'] = recorder.calls
        record['parsed'] = parsed
        record.update(extra)
        metrics = score(record)
        record['metrics'] = metrics
        (variant_dir / f'call_{index:02d}.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        rows.append(row(record, metrics))
        print(f'{name} #{index}: {metrics}', flush=True)
    return rows


def load_records(out_dir, variants):
    """The recorded calls of a run folder, variant by variant (--rescore)."""
    for name in variants:
        for path in sorted((out_dir / name).glob('call_*.json')):
            yield json.loads(path.read_text(encoding='utf-8'))


# =============================================================================
# SUMMARY
# =============================================================================

def row(record, metrics):
    """The summary row of a call (older records: missing keys -> empty)."""
    return {'variant': record['variant'], 'call': record['call'],
            'error': record.get('error') or '', 'error_type': record.get('error_type') or '',
            'duration_ms': (record.get('meta') or {}).get('duration_ms'),
            'wall_ms': record.get('wall_ms'), **metrics}


def count(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def timing_line(name, vrows):
    durations = [r['duration_ms'] for r in vrows if r['duration_ms'] is not None]
    mean = round(sum(durations) / len(durations)) if durations else '-'
    longest = max(durations) if durations else '-'
    errors = count(r['error_type'] for r in vrows if r['error_type'])
    walls = [r['wall_ms'] for r in vrows if r['wall_ms'] is not None]
    return (f'| {name} | {len(vrows)} | {mean} | {longest} | '
            f'{max(walls) if walls else "-"} | {errors or "-"} |')


def write_summary(out_dir, rows, *, title, models_used, versions, recap, suffix=''):
    """summary<suffix>.csv (one row per call) + summary<suffix>.md (the
    recap lines built by the script)."""
    fields = sorted({key for r in rows for key in r}, key=lambda k: (k not in ('variant', 'call'), k))
    with open(out_dir / f'summary{suffix}.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / f'summary{suffix}.md').write_text(
        f'# {title}\n\n'
        f'Modèle par variante : {json.dumps(models_used)}\n\n'
        f'Versions : {json.dumps(versions)}\n\n'
        + '\n'.join(recap) + '\n', encoding='utf-8',
    )
    print('\n'.join(recap))
    print(f'\nOutput: {out_dir}')
