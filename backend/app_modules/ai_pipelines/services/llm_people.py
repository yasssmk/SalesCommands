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
    department, "P1 Marc (Finance)" / "P2 Marc (IT)" (formats in
    constants.py, the NEXT_STEPS_STEP_REF_FORMAT pattern). A person with a
    unique first name keeps the bare first name. The same person registered
    twice (a stakeholder who also raised a blocker) gets ONE label.

Out of scope (TD RGPD at the sprint closure): the names written INSIDE free
text (transcripts, notes) are not masked here.
"""

from ..constants import (
    LABEL_AMBIGUOUS,
    LABEL_NO_STAKEHOLDER,
    LABEL_RESOLVED,
    LABEL_UNKNOWN,
    LLM_PERSON_HOMONYM_LABEL_FORMAT,
    LLM_PERSON_HOMONYM_LABEL_NO_DEPT_FORMAT,
    LLM_PERSON_REF_FORMAT,
    people_role_for_prompt,
)
from .participant_refs import _normalize_person_name, ordered_participants


__all__ = [
    'ActivityRoster', 'LLMPeopleRoster', 'activity_roster', 'cycle_roster',
    'first_name_of', 'roster_last_names', 'stakeholder_for', 'stakeholder_for_label',
    'stakeholder_prompt_facts',
]


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
        roster.label(blocker.contact)   # "Marc", or "P2 Marc (IT)"

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
        identity = _identity(person)
        entry = self._people.get(identity)
        if entry is None:
            return first_name_of(person)
        return self._label_of(identity, entry)

    def entries(self):
        """[(identity, label, department)] of the named people, in
        registration order — what a prompt lists (deal health v2, step 5)."""
        rows = []
        for identity, entry in self._people.items():
            label = self._label_of(identity, entry)
            if label:
                rows.append((identity, label, entry['department']))
        return rows

    def first_name_for(self, identity):
        """The first name the roster gave `identity` ('' / None when none)."""
        entry = self._people.get(identity)
        return entry['first_name'] if entry else None

    def identity_of(self, label):
        """The identity behind a label the LLM wrote back (exact label,
        whitespace-trimmed), or None — the server resolves a person, never
        the LLM (step 5)."""
        wanted = (label or '').strip()
        if not wanted:
            return None
        for identity, entry in self._people.items():
            if self._label_of(identity, entry) == wanted:
                return identity
        return None

    def _label_of(self, identity, entry):
        first_name = entry['first_name']
        if not first_name:
            return ''
        ref = self._homonym_refs().get(identity)
        if ref is None:
            return first_name
        fmt = (
            LLM_PERSON_HOMONYM_LABEL_FORMAT if entry['department']
            else LLM_PERSON_HOMONYM_LABEL_NO_DEPT_FORMAT
        )
        return fmt.format(ref=ref, first_name=first_name, department=entry['department'])

    def _homonym_refs(self):
        """identity -> reference, for the people sharing a first name, numbered
        in registration order across the roster (P1, P2, ...)."""
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
    contacts of its validated Blocker signals (oldest first), then the
    other stakeholders of the cycle (step 5: the deal health profiles every
    stakeholder). Deterministic, so a homonym keeps its reference from one
    run to the next while the evidence is unchanged.
    """
    from app_modules.decision_cycles.models import Stakeholder
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
    for stakeholder in (
        Stakeholder.objects.filter(
            decision_cycle=decision_cycle, client_id=decision_cycle.client_id,
        ).select_related(
            'contact__standard_department', 'department',
        ).order_by('created_at', 'id')
    ):
        roster.add(stakeholder)
    return roster


