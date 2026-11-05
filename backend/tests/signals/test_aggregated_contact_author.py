# backend/tests/signals/test_aggregated_contact_author.py
"""
Sprint « Cycle de vie des contacts », 8g-6f — « See signals » of a CONTACT =
what the person SAID: the signals of the activities it attended (unchanged)
UNION the signals it explicitly AUTHORED — today only Blocker / Objection
.contact (« Raised by »). A SUBJECT (PeopleSignal.target_contact) or an OWNER
(Objective.target_contact) is not an author; never a fallback on the
participants to attribute (TD-254). GET /module-signals/all/?contact=…,
bounded by the tenant + the account; no duplicate (present AND author).
"""

import pytest
from rest_framework import status

from tests.signals.test_aggregated_signals_endpoint import _mk_blocker, _mk_objective, _results, _url
from tests.signals.test_signal_cycle_attachment import _people, _plain_activity


pytestmark = pytest.mark.django_db


def _ids(r):
    assert r.status_code == status.HTTP_200_OK, r.content
    rows = _results(r)
    return [row['id'] for row in rows]


def _get(api, account, contact):
    return api.get(_url(), {'account_id': str(account.id), 'contact': str(contact.id)})


def _blocker_raised_by(account, activity, user, contact):
    b = _mk_blocker(account, activity, user)
    type(b).objects.filter(pk=b.pk).update(contact=contact)
    return b


def test_an_objection_it_raised_where_it_was_not_present(authed_api_a, account, user_a, contact, contact_extra):
    absent = _plain_activity(account, user_a, 'Call without the contact')
    absent.contacts.add(contact_extra)
    raised = _blocker_raised_by(account, absent, user_a, contact)
    assert _ids(_get(authed_api_a, account, contact)) == [str(raised.id)]


def test_a_people_signal_it_is_the_subject_of_is_not_said_by_it(authed_api_a, account, user_a, contact, contact_extra):
    from app_modules.signals.models import PeopleSignal
    absent = _plain_activity(account, user_a, 'Call about the contact')
    absent.contacts.add(contact_extra)
    subject = _people(absent, user_a, 'Paul')
    PeopleSignal.objects.filter(pk=subject.pk).update(target_contact=contact)
    assert _ids(_get(authed_api_a, account, contact)) == []


def test_an_objective_it_owns_is_not_said_by_it(authed_api_a, account, user_a, contact, contact_extra):
    absent = _plain_activity(account, user_a, 'Call about the goal')
    absent.contacts.add(contact_extra)
    owned = _mk_objective(account, absent, user_a)
    type(owned).objects.filter(pk=owned.pk).update(target_contact=contact)
    assert _ids(_get(authed_api_a, account, contact)) == []


def test_another_account_is_absent(authed_api_a, account, other_account, user_a, contact):
    elsewhere = _plain_activity(other_account, user_a, 'Other account call')
    _blocker_raised_by(other_account, elsewhere, user_a, contact)
    assert _ids(_get(authed_api_a, account, contact)) == []


def test_present_and_author_appears_once(authed_api_a, account, user_a, contact, contact_extra):
    attended = _plain_activity(account, user_a, 'Workshop')
    attended.contacts.add(contact, contact_extra)
    raised = _blocker_raised_by(account, attended, user_a, contact)
    assert _ids(_get(authed_api_a, account, contact)) == [str(raised.id)]
