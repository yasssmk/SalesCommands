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

from app_modules.ai_pipelines.constants import PREP_CALL_LINE_MAX_WORDS
from app_modules.ai_pipelines.prompts.prep_call.message_v2 import PREP_CALL_MESSAGE_SCHEMA
from app_modules.ai_pipelines.prompts.prep_call import PREP_CALL_OUTLINE_SCHEMA  # the one sent

from evals.deal_health import scoring as _generic
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
# G13c — a separator is a space (non-breaking included) or ANY hyphen / dash
# (« 20‑minute » with U+2011, « 20–minute »): models write the typographic ones.
_SEP = r'[\s\-\u2010-\u2015]'
# « 30-minute working session », « 45 minutes demo », « a one-hour call »
_MEETING_DURATION = re.compile(
    rf'\b{_QUANTITY}{_SEP}?{_DURATION_UNIT}{_SEP}+(?:[a-z\-\u2010-\u2015]+\s+){{0,2}}{_MEETING_NOUNS}\b',
    re.IGNORECASE,
)
# « ask for 30 minutes », « take 20 minutes » — never « … per week », « … of labor »
_ASKED_DURATION = re.compile(
    rf'\b(?:for|take|takes|taking|book|block|ask(?:\s+for)?|need|needs|schedule|keep\s+it\s+to)'
    rf'\s+(?:about\s+|around\s+|only\s+)?{_QUANTITY}{_SEP}?{_DURATION_UNIT}\b'
    rf'(?!\s+(?:per|a|an|each|every)\s+(?:day|week|month|year|quarter))'
    rf'(?!\s+of\s+(?:labou?r|work|effort|time|savings?))',
    re.IGNORECASE,
)
# G13c — the same durations in French: « un échange de 30 minutes »,
# « un point rapide de 20 min », « 30 minutes d'échange », « proposer 30 min » —
# never « … par semaine / par jour / par mois / par an ».
_FR_MEETING_NOUNS = (
    r'(?:[ée]change|appel|rendez-vous|rdv|point|r[ée]union|entretien|visio|visioconf[ée]rence'
    r'|d[ée]mo|d[ée]monstration|atelier|session|cr[ée]neau|call|conversation|pr[ée]sentation)s?'
)
_FR_UNIT = r'(?:minutes?|min|heures?|h)'
_FR_NOT_A_RATE = r'(?!\s+(?:par|chaque|toutes?\s+les)\s+(?:jour|semaine|mois|an|ann[ée]e|trimestre))'
_FR_MEETING_DURATION = re.compile(
    rf'\b{_FR_MEETING_NOUNS}(?:\s+(?:rapide|court|bref|de\s+travail))?\s+'
    rf'(?:de|d[\'’]environ|d[\'’]une?\s+dur[ée]e\s+de)\s+(?:\d+|une?|une\s+demi)\s*-?\s*{_FR_UNIT}\b{_FR_NOT_A_RATE}'
    rf'|\b\d+\s*{_FR_UNIT}\s+(?:d[\'’]|de\s+)?{_FR_MEETING_NOUNS}\b'
    rf'|\b(?:propos\w*|demand\w*|pren\w*|bloqu\w*|r[ée]serv\w*|cal\w*|accord\w*|consacr\w*)'
    rf'\s+(?:environ\s+|seulement\s+|juste\s+)?\d+\s*{_FR_UNIT}\b{_FR_NOT_A_RATE}',
    re.IGNORECASE,
)
_GAIN_UNIT = (
    r'(?:full\s+)?(?:hours?|days?|weeks?|months?|years?|percent|per\s+cent|people'
    r'|employees|ftes?|euros?|dollars?)'
)
# A gain or a volume in WORDS (the digit detector does not see it).
_SPELLED_GAIN = re.compile(
    rf'\b(?:(?:save|saves|saved|saving|lose|loses|lost|losing|gain|gains|cut|cuts|reduce|reduces'
    rf'|free|frees|over|more\s+than|up\s+to|nearly|almost)\s+{_NUMBER_WORDS}{_SEP}+{_GAIN_UNIT}'
    rf'|{_NUMBER_WORDS}{_SEP}+{_GAIN_UNIT}\s+of\s+(?:labou?r|work|effort))\b',
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


def _blank(match):
    """A span blanked out at its own length — the positions stay those of the
    original text (the excerpts of the report, G13c)."""
    return ' ' * len(match.group(0))


# G13d — a duration ON ITS OWN is logistics (« 15 minutes », « spend 20
# minutes »), unless a rate follows it (« per week », « par semaine ») or a
# gain surrounds it (« of labor », « saved », « saves 8 hours »).
_BARE_DURATION = re.compile(
    rf'\b(?:\d+|{_NUMBER_WORDS}){_SEP}?(?:minutes?|mins?|hours?|hrs?|heures?)\b', re.IGNORECASE,
)
_RATE_OR_GAIN_AFTER = re.compile(
    r'^\s+(?:(?:per|a|an|each|every|par|chaque|toutes?\s+les)\s+'
    r'(?:day|week|month|year|quarter|jour|semaine|mois|an|ann[ée]e|trimestre)'
    r'|of\s+(?:labou?r|work|effort|time|savings?)|saved|gagn[ée]es?|[ée]conomis[ée]es?'
    r'|de\s+(?:travail|gagn[ée]es?))\b',
    re.IGNORECASE,
)
_GAIN_BEFORE = re.compile(
    r'\b(?:save|saves|saved|saving|lose|loses|lost|losing|gain|gains|gained|cut|cuts|reduce'
    r'|reduces|free|frees|freed|recover|reclaim|over|more\s+than|gagner|gagnez|gagne'
    r'|[ée]conomiser|[ée]conomisez|perdre|perdez|perd|plus\s+de)'
    r'\s+(?:up\s+to\s+|about\s+|around\s+|nearly\s+|jusqu[\'’]à\s+|environ\s+)?$',
    re.IGNORECASE,
)


def _blank_bare_durations(text):
    chars = list(text)
    for match in _BARE_DURATION.finditer(text):
        if _RATE_OR_GAIN_AFTER.match(text[match.end():]) or _GAIN_BEFORE.search(text[:match.start()]):
            continue
        chars[match.start():match.end()] = ' ' * (match.end() - match.start())
    return ''.join(chars)


def _without_meeting_durations(text):
    for pattern in (_MEETING_DURATION, _ASKED_DURATION, _FR_MEETING_DURATION):
        text = pattern.sub(_blank, text)
    return _blank_bare_durations(text)


# =============================================================================
# NO INVENTED SLOT — a precise meeting date / time, a claimed action (G13d)
# =============================================================================
# PO decision: never a precise meeting date or time that is not in the pack,
# never a claimed action (an invitation sent, a meeting booked). An open
# window (« Tuesday or Wednesday? », « early next week ») and the placeholder
# (constants.PREP_CALL_SLOT_PLACEHOLDERS) are fine; so is a date of the pack.

_MONTH_NUMBERS = {
    **{m: i for i, m in enumerate(('january', 'february', 'march', 'april', 'may', 'june', 'july',
                                   'august', 'september', 'october', 'november', 'december'), 1)},
    **{m: i for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
                                   'oct', 'nov', 'dec'), 1)},
    'sept': 9,
    **{m: i for i, m in enumerate(('janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet',
                                   'aout', 'septembre', 'octobre', 'novembre', 'decembre'), 1)},
}
_SLOT_DATE = re.compile('|'.join((
    r'\b(?P<iso_y>(?:19|20)\d{2})-(?P<iso_m>\d{1,2})-(?P<iso_d>\d{1,2})\b',
    r'\b(?P<num_a>\d{1,2})/(?P<num_b>\d{1,2})(?:/\d{2,4})?\b',
    rf'\b(?P<dm_d>\d{{1,2}})(?:st|nd|rd|th|er)?(?:\s+of)?\s+(?P<dm_m>{_generic._MONTHS})',
    rf'\b(?P<md_m>{_generic._MONTHS})\s+(?P<md_d>\d{{1,2}})(?:st|nd|rd|th)?\b',
)), re.IGNORECASE)
_SLOT_TIME = re.compile(
    r'\b(?P<h1>\d{1,2}):(?P<m1>\d{2})(?:\s*(?P<p1>am|pm|a\.m\.|p\.m\.))?'
    r'|\b(?P<h2>\d{1,2})\s*(?P<p2>am|pm|a\.m\.|p\.m\.)'
    r'|\b(?P<h3>\d{1,2})h(?P<m3>\d{2})?\b(?!\s*(?:par|per))'
    r'|\bà\s+(?P<h4>\d{1,2})\s?h(?:\s?(?P<m4>\d{2}))?\b'
    r"|\b(?P<h5>\d{1,2})\s*o['’]clock\b",
    re.IGNORECASE,
)
# A claimed action — done (« I've sent », « I booked », « j'ai envoyé »,
# « l'invitation est envoyée ») or being done on a meeting (« I'm sending you
# an invite », « je vous envoie une invitation »). An intention (« I'll send an
# invitation once you confirm ») and an instruction to the rep (« Send the
# invitation today ») are not claims.
_MEETING_OBJECT = (
    r'(?:invit\w*|meeting|call|calendar|slot|appointment|session|demo\w*'
    r'|r[ée]union|rendez-vous|rdv|cr[ée]neau|[ée]change|appel|visio\w*|lien|agenda)'
)
_CLAIMED_ACTION = re.compile('|'.join((
    r"\bI(?:['’]ve|\s+have)?\s+(?:just\s+|already\s+)?(?:sent|booked|scheduled|set\s+up|blocked"
    r"|reserved|put\s+(?:in|on)|added|shared)\b",
    rf"\bI(?:['’]m|\s+am)\s+(?:now\s+)?(?:sending|booking|scheduling|setting\s+up|blocking)\b.{{0,40}}?\b{_MEETING_OBJECT}",
    rf"\b{_MEETING_OBJECT}\s+(?:has\s+been|is|was|have\s+been)\s+(?:sent|booked|scheduled|set\s+up|blocked|added)\b",
    r"\bj['’]ai\s+(?:d[ée]j[àa]\s+)?(?:envoy|transmis|r[ée]serv|bloqu|pos|cal|planifi|ajout|partag)\w*",
    rf"\bje\s+(?:vous\s+|t['’]\s*)?(?:envoie|adresse|transmets|r[ée]serve|bloque|pose|cale|planifie)\b.{{0,40}}?\b{_MEETING_OBJECT}",
    rf"\b{_MEETING_OBJECT}\s+(?:est|a\s+[ée]t[ée])\s+(?:envoy|r[ée]serv|bloqu|pos|cal|planifi)[ée]e?s?\b",
    r"\bje\s+viens\s+d[e'’]\s*(?:vous\s+)?(?:envoyer|r[ée]server|bloquer|poser|caler|planifier)\b",
)), re.IGNORECASE)


