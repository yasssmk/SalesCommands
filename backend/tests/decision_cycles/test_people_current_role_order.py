# backend/tests/decision_cycles/test_people_current_role_order.py
"""
Sprint « Cycle de vie des contacts », étape 1 -- the role shown for a contact
in a decision cycle is the MOST RECENT validated one, never the
alphabetically first.

Real path: GET /decision_cycles/{id}/people/ (PeopleConsolidationService).
The front drawers (ContactDrawerContent, EditContactContent) take the FIRST
qualified entry of a contact (`.find()`), so the server order IS the role
shown: a contact moved from Champion to Decision Maker must read Decision
Maker first -- and the reverse move (Decision Maker -> Champion) must read
Champion first (recency, not a role ranking).
"""

import datetime

import pytest
from django.utils import timezone

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db


def _people(account, cycle, user, contact, role, *, days_ago):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(
        account=account, decision_cycle=cycle, status=SignalStatus.VALIDATED,
        source=SignalSource.MANUAL, role=role, target_contact=contact,
    )
    p.save(user=user, client_id=account.client_id)
    # Deterministic chronology (created_at is auto_now_add).
    PeopleSignal.objects.filter(pk=p.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=days_ago),
    )
    return p


def _first_role_of(authed_api, cycle, contact):
    response = authed_api.get(f'/decision_cycles/{cycle.id}/people/')
    assert response.status_code == 200, response.content
    entries = [
        q for q in response.json()['data']['qualified']
        if (q.get('target_contact') or {}).get('id') == str(contact.id)
    ]
    assert entries, 'the contact must be qualified'
    return entries[0]['role']


def test_champion_then_decision_maker_shows_decision_maker(
    authed_api_a, account, cycle, user_a, contact,
):
    _people(account, cycle, user_a, contact, PeopleRole.CHAMPION, days_ago=2)
    _people(account, cycle, user_a, contact, PeopleRole.DECISION_MAKER, days_ago=1)
    assert _first_role_of(authed_api_a, cycle, contact) == PeopleRole.DECISION_MAKER


def test_decision_maker_then_champion_shows_champion(
    authed_api_a, account, cycle, user_a, contact,
):
    _people(account, cycle, user_a, contact, PeopleRole.DECISION_MAKER, days_ago=2)
    _people(account, cycle, user_a, contact, PeopleRole.CHAMPION, days_ago=1)
    assert _first_role_of(authed_api_a, cycle, contact) == PeopleRole.CHAMPION
