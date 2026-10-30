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
  summary.csv / summary.md   one row per call + the per-variant recap, with
                             the call durations (meta.duration_ms: mean / max;
                             wall_ms: wall clock, failed calls included) and
                             the TYPE of each error (timeout, troncature,
                             refus, parsing, ...)

Usage (from backend/, with the usual .env holding OPENAI_API_KEY):
  python evals/td279/run_attribution_eval.py                 # 9 x 10 calls
  python evals/td279/run_attribution_eval.py --only atelier_people atelier_pain_impact \
      atelier_objective atelier_techstack atelier_blocker   # the atelier audit
  python evals/td279/run_attribution_eval.py --n 3 --only people_V0
  python evals/td279/run_attribution_eval.py --n 20 --model gpt-5.4-mini-2026-03-17 \
      --only people_V0 people_WITNESS atelier_people   # the People challenger
  python evals/td279/run_attribution_eval.py --dry-run       # no API call
  python evals/td279/run_attribution_eval.py --rescore evals/td279/out/<stamp>
      # recompute the summary from the recorded raw answers, no API call
"""

import argparse
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
    STAGE_RESPONSE_SCHEMAS,
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
from app_modules.ai_pipelines import config as ai_config  # noqa: E402
from app_modules.ai_pipelines.providers import get_provider  # noqa: E402
from app_modules.ai_pipelines.providers.base import LLMCallResult  # noqa: E402
from app_modules.ai_pipelines.services import participant_refs  # noqa: E402
from app_modules.ai_pipelines.services.people_evidence import check_people_evidence  # noqa: E402
from app_modules.ai_pipelines.services.transcript_text import TranscriptText  # noqa: E402
from app_modules.ai_pipelines.services.safety_filter import passes_safety_filter  # noqa: E402
from app_modules.ai_pipelines.services.transcript_signal_extractor import (  # noqa: E402
    _iso_date,
    resolve_person_department_or_title,
)
from app_modules.core_modules.models import StandardDepartment  # noqa: E402

# Shared eval plumbing (evals/common/eval_kit.py) — one implementation, also
# used by evals/next_steps.
from evals.common.eval_kit import (  # noqa: E402
    RecordingProvider,
    add_common_arguments,
    count as _count,
    declared_models,
    load_records,
    prepare_out_dir,
    row as _row,
    run_calls,
    timing_line as _timing_line,
    write_summary,
)


# =============================================================================
# TEST CASE (TD-279 smoke, activity 5b53de3d)
# =============================================================================

# --model choices: ONLY the models declared in the repo config (never invented)
# -> PROVIDER_CONFIG key.
MODELS = declared_models()

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


def _context(activity, stage, transcript=None):
    # Context v10 (D7): the Conversation date comes from the transcript header.
    context = ctx.build_context_layer(activity, target_stage=stage, transcript=transcript)
    # Context v8: the registered contacts are never sent to the LLM.
    assert 'Criminelle' not in context
    return context


# =============================================================================
# PROVIDERS
# =============================================================================

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

def _said_by(quote, transcript, speaker):
    """The quote is part of a line of `speaker` (production text service,
    services/transcript_text.py -- TD-279 V), a speaker label copied at its
    head removed as the server does (strip_speaker_label)."""
    text = TranscriptText(transcript)
    return text.said_by(text.strip_speaker_label(quote), speaker)


def _evidence_metrics(signals, transcript):
    """TD-279 V: the server check of each People proof (production
    function): rejected proofs, per cause and per person."""
    text = TranscriptText(transcript)
    rejected = {}
    for s in signals:
        # Same order as the server: label removed, then the check.
        quote = text.strip_speaker_label(s.get('source_quote') or '')
        status = check_people_evidence(s.get('full_name'), quote, text)
        if status != 'ok':
            rejected.setdefault(str(status), []).append(_who(s.get('full_name')))
    return {
        'evidence_rejected': sum(len(names) for names in rejected.values()),
        'evidence_rejected_detail': json.dumps(rejected, ensure_ascii=False),
    }


def _who(name):
    """Speaker key for a name as returned by the LLM (or 'null' / 'other')."""
    if not isinstance(name, str) or not name.strip():
        return 'null'
    # The production word match (participant_refs.resolve_speaker_label).
    label = participant_refs.resolve_speaker_label(name, list(SPEAKERS.values()))
    keys = {full: key for key, full in SPEAKERS.items()}
    return keys[label] if label is not None else f'other: {name}'


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


def _controleur(signals):
    """
    The management controller of the atelier: the entry whose job_title
    names the function, else an UNNAMED entry whose quote / notes do -- never
    a named person whose quote merely mentions it (Isabelle: "... la
    présenter au contrôleur de gestion, puis à Marc").
    """
    def names_it(text):
        return 'contr' in text and 'gestion' in text
    return (
        _first(signals, lambda s: names_it(_text(s, 'job_title')))
        or _first(signals, lambda s: not (s.get('full_name') or '').strip()
                  and names_it(_text(s, 'notes', 'source_quote')))
    )


def _atelier_metrics(stage, parsed, activity=None):
    m = {}
    if stage == 'people':
        signals = _signals(parsed)
        name = lambda s: (s.get('full_name') or '').lower()  # noqa: E731
        named = lambda *keys: _first(signals, lambda s: any(k in name(s) for k in keys))  # noqa: E731
        for key, words in (('isabelle', ('isabelle', 'roux')), ('laurent', ('laurent', 'petit')),
                           ('nadia', ('nadia', 'benali')), ('marc', ('marc',)), ('karim', ('karim',))):
            person = named(*words)
            m.update(_found(key, person, stage))
            if key in ('isabelle', 'marc'):
                m[f'{key}_role'] = (person or {}).get('role') or ''
        if activity is not None:
            m['linked_to_criminelle'] = sum(1 for s in signals if _linked(s.get('full_name'), activity))
        thomas = named('thomas', 'lefèvre', 'lefevre')
        m.update(_found('thomas', thomas, stage))
        m['thomas_role'] = (thomas or {}).get('role') or ''
        m['thomas_not_decision_maker'] = bool(thomas) and thomas.get('role') != 'DECISION_MAKER'
        controleur = _controleur(signals)
        m.update(_found('controleur', controleur, stage))
        department = ((controleur or {}).get('department') or '').strip()
        m['controleur_department'] = department
        m['controleur_department_finance'] = department.lower() == FINANCE.lower()
        # TD-279 D: the job title as said, and the department the SERVER keeps
        # (production resolver: the department, else the job title).
        m['controleur_job_title'] = ((controleur or {}).get('job_title') or '').strip()
        server_department = resolve_person_department_or_title(
            (controleur or {}).get('department'), (controleur or {}).get('job_title'))
        m['controleur_department_after_server'] = server_department.name if server_department else ''
        # Server identity rule (_build_people_data): no contact, no name and no
        # resolved department -> dropped.
        m['controleur_has_identity'] = bool(controleur) and bool(
            (controleur.get('full_name') or '').strip() or server_department
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

def _provider_key(stage, forced_key):
    """The PROVIDER_CONFIG entry of the call: --model, else the production
    model-per-stage setting (config.STAGE_PROVIDER, TD-279 P1), else None
    (the active provider)."""
    return forced_key or ai_config.STAGE_PROVIDER.get(stage)


def run_variant(name, n, out_dir, dry_run, tenant_name, forced_key=None):
    stage, transcript_key = VARIANTS[name]
    provider_key = _provider_key(stage, forced_key)
    provider = DryRunProvider() if dry_run else get_provider(provider_key or ai_config.ACTIVE_PROVIDER)
    model = ai_config.PROVIDER_CONFIG[provider_key or ai_config.ACTIVE_PROVIDER]['model']
    transcript = TRANSCRIPTS[transcript_key].read_text(encoding='utf-8')
    activity = _activity(tenant_name, CONVERSATION_DATES[transcript_key])
    context = _context(activity, stage, transcript)
    request = REQUEST_BUILDERS[stage](transcript)
    base_record = {'stage': stage, 'transcript': transcript_key,
                   'provider_key': provider_key, 'model': model,
                   'prompt_versions': dict(QualificationSignalsPipeline.PROMPT_VERSIONS)}

    def make_call(recorder):
        pipeline = QualificationSignalsPipeline(provider=recorder)
        parsed, meta = pipeline._call_llm(
            system_prompt=SYSTEM_PROMPT, context=context, request=request,
            provider_key=provider_key,
            # Same strict schema as production (TD-279 M).
            response_schema=STAGE_RESPONSE_SCHEMAS.get(stage),
        )
        return parsed, meta, {}

    return run_calls(
        name=name, n=n, variant_dir=out_dir / name, base_record=base_record,
        make_recorder=lambda: RecordingProvider(provider), make_call=make_call,
        score=lambda record: _score(record, transcript, activity),
    )


def _score(record, transcript, activity):
    """The metrics of ONE recorded call, from its raw parsed answer only
    (shared by a run and --rescore)."""
    stage, parsed = record['stage'], record.get('parsed')
    signals = _signals(parsed)
    if record['transcript'] == 'atelier':
        metrics = _atelier_metrics(stage, parsed, activity)
    elif stage == 'people':
        metrics = _people_metrics(signals, transcript, activity)
    else:
        metrics = _blocker_metrics(signals, activity)
    if stage == 'people':
        metrics.update(_evidence_metrics(signals, transcript))
    return metrics


def rescore(out_dir, tenant_name):
    """
    --rescore: recompute the metrics and the summary of a run folder from the
    raw answers ALREADY recorded (call_NN.json) -- no API call, no provider.
    Writes summary_rescored.csv / summary_rescored.md next to the originals
    (kept). Transcripts: the current files of this folder.
    """
    rows, models_used, versions = [], {}, {}
    for record in load_records(out_dir, VARIANTS):
        key = record['transcript']
        transcript = TRANSCRIPTS[key].read_text(encoding='utf-8')
        activity = _activity(tenant_name, CONVERSATION_DATES[key])
        rows.append(_row(record, _score(record, transcript, activity)))
        models_used[record['variant']] = record.get('model')
        versions = versions or record.get('prompt_versions') or {}
    if not rows:
        sys.exit(f'No call_NN.json under {out_dir} -- nothing to rescore.')
    _write_summary(out_dir, rows, models_used, versions, suffix='_rescored')


# Columns of a row that are not metrics of the variant's stage (shown in
# their own recap sections).
_CALL_KEYS = ('variant', 'call', 'error', 'error_type', 'duration_ms', 'wall_ms',
              'evidence_rejected', 'evidence_rejected_detail')


def _evidence_line(name, vrows):
    by_cause, by_person = {}, {}
    for r in vrows:
        for cause, names in json.loads(r['evidence_rejected_detail']).items():
            by_cause[cause] = by_cause.get(cause, 0) + len(names)
            for who in names:
                key = f'{who} ({cause})'
                by_person[key] = by_person.get(key, 0) + 1
    calls = sum(1 for r in vrows if r['evidence_rejected'])
    return (f'| {name} | {sum(r["evidence_rejected"] for r in vrows)} | {calls}/{len(vrows)} | '
            f'{by_cause or "-"} | {by_person or "-"} |')


def _recap(rows):
    people, blockers, atelier, timings, evidence = [], [], [], [], []
    for name in VARIANTS:
        vrows = [r for r in rows if r['variant'] == name]
        if not vrows:
            continue
        timings.append(_timing_line(name, vrows))
        if VARIANTS[name][0] == 'people':
            evidence.append(_evidence_line(name, vrows))
        if VARIANTS[name][1] == 'atelier':
            n = len(vrows)
            errors = sum(1 for r in vrows if r['error'])
            for key in sorted(vrows[0]):
                if key in _CALL_KEYS:
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
    lines = [
        '## Durées et erreurs (duration_ms = meta de l\'appel réussi ; wall_ms = '
        'horloge, appels en erreur compris)',
        '',
        '| variante | appels | duration_ms moyenne | duration_ms max | wall_ms max | '
        'erreurs par type |',
        '|---|---|---|---|---|---|',
        *timings, '',
    ]
    if evidence:
        lines += [
            '## People — preuves rejetées par le serveur (TD-279 V : rôle -> UNKNOWN, '
            'personne gardée)',
            '',
            '| variante | preuves rejetées | appels concernés | par cause | par personne (cause) |',
            '|---|---|---|---|---|',
            *evidence, '',
        ]
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
    add_common_arguments(
        parser, VARIANTS, MODELS,
        model_help='force a model DECLARED in ai_pipelines/config.py PROVIDER_CONFIG '
                   '(e.g. the People challenger) for every variant run; default: the '
                   'production model per stage (config.STAGE_PROVIDER, else the '
                   'active provider)',
    )
    args = parser.parse_args()

    if args.rescore:
        rescore(Path(args.rescore), args.tenant_name)
        return

    # Never overwrite a previous run (the earlier reference outputs are kept).
    out_dir = prepare_out_dir(args.out, HERE)

    forced_key = MODELS[args.model] if args.model else None
    names = args.only or list(VARIANTS)
    models_used = {
        name: ai_config.PROVIDER_CONFIG[
            _provider_key(VARIANTS[name][0], forced_key) or ai_config.ACTIVE_PROVIDER
        ]['model']
        for name in names
    }
    rows = []
    for name in names:
        rows.extend(run_variant(name, args.n, out_dir, args.dry_run, args.tenant_name, forced_key))
    _write_summary(out_dir, rows, models_used, QualificationSignalsPipeline.PROMPT_VERSIONS)


def _write_summary(out_dir, rows, models_used, versions, suffix=''):
    write_summary(out_dir, rows, title='TD-279 — récap', models_used=models_used,
                  versions=versions, recap=_recap(rows), suffix=suffix)


if __name__ == '__main__':
    main()
