# app_modules/decision_cycles/services/stakeholder_service.py
"""
Stakeholders of a decision cycle -- sprint « Cycle de vie des contacts »,
étape 3 (backend preparation for the Activity flow).

attach_signal(ps, stakeholder): affiliate a PeopleSignal (an observation) to
a DC stakeholder (the person). The signal is never merged (règle doublons);
the affiliation writes only `stakeholder` and, when the stakeholder is
linked to a contact, `target_contact` (étape 5b: the user's choice prevails,
even over a contact the AI had proposed — so the readers of
PeopleSignal.target_contact see the link). The FIRST affiliated role becomes
the stakeholder's current_signal; a later one leaves it unchanged (the
"rôle à confirmer" choice and set_current / convert / readiness belong to
the DC sprint -- TD).

Naming rule (étape 5b, ONE rule — Stakeholder.display_name): a stakeholder
linked to a contact is named by its CONTACT (read time); full_name only
serves the non-converted stakeholders.
"""

from django.core.exceptions import ValidationError
from django.db import transaction


@transaction.atomic
def attach_signal(people_signal, stakeholder):
    """
    Affiliate `people_signal` to `stakeholder`.

    Args:
        people_signal: a PeopleSignal of the stakeholder's decision cycle.
        stakeholder:   a Stakeholder.

    Returns:
        The stakeholder (current_signal set on the first affiliation).

    Raises:
        ValidationError: different tenant, or the signal is not on the
        stakeholder's decision cycle.
    """
    from app_modules.signals.models import PeopleSignal

    # Compared as strings: a freshly created instance may still carry the
    # client_id / FK id as passed (str) while a DB-read one carries a UUID.
    if str(people_signal.client_id) != str(stakeholder.client_id):
        raise ValidationError('The signal and the stakeholder belong to different tenants.')
    if str(people_signal.decision_cycle_id) != str(stakeholder.decision_cycle_id):
        raise ValidationError("The signal is not on the stakeholder's decision cycle.")

    fields = {'stakeholder': stakeholder}
    if stakeholder.contact_id:
        # Étape 5b: the stakeholder's contact is the signal's contact.
        fields['target_contact_id'] = stakeholder.contact_id
    PeopleSignal.objects.filter(pk=people_signal.pk).update(**fields)
    people_signal.stakeholder = stakeholder
    if stakeholder.contact_id:
        people_signal.target_contact_id = stakeholder.contact_id

    if stakeholder.current_signal_id is None:
        stakeholder.current_signal = people_signal
        stakeholder.save(update_fields=['current_signal', 'updated_at'])
    return stakeholder


# =============================================================================
# RESOLVE A PEOPLE SIGNAL (étape 5): signal -> stakeholder of the DC
# =============================================================================

def _contact_full_name(contact):
    return f'{contact.first_name or ""} {contact.last_name or ""}'.strip()


def _signal_cycle_or_refuse(people_signal):
    """The DC of the signal (= of its activity, kept in sync by the
    activity -> cycle attachment); none -> the business refusal."""
    from core.error_messages import SignalErrorMessages
    from core.exceptions import StandardizedValidationError
    if not people_signal.decision_cycle_id:
        raise StandardizedValidationError(SignalErrorMessages.PEOPLE_REQUIRES_DECISION_CYCLE)
    return people_signal.decision_cycle


@transaction.atomic
def resolve_people_signal(people_signal, user, *, stakeholder_id=None, contact_id=None,
                          create=None):
    """
    Validate `people_signal` WITH its stakeholder in the signal's decision
    cycle -- exactly ONE of:
      * stakeholder_id: an existing stakeholder of that DC;
      * contact_id:     an account contact -> its stakeholder in that DC
                        (get_or_create, linked to the contact);
      * create:         {full_name?, department_id?} -> a new "not linked"
                        stakeholder (a name or a department required).
    Affiliation (attach_signal) then validation (SignalManager.validate), in
    ONE transaction: a refusal rolls everything back. Never creates a
    Contact; no role step (the first role becomes current_signal).
    8b-1 (PO): a People VALIDATED without stakeholder (validated before its
    activity joined a DC) is affiliated only — « Link to the deal », its
    status untouched; a People already affiliated is refused.

    Raises:
        StandardizedValidationError (400) on every business refusal.
    """
    from core.error_messages import SignalErrorMessages
    from core.exceptions import StandardizedValidationError
    from app_modules.contacts.models import Contact
    from app_modules.core_modules.models import StandardDepartment
    from app_modules.signals.constants import SignalStatus
    from app_modules.signals.services.signal_manager import SignalManager
    from ..models import Stakeholder

    chosen = [c for c in (stakeholder_id, contact_id, create) if c not in (None, '')]
    if len(chosen) != 1:
        raise StandardizedValidationError(SignalErrorMessages.PEOPLE_RESOLVE_ONE_CHOICE)
    link_only = people_signal.status == SignalStatus.VALIDATED
    if link_only and people_signal.stakeholder_id:
        raise StandardizedValidationError(SignalErrorMessages.PEOPLE_ALREADY_AFFILIATED)
    if people_signal.status not in (SignalStatus.PENDING, SignalStatus.VALIDATED):
        raise StandardizedValidationError(SignalErrorMessages.NOT_PENDING_VALIDATED)
    cycle = _signal_cycle_or_refuse(people_signal)
    client_id = people_signal.client_id

    if stakeholder_id:
        stakeholder = Stakeholder.objects.filter(
            pk=stakeholder_id, client_id=client_id, decision_cycle_id=cycle.id,
        ).first()
        if stakeholder is None:
            raise StandardizedValidationError(
                SignalErrorMessages.PEOPLE_RESOLVE_STAKEHOLDER_INVALID
            )
    elif contact_id:
        contact = Contact.objects.filter(
            pk=contact_id, client_id=client_id, account_id=people_signal.account_id,
        ).first()
        if contact is None:
            raise StandardizedValidationError(
                SignalErrorMessages.PEOPLE_RESOLVE_CONTACT_INVALID
            )
        stakeholder = get_or_create_contact_stakeholder(cycle, contact, user)
    else:
        if not isinstance(create, dict):
            raise StandardizedValidationError(SignalErrorMessages.PEOPLE_RESOLVE_ONE_CHOICE)
        full_name = str(create.get('full_name') or '').strip()
        department = None
        if create.get('department_id'):
            department = StandardDepartment.objects.filter(pk=create['department_id']).first()
        if not full_name and department is None:
            raise StandardizedValidationError(SignalErrorMessages.PEOPLE_RESOLVE_CREATE_EMPTY)
        stakeholder = Stakeholder(decision_cycle=cycle, full_name=full_name[:255],
                                  department=department)
        stakeholder.save(user=user, client_id=client_id)

    attach_signal(people_signal, stakeholder)
    if link_only:
        return people_signal
    return SignalManager.validate(people_signal, user=user)


