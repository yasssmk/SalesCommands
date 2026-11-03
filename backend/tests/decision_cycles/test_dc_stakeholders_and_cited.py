# backend/tests/decision_cycles/test_dc_stakeholders_and_cited.py
"""
Sprint « Cycle de vie des contacts », étapes 7 (3) / 7c, backend side of
the activity drawer's single « Add stakeholder » picker:

  * GET /decision_cycles/{id}/stakeholders/ — EVERY stakeholder of the cycle
    (7c), converted ones with their `contact` (taken by an activity as that
    contact) and non-converted ones (taken as stakeholders): display_name,
    department, is_linked, contact, decision_cycle;
  * GET /module-signals/next-steps/{id}/cited-contacts/ — each cited name
    comes with its account contact (as before) OR, without contact, with the
    non-converted stakeholder of the next step's cycle it designates: the
    stakeholder its People signal was resolved to, else an EXACT normalised
    name match (unique — a tie proposes nobody).
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    return dc


def _stakeholder(cycle, user, **fields):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, **fields)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _contact(account, user, first, last):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last)
    c.save(user=user, client_id=account.client_id)
    return c


def _activity_in(cycle, account, user):
    from app_modules.activities.models import Activity
    a = Activity(title='Workshop', activity_type='MEETING', status='COMPLETED', account=account,
                 owner=user, decision_cycle=cycle, scheduled_date='2026-11-01')
    a.save(user=user, client_id=account.client_id)
    return a


def _next_step(activity, user, cycle, people=(), names=()):
    from app_modules.signals.models import NextStepSignal
    ns = NextStepSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                        suggested_title='Demo', suggested_activity_type='DEMO',
                        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
                        suggested_people_names=list(names))
    ns.save(user=user, client_id=activity.client_id)
    ns.suggested_people.set(list(people))
    return ns


def _people(activity, user, cycle, name, stakeholder=None):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=PeopleRole.CHAMPION, full_name=name,
                     source_quote='q', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    if stakeholder:
        PeopleSignal.objects.filter(pk=p.pk).update(stakeholder=stakeholder,
                                                    status=SignalStatus.VALIDATED)
    return p


def _cited(api, ns):
    r = api.get(f'/module-signals/next-steps/{ns.id}/cited-contacts/')
    assert r.status_code == 200, r.content
    return {c['name']: c for c in r.json()['data']['cited']}


# =============================================================================
# DC stakeholders endpoint
# =============================================================================

def test_the_cycle_lists_all_its_stakeholders_converted_with_their_contact(
    authed_api_a, account, user_a,
):
    """Étape 7c (PO): the drawer's ONE « Add stakeholder » picker offers every
    stakeholder of the DC — converted (sent as its contact) or not."""
    from app_modules.core_modules.models import StandardDepartment
    sales, _ = StandardDepartment.objects.get_or_create(name='Sales')
    cycle = _cycle(account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    dept = _stakeholder(cycle, user_a, department=sales)
    paul_contact = _contact(account, user_a, 'Paul', 'X')
    paul = _stakeholder(cycle, user_a, contact=paul_contact)                      # converted
    _stakeholder(_cycle(account, user_a, 'Other'), user_a, full_name='Elsewhere')  # other cycle
    r = authed_api_a.get(f'/decision_cycles/{cycle.id}/stakeholders/')
    assert r.status_code == status.HTTP_200_OK, r.content
    rows = {s['id']: s for s in r.json()['data']}
    assert set(rows) == {str(marc.id), str(dept.id), str(paul.id)}
    assert rows[str(marc.id)]['display_name'] == 'Marc'
    assert rows[str(marc.id)]['is_linked'] is False and rows[str(marc.id)]['contact'] is None
    assert rows[str(marc.id)]['decision_cycle'] == str(cycle.id)
    assert rows[str(dept.id)]['department']['id'] == sales.id
    assert rows[str(paul.id)]['is_linked'] is True
    assert rows[str(paul.id)]['contact']['id'] == str(paul_contact.id)
    assert rows[str(paul.id)]['display_name'] == 'Paul X'


def test_another_tenant_cannot_read_them(authed_api_b, account, user_a):
    cycle = _cycle(account, user_a)
    r = authed_api_b.get(f'/decision_cycles/{cycle.id}/stakeholders/')
    assert r.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# cited-contacts proposes the non-converted stakeholders
# =============================================================================

def test_a_cited_person_resolved_to_a_not_linked_stakeholder(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _activity_in(cycle, account, user_a)
    marc = _stakeholder(cycle, user_a, full_name='Marc')
    ns = _next_step(activity, user_a, cycle,
                    people=[_people(activity, user_a, cycle, 'Marc D.', stakeholder=marc)])
    row = _cited(authed_api_a, ns)['Marc D.']
    assert row['contact'] is None
    assert row['stakeholder']['id'] == str(marc.id)
    assert row['stakeholder']['display_name'] == 'Marc'


def test_a_cited_name_matching_a_not_linked_stakeholder_exactly(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _activity_in(cycle, account, user_a)
    zoe = _stakeholder(cycle, user_a, full_name='Zoé Martin')
    ns = _next_step(activity, user_a, cycle, names=['zoé  martin', 'Zoé'])
    cited = _cited(authed_api_a, ns)
    assert cited['zoé  martin']['stakeholder']['id'] == str(zoe.id)
    assert cited['Zoé']['stakeholder'] is None          # exact only, never a guess


def test_a_tie_proposes_no_stakeholder(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _activity_in(cycle, account, user_a)
    _stakeholder(cycle, user_a, full_name='Marc')
    _stakeholder(cycle, user_a, full_name='marc')
    ns = _next_step(activity, user_a, cycle, names=['Marc'])
    assert _cited(authed_api_a, ns)['Marc']['stakeholder'] is None


def test_a_name_with_a_contact_keeps_the_contact(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _activity_in(cycle, account, user_a)
    jane = _contact(account, user_a, 'Jane', 'Doe')
    _stakeholder(cycle, user_a, full_name='Jane Doe')
    ns = _next_step(activity, user_a, cycle, names=['Jane Doe'])
    row = _cited(authed_api_a, ns)['Jane Doe']
    assert row['contact']['id'] == str(jane.id)
    assert row['stakeholder'] is None