def stakeholder_for(decision_cycle, identity):
    """
    The Stakeholder of `decision_cycle` behind a roster identity, or None —
    THE server-side resolution of a label the LLM wrote back (deal health
    v2, step 5). Tenant- and cycle-scoped; never creates a stakeholder; an
    ambiguous name (two non-converted stakeholders) resolves to None.
    """
    from app_modules.decision_cycles.models import Stakeholder

    if not identity:
        return None
    rows = Stakeholder.objects.filter(
        decision_cycle=decision_cycle, client_id=decision_cycle.client_id,
    )
    kind, key = identity[0], identity[1]
    if kind == 'contact':
        rows = rows.filter(contact_id=key)
    elif kind == 'stakeholder':
        rows = rows.filter(pk=key)
    elif kind == 'name':
        # The roster's normalisation (accents stripped), not the column's.
        found = [
            s for s in rows.filter(contact__isnull=True)
            if _normalize_person_name(s.full_name or '') == key
        ]
        return found[0] if len(found) == 1 else None
    else:
        return None
    found = list(rows[:2])
    return found[0] if len(found) == 1 else None


def stakeholder_for_label(decision_cycle, roster, label):
    """
    THE resolution of a label the LLM wrote back to ONE stakeholder
    (sub-step 5c): (stakeholder | None, outcome).

    A label names a person; the stakeholder is accepted only when it carries
    THAT name ITSELF — its contact's first name, or its own full_name. A
    stakeholder with no name of its own (department only), whose label came
    from an observation affiliated to it, is AMBIGUOUS: an affiliation may
    group several people (resolve_people_signal accepts any stakeholder of
    the cycle), so a person's profile never lands on it.
    """
    identity = roster.identity_of(label)
    if identity is None:
        return None, LABEL_UNKNOWN
    stakeholder = stakeholder_for(decision_cycle, identity)
    if stakeholder is None:
        return None, LABEL_NO_STAKEHOLDER
    own = first_name_of(stakeholder)
    named = roster.first_name_for(identity)
    if not own or _normalize_person_name(own) != _normalize_person_name(named or ''):
        return None, LABEL_AMBIGUOUS
    return stakeholder, LABEL_RESOLVED


def stakeholder_prompt_facts(stakeholder):
    """
    What a prompt may say of a stakeholder beside its label: (role, profile).
    role — its current signal's role, as prompts write it
    (people_role_for_prompt), or None; profile — the profile VALUES only
    (manual ones included), never their source / author / dates. {} for no
    stakeholder. Shared by the deal health (its stakeholders block) and the
    Game Plan (activity_roster), sprint 2 G4.
    """
    if stakeholder is None:
        return None, {}
    signal = stakeholder.current_signal
    role = people_role_for_prompt(signal.role) if signal else None
    profile = {field: entry.get('value') for field, entry in (stakeholder.profile or {}).items()}
    return role, profile


class ActivityRoster:
    """
    The people of an activity's Game Plan (sprint 2, G4): the prompt's roster
    and its participants.

    roster       — the LLMPeopleRoster of the prompt (the cycle's people + the
                   participants, all registered: labels are final);
    participants — [{'label', 'contact_id', 'stakeholder_id', 'role',
                   'department', 'profile', 'identity'}], one per person, in
                   the order contacts (ordered_participants) then
                   stakeholders. 'contact_id' / 'stakeholder_id' / 'identity'
                   are server-side (never rendered in a prompt).
    """

    def __init__(self, roster, participants):
        self.roster = roster
        self.participants = participants
        self._by_identity = {p['identity']: p for p in participants}

    def participant_for_label(self, label):
        """The participant behind a label the LLM wrote back, or None — the
        roster's own resolution (identity_of: the exact label); a label of
        a cycle person who is not a participant resolves to None."""
        return self._by_identity.get(self.roster.identity_of(label))


