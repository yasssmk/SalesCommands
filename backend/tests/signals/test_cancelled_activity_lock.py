# backend/tests/signals/test_cancelled_activity_lock.py
"""
Sprint « Cycle de vie des contacts », 8g-2 (TD-297) — the lock of a
CANCELLED activity's signal bands was front-only (utils/activitySignalsLock.js).
The server now applies THE same rule (activities/services/signals_lock.py):
  * SignalManager.validate / reject / reopen — the central point behind
    POST /module-signals/<type>/{id}/validate|reject|reopen/, the People
    resolve and the next-step materialisation;
  * POST /module-ai-pipelines/activity-extraction/run/.
A COMPLETED activity stays workable (5.11). Standard errors (400).
Helpers reused from test_signal_cycle_attachment.py.
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus
from app_modules.signals.constants import SignalStatus
from tests.signals.test_signal_cycle_attachment import (
    _cycle, _next_step, _pain, _people, _plain_activity,
)


pytestmark = pytest.mark.django_db


def _cancelled(account, user):
    from app_modules.activities.models import Activity
    a = _plain_activity(account, user)
    Activity.objects.filter(pk=a.pk).update(status=ActivityStatus.CANCELLED)
    a.refresh_from_db()
    return a


def _locked(r):
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content
    assert 'cancelled' in r.content.decode().lower()


@pytest.mark.parametrize('action', ['validate', 'reject'])
def test_a_pending_signal_of_a_cancelled_activity_is_not_processed(authed_api_a, account, user_a, action):
    pain = _pain(_cancelled(account, user_a), user_a)
    _locked(authed_api_a.post(f'/module-signals/pain/{pain.id}/{action}/', {}, format='json'))
    pain.refresh_from_db()
    assert pain.status == SignalStatus.PENDING


def test_a_validated_signal_of_a_cancelled_activity_is_not_reopened(authed_api_a, account, user_a):
    from app_modules.signals.models import PainSignal
    pain = _pain(_cancelled(account, user_a), user_a)
    PainSignal.objects.filter(pk=pain.pk).update(status=SignalStatus.VALIDATED)
    _locked(authed_api_a.post(f'/module-signals/pain/{pain.id}/reopen/', {}, format='json'))


def test_a_people_of_a_cancelled_activity_is_not_resolved(authed_api_a, account, user_a):
    activity = _cancelled(account, user_a)
    ps = _people(activity, user_a, 'Marc', decision_cycle=_cycle(account, user_a))
    _locked(authed_api_a.post(f'/module-signals/people/{ps.id}/resolve/',
                              {'create': {'full_name': 'Marc'}}, format='json'))


def test_a_next_step_of_a_cancelled_activity_is_not_materialised(authed_api_a, account, user_a):
    from app_modules.activities.models import Activity
    ns = _next_step(_cancelled(account, user_a), user_a)
    before = Activity.objects.count()
    _locked(authed_api_a.post('/module-activities/', {
        'title': 'Demo', 'activity_type': 'TASK', 'status': 'PLANNED',
        'account_id': str(account.id), 'due_date': '2026-12-01',
        'next_step_signal_id': str(ns.id),
    }, format='json'))
    assert Activity.objects.count() == before


def test_a_cancelled_activity_is_not_analysed(authed_api_a, account, user_a):
    activity = _cancelled(account, user_a)
    _locked(authed_api_a.post('/module-ai-pipelines/activity-extraction/run/',
                              {'activity_id': str(activity.id), 'transcript': 'Paul: we lose data every week and need a fix before the end of the quarter.'},
                              format='json'))


def test_a_completed_activity_stays_workable(authed_api_a, account, user_a):
    """5.11: only CANCELLED locks — a COMPLETED activity's signals are handled."""
    pain = _pain(_plain_activity(account, user_a), user_a)        # COMPLETED
    r = authed_api_a.post(f'/module-signals/pain/{pain.id}/validate/', {}, format='json')
    assert r.status_code == status.HTTP_200_OK, r.content


def test_link_to_the_deal_on_a_cancelled_activity_is_refused(authed_api_a, account, user_a):
    """The link-only resolve (8b-1: a VALIDATED People without stakeholder)
    does not go through SignalManager.validate — guarded at its own start."""
    from app_modules.signals.models import PeopleSignal
    activity = _cancelled(account, user_a)
    ps = _people(activity, user_a, 'Marc', status=SignalStatus.VALIDATED,
                 decision_cycle=_cycle(account, user_a))
    _locked(authed_api_a.post(f'/module-signals/people/{ps.id}/resolve/',
                              {'create': {'full_name': 'Marc'}}, format='json'))
    assert PeopleSignal.objects.get(pk=ps.pk).stakeholder_id is None
