# app_modules/ai_pipelines/services/participant_refs.py
"""
Participant references shared by the context layer and the extractors.

The transcript_signals context layer lists the activity's participants,
each prefixed with a short reference ("P1", "P2", ...). An extraction
stage may return such a reference to attribute a signal to the
participant who voiced it (Blocker `raised_by` -- Objection S3). The
server resolves the reference back to a Contact HERE, against the very
same ordered list -- never by name, never guessed.

Why a shared module (mirror of safety_filter.py)
------------------------------------------------
The numbering MUST be identical when it is rendered (context.py) and
when it is resolved (the extractor): ordered_participants() is the
SINGLE source of that order, and PARTICIPANT_REF_PREFIX the single
definition of the reference format. NextStep.suggested_contacts (TD-7)
is expected to reuse this module.

Tenant / account guard
----------------------
A participant is NOT guaranteed to belong to the activity's account
(activities/services/activity_creation_service.py binds contacts on the
tenant only), and the pipeline creates signals through
SignalManager.create(), which bypasses the serializer FK scope guard.
ordered_participants() therefore filters on the activity's client_id
AND account_id: a contact outside that scope is never listed, never
numbered, never resolvable.

Tolerance (mirror of the department resolver in
transcript_signal_extractor.py)
--------------------------------
Only an exact "P<n>" within the list resolves. Anything else (None,
a name, an int, "p 1", an out-of-range index) -> None. The caller
decides what to do with None (the Blocker builder keeps the signal
without a contact).
"""

import re
import unicodedata


__all__ = [
    'PARTICIPANT_REF_PREFIX',
    'format_participant_ref',
    'ordered_participants',
    'resolve_participant_by_name',
    'resolve_participant_ref',
    'stated_name_matches_contact',
]


# The reference format: PARTICIPANT_REF_PREFIX + 1-based index ("P1").
PARTICIPANT_REF_PREFIX = 'P'

_REF_PATTERN = re.compile(rf'^{re.escape(PARTICIPANT_REF_PREFIX)}([1-9][0-9]*)$')


def format_participant_ref(index):
    """Reference of the participant at the 0-based `index` ("P1" for 0)."""
    return f'{PARTICIPANT_REF_PREFIX}{index + 1}'


def ordered_participants(activity):
    """
    The activity's participants, filtered on its tenant AND account,
    ordered last_name, first_name, id (id breaks homonym ties so the
    numbering is deterministic).

    Returns:
        list[Contact] -- possibly empty.
    """
    return list(
        activity.contacts
        .filter(client_id=activity.client_id, account_id=activity.account_id)
        .select_related('standard_department')
        .order_by('last_name', 'first_name', 'id')
    )


def resolve_participant_ref(ref, activity):
    """
    Resolve a participant reference ("P<n>") to a Contact of the activity.

    Returns:
        Contact | None -- None for anything but a valid in-range reference.
    """
    if not isinstance(ref, str):
        return None
    match = _REF_PATTERN.match(ref)
    if not match:
        return None
    index = int(match.group(1)) - 1
    participants = ordered_participants(activity)
    if index >= len(participants):
        return None
    return participants[index]


# =============================================================================
# NAMES AS WRITTEN (TD-279)
# =============================================================================

def _normalize_person_name(value):
    """Lowercase, accents stripped, whitespace collapsed ("  Hélène " -> "helene")."""
    decomposed = unicodedata.normalize('NFKD', str(value))
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ' '.join(stripped.lower().split())


def _matched_name_parts(stated, contact):
    """
    How many of the contact's first / last name appear in the normalised
    stated name, each as one word or as consecutive words ("Le Gall").
    """
    padded = f' {stated} '
    count = 0
    for part in (contact.first_name, contact.last_name):
        name = _normalize_person_name(part or '')
        if name and f' {name} ' in padded:
            count += 1
    return count


def stated_name_matches_contact(stated_name, contact):
    """
    TD-279 guard: does a name as written by the LLM designate THAT contact?

    Simple word match, no AI: the stated name matches when one of its words
    (normalised: lowercase, no accents) equals the contact's first name OR
    last name -- a multi-word first / last name ("Le Gall") must appear as
    consecutive words. A missing / blank stated name has nothing to compare
    and matches (a participant reference is then kept).

    Returns:
        bool -- False means the name describes ANOTHER person.
    """
    if not isinstance(stated_name, str):
        return True
    stated = _normalize_person_name(stated_name)
    if not stated:
        return True
    return _matched_name_parts(stated, contact) > 0


def resolve_participant_by_name(stated_name, activity):
    """
    TD-279 B4a: link a name as written in the transcript (People full_name,
    Blocker raised_by_name) to a contact REGISTERED on the activity.

    Same scope as the references: ordered_participants() (tenant AND account
    filtered). Same word match as stated_name_matches_contact. Never a guess:
      * missing / blank name -> None;
      * no participant matches -> None;
      * several participants match: the one matching the MOST name parts
        (first AND last name) wins only if it is the only one -- two "Marie"
        and the name "Marie" -> None; "Marie Dupont" -> Marie Dupont.

    Returns:
        Contact | None
    """
    if not isinstance(stated_name, str):
        return None
    stated = _normalize_person_name(stated_name)
    if not stated:
        return None

    scored = [
        (_matched_name_parts(stated, contact), contact)
        for contact in ordered_participants(activity)
    ]
    best = max((score for score, _ in scored), default=0)
    if best == 0:
        return None
    winners = [contact for score, contact in scored if score == best]
    return winners[0] if len(winners) == 1 else None
