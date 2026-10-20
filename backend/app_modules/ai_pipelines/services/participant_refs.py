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

import unicodedata


__all__ = [
    'ordered_participants',
    'resolve_participant_by_name',
    'stated_name_matches_contact',
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
    Does a name as written by the LLM designate THAT contact? (TD-279; the
    word match resolve_participant_by_name relies on, also used by the
    evals/td279 measurement script.)

    Simple word match, no AI: the stated name matches when one of its words
    (normalised: lowercase, no accents) equals the contact's first name OR
    last name -- a multi-word first / last name ("Le Gall") must appear as
    consecutive words. A missing / blank stated name has nothing to compare
    and matches (nothing to compare).

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

    Scope: ordered_participants() (tenant AND account filtered). Same word match as stated_name_matches_contact. Never a guess:
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
