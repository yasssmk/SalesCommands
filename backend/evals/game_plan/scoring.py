# backend/evals/game_plan/scoring.py
"""
Game Plan evaluation — the automatic checks of ONE recorded call (sprint 2
Game Plan, G13). Pure functions of the recorded data: shared by a run and by
--rescore (the evals/deal_health/scoring.py pattern). NOT product code.

Generic checks — REUSED from evals/deal_health/scoring.py (one
implementation): schema validity (against the Game Plan's own strict schema),
invented numbers, invented names, planted last names, rhetoric labels.

New checks (README.md « Contrôles automatiques »):
  participants_covered     — every participant of the plan has an angle;
  plans_ok                 — plans A / B / C in order, 1 to 3;
  opening_complete         — the 5 parts of the opening, non empty;
  discovery_covers_dh      — the discovery reuses the deal health's missing info;
  language_ok              — each recipient's message in its expected language;
  subject_ok               — a subject for an email, none for LinkedIn;
  campaign_diagnostic_ok   — present ONLY for the campaign activity without DC;
  parse_error_cause        — why the server refused an answer (rhetoric label /
                             last name / structure), a last name refused while
                             written as a common word told apart (a false
                             rejection).
"""

import re

from app_modules.ai_pipelines.prompts.prep_call.message_v2 import PREP_CALL_MESSAGE_SCHEMA
from app_modules.ai_pipelines.prompts.prep_call.outline_v2 import PREP_CALL_OUTLINE_SCHEMA

from evals.deal_health.scoring import (
    _fold,
    invented_names as _invented_names,
    invented_numbers as _invented_numbers,
    last_names_found,
    rhetoric_labels,
    schema_errors,
    texts,
)


# =============================================================================
# GENERIC CHECKS — adapted to the Game Plan's output, not redefined
# =============================================================================

# The code fields of the Game Plan's answers (labels, refs, language tags,
# sources): not prose, not scanned for names.
_CODE_KEYS = {'label', 'ref', 'language', 'language_source'}

# Game Plan vocabulary that is not a name: the plans' letters, the channels.
_GAME_PLAN_ALLOWLIST = {'b', 'c', 'linkedin', 'email', 'teams', 'zoom'}


def prose(parsed):
    """The answer without its code fields (refs, labels, languages)."""
    if isinstance(parsed, dict):
        return {k: prose(v) for k, v in parsed.items() if k not in _CODE_KEYS}
    if isinstance(parsed, list):
        return [prose(v) for v in parsed]
    return parsed


def invented_names(parsed, input_text):
    """The deal health's heuristic, on the prose, without the Game Plan's
    own vocabulary (plans B / C, the channels)."""
    return [n for n in _invented_names(prose(parsed), input_text)
            if _fold(n) not in _GAME_PLAN_ALLOWLIST]


# =============================================================================
# FIGURES — what a Game Plan may write, what it may never invent (G13b)
# =============================================================================
# ALLOWED (the generic detector already leaves dates and times out): the
# duration of a meeting the plan proposes — « a 30-minute working session »,
# « a 45-minute targeted demonstration », « ask for 20 minutes ».
# ALWAYS INVENTED when absent from the pack: a percentage, an amount, a gain
# or a volume — in figures (« 20 % », « saves 8 hours per week ») or in words
# (« over one month of labor »).

_MEETING_NOUNS = (
    r'(?:session|meeting|call|demo|demonstration|workshop|slot|discussion|review|check-in'
    r'|conversation|walkthrough|walk-through|presentation|follow-up|chat|visit|exchange'
    r'|appointment|catch-up|sync|briefing|interview)s?'
)
_NUMBER_WORDS = (
    r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty'
    r'|thirty|forty|forty-five|fifty|sixty|ninety|hundred|thousand|half|a\s+half|a\s+dozen|dozen)'
)
_DURATION_UNIT = r'(?:minutes?|mins?|hours?|hrs?)'
_QUANTITY = rf'(?:\d+|{_NUMBER_WORDS}|an?)'
# « 30-minute working session », « 45 minutes demo », « a one-hour call »
_MEETING_DURATION = re.compile(
    rf'\b{_QUANTITY}[\s-]?{_DURATION_UNIT}(?:\s+|-)(?:[a-z-]+\s+){{0,2}}{_MEETING_NOUNS}\b',
    re.IGNORECASE,
)
# « ask for 30 minutes », « take 20 minutes » — never « … per week », « … of labor »
_ASKED_DURATION = re.compile(
    rf'\b(?:for|take|takes|taking|book|block|ask(?:\s+for)?|need|needs|schedule|keep\s+it\s+to)'
    rf'\s+(?:about\s+|around\s+|only\s+)?{_QUANTITY}[\s-]?{_DURATION_UNIT}\b'
    rf'(?!\s+(?:per|a|an|each|every)\s+(?:day|week|month|year|quarter))'
    rf'(?!\s+of\s+(?:labou?r|work|effort|time|savings?))',
    re.IGNORECASE,
)
_GAIN_UNIT = (
    r'(?:full\s+)?(?:hours?|days?|weeks?|months?|years?|percent|per\s+cent|people'
    r'|employees|ftes?|euros?|dollars?)'
)
# A gain or a volume in WORDS (the digit detector does not see it).
_SPELLED_GAIN = re.compile(
    rf'\b(?:(?:save|saves|saved|saving|lose|loses|lost|losing|gain|gains|cut|cuts|reduce|reduces'
    rf'|free|frees|over|more\s+than|up\s+to|nearly|almost)\s+{_NUMBER_WORDS}[\s-]+{_GAIN_UNIT}'
    rf'|{_NUMBER_WORDS}[\s-]+{_GAIN_UNIT}\s+of\s+(?:labou?r|work|effort))\b',
    re.IGNORECASE,
)