def _month_number(name):
    return _MONTH_NUMBERS.get(_fold(name).rstrip('.'))


def _day_months(match):
    """The (day, month) pairs a date match may mean (d/m and m/d for a numeric one)."""
    g = match.groupdict()
    if g['iso_y']:
        return {(int(g['iso_d']), int(g['iso_m']))}
    if g['num_a']:
        a, b = int(g['num_a']), int(g['num_b'])
        return {(a, b), (b, a)}
    if g['dm_d']:
        return {(int(g['dm_d']), _month_number(g['dm_m']))}
    return {(int(g['md_d']), _month_number(g['md_m']))}


def _clock(match):
    """'HH:MM' of a time match (12-hour forms converted)."""
    g = match.groupdict()
    hour = next(int(g[k]) for k in ('h1', 'h2', 'h3', 'h4', 'h5') if g[k])
    minute = next((int(g[k]) for k in ('m1', 'm3', 'm4') if g[k]), 0)
    period = _fold(g['p1'] or g['p2'] or '').replace('.', '')
    if period == 'pm' and hour < 12:
        hour += 12
    if period == 'am' and hour == 12:
        hour = 0
    return f'{hour:02d}:{minute:02d}'


def invented_slots(parsed, input_text):
    """[{'kind': 'slot', 'value', 'path', 'excerpt'}] — a precise date or time
    absent from the input, or a claimed action, in the prose."""
    known_dates = set()
    for match in _SLOT_DATE.finditer(input_text or ''):
        known_dates |= _day_months(match)
    known_times = {_clock(m) for m in _SLOT_TIME.finditer(input_text or '')}
    found = []
    for path, text in texts(prose(parsed)):
        for match in _SLOT_DATE.finditer(text):
            if not (_day_months(match) & known_dates):
                found.append({'kind': 'slot', 'value': f'date: {match.group(0).strip()}', 'path': path,
                              'excerpt': _excerpt(text, match.start(), match.end())})
        for match in _SLOT_TIME.finditer(text):
            if _clock(match) not in known_times:
                found.append({'kind': 'slot', 'value': f'heure: {match.group(0).strip()}', 'path': path,
                              'excerpt': _excerpt(text, match.start(), match.end())})
        for match in _CLAIMED_ACTION.finditer(text):
            found.append({'kind': 'slot', 'value': f'action: {" ".join(match.group(0).split())}',
                          'path': path, 'excerpt': _excerpt(text, match.start(), match.end())})
    return found


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


