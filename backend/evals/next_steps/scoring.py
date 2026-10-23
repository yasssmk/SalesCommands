# backend/evals/next_steps/scoring.py
"""
Scoring of the next_steps eval (Sprint Next steps 3.0) — pure functions, no
database, no LLM. Shared by a run and --rescore (run_next_steps_eval.py) and
unit-tested (tests/evals/test_next_steps_scoring.py).

  * load_expected / validate_expected — the ground truth (expected.json);
  * normalize / keyword_in / matches  — the TOLERANT match of a next step
                                        with an expected item (README.md);
  * in_window                         — the date is in the item's window;
  * is_invented                       — the quote is NOT in the transcript
                                        (production rule: TranscriptText,
                                        the check a) of people_evidence.py);
  * prompt_leaks                      — the transcripts never leak into the
                                        prompt outside the transcript itself;
  * score_call                        — the metrics of one call.

A quote is checked as the server stores it: a speaker label of THIS
transcript copied at its head removed first (strip_speaker_label).
"""

import datetime
import json
import re
import unicodedata
from pathlib import Path

from app_modules.ai_pipelines.services.participant_refs import name_appears_in_text
from app_modules.ai_pipelines.services.transcript_text import TranscriptText


# The markers around the transcript in the next_steps request layer
# (prompts/next_steps/next_steps_v1.py).
TRANSCRIPT_START = '<<<TRANSCRIPT_START>>>'
TRANSCRIPT_END = '<<<TRANSCRIPT_END>>>'

# Fields added to NextStepSignal in Sprint Next steps 1.1, not emitted by the
# v1 prompt: counted on the RAW answer, shown N/A while the prompt is v1.
NEW_FIELDS = (
    'suggested_decision_step',      # étape
    'suggested_people_names',       # personnes (prospect)
    'suggested_internal_names',     # personnes (vendeur)
    'suggested_topics',             # sujets
    'suggested_success_criterion',  # critère
    'carried_by_prospect',
)
BASELINE_PROMPT_VERSIONS = ('v1',)

_ITEM_KEYS = {'id', 'transcript', 'required', 'label', 'match', 'expected_types',
              'date_window', 'carried_by_prospect'}


# =============================================================================
# GROUND TRUTH
# =============================================================================

def validate_expected(data):
    """Raise ValueError on a malformed ground truth; return it unchanged."""
    transcripts = data.get('transcripts') or {}
    seen = set()
    for item in data.get('items') or []:
        missing = _ITEM_KEYS - set(item)
        if missing:
            raise ValueError(f'item {item.get("id")}: missing {sorted(missing)}')
        if item['id'] in seen:
            raise ValueError(f'item {item["id"]}: duplicate id')
        seen.add(item['id'])
        if item['transcript'] not in transcripts:
            raise ValueError(f'item {item["id"]}: unknown transcript {item["transcript"]}')
        match = item['match']
        if not match.get('fields') or not match.get('all_of') or not all(match['all_of']):
            raise ValueError(f'item {item["id"]}: match needs fields and non-empty all_of groups')
        start, end = (datetime.date.fromisoformat(d) for d in item['date_window'])
        if start > end:
            raise ValueError(f'item {item["id"]}: empty date window')
    if not seen:
        raise ValueError('no expected item')
    return data


def load_expected(path):
    return validate_expected(json.loads(Path(path).read_text(encoding='utf-8')))


# =============================================================================
# TOLERANT MATCH
# =============================================================================

def normalize(text):
    """Lower case, no accents, every non-alphanumeric character -> one
    space ("SOC-2" -> "soc 2", "d'affaires" -> "d affaires")."""
    text = unicodedata.normalize('NFKD', str(text or '').lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^0-9a-z]+', ' ', text).split())


def keyword_in(keyword, normalized_text):
    """A WHOLE word / phrase, or a word PREFIX when the keyword ends with '*'
    ("rencontr*")."""
    prefix = keyword.endswith('*')
    words = normalize(keyword.rstrip('*'))
    if not words:
        return False
    pattern = r'(?<![0-9a-z])' + re.escape(words) + ('' if prefix else r'(?![0-9a-z])')
    return re.search(pattern, normalized_text) is not None


def matches(signal, item):
    """Each all_of group has a keyword in the item's fields, no none_of
    keyword is there. Type and date are NOT match criteria (measured apart)."""
    match = item['match']
    text = normalize(' '.join(str(signal.get(f) or '') for f in match['fields']))
    return (
        all(any(keyword_in(k, text) for k in group) for group in match['all_of'])
        and not any(keyword_in(k, text) for k in match.get('none_of') or [])
    )


def in_window(date, window):
    """True / False for an ISO date against [start, end] (inclusive); None
    when there is no (valid) date."""
    try:
        value = datetime.date.fromisoformat(str(date))
    except (TypeError, ValueError):
        return None
    start, end = (datetime.date.fromisoformat(d) for d in window)
    return start <= value <= end


