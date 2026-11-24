# backend/tests/signals/test_signals_fk_no_existence_oracle.py
"""
NO EXISTENCE ORACLE on the FKs written by the signals endpoints (TD-246,
Lot 0 — 0.4, signals switched to core/tenant_fk.py).

The tenant isolation of the signals writes was fixed post-resolution
(`_validate_fk_scope`): DRF first resolved every FK on `Model.objects.all()`,
then the serializer refused an object of another tenant with
OBJECT_NOT_FOUND. But an id that does NOT exist never reached that check:
DRF refused it first with its own message (`Invalid pk "<id>" - object does
not exist.`). The two bodies differed — a requester could tell that a UUID
exists in ANOTHER tenant.

Through the real endpoints (two tenants, conftest fixtures), for every FK a
signal write accepts — account, source_activity, contact (Blocker),
target_contact (Objective, People), decision_cycle (People),
suggested_contacts (NextStep, M2M), and the two FKs of the NextStep PATCH
found by introspecting the serializers (suggested_decision_step,
suggested_people, M2M) — an unknown id and an id of another
tenant must give the SAME status and the SAME body (400, OBJECT_NOT_FOUND),
and nothing is written.

Payload builders are the ones of test_signals_tenant_isolation.py (imported,
not duplicated).

DB: Postgres.
"""

import uuid

import pytest
from rest_framework import status

from app_modules.signals.constants import InfluenceLevel, PeopleRole
from app_modules.signals.models import (
    BlockerSignal,
    NextStepSignal,
    ObjectiveSignal,
    PeopleSignal,
)
from core.error_messages import CoreErrorMessages
from tests.signals.test_nextstep_api import (
    _llm_next_step,
    _people,
    _step,
    _url_detail as _nextstep_detail,
)
from tests.signals.test_signals_tenant_isolation import (
    _blocker_detail,
    _blocker_list,
    _blocker_payload,
    _mk_blocker,
    _nextstep_list,
    _nextstep_payload,
    _objective_list,
    _objective_payload,
    _people_list,
    _people_payload,
)

pytestmark = pytest.mark.django_db

OBJECT_NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)


def _assert_same_refusal(unknown, foreign):
    """Same status, same body; the standard refusal; no DRF existence wording."""
    assert unknown.status_code == foreign.status_code == status.HTTP_400_BAD_REQUEST, (
        unknown.status_code, unknown.content, foreign.status_code, foreign.content,
    )
    assert unknown.content == foreign.content, (
        'existence oracle: an unknown id and an id of another tenant give '
        f'different bodies:\n  unknown -> {unknown.content!r}\n  foreign -> {foreign.content!r}'
    )
    assert OBJECT_NOT_FOUND in foreign.content.decode()
    assert 'does not exist' not in unknown.content.decode()


def _unknown_id():
    return str(uuid.uuid4())


class TestBaseFKs:

    def test_account(self, authed_api_a, activity, other_tenant_account):
        unknown = authed_api_a.post(
            _blocker_list(), {**_blocker_payload(other_tenant_account, activity),
                              'account': _unknown_id()}, format='json')
        foreign = authed_api_a.post(
            _blocker_list(), _blocker_payload(other_tenant_account, activity), format='json')
        _assert_same_refusal(unknown, foreign)
        assert BlockerSignal.objects.count() == 0

    def test_source_activity(self, authed_api_a, account, other_tenant_activity):
        unknown = authed_api_a.post(
            _blocker_list(), {**_blocker_payload(account, other_tenant_activity),
                              'source_activity': _unknown_id()}, format='json')
        foreign = authed_api_a.post(
            _blocker_list(), _blocker_payload(account, other_tenant_activity), format='json')
        _assert_same_refusal(unknown, foreign)
        assert BlockerSignal.objects.count() == 0


class TestBlockerContact:

    def test_post(self, authed_api_a, account, activity, other_tenant_contact):
        unknown = authed_api_a.post(
            _blocker_list(), _blocker_payload(account, activity, contact=_unknown_id()),
            format='json')
        foreign = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, activity, contact=str(other_tenant_contact.id)),
            format='json')
        _assert_same_refusal(unknown, foreign)
        assert BlockerSignal.objects.count() == 0

    def test_patch(self, authed_api_a, account, activity, contact, other_tenant_contact, user_a):
        b = _mk_blocker(account, activity, user_a, contact=contact)
        unknown = authed_api_a.patch(_blocker_detail(b.id), {'contact': _unknown_id()},
                                     format='json')
        foreign = authed_api_a.patch(_blocker_detail(b.id),
                                     {'contact': str(other_tenant_contact.id)}, format='json')
        _assert_same_refusal(unknown, foreign)
        b.refresh_from_db()
        assert b.contact_id == contact.id