# =============================================================================
# WHERE A FINDING IS — its section and an excerpt (the report, G13c)
# =============================================================================

EXCERPT_RADIUS = 40     # ~80 characters around the occurrence


def _excerpt(text, start, end):
    left, right = max(0, start - EXCERPT_RADIUS), min(len(text), end + EXCERPT_RADIUS)
    snippet = ' '.join(text[left:right].split())
    return f"{'…' if left else ''}{snippet}{'…' if right < len(text) else ''}"


def locate_findings(parsed, numbers, names):
    """[{'kind', 'value', 'path', 'excerpt'}] — every occurrence of an
    invented figure or name in the prose, with its section (« closing.
    with_whom », « messages[0].body ») and ~80 characters around it. A figure
    is searched where the detector reads it: dates, times and meeting
    durations blanked out first."""
    numbers, found = set(numbers or []), []
    for path, text in texts(prose(parsed)):
        masked = _without_meeting_durations(_generic._DATES_AND_TIMES.sub(_blank, text))
        for match in _generic._NUMBER.finditer(masked):
            for value in _generic._numbers(match.group(0)) & numbers:
                found.append({'kind': 'number', 'value': value, 'path': path,
                              'excerpt': _excerpt(text, match.start(), match.end())})
        for match in _SPELLED_GAIN.finditer(text):
            phrase = ' '.join(match.group(0).split())
            if phrase in numbers:
                found.append({'kind': 'number', 'value': phrase, 'path': path,
                              'excerpt': _excerpt(text, match.start(), match.end())})
        for name in names or []:
            for match in re.finditer(rf'(?<![\w]){re.escape(name)}(?![\w])', text):
                found.append({'kind': 'name', 'value': name, 'path': path,
                              'excerpt': _excerpt(text, match.start(), match.end())})
    return found


