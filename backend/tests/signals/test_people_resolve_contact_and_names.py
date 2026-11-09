# backend/tests/signals/test_people_resolve_contact_and_names.py
"""
Sprint « Cycle de vie des contacts », étape 5b.

(1) attach_signal (THE central point) gives the signal its stakeholder's
    contact: when the stakeholder is linked, PeopleSignal.target_contact =
    stakeholder.contact — the user's choice prevails, even over a contact the
    AI had proposed. So the readers of PeopleSignal.target_contact
    (cited-contacts, People consolidation, the contact drawers) see the link.
    A "not linked" stakeholder leaves target_contact untouched.

(2) ONE naming rule for a stakeholder: linked to a contact -> its name is the
    CONTACT's, read at read time (Stakeholder.display_name); full_name only
    serves the non-converted stakeholders. get_or_create_contact_stakeholder
    no longer writes full_name (as the migration of a contact group did), and
    resolution_candidates matches a linked stakeholder on its CONTACT's
    normalised name only (a stale full_name never proposes it).

Real paths: POST /module-signals/people/{id}/resolve/,
GET /module-signals/people/{id}/resolution-candidates/.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import PeopleRole, SignalSource


pytestmark = pytest.mark.django_db

URL = '/module-signals/people/'


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _contact(account, user, first, last):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last)
    c.save(user=user, client_id=account.client_id)
    return c


def _people(activity, user, *, cycle, name='Paul Xavier', contact=None):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=PeopleRole.CHAMPION, full_name=name,
                     target_contact=contact, source_quote=f'{name} said so', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    return p


def _stakeholder(cycle, user, **fields):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, **fields)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _resolve(api, ps, body):
    r = api.post(f'{URL}{ps.id}/resolve/', body, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content
    ps.refresh_from_db()
    return ps


# =============================================================================
# (1) target_contact follows the stakeholder's contact
# =============================================================================

def test_resolve_contact_id_sets_the_signal_contact(authed_api_a, account, activity, user_a):
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    ps = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle), {'contact_id': str(paul.id)})
    assert ps.target_contact_id == paul.id


def test_resolve_to_a_linked_stakeholder_sets_the_signal_contact(
    authed_api_a, account, activity, user_a,
):
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    linked = _stakeholder(cycle, user_a, contact=paul)
    ps = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle),
                  {'stakeholder_id': str(linked.id)})
    assert ps.target_contact_id == paul.id


def test_the_user_choice_prevails_over_the_ai_contact(authed_api_a, account, activity, user_a):
    cycle = _cycle(account, user_a)
    ai_guess = _contact(account, user_a, 'Ana', 'Lopez')
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    ps = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle, contact=ai_guess),
                  {'contact_id': str(paul.id)})
    assert ps.target_contact_id == paul.id


def test_a_not_linked_stakeholder_leaves_the_signal_contact_untouched(
    authed_api_a, account, activity, user_a,
):
    cycle = _cycle(account, user_a)
    ana = _contact(account, user_a, 'Ana', 'Lopez')
    not_linked = _stakeholder(cycle, user_a, full_name='Paul')
    with_contact = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle, contact=ana),
                            {'stakeholder_id': str(not_linked.id)})
    without = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle, name='Paul'),
                       {'stakeholder_id': str(not_linked.id)})
    assert with_contact.target_contact_id == ana.id
    assert without.target_contact_id is None


def test_the_contact_becomes_visible_to_cited_contacts(authed_api_a, account, activity, user_a):
    """A reader of PeopleSignal.target_contact sees the link: the next step
    citing this person resolves to the chosen contact."""
    from app_modules.signals.models import NextStepSignal
    from app_modules.signals.services.next_step_cited_names import next_step_cited_contacts
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    ps = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle, name='PX'),
                  {'contact_id': str(paul.id)})
    ns = NextStepSignal(account=account, source_activity=activity, suggested_title='Demo',
                        suggested_activity_type='MEETING', source=SignalSource.LLM_EXTRACTED,
                        confidence=0.8)
    ns.save(user=user_a, client_id=account.client_id)
    ns.suggested_people.set([ps])
    assert next_step_cited_contacts(ns) == [('PX', paul)]


# =============================================================================
# (2) ONE naming rule: a linked stakeholder is named by its contact
# =============================================================================

def test_display_name_reads_the_contact_for_a_linked_stakeholder(account, user_a):
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    assert _stakeholder(cycle, user_a, contact=paul, full_name='Old Name').display_name == 'Paul Xavier'
    assert _stakeholder(cycle, user_a, full_name='Marc').display_name == 'Marc'


def test_the_contact_shortcut_no_longer_writes_full_name(authed_api_a, account, activity, user_a):
    """Aligned on the migration of a contact group: the name lives on the
    contact, not on the stakeholder."""
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    ps = _resolve(authed_api_a, _people(activity, user_a, cycle=cycle), {'contact_id': str(paul.id)})
    assert ps.stakeholder.full_name == ''
    assert ps.stakeholder.display_name == 'Paul Xavier'


def test_a_new_signal_finds_the_migrated_stakeholder_by_its_contact_name(
    authed_api_a, account, activity, user_a,
):
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    migrated = _stakeholder(cycle, user_a, contact=paul)          # full_name '' (migration)
    ps = _people(activity, user_a, cycle=cycle, name='paul  xavier')
    r = authed_api_a.get(f'{URL}{ps.id}/resolution-candidates/')
    row = next(s for s in r.json()['data']['stakeholders'] if s['id'] == str(migrated.id))
    assert row['proposed'] is True
    assert row['display_name'] == 'Paul Xavier'


def test_a_stale_full_name_never_proposes_a_linked_stakeholder(
    authed_api_a, account, activity, user_a,
):
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    stale = _stakeholder(cycle, user_a, contact=paul, full_name='Old Name')
    ps = _people(activity, user_a, cycle=cycle, name='Old Name')
    r = authed_api_a.get(f'{URL}{ps.id}/resolution-candidates/')
    row = next(s for s in r.json()['data']['stakeholders'] if s['id'] == str(stale.id))
    assert row['proposed'] is False


def test_attach_signal_alone_persists_the_contact(account, activity, user_a):
    """attach_signal is THE central point: called on its own (no save
    afterwards), it persists the signal's contact."""
    from app_modules.decision_cycles.services.stakeholder_service import attach_signal
    from app_modules.signals.models import PeopleSignal
    cycle = _cycle(account, user_a)
    paul = _contact(account, user_a, 'Paul', 'Xavier')
    ps = _people(activity, user_a, cycle=cycle)
    attach_signal(ps, _stakeholder(cycle, user_a, contact=paul))
    assert PeopleSignal.objects.get(pk=ps.pk).target_contact_id == paul.id
