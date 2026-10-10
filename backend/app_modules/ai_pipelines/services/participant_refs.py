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


__all__ = [
    'PARTICIPANT_REF_PREFIX',
    'format_participant_ref',
    'ordered_participants',
    'resolve_participant_ref',
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
