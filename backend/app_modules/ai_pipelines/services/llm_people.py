# app_modules/ai_pipelines/services/llm_people.py
"""
THE point that decides how a PERSON is named to the LLM — sprint « Deal
health v2 », step 3a (PO rule: first names only, never a last name).

Every pipeline that names a person in a prompt goes through here:
  * first_name_of(person) -- the first name of a Contact, a Stakeholder
    (linked to a contact: the contact's; not converted: the first word of
    its full_name) or a PeopleSignal (its target contact, else the first word
    of its full_name). '' when the person has no name (department only).
  * LLMPeopleRoster -- the people of ONE prompt, so that two of them sharing a
    first name are told apart (amendment A4): a reference + first name +
    department, "S1 Marc (Finance)" / "S2 Marc (IT)" (formats in
    constants.py, the NEXT_STEPS_STEP_REF_FORMAT pattern). A person with a
    unique first name keeps the bare first name. The same person registered
    twice (a stakeholder who also raised a blocker) gets ONE label.

Out of scope (TD RGPD at the sprint closure): the names written INSIDE free
text (transcripts, notes) are not masked here.
"""

from ..constants import (
    LLM_PERSON_HOMONYM_LABEL_FORMAT,
    LLM_PERSON_HOMONYM_LABEL_NO_DEPT_FORMAT,
    LLM_PERSON_REF_FORMAT,
)
from .participant_refs import _normalize_person_name


__all__ = ['LLMPeopleRoster', 'cycle_roster', 'first_name_of']


def _first_word(name):
    """First word of a free-text name ("  Marc  Dupont " -> "Marc")."""
    parts = (name or '').split()
    return parts[0] if parts else ''


def _kind(person):
    return getattr(getattr(person, '_meta', None), 'model_name', None)


def first_name_of(person):
    """
    The name under which `person` may appear in a prompt: its first name.

    Args:
        person: Contact | Stakeholder | PeopleSignal | str (a name as
            written) | None.

    Returns:
        str -- the first name ('' when none). A Contact's first_name is
        returned as stored (the next_steps context v6 behaviour).
    """
    if person is None:
        return ''
    if isinstance(person, str):
        return _first_word(person)
    kind = _kind(person)
    if kind == 'contact':
        return person.first_name or ''
    if kind == 'stakeholder':
        if person.contact_id:
            return first_name_of(person.contact)
        return _first_word(person.full_name)
    if kind == 'peoplesignal':
        if person.target_contact_id:
            return first_name_of(person.target_contact)
        return _first_word(person.full_name)
    raise TypeError(f'first_name_of: unsupported person {type(person).__name__}')


def _department_of(person):
    """The display name of the person's department, or None."""
    kind = _kind(person)
    if kind == 'contact':
        if person.standard_department_id:
            return person.standard_department.get_name_display()
        return person.department or None
    if kind == 'stakeholder':
        if person.department_id:
            return person.department.get_name_display()
        return _department_of(person.contact) if person.contact_id else None
    if kind == 'peoplesignal':
        if person.target_department_id:
            return person.target_department.get_name_display()
        return _department_of(person.target_contact) if person.target_contact_id else None
    return None


def _identity(person):
    """One key per real person, whichever object carries it."""
    kind = _kind(person)
    if kind == 'contact':
        return ('contact', person.pk)
    if kind == 'stakeholder':
        if person.contact_id:
            return ('contact', person.contact_id)
        return ('stakeholder', person.pk)
    if kind == 'peoplesignal':
        if person.target_contact_id:
            return ('contact', person.target_contact_id)
        if person.stakeholder_id:
            return ('stakeholder', person.stakeholder_id)
        if (person.full_name or '').strip():
            return ('name', _normalize_person_name(person.full_name))
        return ('signal', person.pk)
    if isinstance(person, str):
        return ('name', _normalize_person_name(person))
    raise TypeError(f'LLMPeopleRoster: unsupported person {type(person).__name__}')


class LLMPeopleRoster:
    """
    The people named in ONE prompt.

    Usage:
        roster = LLMPeopleRoster()
        for signal in people_signals:
            roster.add(signal)
        for blocker in blockers:
            roster.add(blocker.contact)
        roster.label(blocker.contact)   # "Marc", or "S2 Marc (IT)"

    Register EVERY person of the prompt before reading a label: a label
    depends on the whole roster (homonyms).
    """

    def __init__(self):
        self._people = {}   # identity -> {'first_name', 'department'}

    def add(self, person, department=None):
        """Register `person` (None ignored). The first registration of a
        person fixes its department (default: the person's own)."""
        if person is None:
            return
        identity = _identity(person)
        if identity in self._people:
            return
        self._people[identity] = {
            'first_name': first_name_of(person),
            'department': department if department is not None else _department_of(person),
        }

    def label(self, person):
        """
        The name of `person` in this prompt: its first name, or the
        homonym label when another person of the roster shares it. ''
        for a person with no name. A person not registered is named by
        its first name.
        """
        if person is None:
            return ''
        entry = self._people.get(_identity(person))
        if entry is None:
            return first_name_of(person)
        first_name = entry['first_name']
        if not first_name:
            return ''
        refs = self._homonym_refs()
        ref = refs.get(_identity(person))
        if ref is None:
            return first_name
        fmt = (
            LLM_PERSON_HOMONYM_LABEL_FORMAT if entry['department']
            else LLM_PERSON_HOMONYM_LABEL_NO_DEPT_FORMAT
        )
        return fmt.format(ref=ref, first_name=first_name, department=entry['department'])

    def _homonym_refs(self):
        """identity -> reference, for the people sharing a first name, numbered
        in registration order across the roster (S1, S2, ...)."""
        counts = {}
        for entry in self._people.values():
            key = _normalize_person_name(entry['first_name']) if entry['first_name'] else ''
            if key:
                counts[key] = counts.get(key, 0) + 1
        refs = {}
        index = 0
        for identity, entry in self._people.items():
            key = _normalize_person_name(entry['first_name']) if entry['first_name'] else ''
            if key and counts[key] > 1:
                index += 1
                refs[identity] = LLM_PERSON_REF_FORMAT.format(index=index)
        return refs


def cycle_roster(decision_cycle):
    """
    The roster of a decision-cycle prompt (deal health, prep call): every
    person its evidence names — the validated People signals of the cycle
    (most recent first, the PeopleConsolidationService order), then the
    contacts of its validated Blocker signals (oldest first). Deterministic,
    so a homonym keeps its reference from one run to the next while the
    evidence is unchanged.
    """
    from app_modules.signals.constants import SignalStatus
    from app_modules.signals.models import BlockerSignal, PeopleSignal

    roster = LLMPeopleRoster()
    for signal in (
        PeopleSignal.objects.filter(
            decision_cycle=decision_cycle, status=SignalStatus.VALIDATED,
        ).select_related(
            'target_contact__standard_department', 'target_department',
        ).order_by('-created_at', '-id')
    ):
        roster.add(signal)
    for blocker in (
        BlockerSignal.objects.filter(
            decision_cycle=decision_cycle, status=SignalStatus.VALIDATED,
            contact__isnull=False,
        ).select_related('contact__standard_department').order_by('created_at', 'id')
    ):
        roster.add(blocker.contact)
    return roster