@transaction.atomic
def join_contact_stakeholder(people_signal, user):
    """
    Étape 5 (2): a People signal carrying a contact in a DC joins the
    stakeholder (dc, contact) — get_or_create, then attach_signal. Called by
    SignalManager.create for the MANUAL People signals (the user chose the
    contact).
    """
    stakeholder = get_or_create_contact_stakeholder(
        people_signal.decision_cycle, people_signal.target_contact, user,
    )
    return attach_signal(people_signal, stakeholder)


def get_or_create_contact_stakeholder(cycle, contact, user):
    """The stakeholder of `contact` in `cycle` (unique per (cycle, contact)),
    created linked when absent."""
    from ..models import Stakeholder
    stakeholder = Stakeholder.objects.filter(decision_cycle=cycle, contact=contact).first()
    if stakeholder is None:
        # Étape 5b: no full_name — a linked stakeholder is named by its
        # contact (Stakeholder.display_name), as the migration's contact
        # groups.
        stakeholder = Stakeholder(decision_cycle=cycle, contact=contact,
                                  department=contact.standard_department)
        stakeholder.save(user=user, client_id=cycle.client_id)
    return stakeholder


def resolution_candidates(people_signal):
    """
    What the rep can resolve `people_signal` to:
      * stakeholders -- every stakeholder of the signal's DC;
      * contacts     -- the account contacts NOT yet stakeholders of it.
    An EXACT match is marked proposed (never applied): the same contact as
    the signal's target_contact, or the same normalised name. Proposed
    first, then by name. No DC -> has_cycle False, nothing proposed.
    """
    from app_modules.ai_pipelines.services.participant_refs import account_contacts
    from app_modules.signals.models import PeopleSignal
    from ..models import Stakeholder

    if not people_signal.decision_cycle_id:
        return {'has_cycle': False, 'stakeholders': [], 'contacts': []}

    name = people_signal.full_name_normalized
    contact_id = people_signal.target_contact_id
    normalize = PeopleSignal._normalize_full_name

    stakeholders = list(
        Stakeholder.objects
        .filter(decision_cycle_id=people_signal.decision_cycle_id,
                client_id=people_signal.client_id)
        .select_related('contact', 'department', 'current_signal')
    )
    taken_contacts = {s.contact_id for s in stakeholders if s.contact_id}

    def _stakeholder_row(s):
        # Étape 5b, ONE naming rule: a linked stakeholder is matched on its
        # CONTACT's normalised name only (a stale full_name never proposes
        # it); a non-converted one on its full_name.
        own_name = (normalize(_contact_full_name(s.contact)) if s.contact
                    else s.full_name_normalized)
        proposed = bool(
            (contact_id and s.contact_id == contact_id)
            or (name and own_name == name)
        )
        current = s.current_signal
        return {
            'id': str(s.id),
            'display_name': s.display_name,
            'full_name': s.full_name,
            'contact': ({'id': str(s.contact.id), 'first_name': s.contact.first_name,
                         'last_name': s.contact.last_name} if s.contact else None),
            'department': ({'id': s.department.id, 'name': s.department.get_name_display()}
                           if s.department else None),
            'current_role': current.role if current else None,
            'current_role_display': current.get_role_display() if current else None,
            'proposed': proposed,
        }

    def _contact_row(c):
        return {
            'id': str(c.id),
            'first_name': c.first_name,
            'last_name': c.last_name,
            'job_title': c.job_title,
            'department': ({'id': c.standard_department.id,
                            'name': c.standard_department.get_name_display()}
                           if c.standard_department else None),
            'proposed': bool((contact_id and c.id == contact_id)
                             or (name and normalize(_contact_full_name(c)) == name)),
        }

    stakeholder_rows = sorted(
        (_stakeholder_row(s) for s in stakeholders),
        key=lambda r: (not r['proposed'],
                       ((r['contact'] or {}).get('last_name') or r['full_name'] or '').lower()),
    )
    contact_rows = sorted(
        (_contact_row(c) for c in account_contacts(people_signal.client_id,
                                                   people_signal.account_id)
         if c.id not in taken_contacts),
        key=lambda r: (not r['proposed'], (r['last_name'] or '').lower(),
                       (r['first_name'] or '').lower()),
    )
    return {'has_cycle': True, 'stakeholders': stakeholder_rows, 'contacts': contact_rows}
