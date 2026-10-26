# backend/tests/decision_cycles/test_people_consolidation_full_name.py
"""
Sprint Next steps 5.8a -- the consolidated People view of a decision cycle
(GET /decision_cycles/{id}/people/, PeopleConsolidationService) exposes each
qualified People's full_name: a People without contact (e.g. "Add as person",
B0: MANUAL, role UNKNOWN, full_name only) is named, not "Unknown"
(PeopleTab.jsx contactDisplayName).
"""

import pytest

from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus


pytestmark = pytest.mark.django_db


def _people(account, cycle, user, **fields):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=account, decision_cycle=cycle, status=SignalStatus.VALIDATED,
                     **fields)
    p.save(user=user, client_id=account.client_id)
    return p


def _qualified(authed_api, cycle):
    response = authed_api.get(f'/decision_cycles/{cycle.id}/people/')
    assert response.status_code == 200, response.content
    return {q['signal_id']: q for q in response.json()['data']['qualified']}


def test_a_people_without_contact_is_named(authed_api_a, account, cycle, user_a):
    karim = _people(account, cycle, user_a, role=PeopleRole.UNKNOWN, full_name='Karim Benali',
                    source=SignalSource.MANUAL)
    entry = _qualified(authed_api_a, cycle)[str(karim.id)]
    assert entry['full_name'] == 'Karim Benali'
    assert entry['target_contact'] is None


def test_a_people_with_contact_keeps_its_contact(authed_api_a, account, cycle, user_a, contact):
    jane = _people(account, cycle, user_a, role=PeopleRole.CHAMPION, target_contact=contact,
                   full_name='Jane Doe')
    entry = _qualified(authed_api_a, cycle)[str(jane.id)]
    assert entry['full_name'] == 'Jane Doe'
    assert entry['target_contact']['id'] == str(contact.id)
