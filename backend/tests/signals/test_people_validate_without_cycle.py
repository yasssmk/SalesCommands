# backend/tests/signals/test_people_validate_without_cycle.py
"""
Sprint « Cycle de vie des contacts », 8b-1 (PO) — a People signal on an
activity WITHOUT a decision cycle is validated (true / false) like any
signal, WITHOUT a stakeholder:
  * SignalManager.validate and POST /module-signals/people/{id}/validate/
    refuse a People without stakeholder ONLY when the signal has a DC;
  * once the activity is linked to a DC (« Start Decision Cycle », étape 2
    attachment), the VALIDATED People arrives without stakeholder: POST
    /people/{id}/resolve/ affiliates it WITHOUT changing its status; a People
    already affiliated is still refused; never an automatic affiliation.
Real paths; helpers reused from test_people_resolve.py and
test_signal_cycle_attachment.py.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import SignalStatus
from tests.signals.test_people_resolve import URL, _cycle, _people, _resolve
from tests.signals.test_signal_cycle_attachment import (
    _cycle as _attach_cycle,
    _patch_cycle,
    _plain_activity,
)


pytestmark = pytest.mark.django_db


def _validate(api, ps):
    return api.post(f'{URL}{ps.id}/validate/')


def test_without_a_cycle_the_generic_validate_validates_the_people(authed_api_a, activity, user_a):
    ps = _people(activity, user_a, cycle=None, name='Marc')
    r = _validate(authed_api_a, ps)
    assert r.status_code == status.HTTP_200_OK, r.content
    ps.refresh_from_db()
    assert ps.status == SignalStatus.VALIDATED
    assert ps.stakeholder_id is None


def test_signal_manager_validates_a_people_without_cycle(activity, user_a):
    from app_modules.signals.services.signal_manager import SignalManager
    ps = _people(activity, user_a, cycle=None)
    SignalManager.validate(ps, user=user_a)
    ps.refresh_from_db()
    assert ps.status == SignalStatus.VALIDATED and ps.stakeholder_id is None


def test_with_a_cycle_the_people_stays_subject_to_resolve(authed_api_a, account, activity, user_a):
    ps = _people(activity, user_a, cycle=_cycle(account, user_a))
    r = _validate(authed_api_a, ps)
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    ps.refresh_from_db()
    assert ps.status == SignalStatus.PENDING


def test_validated_without_cycle_then_linked_to_a_dc_later_then_link_to_the_deal(
    authed_api_a, account, user_a,
):
    """The PO scenario outside the campaign -> DC passage (8c-0 links that
    one automatically): ✓ without DC -> the activity linked to a DC later ->
    the validated People has the DC and no stakeholder (never auto-affiliated
    here) -> resolve affiliates it, its status and validation untouched."""
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal
    activity = _plain_activity(account, user_a)
    ps = _people(activity, user_a, cycle=None, name='Marc')
    assert _validate(authed_api_a, ps).status_code == 200
    ps.refresh_from_db()
    validated_at = ps.validated_at

    dc = _attach_cycle(account, user_a)
    _patch_cycle(authed_api_a, activity, dc)
    ps.refresh_from_db()
    assert ps.decision_cycle_id == dc.id
    assert ps.status == SignalStatus.VALIDATED
    assert ps.stakeholder_id is None                       # never automatic here
    assert not Stakeholder.objects.filter(decision_cycle=dc).exists()

    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}})
    assert r.status_code == status.HTTP_200_OK, r.content
    ps = PeopleSignal.objects.get(pk=ps.pk)
    assert ps.stakeholder is not None and ps.stakeholder.decision_cycle_id == dc.id
    assert ps.status == SignalStatus.VALIDATED
    assert ps.validated_at == validated_at                 # status untouched


def test_resolve_still_refuses_an_already_affiliated_people(authed_api_a, account, activity, user_a):
    ps = _people(activity, user_a, cycle=_cycle(account, user_a))
    assert _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}}).status_code == 200
    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Other'}})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'already' in r.content.decode().lower()


def test_resolve_refuses_a_validated_people_without_cycle(authed_api_a, activity, user_a):
    ps = _people(activity, user_a, cycle=None)
    assert _validate(authed_api_a, ps).status_code == 200
    r = _resolve(authed_api_a, ps, {'create': {'full_name': 'Marc'}})
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert 'decision cycle' in r.content.decode().lower()