def _map_strings(value, fn):
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, dict):
        return {k: _map_strings(v, fn) for k, v in value.items()}
    if isinstance(value, list):
        return [_map_strings(v, fn) for v in value]
    return value


def _without_meeting_durations(text):
    return _ASKED_DURATION.sub(' ', _MEETING_DURATION.sub(' ', text))


def spelled_gains(parsed, input_text):
    """The gains / volumes written in words (« over one month of labor »),
    absent from the input."""
    known = _fold(input_text)
    found = []
    for _path, text in texts(parsed):
        for match in _SPELLED_GAIN.finditer(text):
            phrase = ' '.join(match.group(0).split())
            if _fold(phrase) not in known and phrase not in found:
                found.append(phrase)
    return found


def invented_numbers(parsed, input_text):
    """The invented figures of a Game Plan: the generic detector (its dates
    and times left out) on the prose without the meeting durations it
    proposes, plus the gains / volumes written in words."""
    digits = _invented_numbers(_map_strings(parsed, _without_meeting_durations), input_text)
    return digits + spelled_gains(parsed, input_text)


def schema_for(output_kind):
    return PREP_CALL_MESSAGE_SCHEMA if output_kind == 'MESSAGE' else PREP_CALL_OUTLINE_SCHEMA


# =============================================================================
# THE PLAN
# =============================================================================

def participants_covered(parsed, expected_refs):
    """The expected participants (their labels) WITHOUT an angle in
    `participants` — [] when every one is covered."""
    angles = {p.get('ref'): (p.get('angle') or '').strip()
              for p in (parsed or {}).get('participants') or [] if isinstance(p, dict)}
    return [ref for ref in expected_refs if not angles.get(ref)]


def plans_ok(parsed):
    """objective.plans: 1 to 3 plans labelled A, B, C in that order."""
    plans = ((parsed or {}).get('objective') or {}).get('plans') or []
    labels = [p.get('label') for p in plans if isinstance(p, dict)]
    return 1 <= len(labels) <= 3 and labels == ['A', 'B', 'C'][:len(labels)]


OPENING_PARTS = ('objective', 'time', 'client_agenda', 'our_agenda', 'expected_outcome')


def opening_missing(parsed):
    """The parts of the opening that are absent or empty."""
    opening = (parsed or {}).get('opening') or {}
    return [part for part in OPENING_PARTS if not str(opening.get(part) or '').strip()]


def discovery_covers_dh(parsed, keywords):
    """The discovery's missing info (item / question) carries one keyword of
    the deal health's missing info. None when the case has none."""
    if not keywords:
        return None
    text = _fold(' '.join(
        f"{m.get('item') or ''} {m.get('question') or ''}"
        for m in ((parsed or {}).get('discovery') or {}).get('missing_info') or []
        if isinstance(m, dict)
    ))
    return any(_fold(k) in text for k in keywords)


def campaign_diagnostic_ok(parsed, expected_present):
    """campaign_diagnostic present (a reading) exactly when expected (plans only)."""
    diagnostic = (parsed or {}).get('campaign_diagnostic')
    present = isinstance(diagnostic, dict) and bool(str(diagnostic.get('reading') or '').strip())
    return present == bool(expected_present)


# =============================================================================
# THE MESSAGE
# =============================================================================

def wrong_languages(parsed, expected_languages):
    """{ref: (expected, written)} of the recipients whose message is missing
    or in another language — {} when every one is right."""
    written = {m.get('ref'): m.get('language')
               for m in (parsed or {}).get('messages') or [] if isinstance(m, dict)}
    return {ref: (lang, written.get(ref)) for ref, lang in expected_languages.items()
            if (written.get(ref) or '').lower() != lang.lower()}


def subject_ok(parsed, channel):
    """A non-empty subject on every email; no subject on a LinkedIn message."""
    messages = [m for m in (parsed or {}).get('messages') or [] if isinstance(m, dict)]
    if not messages:
        return False
    if channel == 'EMAIL':
        return all(str(m.get('subject') or '').strip() for m in messages)
    return all(m.get('subject') in (None, '') for m in messages)


# =============================================================================
# PARSE_ERROR — the cause of a server refusal
# =============================================================================

