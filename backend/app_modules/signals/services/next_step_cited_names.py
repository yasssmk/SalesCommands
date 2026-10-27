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
    (same tenant AND account) -- never a guess (tie / no match -> None).

Read-only.
"""

from app_modules.ai_pipelines.services.participant_refs import (
    account_contacts,
    resolve_contact_by_name,
)


def _people_name(people):
    contact = people.target_contact
    contact_name = (
        f'{contact.first_name or ""} {contact.last_name or ""}'.strip() if contact else ''
    )
    return people.full_name or contact_name


def next_step_cited_contacts(signal):
    """[(name, Contact | None)] for the names `signal` cites."""
    contacts = account_contacts(signal.client_id, signal.account_id)
    cited = []
    for people in signal.suggested_people.select_related('target_contact'):
        name = _people_name(people)
        if not name:
            continue
        contact = people.target_contact
        if contact is None or contact.account_id != signal.account_id \
                or contact.client_id != signal.client_id:
            contact = resolve_contact_by_name(name, contacts)
        cited.append((name, contact))
    for name in signal.suggested_people_names or []:
        if isinstance(name, str) and name.strip():
            cited.append((name, resolve_contact_by_name(name, contacts)))
    return cited
