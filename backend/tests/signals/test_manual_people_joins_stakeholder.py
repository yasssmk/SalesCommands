# backend/tests/signals/test_manual_people_joins_stakeholder.py
"""
Sprint « Cycle de vie des contacts », étape 5 (2) -- a MANUAL People signal
created by the user WITH a contact in a DC (e.g. the role typed in
EditContactContent, EditContactContent.jsx:128-149) joins the stakeholder
(dc, contact) automatically: the user already chose the contact. Done at the
central creation point (SignalManager.create) through stakeholder_service
(get_or_create (dc, contact) + attach_signal: the first role becomes
current_signal, a later one leaves it -- « rôle à confirmer », DC sprint).

Real path: POST /module-signals/people/ with the EditContactContent payload
{role, target_contact, account, source: MANUAL, decision_cycle}.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import PeopleRole, SignalSource


pytestmark = pytest.mark.django_db

URL = '/module-signals/people/'


def _create(api, account, *, role=PeopleRole.CHAMPION, contact=None, cycle=None,
            source='MANUAL', activity=None, **extra):
    body = {'role': role, 'account': str(account.id), 'source': source, **extra}
    if contact:
        body['target_contact'] = str(contact.id)
    if cycle:
        body['decision_cycle'] = str(cycle.id)
    if activity:
        body['source_activity'] = str(activity.id)
    r = api.post(URL, body, format='json')
    assert r.status_code == status.HTTP_201_CREATED, r.content
    from app_modules.signals.models import PeopleSignal
    return PeopleSignal.objects.get(pk=r.json()['data']['id'])


def test_a_manual_role_on_a_contact_joins_its_stakeholder(
    authed_api_a, account, decision_cycle, contact,
):
    from app_modules.decision_cycles.models import Stakeholder
    first = _create(authed_api_a, account, contact=contact, cycle=decision_cycle)
    second = _create(authed_api_a, account, contact=contact, cycle=decision_cycle,
                     role=PeopleRole.DECISION_MAKER)

    s = Stakeholder.objects.get(decision_cycle=decision_cycle, contact=contact)
    assert first.stakeholder_id == s.id == second.stakeholder_id
    assert s.current_signal_id == first.id          # the later role does not move it


def test_an_existing_stakeholder_of_the_contact_is_reused(
    authed_api_a, account, decision_cycle, contact, user_a,
):
    from app_modules.decision_cycles.models import Stakeholder
    existing = Stakeholder(decision_cycle=decision_cycle, contact=contact)
    existing.save(user=user_a, client_id=account.client_id)
    ps = _create(authed_api_a, account, contact=contact, cycle=decision_cycle)
    assert ps.stakeholder_id == existing.id
    assert Stakeholder.objects.filter(decision_cycle=decision_cycle).count() == 1


def test_without_a_contact_no_stakeholder(authed_api_a, account, decision_cycle):
    from app_modules.core_modules.models import StandardDepartment
    sales, _ = StandardDepartment.objects.get_or_create(name='Sales')
    ps = _create(authed_api_a, account, cycle=decision_cycle, target_department=str(sales.id))
    assert ps.stakeholder_id is None


def test_an_llm_signal_never_joins_at_creation(
    authed_api_a, account, activity, contact, decision_cycle,
):
    """Even in a DC with a contact: an extracted signal is resolved by the
    rep (resolve), never joined at creation."""
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(decision_cycle=decision_cycle)
    ps = _create(authed_api_a, account, contact=contact, activity=activity, source='LLM_EXTRACTED')
    assert ps.decision_cycle_id == decision_cycle.id
    assert ps.stakeholder_id is None


def test_without_a_decision_cycle_no_stakeholder(authed_api_a, account, activity, contact):
    ps = _create(authed_api_a, account, contact=contact, activity=activity)
    assert ps.decision_cycle_id is None
    assert ps.stakeholder_id is None
