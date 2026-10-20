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
  atelier_people / atelier_pain_impact / atelier_objective /
  atelier_techstack / atelier_blocker
                    "Atelier business case" transcript (PO smoke 2026-10-20,
                    activity 0254973b; Conversation date 2026-10-20): the
                    expected items are checked one by one, on the RAW answer
                    and after the server safety filter (same thresholds as
                    the pipeline) -- people: Isabelle, Thomas (role, not
                    DECISION_MAKER), the cost controller (Finance), Laurent,
                    Nadia, Marc, Karim, no seller entry; pain_impact: the
                    "80 h / 2 FTE" impact and the 18 % impact, each with a
                    metric_text; objective: target_date 2027-03-31; blocker:
                    adoption risk, hosting -> "will block" threat.
                    All variants run on the PRODUCTION prompts.

The Logistix variants are scored on the FINAL result a run would store (link
by name).

Output (one folder per run, see --out; a non-empty folder is refused):
  <variant>/call_<NN>.json   rendered system + user prompt, raw response(s),
                             parsed JSON, metrics of the call
  summary.csv / summary.md   one row per call + the per-variant recap

Usage (from backend/, with the usual .env holding OPENAI_API_KEY):
  python evals/td279/run_attribution_eval.py                 # 9 x 10 calls
  python evals/td279/run_attribution_eval.py --only atelier_people atelier_pain_impact \
      atelier_objective atelier_techstack atelier_blocker   # the atelier audit
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
from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (  # noqa: E402
    build_objective_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (  # noqa: E402
    build_pain_impact_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (  # noqa: E402
    build_people_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (  # noqa: E402
    build_techstack_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.system import (  # noqa: E402
    SYSTEM_PROMPT,
)
from app_modules.ai_pipelines.providers import get_active_provider  # noqa: E402
from app_modules.ai_pipelines.providers.base import LLMCallResult  # noqa: E402
from app_modules.ai_pipelines.services import participant_refs  # noqa: E402
from app_modules.ai_pipelines.services.safety_filter import passes_safety_filter  # noqa: E402
from app_modules.ai_pipelines.services.transcript_signal_extractor import _iso_date  # noqa: E402
from app_modules.core_modules.models import StandardDepartment  # noqa: E402


# =============================================================================
# TEST CASE (TD-279 smoke, activity 5b53de3d)
# =============================================================================

DEPARTMENTS = StandardDepartment.DepartmentChoices.values
FINANCE = StandardDepartment.DepartmentChoices.FINANCE.value

CONTACT = types.SimpleNamespace(
    first_name='Criminelle',
    last_name='Husky',
    job_title='',
    standard_department=types.SimpleNamespace(
        get_name_display=lambda: 'Finance', name='Finance',
    ),
)
TRANSCRIPTS = {
    'logistix': HERE / 'transcript_logistix.txt',
    'witness': HERE / 'transcript_logistix_witness.txt',
    'atelier': HERE / 'transcript_atelier.txt',
}

# The activity date sent as "Conversation date" (completed_at of the case).
CONVERSATION_DATES = {
    'logistix': '2026-10-14',
    'witness': '2026-10-14',
    'atelier': '2026-10-20',
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
    'people_V0':           ('people', 'logistix'),
    'people_WITNESS':      ('people', 'witness'),
    'blocker_V0':          ('blocker', 'logistix'),
    'blocker_WITNESS':     ('blocker', 'witness'),
    'atelier_people':      ('people', 'atelier'),
    'atelier_pain_impact': ('pain_impact', 'atelier'),
    'atelier_objective':   ('objective', 'atelier'),
    'atelier_techstack':   ('techstack', 'atelier'),
    'atelier_blocker':     ('blocker', 'atelier'),
}

REQUEST_BUILDERS = {
    'people': build_people_request,
    'blocker': build_blocker_request,
    'pain_impact': build_pain_impact_request,
    'objective': build_objective_request,
    'techstack': build_techstack_request,
}


def _activity(tenant_name, conversation_date):
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
        completed_at=datetime.datetime.fromisoformat(f'{conversation_date}T10:02:00'),
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
    """--dry-run: no API call, a fixed answer per stage, to check the plumbing."""

    def call(self, **kwargs):
        user = kwargs['user']
        base = {'confidence': 0.9, 'is_inferred': False, 'summary': 'dry run'}
        if 'Extract PEOPLE signals' in user:
            content = {'signals': [{
                'full_name': 'Claire Dubois', 'role': 'CHAMPION', 'influence': 'HIGH',
                'department': 'Sales', 'notes': 'dry run',
                'source_quote': "honnêtement c'est moi qui ai poussé pour qu'on regarde votre solution",
                'confidence': 0.9, 'is_inferred': False,
            }]}
        elif 'Extract PAIN and IMPACT signals' in user:
            content = {'pains': [], 'impacts': [{
                **base, 'what': 'OPS', 'dimension': 'TIME', 'impact_type': 'TIME',
                'source_quote': 'ça fait quatre-vingts heures par semaine',
            }]}
        elif 'Extract OBJECTIVE signals' in user:
            content = {'signals': [{
                **base, 'what': 'OPS', 'dimension': 'TIME',
                'source_quote': 'Diviser par deux le temps de saisie',
            }]}
        elif 'Extract TECH STACK signals' in user:
            content = {'signals': [{
                **base, 'tech_name': 'Zendesk', 'is_discontinued': True,
                'discontinued_date': None, 'source_quote': 'on a arrêté Zendesk en juin dernier',
            }]}
        else:
            content = {'signals': [{**base, 'raised_by_name': 'Thomas Lefèvre',
                                    'source_quote': "Si les commerciaux ne l'utilisent pas"}]}
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


# --- Atelier business case (PO smoke 2026-10-20) -------------------------------

def _survives(raw, stage):
    """The server safety filter of the pipeline, same thresholds (constants;
    one policy for every stage since TD-279 C1 -- `stage` kept for the call
    sites)."""
    return passes_safety_filter(
        raw, QualificationSignalsPipeline.CONFIDENCE_MIN, QualificationSignalsPipeline.DROP_INFERRED,
    )


def _text(raw, *keys):
    return ' '.join(str(raw.get(key) or '') for key in keys).lower()


def _first(signals, predicate):
    return next((s for s in signals if predicate(s)), None)


def _found(prefix, raw, stage):
    """<prefix>_emitted / <prefix>_survives_filter / <prefix>_inferred for one item."""
    return {
        f'{prefix}_emitted': raw is not None,
        f'{prefix}_survives_filter': raw is not None and _survives(raw, stage),
        f'{prefix}_inferred': bool(raw and raw.get('is_inferred') is True),
    }


def _atelier_metrics(stage, parsed):
    m = {}
    if stage == 'people':
        signals = _signals(parsed)
        name = lambda s: (s.get('full_name') or '').lower()  # noqa: E731
        named = lambda *keys: _first(signals, lambda s: any(k in name(s) for k in keys))  # noqa: E731
        for key, words in (('isabelle', ('isabelle', 'roux')), ('laurent', ('laurent', 'petit')),
                           ('nadia', ('nadia', 'benali')), ('marc', ('marc',)), ('karim', ('karim',))):
            m.update(_found(key, named(*words), stage))
        thomas = named('thomas', 'lefèvre', 'lefevre')
        m.update(_found('thomas', thomas, stage))
        m['thomas_role'] = (thomas or {}).get('role') or ''
        m['thomas_not_decision_maker'] = bool(thomas) and thomas.get('role') != 'DECISION_MAKER'
        controleur = _first(signals, lambda s: 'contr' in _text(s, 'full_name', 'notes', 'source_quote')
                            and 'gestion' in _text(s, 'full_name', 'notes', 'source_quote'))
        m.update(_found('controleur', controleur, stage))
        department = ((controleur or {}).get('department') or '').strip()
        m['controleur_department'] = department
        m['controleur_department_finance'] = department.lower() == FINANCE.lower()
        # Server identity rule (_build_people_data): no contact, no name and no
        # resolvable department -> dropped. Approximated without the DB: exact
        # StandardDepartment value (the server also accepts an unambiguous word).
        m['controleur_has_identity'] = bool(controleur) and bool(
            (controleur.get('full_name') or '').strip()
            or department.lower() in {v.lower() for v in DEPARTMENTS}
        )
        m['seller_entries'] = sum(1 for s in signals if _who(s.get('full_name')) == 'Julien (seller)'
                                  or 'sophie' in name(s) or 'garnier' in name(s))
        m['roles'] = '; '.join(f"{s.get('full_name')}={s.get('role')}" for s in signals)
        m['names'] = '; '.join(str(s.get('full_name')) for s in signals)
        m['total_entries'] = len(signals)
    elif stage == 'pain_impact':
        pains = parsed.get('pains') if isinstance(parsed, dict) and isinstance(parsed.get('pains'), list) else []
        impacts = parsed.get('impacts') if isinstance(parsed, dict) and isinstance(parsed.get('impacts'), list) else []
        etp = lambda s: any(k in _text(s, 'source_quote') for k in ('quatre-vingts', 'temps plein', '80'))  # noqa: E731
        i2 = _first(impacts, etp)
        m.update(_found('impact_2etp', i2, 'impact'))
        m['impact_2etp_metric_text'] = bool(i2 and str(i2.get('metric_text') or '').strip())
        m['impact_2etp_metric_text_value'] = str((i2 or {}).get('metric_text') or '')
        m['etp_in_pains_instead'] = _first(pains, etp) is not None
        i18 = _first(impacts, lambda s: 'dix-huit' in _text(s, 'source_quote') or '18' in _text(s, 'source_quote'))
        m.update(_found('impact_18', i18, 'impact'))
        m['impact_18_metric_text'] = bool(i18 and str(i18.get('metric_text') or '').strip())
        m['impact_18_metric_text_value'] = str((i18 or {}).get('metric_text') or '')
        m['total_pains'] = len(pains)
        m['total_impacts'] = len(impacts)
    elif stage == 'objective':
        signals = _signals(parsed)
        obj = _first(signals, lambda s: 'diviser par deux' in _text(s, 'source_quote', 'summary')
                     or 'temps de saisie' in _text(s, 'source_quote', 'summary'))
        m.update(_found('objective_halve', obj, stage))
        m['objective_target_date_in_raw'] = (obj or {}).get('target_date') or ''
        m['objective_target_date_2027_03_31'] = (obj or {}).get('target_date') == '2027-03-31'
        m['total_entries'] = len(signals)
    elif stage == 'techstack':
        signals = _signals(parsed)
        zd = _first(signals, lambda s: 'zendesk' in _text(s, 'tech_name'))
        m.update(_found('zendesk', zd, stage))
        date = _iso_date((zd or {}).get('discontinued_date'))
        m['zendesk_discontinued_raw'] = bool(zd and zd.get('is_discontinued'))
        m['zendesk_discontinued_date'] = date.isoformat() if date else ''
        m['zendesk_date_june_2026'] = bool(date and date.year == 2026 and date.month == 6)
        # Server rule D2: discontinued without a valid date -> NOT discontinued.
        m['zendesk_discontinued_after_server'] = bool(zd and zd.get('is_discontinued') and date)
        m['tools'] = '; '.join(str(s.get('tech_name')) for s in signals)
        m['total_entries'] = len(signals)
    elif stage == 'blocker':
        signals = _signals(parsed)
        adoption = _first(signals, lambda s: 'utilisent pas' in _text(s, 'source_quote')
                          or 'adoption' in _text(s, 'source_quote', 'summary'))
        m.update(_found('blocker_adoption', adoption, stage))
        hosting = _first(signals, lambda s: 'bloquera' in _text(s, 'source_quote')
                         or 'hébergement' in _text(s, 'source_quote'))
        m.update(_found('blocker_hosting_threat', hosting, stage))
        m['raised_by'] = '; '.join(str(s.get('raised_by_name')) for s in signals)
        m['total_entries'] = len(signals)
    if isinstance(parsed, dict):
        entries = [s for key in ('signals', 'pains', 'impacts') for s in (parsed.get(key) or [])
                   if isinstance(s, dict)]
        inner = {'pain_impact': 'impact'}.get(stage, stage)
        m['emitted_all'] = len(entries)
        m['survive_filter_all'] = sum(1 for s in entries if _survives(s, inner))
    return m


def _signals(parsed):
    if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
        return [s for s in parsed['signals'] if isinstance(s, dict)]
    return []


# =============================================================================
# RUN
# =============================================================================

def run_variant(name, n, out_dir, provider, tenant_name):
    stage, transcript_key = VARIANTS[name]
    transcript = TRANSCRIPTS[transcript_key].read_text(encoding='utf-8')
    activity = _activity(tenant_name, CONVERSATION_DATES[transcript_key])
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
        if transcript_key == 'atelier':
            metrics = _atelier_metrics(stage, parsed)
        elif stage == 'people':
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
    people, blockers, atelier = [], [], []
    for name in VARIANTS:
        vrows = [r for r in rows if r['variant'] == name]
        if not vrows:
            continue
        if VARIANTS[name][1] == 'atelier':
            n = len(vrows)
            errors = sum(1 for r in vrows if r['error'])
            for key in sorted(vrows[0]):
                if key in ('variant', 'call', 'error'):
                    continue
                values = [r.get(key) for r in vrows]
                if all(isinstance(v, bool) for v in values):
                    shown = f'{sum(values)}/{n}'
                elif all(isinstance(v, int) for v in values):
                    shown = f'{min(values)}-{max(values)}'
                else:
                    shown = str(_count(v or '-' for v in values))
                atelier.append(f'| {name} | {key} | {shown} |')
            atelier.append(f'| {name} | erreurs | {errors} |')
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
    if atelier:
        lines += [
            '## Atelier business case (appels avec ... / N ; _emitted = réponse brute, '
            '_survives_filter = après le filtre de sécurité du serveur)',
            '',
            '| variante | mesure | valeur |',
            '|---|---|---|',
            *atelier, '',
        ]
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
    rows = []
    for name in args.only or list(VARIANTS):
        rows.extend(run_variant(name, args.n, out_dir, provider, args.tenant_name))

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
