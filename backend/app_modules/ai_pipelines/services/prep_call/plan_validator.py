# app_modules/ai_pipelines/services/prep_call/plan_validator.py
"""
Server-side validation of a Game Plan v2 (sprint 2 Game Plan, G10) — the
deal health v2 writer's pattern (services/deal_health_writer.py _validate_v2
and apply_profiles):

  * the structure of PREP_CALL_OUTLINE_SCHEMA, the bounds (plans A / B / C,
    3 at most, in order; PREP_CALL_ARGUMENTS_MAX arguments per participant);
  * REFUSED (PromptParseError — nothing written, the run is a PARSE_ERROR):
    a classical rhetoric label (PREP_CALL_RHETORIC_LABELS, whole word, any
    case) or a last name of the roster (llm_people.roster_last_names)
    anywhere in the text;
  * every `ref` (participants, argumentation) is resolved server side
    against the activity's roster (G4, ActivityRoster.participant_for_label):
    an unknown ref — not a participant's exact label — is DROPPED, never
    guessed; a participant designated by more than one entry of the same
    list is ambiguous: all its entries are dropped. Both traced;
  * campaign_diagnostic is null unless the pack carries a campaign block
    (a campaign activity outside a cycle, G8).

validate_messages (G11) applies the SAME refusals to the AI message, and
resolves each message's ref against the RECIPIENTS of the pack (exact
label): unknown / repeated -> dropped, a language other than the
recipient's -> dropped, a recipient left without message -> traced. The
subject is required for an email, null for a LinkedIn message.
"""

import copy
import re

from app_modules.ai_pipelines.constants import (
    PREP_CALL_ARGUMENTS_MAX,
    PREP_CALL_PLAN_LABELS,
    PREP_CALL_RHETORIC_LABELS,
)
from app_modules.ai_pipelines.prompts.base import PromptParseError
from app_modules.ai_pipelines.services.participant_refs import names_appearing_in_text


__all__ = ['validate_messages', 'validate_plan']

_RHETORIC_RE = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in PREP_CALL_RHETORIC_LABELS) + r')\b', re.IGNORECASE,
)

_OPENING_KEYS = ('objective', 'time', 'client_agenda', 'our_agenda', 'expected_outcome')
_CLOSING_KEYS = ('next_step', 'with_whom', 'when', 'keep_control')
_CONVICTION_KEYS = ('needs_and_urgency', 'credibility', 'fit_and_value')
_ARGUMENT_KEYS = ('benefit', 'advantage', 'feature')
# The lists whose entries name a participant by `ref`.
_REF_LISTS = ('participants', 'argumentation')


def validate_plan(parsed, *, people, last_names, has_campaign):
    """
    Validate a Game Plan v2 answer and return what is persisted.

    Args:
        parsed:       the JSON answer.
        people:       ActivityRoster of the activity (None: every ref unknown).
        last_names:   frozenset of normalised last names (never written).
        has_campaign: the pack carries a campaign block.

    Returns:
        (plan, counts) — plan: a copy with the dropped refs removed and
        campaign_diagnostic forced to None without a campaign; counts:
        {'unknown_refs': [...], 'ambiguous_refs': [...]}.

    Raises:
        PromptParseError — structure, a rhetoric label, a last name.
    """
    _check_structure(parsed)
    _refuse_labels_and_last_names(parsed, last_names)

    plan = copy.deepcopy(parsed)
    counts = {'unknown_refs': [], 'ambiguous_refs': []}
    for key in _REF_LISTS:
        plan[key] = _resolved(plan[key], people, counts)
    if not has_campaign:
        plan['campaign_diagnostic'] = None
    return plan, counts


