# backend/tests/activities/test_stakeholder_role_on_activity.py
"""
Sprint « Cycle de vie des contacts », 8g-6 (TD-232) — the stakeholder fiche
(opened from the Activity's « External team ») shows the role of a
non-converted stakeholder. GET /module-activities/{id}/ → stakeholders_detail
carries role / role_display / influence_display, READ on the stakeholder's
current_signal (the role is never copied onto the stakeholder) — None when it
has no current signal.
"""

import pytest

from tests.signals.test_signal_cycle_attachment import _cycle, _people, _plain_activity


pytestmark = pytest.mark.django_db


def _stakeholder(cycle, user, current_signal=None):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, full_name='Marc', current_signal=current_signal)
    s.save(user=user, client_id=cycle.client_id)
    return s


def _detail(api, activity):
    r = api.get(f'/module-activities/{activity.id}/')
    assert r.status_code == 200, r.content
    body = r.json()
    return body.get('data', body)['stakeholders_detail'][0]


def test_the_role_is_read_on_the_current_signal(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _plain_activity(account, user_a)
    signal = _people(activity, user_a, 'Marc', decision_cycle=cycle)
    st = _stakeholder(cycle, user_a, current_signal=signal)
    activity.stakeholders.add(st)
    row = _detail(authed_api_a, activity)
    assert row['role'] == signal.role
    assert row['role_display'] == signal.get_role_display()


def test_no_current_signal_no_role(authed_api_a, account, user_a):
    activity = _plain_activity(account, user_a)
    activity.stakeholders.add(_stakeholder(_cycle(account, user_a), user_a))
    row = _detail(authed_api_a, activity)
    assert row['role'] is None and row['role_display'] is None
