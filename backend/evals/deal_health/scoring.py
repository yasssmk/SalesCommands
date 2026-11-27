# backend/evals/deal_health/scoring.py
"""
Deal health evaluation — the automatic checks of ONE recorded call (sprint
« Deal health v2 », step 7). Pure functions of the recorded data: shared by
a run and by --rescore (the evals/next_steps/scoring.py pattern). NOT
product code.

Checks (README.md, « Contrôles automatiques », documents each heuristic):

  schema_errors                — the answer against DEAL_HEALTH_RESPONSE_SCHEMA
                                 (the keywords it uses: type, properties,
                                 required, additionalProperties: false,
                                 items, enum);
  last_names_found             — first names only: a planted last name (seed)
                                 in the prompt or in the output;
  invented_numbers             — a number of the output absent from the input;
  invented_names               — a name-like word (client, reference, product)
                                 of the output absent from the input;
  guardrail_leaks              — a guard-rail phrase in the rendered text
                                 (constants.DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES);
  rhetoric_labels              — ethos / pathos / logos (constants);
  rep_tasks_in_top_arguments   — an argument that is a rep TASK (an action
                                 verb at its head), not a need / value;
  missing_info_found           — the planted missing info, at its level;
  step_ok                      — estimated step = the expected real step;
  found_in_output              — keywords of the hidden objection / the
                                 decision-maker somewhere in the output;
  bant_ok                      — the expected BANT statuses (when given);
  summary_structured           — the summary's « What is won / What blocks /
                                 What comes next » (prompt v2.2, informative).
"""

import re
import unicodedata

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES,
    DEAL_HEALTH_RHETORIC_LABELS,
)
from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v2 import (
    DEAL_HEALTH_RESPONSE_SCHEMA,
)


# =============================================================================
# TEXT HELPERS
# =============================================================================

def _fold(text):
    """Lower case, no accents."""
    text = unicodedata.normalize('NFKD', str(text or ''))
    return ''.join(c for c in text if not unicodedata.combining(c)).lower()


