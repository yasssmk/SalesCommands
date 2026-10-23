# app_modules/ai_pipelines/services/participant_refs.py
"""
Link a person NAMED in a transcript to a contact registered on the activity.

TD-279 B4b: the LLM no longer receives the activity's contacts nor picks a
participant reference ("P1", ...) -- it filled that slot even for a
registered contact who never spoke. It returns names as written (People
`full_name`, Blocker `raised_by_name`); the server links them HERE with
resolve_participant_by_name() -- a word match, never a guess. (The module
name is kept from the participant-reference era, Objection S3.)

Tenant / account guard
----------------------
A participant is NOT guaranteed to belong to the activity's account
(activities/services/activity_creation_service.py binds contacts on the
tenant only), and the pipeline creates signals through
SignalManager.create(), which bypasses the serializer FK scope guard.
ordered_participants() therefore filters on the activity's client_id
AND account_id: a contact outside that scope is never linked.
"""

import re
import unicodedata


__all__ = [
    'name_appears_in_text',
    'ordered_participants',
    'resolve_participant_by_name',
    'resolve_people_signal_by_name',
    'resolve_speaker_label',
]


def ordered_participants(activity):
    """
    The activity's participants, filtered on its tenant AND account,
    ordered last_name, first_name, id (deterministic order).

    Returns:
        list[Contact] -- possibly empty.
    """
    return list(
        activity.contacts
        .filter(client_id=activity.client_id, account_id=activity.account_id)
        .select_related('standard_department')
        .order_by('last_name', 'first_name', 'id')
    )


# =============================================================================
# NAMES AS WRITTEN (TD-279)
# =============================================================================

# Anything but letters / digits is a word boundary when a name is searched in
# free text (apostrophes included: "d'Isabelle" contains "Isabelle").
_NON_WORD_RE = re.compile(r'[\W_]+')


def _normalize_person_name(value):
    """Lowercase, accents stripped, whitespace collapsed ("  Hélène " -> "helene")."""
    decomposed = unicodedata.normalize('NFKD', str(value))
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ' '.join(stripped.lower().split())


def _matched_name_parts(stated, name_parts):
    """
    How many of the name parts (first name, last name) appear in the
    normalised stated name, each as one word or as consecutive words
    ("Le Gall").
    """
    padded = f' {stated} '
    count = 0
    for part in name_parts:
        name = _normalize_person_name(part or '')
        if name and f' {name} ' in padded:
            count += 1
    return count


def _contact_name_parts(contact):
    return (contact.first_name, contact.last_name)


def _written_name_parts(name):
    """A name as written ("Jean Le Gall", a speaker label) split into
    (first name, last name): the first word, then the rest."""
    words = str(name or '').split()
    return (words[0] if words else '', ' '.join(words[1:]))


def _best_unique_match(stated_name, candidates):
    """
    The candidate whose name parts best match the stated name -- the rule of
    resolve_participant_by_name, shared (TD-279 V): None when the name is
    missing / blank, when nothing matches, or when several candidates tie on
    the best score (never a guess).

    Simple word match, no AI: a name part (first or last name) matches when
    it appears in the stated name (normalised: lowercase, no accents) as a
    word -- a multi-word part ("Le Gall") as consecutive words.

    Args:
        candidates: iterable of (name_parts, value).
    """
    if not isinstance(stated_name, str):
        return None
    stated = _normalize_person_name(stated_name)
    if not stated:
        return None

    scored = [(_matched_name_parts(stated, parts), value) for parts, value in candidates]
    best = max((score for score, _ in scored), default=0)
    if best == 0:
        return None
    winners = [value for score, value in scored if score == best]
    return winners[0] if len(winners) == 1 else None


def resolve_participant_by_name(stated_name, activity):
    """
    TD-279 B4a: link a name as written in the transcript (People full_name,
    Blocker raised_by_name) to a contact REGISTERED on the activity.

    Scope: ordered_participants() (tenant AND account filtered). Word match
    of _best_unique_match (no AI). Never a guess:
      * missing / blank name -> None;
      * no participant matches -> None;
      * several participants match: the one matching the MOST name parts
        (first AND last name) wins only if it is the only one -- two "Marie"
        and the name "Marie" -> None; "Marie Dupont" -> Marie Dupont.

    Returns:
        Contact | None
    """
    return _best_unique_match(stated_name, [
        (_contact_name_parts(contact), contact)
        for contact in ordered_participants(activity)
    ])


def resolve_people_signal_by_name(stated_name, people_signals):
    """
    Sprint Next steps 3.4: the PeopleSignal a prospect name as written (a
    next step's suggested_people_names) designates, among `people_signals`
    (the caller scopes them) -- the SAME word rule (_best_unique_match),
    applied to IDENTITIES:

      * identity = the signal's contact when it has one, else its full name
        normalised (lowercase, no accents); an unnamed signal without contact
        is no identity;
      * several identities tie on the best score -> None (ambiguous: the
        name is kept as written); a first name alone therefore links only
        when one identity bears it;
      * the identity found -> its MOST RECENT signal (created_at, then id).

    Returns:
        PeopleSignal | None
    """
    identities = {}
    for signal in people_signals:
        if signal.target_contact_id:
            key = ('contact', signal.target_contact_id)
            parts = _contact_name_parts(signal.target_contact)
        else:
            name = _normalize_person_name(signal.full_name or '')
            if not name:
                continue
            key = ('name', name)
            parts = _written_name_parts(signal.full_name)
        identities.setdefault(key, (parts, []))[1].append(signal)

    key = _best_unique_match(stated_name, [
        (parts, key) for key, (parts, _signals) in identities.items()
    ])
    if key is None:
        return None
    return max(identities[key][1], key=lambda s: (s.created_at, str(s.pk)))


def resolve_speaker_label(stated_name, labels):
    """
    TD-279 V: the speaker label (transcript_text.TranscriptText.labels) a
    name as written designates -- the SAME rule as resolve_participant_by_name
    (a label is split first word / rest). None when not a speaker or
    ambiguous.
    """
    return _best_unique_match(stated_name, [
        (_written_name_parts(label), label) for label in labels
    ])


def name_appears_in_text(stated_name, text):
    """
    TD-279 V: does the text (a quote) contain the first or the last name of
    the name as written, as a word -- the SAME word match, punctuation
    ignored ("... avec Marc, notre DAF" contains "Marc")?
    """
    if not isinstance(stated_name, str):
        return False
    words = _normalize_person_name(_NON_WORD_RE.sub(' ', str(text or '')))
    return _matched_name_parts(words, _written_name_parts(stated_name)) > 0