def roster_last_names(roster, client_id):
    """
    Sprint 2 Game Plan, G10: the last names of the people of a roster —
    server side only, to refuse an answer that writes one (a prompt never
    carries a last name). The contacts' last_name (ONE query, tenant-scoped),
    the words after the first name of a stakeholder / an observation known by
    its full name only. A last name that is also a first name of the roster is
    left out (writing that first name is allowed). Normalised (accents and
    case stripped).
    """
    from app_modules.contacts.models import Contact
    from app_modules.decision_cycles.models import Stakeholder

    identities = list(roster._people)   # every person, named or not
    by_kind = {}
    for kind, key in identities:
        by_kind.setdefault(kind, []).append(key)
    names = set()
    if by_kind.get('contact'):
        names.update(
            Contact.objects.filter(client_id=client_id, pk__in=by_kind['contact'])
            .values_list('last_name', flat=True)
        )
    full_names = list(by_kind.get('name') or [])
    if by_kind.get('stakeholder'):
        full_names += list(
            Stakeholder.objects.filter(client_id=client_id, pk__in=by_kind['stakeholder'])
            .values_list('full_name', flat=True)
        )
    names.update(' '.join((full or '').split()[1:]) for full in full_names)
    first_names = {
        _normalize_person_name(roster.first_name_for(identity) or '') for identity in identities
    }
    return frozenset(
        n for n in (_normalize_person_name(name or '') for name in names)
        if n and n not in first_names
    )


def _contacts_stakeholders(cycle, contacts):
    """[stakeholder | None] aligned on `contacts`: the stakeholder of each
    contact in `cycle` — stakeholder_for's rule (tenant- and cycle-scoped, the
    contact's ONE stakeholder, else None) — in ONE query."""
    from app_modules.decision_cycles.models import Stakeholder

    if cycle is None or not contacts:
        return [None] * len(contacts)
    by_contact = {}
    for stakeholder in Stakeholder.objects.filter(
        decision_cycle=cycle, client_id=cycle.client_id,
        contact_id__in=[c.pk for c in contacts],
    ).select_related('contact', 'department', 'current_signal'):
        by_contact.setdefault(stakeholder.contact_id, []).append(stakeholder)
    return [
        found[0] if len(found) == 1 else None
        for found in (by_contact.get(c.pk, []) for c in contacts)
    ]


def activity_roster(activity):
    """
    THE roster of an activity's Game Plan (sprint 2, G4 — TD-46 / TD-48):
    cycle_roster(its cycle) — the labels the deal health uses — or an empty
    roster without a cycle, plus EVERY participant of the activity:
      * its contacts, bounded on its tenant AND account
        (participant_refs.ordered_participants);
      * its stakeholders (the non-converted ones of its cycle,
        participant_rules), bounded on its tenant, its cycle and that
        cycle's account.
    Every participant is registered BEFORE a label is read (a label depends
    on the whole roster — homonyms). A contact's stakeholder (its role, its
    profile) is resolved with stakeholder_for's rule — the cycle's ONE
    stakeholder of that contact — for every contact in a single query (G7: no
    N+1, the cost does not grow with the participants). First names only:
    the roster never carries a last name, an email or a phone.
    """
    cycle = activity.decision_cycle if activity.decision_cycle_id else None
    roster = cycle_roster(cycle) if cycle is not None else LLMPeopleRoster()

    contacts = ordered_participants(activity)
    people = [
        (contact, stakeholder)
        for contact, stakeholder in zip(contacts, _contacts_stakeholders(cycle, contacts))
    ]
    if cycle is not None:
        people += [
            (None, stakeholder)
            for stakeholder in activity.stakeholders.filter(
                client_id=activity.client_id,
                decision_cycle_id=cycle.id,
                decision_cycle__account_id=activity.account_id,
            ).select_related('contact', 'department', 'current_signal').order_by('created_at', 'id')
        ]

    for contact, stakeholder in people:          # ALL registered first
        roster.add(contact if contact is not None else stakeholder)

    participants, seen = [], set()
    for contact, stakeholder in people:
        person = contact if contact is not None else stakeholder
        identity = _identity(person)
        if identity in seen:                     # a converted stakeholder = its contact
            continue
        seen.add(identity)
        role, profile = stakeholder_prompt_facts(stakeholder)
        participants.append({
            'label': roster.label(person),
            'contact_id': str(contact.id) if contact is not None else None,
            'stakeholder_id': str(stakeholder.id) if stakeholder is not None else None,
            'role': role,
            'department': _department_of(person),
            'profile': profile,
            'identity': identity,
        })
    return ActivityRoster(roster, participants)