# =============================================================================
# INVENTION / LEAK
# =============================================================================

def is_invented(quote, transcript_text):
    """The quote (speaker label of THIS transcript removed) is not in the
    transcript — the production rule (TranscriptText.contains)."""
    return not transcript_text.contains(transcript_text.strip_speaker_label(quote or ''))


def _ngrams(normalized_text, n):
    words = normalized_text.split()
    return {' '.join(words[i:i + n]) for i in range(len(words) - n + 1)}


def prompt_outside_transcript(user_prompt):
    """The user prompt without the transcript block itself."""
    start = user_prompt.find(TRANSCRIPT_START)
    end = user_prompt.find(TRANSCRIPT_END)
    if start == -1 or end == -1:
        return user_prompt
    return user_prompt[:start] + user_prompt[end + len(TRANSCRIPT_END):]


def prompt_leaks(system_prompt, user_prompt, transcripts, names, n):
    """
    The passages of the eval transcripts found in the prompt OUTSIDE the
    transcript block (point 7: no prompt example comes from them): every
    n-word sequence of a transcript, every listed name. [] = no leak.
    """
    outside = normalize(f'{system_prompt or ""} {prompt_outside_transcript(user_prompt or "")}')
    outside_grams = _ngrams(outside, n)
    leaks = set()
    for transcript in transcripts:
        leaks |= _ngrams(normalize(transcript), n) & outside_grams
    leaks |= {name for name in names if keyword_in(name, outside)}
    return sorted(leaks)


# =============================================================================
# ONE CALL
# =============================================================================

def _raw_signals(parsed):
    if isinstance(parsed, dict) and isinstance(parsed.get('signals'), list):
        return [s for s in parsed['signals'] if isinstance(s, dict)]
    return []


def _filled(value):
    return value not in (None, '', [], {})


def score_call(*, persisted, parsed, items, transcript, prompt_version, leaks=None):
    """
    The metrics of one call.

    Args:
        persisted:      list[dict] — the NextStepSignal rows the REAL pipeline
                        stored (safety filter + extractor applied), serialised;
                        what the rep sees. The expected items are scored here.
        parsed:         the raw parsed answer (inventions and new fields are
                        also counted on it).
        items:          the expected items of this transcript.
        transcript:     str.
        prompt_version: NEXT_STEPS_PROMPT_VERSION of the call.
        leaks:          prompt_leaks() of the prompt sent (None: not checked).
    """
    text = TranscriptText(transcript)
    raw = _raw_signals(parsed)
    baseline = prompt_version in BASELINE_PROMPT_VERSIONS
    metrics = {
        'emitted': len(raw),
        'persisted': len(persisted),
        'inventions': sum(1 for s in persisted if is_invented(s.get('source_quote'), text)),
        'inventions_raw': sum(1 for s in raw if is_invented(s.get('source_quote'), text)),
    }
    matched_any = set()
    duplicates = 0
    for item in items:
        hits = [i for i, s in enumerate(persisted) if matches(s, item)]
        matched_any.update(hits)
        duplicates += max(len(hits) - 1, 0)
        first = persisted[hits[0]] if hits else {}
        key = item['id']
        metrics[f'{key}_present'] = bool(hits)
        metrics[f'{key}_matches'] = len(hits)
        metrics[f'{key}_type_ok'] = (
            first.get('suggested_activity_type') in item['expected_types'] if hits else None
        )
        metrics[f'{key}_type'] = first.get('suggested_activity_type') or ''
        metrics[f'{key}_date'] = first.get('suggested_due_date') or ''
        metrics[f'{key}_date_in_window'] = (
            in_window(first.get('suggested_due_date'), item['date_window']) if hits else None
        )
        metrics[f'{key}_date_missing'] = bool(hits) and not first.get('suggested_due_date')
        # New field (1.1): N/A on the baseline prompt, which does not emit it.
        metrics[f'{key}_carried_ok'] = (
            None if baseline or not hits or first.get('carried_by_prospect') is None
            else first['carried_by_prospect'] == item['carried_by_prospect']
        )
    metrics['duplicates'] = duplicates
    titles = [normalize(s.get('suggested_title')) for s in persisted]
    metrics['duplicate_titles'] = len(titles) - len(set(titles))
    metrics['unmatched'] = len(persisted) - len(matched_any)
    for field in NEW_FIELDS:
        metrics[f'new_{field}'] = None if baseline else sum(
            1 for s in raw if _filled(s.get(field)))
    metrics['people_names_not_in_transcript'] = None if baseline else sum(
        1 for s in raw for name in (s.get('suggested_people_names') or [])
        if isinstance(name, str) and not name_appears_in_text(name, transcript)
    )
    metrics['prompt_leaks'] = None if leaks is None else len(leaks)
    return metrics