def validate_messages(parsed, *, recipients, last_names, is_email):
    """
    Validate an AI-message answer (G11) and return what is persisted.

    Args:
        parsed:     the JSON answer ({'messages': [...]}).
        recipients: the pack's recipients [{'ref', 'language', ...}].
        last_names: frozenset of normalised last names (never written).
        is_email:   an email (subject required) or a LinkedIn message
                    (subject null).

    Returns:
        (messages, counts) — messages: {'messages': [...]} in the recipients'
        order, one per recipient at most; counts: {'unknown_refs',
        'ambiguous_refs', 'wrong_language_refs', 'missing_refs'}.

    Raises:
        PromptParseError — structure, a rhetoric label, a last name.
    """
    if not isinstance(parsed, dict) or not isinstance(parsed.get('messages'), list):
        raise PromptParseError('Missing or invalid "messages" (expected list).')
    for message in parsed['messages']:
        if not isinstance(message, dict):
            raise PromptParseError('Invalid "messages" entry.')
        for key in ('ref', 'language', 'body'):
            _require_str(message, key, 'messages.')
        if not message['body'].strip():
            raise PromptParseError('Empty "messages.body".')
        if is_email and (not isinstance(message.get('subject'), str) or not message['subject'].strip()):
            raise PromptParseError('Missing "messages.subject" for an email.')
    _refuse_labels_and_last_names(parsed, last_names)

    expected = {r['ref']: r for r in recipients}
    counts = {'unknown_refs': [], 'ambiguous_refs': [], 'wrong_language_refs': [], 'missing_refs': []}
    per_ref = {}
    for message in parsed['messages']:
        per_ref[message['ref']] = per_ref.get(message['ref'], 0) + 1
    kept = {}
    for message in parsed['messages']:
        ref = message['ref']
        recipient = expected.get(ref)
        if recipient is None:
            counts['unknown_refs'].append(ref)
        elif per_ref[ref] > 1:
            counts['ambiguous_refs'].append(ref)
        elif message['language'].lower() != recipient['language'].lower():
            counts['wrong_language_refs'].append(ref)
        else:
            kept[ref] = {
                'ref': ref,
                'language': recipient['language'],
                # PROFILE / EXCHANGES / DEFAULT / OVERRIDE — the UI warns on
                # DEFAULT (no known language for that person).
                'language_source': recipient['source'],
                'subject': message['subject'] if is_email else None,
                'body': message['body'],
            }
    counts['missing_refs'] = [r['ref'] for r in recipients if r['ref'] not in kept]
    return {'messages': [kept[r['ref']] for r in recipients if r['ref'] in kept]}, counts


def _refuse_labels_and_last_names(parsed, last_names):
    """THE refusals shared by the plan and the message (G10 / G11)."""
    texts = list(_strings(parsed))
    if any(_RHETORIC_RE.search(text) for text in texts):
        raise PromptParseError('The Game Plan names a classical rhetoric label.')
    written = names_appearing_in_text(last_names, '\n'.join(texts))
    if written:
        # The names themselves are not logged (the run's error_message).
        raise PromptParseError(f'The Game Plan writes {len(written)} last name(s).')


def _resolved(entries, people, counts):
    """Keep the entries whose ref designates ONE participant, once."""
    resolved = []
    for entry in entries:
        participant = people.participant_for_label(entry['ref']) if people is not None else None
        if participant is None:
            counts['unknown_refs'].append(entry['ref'])
            continue
        resolved.append((participant['identity'], entry))
    per_person = {}
    for identity, _entry in resolved:
        per_person[identity] = per_person.get(identity, 0) + 1
    kept = []
    for identity, entry in resolved:
        if per_person[identity] > 1:
            counts['ambiguous_refs'].append(entry['ref'])
            continue
        kept.append(entry)
    return kept


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _require_str(container, key, where):
    if not isinstance(container.get(key), str):
        raise PromptParseError(f'Missing or invalid "{where}{key}" (expected text).')


def _require_obj(container, key):
    value = container.get(key)
    if not isinstance(value, dict):
        raise PromptParseError(f'Missing or invalid "{key}" (expected object).')
    return value


def _require_list(container, key, where=''):
    value = container.get(key)
    if not isinstance(value, list):
        raise PromptParseError(f'Missing or invalid "{where}{key}" (expected list).')
    return value