class TestTargetContact:

    def test_objective(self, authed_api_a, account, activity, other_tenant_contact):
        payload = _objective_payload(account, activity, other_tenant_contact)
        unknown = authed_api_a.post(_objective_list(),
                                    {**payload, 'target_contact': _unknown_id()}, format='json')
        foreign = authed_api_a.post(_objective_list(), payload, format='json')
        _assert_same_refusal(unknown, foreign)
        assert ObjectiveSignal.objects.count() == 0

    def test_people(self, authed_api_a, account, activity, other_tenant_contact):
        payload = _people_payload(account, activity, other_tenant_contact)
        unknown = authed_api_a.post(_people_list(),
                                    {**payload, 'target_contact': _unknown_id()}, format='json')
        foreign = authed_api_a.post(_people_list(), payload, format='json')
        _assert_same_refusal(unknown, foreign)
        assert PeopleSignal.objects.count() == 0


class TestPeopleDecisionCycle:

    def test_post(self, authed_api_a, account, contact, other_tenant_decision_cycle):
        # Payload of test_signals_tenant_isolation.py::test_r7_post_decision_cycle_*.
        payload = {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'decision_cycle': str(other_tenant_decision_cycle.id),
            'role': PeopleRole.CHAMPION,
            'influence': InfluenceLevel.HIGH,
            'target_contact': str(contact.id),
            'notes': 'Qualified from DC workspace',
        }
        unknown = authed_api_a.post(_people_list(),
                                    {**payload, 'decision_cycle': _unknown_id()}, format='json')
        foreign = authed_api_a.post(_people_list(), payload, format='json')
        _assert_same_refusal(unknown, foreign)
        assert PeopleSignal.objects.count() == 0


class TestNextStepSuggestedContacts:

    def test_post(self, authed_api_a, account, activity, contact, other_tenant_contact):
        foreign_payload = _nextstep_payload(account, activity, [contact, other_tenant_contact])
        unknown_payload = {**foreign_payload,
                           'suggested_contacts': [str(contact.id), _unknown_id()]}
        unknown = authed_api_a.post(_nextstep_list(), unknown_payload, format='json')
        foreign = authed_api_a.post(_nextstep_list(), foreign_payload, format='json')
        _assert_same_refusal(unknown, foreign)
        assert NextStepSignal.objects.count() == 0


class TestNextStepStructuredFKs:
    """The two NextStep PATCH FKs found by introspecting the serializers."""

    def test_suggested_people(
        self, authed_api_a, account, activity, user_a,
        other_tenant_account, other_tenant_activity, user_b,
    ):
        foreign_people = _people(other_tenant_account, other_tenant_activity, user_b, 'Marc')
        ns = _llm_next_step(account, activity, user_a)
        unknown = authed_api_a.patch(_nextstep_detail(ns.id),
                                     {'suggested_people': [_unknown_id()]}, format='json')
        foreign = authed_api_a.patch(_nextstep_detail(ns.id),
                                     {'suggested_people': [str(foreign_people.id)]},
                                     format='json')
        _assert_same_refusal(unknown, foreign)
        assert list(ns.suggested_people.all()) == []

    def test_suggested_decision_step(
        self, authed_api_a, account, activity, decision_cycle, user_a,
        other_tenant_decision_cycle, user_b,
    ):
        foreign_step = _step(other_tenant_decision_cycle, user_b)
        ns = _llm_next_step(account, activity, user_a, decision_cycle=decision_cycle)
        unknown = authed_api_a.patch(_nextstep_detail(ns.id),
                                     {'suggested_decision_step': _unknown_id()}, format='json')
        foreign = authed_api_a.patch(_nextstep_detail(ns.id),
                                     {'suggested_decision_step': str(foreign_step.id)},
                                     format='json')
        _assert_same_refusal(unknown, foreign)
        ns.refresh_from_db()
        assert ns.suggested_decision_step_id is None