# =============================================================================
# THE CLOSING, SOBER — and READABLE IN THE MIDDLE OF A MEETING (G13f)
# =============================================================================
# PO decisions of 28/11: the closing gets the person's agreement on the next
# step and locks it in during the conversation — no duration, no date, no
# time; every item of a section one short line (PREP_CALL_LINE_MAX_WORDS).

_CLOSING_FIELDS = ('next_step', 'with_whom', 'when', 'keep_control')
_AGREEMENT = re.compile(
    r'\b(?:agree\w*|agreement|accord|commit\w*|confirm\w*|buy-in|sign[\s-]?off|go-ahead'
    r'|green\s+light|consent\w*|approv\w*|yes|valider|validation|obtenir|engag\w*)\b',
    re.IGNORECASE,
)


def closing_findings(parsed):
    """{'durations': [...], 'slots': [...], 'agreement': bool} of the
    closing: any duration, any date or time (even one of the pack: the next
    meeting is never detailed), and whether an agreement is asked for."""
    closing = (parsed or {}).get('closing') or {}
    text = ' \n '.join(str(closing.get(f) or '') for f in _CLOSING_FIELDS)
    spans = [(m.start(), m.end()) for pattern in
             (_MEETING_DURATION, _ASKED_DURATION, _FR_MEETING_DURATION, _BARE_DURATION)
             for m in pattern.finditer(text)]
    # The longest match only: « 45-minute » inside « 45-minute security review ».
    durations = {' '.join(text[a:b].split()) for a, b in spans
                 if not any(c <= a and b <= d and (c, d) != (a, b) for c, d in spans)}
    slots = {m.group(0).strip() for m in _SLOT_DATE.finditer(text)}
    slots |= {m.group(0).strip() for m in _SLOT_TIME.finditer(text)}
    return {'durations': sorted(durations), 'slots': sorted(slots),
            'agreement': bool(_AGREEMENT.search(text))}


