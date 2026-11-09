# app_modules/signals/services/next_step_cited_names.py
"""
The names a next step CITES, with the account contact each one designates
(Sprint Next steps 5.8d -- PO rule: a next step neither creates nor
describes any person, it cites names, used only to create the activity).

  * the cited names: its People's names (full_name, else their contact's
    name), in the People order (the detail's), then suggested_people_names
    as written -- the front's getCitedPersonName / nextStepCitedNames;
  * the contact: a People linked to a contact of the account -> that
    contact; any other name -> participant_refs.resolve_contact_by_name,
    THE TD-279 word rule, among the contacts of the next step's ACCOUNT
    (same tenant AND account) -- never a guess (tie / no match -> None);
  * a REJECTED People is never used (5.8h): neither its name nor its contact.

Sprint « Cycle de vie des contacts », étape 7 (next_step_cited_participants):
a name WITHOUT contact proposes the NON-converted stakeholder of the next
step's cycle it designates — the stakeholder its People was resolved to,
else the UNIQUE stakeholder whose normalised name is exactly the name (a tie
proposes nobody, never a guess). The activity takes it as a participant
(MEETING / CALL / EMAIL / DEMO).

Read-only.
"""

from app_modules.ai_pipelines.services.participant_refs import (
    account_contacts,
    resolve_contact_by_name,
)
from app_modules.signals.constants import SignalStatus


def _people_name(people):
    contact = people.target_contact
    contact_name = (
        f'{contact.first_name or ""} {contact.last_name or ""}'.strip() if contact else ''
    )
    return people.full_name or contact_name


def next_step_cited_contacts(signal):
    """[(name, Contact | None)] for the names `signal` cites."""
    return [(name, contact) for name, contact, _people in _cited(signal)]


def _cited(signal):
    """[(name, Contact | None, PeopleSignal | None)]."""
    contacts = account_contacts(signal.client_id, signal.account_id)
    cited = []
    usable_people = (
        signal.suggested_people
        .exclude(status=SignalStatus.REJECTED)
        .select_related('target_contact', 'stakeholder')
    )
    for people in usable_people:
        name = _people_name(people)
        if not name:
            continue
        contact = people.target_contact
        if contact is None or contact.account_id != signal.account_id \
                or contact.client_id != signal.client_id:
            contact = resolve_contact_by_name(name, contacts)
        cited.append((name, contact, people))
    for name in signal.suggested_people_names or []:
        if isinstance(name, str) and name.strip():
            cited.append((name, resolve_contact_by_name(name, contacts), None))
    return cited


def next_step_cited_participants(signal):
    """[(name, Contact | None, Stakeholder | None)] — étape 7: a name
    without contact proposes the non-converted stakeholder of the next
    step's cycle (its People's stakeholder, else a unique exact name)."""
    from app_modules.activities.services.next_step_materialization import next_step_cycle
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal

    cycle = next_step_cycle(signal)
    not_converted = (
        list(Stakeholder.objects.filter(decision_cycle=cycle, client_id=signal.client_id,
                                        contact__isnull=True).select_related('department'))
        if cycle is not None else []
    )
    by_id = {s.id: s for s in not_converted}

    def _by_name(name):
        key = PeopleSignal._normalize_full_name(name)
        hits = [s for s in not_converted if key and s.full_name_normalized == key]
        return hits[0] if len(hits) == 1 else None

    rows = []
    for name, contact, people in _cited(signal):
        stakeholder = None
        if contact is None:
            stakeholder = (by_id.get(people.stakeholder_id) if people is not None
                           and people.stakeholder_id else None) or _by_name(name)
        rows.append((name, contact, stakeholder))
    return rows