def texts(value, path=''):
    """Every (path, string) of a JSON value — the rendered text of an answer."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from texts(item, f'{path}.{key}' if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from texts(item, f'{path}[{index}]')


def _all_text(output):
    return '\n'.join(text for _path, text in texts(output))


# =============================================================================
# SCHEMA
# =============================================================================

_JSON_TYPES = {
    'object': dict, 'array': list, 'string': str, 'boolean': bool,
    'integer': int, 'number': (int, float), 'null': type(None),
}


def _validate(value, schema, path, errors):
    # anyOf (a nullable object — the Game Plan's campaign_diagnostic, G13):
    # valid when one branch is; the deal-health schema has none.
    if 'anyOf' in schema:
        branches = []
        for branch in schema['anyOf']:
            branch_errors = []
            _validate(value, branch, path, branch_errors)
            if not branch_errors:
                return
            branches.append(branch_errors)
        errors.extend(min(branches, key=len))
        return
    expected = schema.get('type')
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        ok = any(
            isinstance(value, _JSON_TYPES[t]) and not (t in ('integer', 'number') and isinstance(value, bool))
            for t in types
        )
        if not ok:
            errors.append(f'{path or "$"}: expected {expected}, got {type(value).__name__}')
            return
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path or "$"}: {value!r} not in enum')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for key in schema.get('required', []):
            if key not in value:
                errors.append(f'{path or "$"}: missing required {key}')
        if schema.get('additionalProperties') is False:
            for key in value:
                if key not in props:
                    errors.append(f'{path or "$"}: unexpected {key}')
        for key, item in value.items():
            if key in props:
                _validate(item, props[key], f'{path}.{key}' if path else key, errors)
    if isinstance(value, list) and 'items' in schema:
        for index, item in enumerate(value):
            _validate(item, schema['items'], f'{path}[{index}]', errors)


def schema_errors(parsed, schema=None):
    """The answer against a strict schema (default: the deal health v2's;
    the Game Plan eval passes its own, G13); [] when valid."""
    if not isinstance(parsed, dict):
        return ['$: no JSON object']
    errors = []
    _validate(parsed, (schema or DEAL_HEALTH_RESPONSE_SCHEMA)['schema'], '', errors)
    return errors


# =============================================================================
# FIRST NAMES ONLY
# =============================================================================

def last_names_found(text, last_names):
    """The planted last names (seed) present in `text` (whole words, no case
    or accent): the LLM is given first names only (services/llm_people)."""
    folded = _fold(text)
    return [name for name in last_names
            if re.search(rf'(?<![a-z]){re.escape(_fold(name))}(?![a-z])', folded)]


# =============================================================================
# NOTHING INVENTED: numbers, names
# =============================================================================

# A number: digits with optional thousand / decimal separators. A digit glued
# to letters (P1, S2, v2, 2027Q1) is a label, not a quantity.
_NUMBER = re.compile(r'(?<![A-Za-z0-9])\d[\d.,   ]*\d(?![A-Za-z0-9])|(?<![A-Za-z0-9])\d(?![A-Za-z0-9])')


def _numbers(text):
    found = set()
    for match in _NUMBER.findall(text or ''):
        digits = re.sub(r'[.,   ]', '', match)
        digits = digits.lstrip('0') or '0'
        found.add(digits)
    return found


def invented_numbers(output, input_text):
    """The numbers of the output's text absent from the input (separators
    ignored: 48 000 = 48,000 = 48000). Structural integers of the answer
    (evidence_scope.validated_signals_count) are not text and not checked."""
    known = _numbers(input_text)
    return sorted(n for n in _numbers(_all_text(output)) if n not in known)


# Name-like words that are vocabulary, not names: the sales and schema
# vocabulary the answer uses legitimately, the steps, the levels.
_NAME_ALLOWLIST = {
    'i', 'a', 'an', 'the', 'bant', 'it', 'unknown', 'ceo', 'cfo', 'cto', 'cio', 'coo', 'daf', 'dsi',
    'roi', 'kpi', 'erp', 'crm', 'saas', 'api', 'sso', 'rfp', 'poc', 'q1', 'q2', 'q3', 'q4',
    'qualification', 'technical', 'fit', 'solution', 'validation', 'business', 'case', 'closing',
    'department', 'contact', 'game', 'plan', 'finance', 'operations', 'procurement', 'legal',
    'security', 'sales', 'marketing', 'hr', 'ops', 'it', 'gdpr', 'soc', 'iso',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'january', 'february', 'march',
    'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
    'based', 'captured', 'evidence',
}

_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'’-]*")

# The CODE fields of the answer (enums and machine codes such as
# rigidity FIRM, theme OPS:TIME, a BCP-47 language): not prose, not scanned.
_CODE_FIELDS = {
    'key', 'status', 'kind', 'dimension', 'theme', 'related_theme', 'rigidity',
    'level', 'step', 'conviction_state', 'communication_language',
}


# The English possessive ('s, ’s, and the bare apostrophe of « James' »):
# removed before comparing — « Arthur's » is Arthur, not a new name (7b).
_POSSESSIVE = re.compile(r"(?:['’]s|['’])$", re.IGNORECASE)


def _without_possessive(word):
    return _POSSESSIVE.sub('', word)


def _field(path):
    return re.sub(r'\[\d+\]', '', path).rsplit('.', 1)[-1]


def invented_names(output, input_text):
    """Name-like words of the output absent from the input: a capitalised
    word that does NOT open a sentence (or a word with an inner capital /
    all capitals of 3+ letters), unknown to the input (no case, no accent)
    and outside the vocabulary allowlist, its English possessive removed
    first (« Arthur's », « Priya’s » are Arthur and Priya); the code fields
    (_CODE_FIELDS) are not scanned. A heuristic: it flags an invented
    customer, reference, competitor or product name (« Contoso »); the
    findings are listed in the report for review."""
    known = set(_fold(w) for w in _WORD.findall(input_text or ''))
    found = set()
    for path, text in texts(output):
        if _field(path) in _CODE_FIELDS:
            continue
        for sentence in re.split(r'(?<=[.!?:;])\s+|\n+', text):
            words = _WORD.findall(sentence)
            for index, word in enumerate(words):
                inner_capital = any(c.isupper() for c in word[1:])
                capitalised = word[0].isupper() and index > 0
                if not (capitalised or (inner_capital and len(word) >= 3)):
                    continue
                name = _without_possessive(word).strip("'’-")
                folded = _fold(name)
                if not folded or folded in known or folded in _NAME_ALLOWLIST:
                    continue
                found.add(name)
    return sorted(found)


# =============================================================================
# TONE: guard rails, rhetoric, arguments
# =============================================================================

def guardrail_leaks(output):
    """The guard-rail phrases (constants) found in the rendered text: path + phrase."""
    found = []
    for path, text in texts(output):
        lowered = _fold(text)
        found.extend(f'{path}: {phrase}' for phrase in DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES
                     if phrase in lowered)
    return found


def rhetoric_labels(output):
    """ethos / pathos / logos (whole words) in the rendered text."""
    found = []
    for path, text in texts(output):
        for label in DEAL_HEALTH_RHETORIC_LABELS:
            if re.search(rf'(?<![a-z]){label}(?![a-z])', _fold(text)):
                found.append(f'{path}: {label}')
    return found


# A rep TASK opens on an action verb (imperative / infinitive / -ing): the
# list of verbs a rep's to-do starts with. An argument is a need, a value, a
# benefit — a noun phrase. Documented heuristic (README.md).
REP_TASK_VERBS = (
    'build', 'send', 'schedule', 'prepare', 'organise', 'organize', 'call', 'follow',
    'draft', 'set', 'book', 'arrange', 'contact', 'ask', 'meet', 'present', 'share',
    'propose', 'create', 'write', 'plan', 'run', 'deliver', 'email', 'invite',
    'confirm', 'get', 'reach', 'push', 'secure', 'demo', 'pitch',
)
_ARGUMENT_FIELDS = ('need', 'value', 'benefit', 'advantage', 'feature')


def _is_task(text):
    first = _fold(text).strip().split(' ', 1)[0].strip(':,.;-')
    # The imperative ("Build …") or the gerund ("Building …") of a task verb;
    # a plural noun ("Plans adjusted …") is not a task: -s is not stripped.
    stem = re.sub(r'ing$', '', first)
    return first in REP_TASK_VERBS or stem in REP_TASK_VERBS


def rep_tasks_in_top_arguments(parsed):
    """The argument fields of top_arguments that read as a rep task."""
    found = []
    for t_index, target in enumerate((parsed or {}).get('top_arguments') or []):
        for a_index, argument in enumerate((target or {}).get('arguments') or []):
            for field in _ARGUMENT_FIELDS:
                text = (argument or {}).get(field) or ''
                if text and _is_task(text):
                    found.append(f'top_arguments[{t_index}].arguments[{a_index}].{field}: {text}')
    return found


# =============================================================================
# EXPECTED TRUTH (expected.json)
# =============================================================================

def _has_keyword(text, keywords):
    folded = _fold(text)
    return any(_fold(k) in folded for k in keywords)


def missing_info_found(parsed, planted):
    """The planted missing info: an entry of missing_info whose item / why /
    question carries one of `any_of`, AT its `level`. `planted` is one
    {level, any_of}, or a list of alternatives (7b: a gap the clarified grid
    files at two levels — a company constraint at BUSINESS, the tool's
    integration requirements at DEPARTMENT); one match is enough."""
    alternatives = planted if isinstance(planted, list) else [planted]
    for entry in (parsed or {}).get('missing_info') or []:
        text = ' '.join(str(entry.get(k) or '') for k in ('item', 'why_it_matters', 'suggested_question'))
        for alternative in alternatives:
            if entry.get('level') == alternative['level'] and _has_keyword(text, alternative['any_of']):
                return True
    return False


def planted_alternatives(planted):
    """The alternatives of a planted missing info (one dict or a list)."""
    return planted if isinstance(planted, list) else [planted]


def step_ok(parsed, expected_step):
    """The estimated step equals the expected real step."""
    return ((parsed or {}).get('estimated_step') or {}).get('step') == expected_step


def bant_ok(parsed, expected_bant):
    """Each expected BANT letter has the expected status (None: not expected)."""
    if not expected_bant:
        return None
    bant = (parsed or {}).get('bant') or {}
    return all((bant.get(letter) or {}).get('status') == status
               for letter, status in expected_bant.items())


# Prompt v2.2 (7b): the summary's three labelled parts, in this order.
SUMMARY_PARTS = ('what is won', 'what blocks', 'what comes next')


def summary_structured(parsed):
    """The summary follows « What is won / What blocks / What comes next »
    (the three labels, in this order — informative)."""
    summary = _fold((parsed or {}).get('summary'))
    positions = [summary.find(part) for part in SUMMARY_PARTS]
    return all(p >= 0 for p in positions) and positions == sorted(positions)


def found_in_output(parsed, keywords):
    """One of the keywords anywhere in the rendered text (informative)."""
    return _has_keyword(_all_text(parsed or {}), keywords)


# =============================================================================
# ONE CALL
# =============================================================================

def score_call(*, parsed, prompt, expected, meta=None, error_type=None):
    """The metrics of one recorded call (a run and --rescore)."""
    meta = meta or {}
    metrics = {
        'error_type': error_type or '',
        'duration_ms': meta.get('duration_ms'),
        'input_tokens': meta.get('input_tokens'),
        'output_tokens': meta.get('output_tokens'),
        'reasoning_tokens': meta.get('reasoning_tokens'),
        'prompt_chars': len(prompt or ''),
        'input_truncated': bool(meta.get('input_truncation')),
        'last_names_in_prompt': last_names_found(prompt, expected['planted_last_names']),
    }
    if parsed is None:
        return {**metrics, 'answered': False}
    return {
        **metrics,
        'answered': True,
        'schema_errors': schema_errors(parsed),
        'last_names_in_output': last_names_found(
            '\n'.join(t for _p, t in texts(parsed)), expected['planted_last_names']),
        'invented_numbers': invented_numbers(parsed, prompt),
        'invented_names': invented_names(parsed, prompt),
        'guardrail_leaks': guardrail_leaks(parsed),
        'rhetoric_labels': rhetoric_labels(parsed),
        'rep_tasks_in_top_arguments': rep_tasks_in_top_arguments(parsed),
        'missing_info_found': missing_info_found(parsed, expected['missing_info']),
        'estimated_step': ((parsed.get('estimated_step') or {}).get('step')),
        'step_ok': step_ok(parsed, expected['real_step']),
        'objection_found': found_in_output(parsed, expected['hidden_objection']['any_of']),
        'decision_maker_found': found_in_output(parsed, [expected['decision_maker']]),
        'bant_ok': bant_ok(parsed, expected.get('bant')),
        'summary_structured': summary_structured(parsed),
    }


# The pass / fail checks of the recap (True = passed), in report order.
CHECK_LABELS = (
    ('schema', 'schéma valide'),
    ('first_names', 'prénoms seulement'),
    ('numbers', 'aucun nombre inventé'),
    ('names', 'aucun nom inventé'),
    ('missing_info', 'info manquante (niveau)'),
    ('step', 'étape réelle'),
    ('guardrails', 'aucune fuite de garde-fou'),
    ('rhetoric', 'aucun ethos/pathos/logos'),
    ('arguments', 'top_arguments sans tâche'),
)


def checks(metrics):
    """{check: True / False / None (no answer)} from the metrics of a call."""
    if not metrics.get('answered'):
        return {key: None for key, _label in CHECK_LABELS}
    return {
        'schema': not metrics['schema_errors'],
        'first_names': not metrics['last_names_in_output'] and not metrics['last_names_in_prompt'],
        'numbers': not metrics['invented_numbers'],
        'names': not metrics['invented_names'],
        'missing_info': metrics['missing_info_found'],
        'step': metrics['step_ok'],
        'guardrails': not metrics['guardrail_leaks'],
        'rhetoric': not metrics['rhetoric_labels'],
        'arguments': not metrics['rep_tasks_in_top_arguments'],
    }