def _check_structure(parsed):
    if not isinstance(parsed, dict):
        raise PromptParseError('The Game Plan must be a JSON object.')

    if not isinstance(parsed.get('context'), str) or not parsed['context'].strip():
        raise PromptParseError('Missing or invalid "context" (expected text).')

    plans = _require_list(_require_obj(parsed, 'objective'), 'plans', 'objective.')
    labels = [p.get('label') if isinstance(p, dict) else None for p in plans]
    if not plans or labels != list(PREP_CALL_PLAN_LABELS[:len(plans)]):
        raise PromptParseError(
            f'Invalid "objective.plans": 1 to {len(PREP_CALL_PLAN_LABELS)} plans, '
            f'labelled {" / ".join(PREP_CALL_PLAN_LABELS)} in that order.'
        )
    for plan in plans:
        _require_str(plan, 'goal', 'objective.plans.')
        _require_str(plan, 'success_criteria', 'objective.plans.')

    if not all(isinstance(e, str) for e in _require_list(parsed, 'client_expectations')):
        raise PromptParseError('Invalid "client_expectations" (expected a list of text).')

    opening = _require_obj(parsed, 'opening')
    for key in _OPENING_KEYS:
        _require_str(opening, key, 'opening.')

    discovery = _require_obj(parsed, 'discovery')
    for item in _require_list(discovery, 'missing_info', 'discovery.'):
        if not isinstance(item, dict):
            raise PromptParseError('Invalid "discovery.missing_info" entry.')
        _require_str(item, 'item', 'discovery.missing_info.')
        _require_str(item, 'question', 'discovery.missing_info.')
    conviction = discovery.get('conviction')
    if not isinstance(conviction, dict):
        raise PromptParseError('Missing or invalid "discovery.conviction" (expected object).')
    for axis in _CONVICTION_KEYS:
        reading = conviction.get(axis)
        if not isinstance(reading, dict):
            raise PromptParseError(f'Missing or invalid "discovery.conviction.{axis}".')
        _require_str(reading, 'reading', f'discovery.conviction.{axis}.')
        _require_str(reading, 'question', f'discovery.conviction.{axis}.')

    for target in _require_list(parsed, 'argumentation'):
        if not isinstance(target, dict) or not isinstance(target.get('ref'), str):
            raise PromptParseError('Invalid "argumentation" entry (expected {ref, arguments}).')
        arguments = _require_list(target, 'arguments', 'argumentation.')
        if len(arguments) > PREP_CALL_ARGUMENTS_MAX:
            raise PromptParseError(
                f'Invalid "argumentation": at most {PREP_CALL_ARGUMENTS_MAX} arguments per participant.'
            )
        for argument in arguments:
            if not isinstance(argument, dict):
                raise PromptParseError('Invalid "argumentation.arguments" entry.')
            for key in _ARGUMENT_KEYS:
                _require_str(argument, key, 'argumentation.arguments.')

    closing = _require_obj(parsed, 'closing')
    for key in _CLOSING_KEYS:
        _require_str(closing, key, 'closing.')

    for pitch in _require_list(parsed, 'product_pitch'):
        if not isinstance(pitch, dict):
            raise PromptParseError('Invalid "product_pitch" entry.')
        _require_str(pitch, 'product', 'product_pitch.')
        _require_str(pitch, 'pitch', 'product_pitch.')

    for person in _require_list(parsed, 'participants'):
        if not isinstance(person, dict):
            raise PromptParseError('Invalid "participants" entry.')
        _require_str(person, 'ref', 'participants.')
        _require_str(person, 'angle', 'participants.')

    if 'campaign_diagnostic' not in parsed:
        raise PromptParseError('Missing "campaign_diagnostic" (an object or null).')
    diagnostic = parsed['campaign_diagnostic']
    if diagnostic is not None:
        if not isinstance(diagnostic, dict):
            raise PromptParseError('Invalid "campaign_diagnostic" (an object or null).')
        _require_str(diagnostic, 'reading', 'campaign_diagnostic.')
        _require_str(diagnostic, 'next_move', 'campaign_diagnostic.')
