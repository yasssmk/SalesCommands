# backend/tests/signals/test_people_resolve.py
"""
Sprint « Cycle de vie des contacts », étape 5 (1) -- validating a People
signal = « true? » + « which stakeholder of the DC? » (Activity surface).

Real paths:
  * POST /module-signals/people/{id}/resolve/ with ONE of
      {stakeholder_id}  an existing stakeholder of the signal's DC;
      {contact_id}      shortcut: an account contact -> its stakeholder in
                        this DC (created linked if absent, reused if present);
      {create: {full_name?, department_id?}}  a new "not linked" stakeholder.
    Validation + attach_signal in ONE transaction; never creates a Contact;
    no role step.
  * GET /module-signals/people/{id}/resolution-candidates/: the DC
    stakeholders + the account contacts not yet stakeholders; an EXACT match
    (same contact, or same normalised name) is marked "proposed", never
    applied.
  * POST /module-signals/people/{id}/validate/ is REFUSED for People.
  * No DC: resolve refused with a business message (400, never a 500).
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db

URL = '/module-signals/people/'


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _people(activity, user, *, cycle, name='Marc Dupont', contact=None, role=PeopleRole.CHAMPION):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=role, full_name=name,
                     target_contact=contact, source_quote=f'{name} said so', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    return p


def _stakeholder(cycle, user, **fields):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, **fields)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _resolve(api, ps, body):
    return api.post(f'{URL}{ps.id}/resolve/', body, format='json')


def _candidates(api, ps):
    r = api.get(f'{URL}{ps.id}/resolution-candidates/')
    assert r.status_code == status.HTTP_200_OK, r.content
    return r.json()['data']


def _error_text(response):
    return response.content.decode()


@pytest.fixture
def cycle(account, user_a):
    return _cycle(account, user_a)


# =============================================================================
# THE GENERIC VALIDATE IS REFUSED
# =============================================================================

def test_generic_validate_is_refused_for_people(authed_api_a, activity, user_a, cycle):
    ps = _people(activity, user_a, cycle=cycle)
    r = authed_api_a.post(f'{URL}{ps.id}/validate/')
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'stakeholder' in _error_text(r).lower()
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING


def test_generic_validate_stays_refused_for_an_affiliated_reopened_signal(
    authed_api_a, activity, user_a, cycle,
):
    """Even a signal already affiliated (resolved, then reopened) goes back
    through resolve: the generic endpoint is closed for People."""
    ps = _people(activity, user_a, cycle=cycle)
    assert _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}}).status_code == 200
    assert authed_api_a.post(f'{URL}{ps.id}/reopen/').status_code == 200
    r = authed_api_a.post(f'{URL}{ps.id}/validate/')
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING


def test_signal_manager_refuses_a_people_without_stakeholder(activity, user_a, cycle):
    from core.exceptions import StandardizedValidationError
    from app_modules.signals.services.signal_manager import SignalManager
    ps = _people(activity, user_a, cycle=cycle)
    with pytest.raises(StandardizedValidationError):
        SignalManager.validate(ps, user=user_a)


# =============================================================================
# RESOLVE
# =============================================================================

def test_create_a_not_linked_stakeholder_from_a_first_name(authed_api_a, activity, user_a, cycle):
    from app_modules.contacts.models import Contact
    contacts_before = Contact.objects.count()
    ps = _people(activity, user_a, cycle=cycle, name='Marc')

    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}})

    assert r.status_code == status.HTTP_200_OK, r.content
    ps.refresh_from_db()
    assert ps.status == SignalStatus.VALIDATED
    s = ps.stakeholder
    assert s.decision_cycle_id == cycle.id
    assert s.contact_id is None and s.full_name == 'Marc'
    assert s.current_signal_id == ps.id
    assert r.json()['data']['stakeholder'] == str(s.id)
    assert Contact.objects.count() == contacts_before          # never a Contact


def test_create_a_department_only_stakeholder(authed_api_a, activity, user_a, cycle):
    from app_modules.core_modules.models import StandardDepartment
    sales, _ = StandardDepartment.objects.get_or_create(name='Sales')
    ps = _people(activity, user_a, cycle=cycle, name='')
    r = _resolve(authed_api_a, ps, {'create': {'department_id': str(sales.id)}})
    assert r.status_code == status.HTTP_200_OK, r.content
    ps.refresh_from_db()
    assert ps.stakeholder.department_id == sales.id and ps.stakeholder.full_name == ''


def test_create_without_name_nor_department_is_refused(authed_api_a, activity, user_a, cycle):
    ps = _people(activity, user_a, cycle=cycle)
    r = _resolve(authed_api_a, ps, {'create': {}})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING and ps.stakeholder_id is None


def test_link_an_existing_stakeholder_keeps_its_current_role(authed_api_a, activity, user_a, cycle):
    from app_modules.decision_cycles.services.stakeholder_service import attach_signal
    from app_modules.signals.models import PeopleSignal
    first = _people(activity, user_a, cycle=cycle, role=PeopleRole.CHAMPION)
    PeopleSignal.objects.filter(pk=first.pk).update(status=SignalStatus.VALIDATED)
    first.refresh_from_db()
    s = _stakeholder(cycle, user_a, full_name='Marc Dupont')
    attach_signal(first, s)
    later = _people(activity, user_a, cycle=cycle, role=PeopleRole.DECISION_MAKER)

    r = _resolve(authed_api_a, later, {'stakeholder_id': str(s.id)})

    assert r.status_code == status.HTTP_200_OK, r.content
    later.refresh_from_db()
    s.refresh_from_db()
    assert later.status == SignalStatus.VALIDATED and later.stakeholder_id == s.id
    assert s.current_signal_id == first.id                     # never changed here


def test_a_stakeholder_of_another_cycle_is_refused(authed_api_a, account, activity, user_a, cycle):
    other = _stakeholder(_cycle(account, user_a, 'Other'), user_a, full_name='Marc')
    ps = _people(activity, user_a, cycle=cycle)
    r = _resolve(authed_api_a, ps, {'stakeholder_id': str(other.id)})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING and ps.stakeholder_id is None


def test_contact_shortcut_creates_then_reuses_the_linked_stakeholder(
    authed_api_a, activity, user_a, cycle, contact,
):
    from app_modules.decision_cycles.models import Stakeholder
    first = _people(activity, user_a, cycle=cycle, name='Jane')
    second = _people(activity, user_a, cycle=cycle, name='Jane D.', role=PeopleRole.DECISION_MAKER)

    assert _resolve(authed_api_a, first, {'contact_id': str(contact.id)}).status_code == 200
    assert _resolve(authed_api_a, second, {'contact_id': str(contact.id)}).status_code == 200

    stakeholders = Stakeholder.objects.filter(decision_cycle=cycle, contact=contact)
    assert stakeholders.count() == 1
    s = stakeholders.get()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.stakeholder_id == s.id == second.stakeholder_id
    assert s.current_signal_id == first.id


def test_a_contact_of_another_account_is_refused(authed_api_a, activity, user_a, cycle, other_tenant_account, user_b):
    from app_modules.contacts.models import Contact
    stranger = Contact(account=other_tenant_account, first_name='Eve', last_name='Else')
    stranger.save(user=user_b, client_id=other_tenant_account.client_id)
    ps = _people(activity, user_a, cycle=cycle)
    r = _resolve(authed_api_a, ps, {'contact_id': str(stranger.id)})
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize('body', [
    {},
    {'stakeholder_id': None},
    {'create': {'full_name': 'Marc'}, 'contact_id': 'x'},
])
def test_exactly_one_choice(authed_api_a, activity, user_a, cycle, body):
    ps = _people(activity, user_a, cycle=cycle)
    r = _resolve(authed_api_a, ps, body)
    assert r.status_code == status.HTTP_400_BAD_REQUEST


def test_without_a_decision_cycle_resolve_is_refused_with_a_business_message(
    authed_api_a, activity, user_a,
):
    ps = _people(activity, user_a, cycle=None)
    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'decision cycle' in _error_text(r).lower()
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING


def test_only_a_pending_signal_is_resolved(authed_api_a, activity, user_a, cycle):
    from app_modules.signals.models import PeopleSignal
    ps = _people(activity, user_a, cycle=cycle)
    PeopleSignal.objects.filter(pk=ps.pk).update(status=SignalStatus.REJECTED)
    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}})
    assert r.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# CANDIDATES
# =============================================================================

def test_candidates_stakeholders_and_contacts_exact_match_proposed(
    authed_api_a, account, activity, user_a, cycle, contact,
):
    from app_modules.contacts.models import Contact
    marc_contact = Contact(account=account, first_name='Marc', last_name='Dupont')
    marc_contact.save(user=user_a, client_id=account.client_id)
    marc = _stakeholder(cycle, user_a, full_name='marc  dupont')        # same normalised name
    other = _stakeholder(cycle, user_a, full_name='Marc')               # NOT exact
    linked = _stakeholder(cycle, user_a, contact=contact)               # contact already stakeholder
    elsewhere = _stakeholder(_cycle(account, user_a, 'B'), user_a, full_name='Marc Dupont')
    ps = _people(activity, user_a, cycle=cycle, name='Marc Dupont')

    data = _candidates(authed_api_a, ps)

    assert data['has_cycle'] is True
    by_id = {s['id']: s for s in data['stakeholders']}
    assert set(by_id) == {str(marc.id), str(other.id), str(linked.id)}   # this DC only
    assert by_id[str(marc.id)]['proposed'] is True
    assert by_id[str(other.id)]['proposed'] is False
    assert str(elsewhere.id) not in by_id
    contact_ids = {c['id']: c for c in data['contacts']}
    assert str(contact.id) not in contact_ids                           # already a stakeholder
    assert contact_ids[str(marc_contact.id)]['proposed'] is True        # exact name
    assert data['stakeholders'][0]['id'] == str(marc.id)                # proposed first
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING and ps.stakeholder_id is None   # never applied


def test_candidates_propose_the_stakeholder_of_the_signal_contact(
    authed_api_a, activity, user_a, cycle, contact,
):
    linked = _stakeholder(cycle, user_a, contact=contact)
    ps = _people(activity, user_a, cycle=cycle, name='Someone Else', contact=contact)
    data = _candidates(authed_api_a, ps)
    assert {s['id']: s['proposed'] for s in data['stakeholders']}[str(linked.id)] is True


def test_candidates_without_a_cycle(authed_api_a, activity, user_a):
    ps = _people(activity, user_a, cycle=None)
    data = _candidates(authed_api_a, ps)
    assert data['has_cycle'] is False
    assert data['stakeholders'] == []