def closing_sober(parsed):
    found = closing_findings(parsed)
    return not found['durations'] and not found['slots'] and found['agreement']


def readability(parsed, max_words=PREP_CALL_LINE_MAX_WORDS):
    """The items of the plan's sections (every text but the context, the refs,
    the labels): {'items', 'over': [(path, words)], 'over_share', 'mean_words'}."""
    items = [(path, len(text.split())) for path, text in texts(prose(parsed))
             if path != 'context' and text.strip()]
    if not items:
        return {'items': 0, 'over': [], 'over_share': None, 'mean_words': None}
    over = [(path, words) for path, words in items if words > max_words]
    return {'items': len(items), 'over': over,
            'over_share': round(len(over) / len(items), 3),
            'mean_words': round(sum(w for _p, w in items) / len(items), 1)}


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
    metrics['invented_slots'] = invented_slots(parsed, user_prompt)          # G13d
    metrics['findings_context'] = locate_findings(
        parsed, metrics['invented_numbers'], metrics['invented_names']) + metrics['invented_slots']
    if kind == 'PLAN':
        metrics.update({
            'participants_without_angle': participants_covered(parsed, expected['participants']),
            'plans_ok': plans_ok(parsed),
            'opening_missing': opening_missing(parsed),
            'discovery_covers_dh': discovery_covers_dh(parsed, expected.get('dh_missing_any_of')),
            'campaign_diagnostic_ok': campaign_diagnostic_ok(parsed, expected['campaign_diagnostic']),
            'closing_findings': closing_findings(parsed),                  # G13f
            'readability': readability(parsed),
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
    ('slots', 'aucun créneau inventé'),
    ('participants', 'chaque participant a un angle'),
    ('plans', 'plans A/B/C ≤ 3'),
    ('opening', 'ouverture en 5 parties'),
    ('discovery', 'découverte = info manquante DH'),
    ('campaign', 'campaign_diagnostic au bon cas'),
    ('closing', 'closing sobre (accord, ni durée ni date)'),
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
        # Older records (before G13d) have no slot metric: recomputed by --rescore.
        'slots': not metrics.get('invented_slots'),
        'participants': not metrics['participants_without_angle'] if plan else None,
        'plans': metrics['plans_ok'] if plan else None,
        'opening': not metrics['opening_missing'] if plan else None,
        'discovery': metrics['discovery_covers_dh'] if plan else None,
        'campaign': metrics['campaign_diagnostic_ok'] if plan else None,
        # Older records (before G13f) have no closing metric: recomputed by --rescore.
        'closing': (
            (not metrics['closing_findings']['durations'] and not metrics['closing_findings']['slots']
             and metrics['closing_findings']['agreement'])
            if plan and metrics.get('closing_findings') is not None else None
        ),
        'language': not metrics['wrong_languages'] if not plan else None,
        'subject': metrics['subject_ok'] if not plan else None,
    }