PARSE_CAUSES = ('rhetoric', 'last_name', 'last_name_false_reject', 'structure')


def parse_error_cause(error, raw_answer, last_names):
    """
    Why the server refused the answer (services/prep_call/plan_validator.py
    messages): 'rhetoric' (a classical rhetoric label), 'last_name' (a
    roster last name), 'structure' (anything else: schema, bounds, JSON).
    A last-name refusal is a FALSE rejection ('last_name_false_reject') when
    every occurrence of the planted last names in the raw answer is written
    in lower case — a common word (« the price »), not a person (« Sarah
    Price »). '' when the call was not refused.
    """
    message = str(error or '')
    if 'parse_error' not in message and 'PromptParseError' not in message:
        return ''
    if 'rhetoric label' in message:
        return 'rhetoric'
    if 'last name' in message:
        occurrences = [
            match.group(0)
            for name in last_names
            for match in re.finditer(rf'(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])',
                                     raw_answer or '', re.IGNORECASE)
        ]
        if occurrences and all(o[0].islower() for o in occurrences):
            return 'last_name_false_reject'
        return 'last_name'
    return 'structure'


# =============================================================================
# ONE CALL
# =============================================================================

def score_call(*, parsed, prompt, user_prompt, expected, meta=None, error_type=None,
               error=None, raw_answer=None):
    """The metrics of one recorded call (a run and --rescore). `prompt` is the
    whole prompt (system + user: no last name may reach it), `user_prompt`
    the pack and the request — what a number or a name may come from (the
    system prompt's own figures, « 70% », are not evidence)."""
    meta = meta or {}
    kind = expected['output_kind']
    metrics = {
        'output_kind': kind,
        'error_type': error_type or '',
        'parse_error_cause': parse_error_cause(error, raw_answer, expected['planted_last_names']),
        'duration_ms': meta.get('duration_ms'),
        'input_tokens': meta.get('input_tokens'),
        'output_tokens': meta.get('output_tokens'),
        'reasoning_tokens': meta.get('reasoning_tokens'),
        'prompt_chars': len(prompt or ''),
        'last_names_in_prompt': last_names_found(prompt, expected['planted_last_names']),
    }
    if parsed is None:
        return {**metrics, 'answered': False}
    metrics.update({
        'answered': True,
        'schema_errors': schema_errors(parsed, schema_for(kind)),
        'last_names_in_output': last_names_found(
            '\n'.join(t for _p, t in texts(parsed)), expected['planted_last_names']),
        'invented_numbers': invented_numbers(prose(parsed), user_prompt),
        'invented_names': invented_names(parsed, user_prompt),
        'rhetoric_labels': rhetoric_labels(parsed),
    })
    if kind == 'PLAN':
        metrics.update({
            'participants_without_angle': participants_covered(parsed, expected['participants']),
            'plans_ok': plans_ok(parsed),
            'opening_missing': opening_missing(parsed),
            'discovery_covers_dh': discovery_covers_dh(parsed, expected.get('dh_missing_any_of')),
            'campaign_diagnostic_ok': campaign_diagnostic_ok(parsed, expected['campaign_diagnostic']),
        })
    else:
        metrics.update({
            'wrong_languages': wrong_languages(parsed, expected['languages']),
            'subject_ok': subject_ok(parsed, expected['channel']),
        })
    return metrics


# The pass / fail checks of the recap (True = passed), in report order.
CHECK_LABELS = (
    ('schema', 'schéma valide'),
    ('first_names', 'prénoms seulement'),
    ('numbers', 'aucun chiffre inventé'),
    ('names', 'aucun nom inventé'),
    ('rhetoric', 'aucun ethos/pathos/logos'),
    ('participants', 'chaque participant a un angle'),
    ('plans', 'plans A/B/C ≤ 3'),
    ('opening', 'ouverture en 5 parties'),
    ('discovery', 'découverte = info manquante DH'),
    ('campaign', 'campaign_diagnostic au bon cas'),
    ('language', 'langue par destinataire'),
    ('subject', 'subject email / pas LinkedIn'),
)


def checks(metrics):
    """{check: True / False / None (no answer, or not applicable)}."""
    if not metrics.get('answered'):
        return {key: None for key, _label in CHECK_LABELS}
    plan = metrics['output_kind'] == 'PLAN'
    return {
        'schema': not metrics['schema_errors'],
        'first_names': not metrics['last_names_in_output'] and not metrics['last_names_in_prompt'],
        'numbers': not metrics['invented_numbers'],
        'names': not metrics['invented_names'],
        'rhetoric': not metrics['rhetoric_labels'],
        'participants': not metrics['participants_without_angle'] if plan else None,
        'plans': metrics['plans_ok'] if plan else None,
        'opening': not metrics['opening_missing'] if plan else None,
        'discovery': metrics['discovery_covers_dh'] if plan else None,
        'campaign': metrics['campaign_diagnostic_ok'] if plan else None,
        'language': not metrics['wrong_languages'] if not plan else None,
        'subject': metrics['subject_ok'] if not plan else None,
    }
