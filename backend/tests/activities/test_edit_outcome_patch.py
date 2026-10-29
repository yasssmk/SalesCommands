# backend/tests/activities/test_edit_outcome_patch.py
"""
Sprint Next steps 5.17 -- the outcome edited from the Edit activity drawer:
PATCH /module-activities/{id}/ with the drawer's payload on a COMPLETED
activity (ActivityUpdateSerializer accepts `outcome`; it is refused unless
the final status is COMPLETED). On a campaign activity the payload carries
only the always-editable fields (title, type, objective, description) + the
outcome -- the campaign-locked ones are never sent (COND-1).

The 5.14a post_save applies on that path, by the real endpoint:
  * a final outcome -> the prospect's sequence stops;
  * an outcome changed after a final one -> accepted on the activity, no
    transition of the prospect, no 500, logged.
"""

import logging

import pytest

from app_modules.activities.constants import ActivityStatus
from tests.activities.test_campaign_sequence_stop import (  # noqa: F401
    _contact_status, _in_progress, _open_steps,
)
from tests.activities.test_next_planned_step import _days, chain  # noqa: F401


pytestmark = pytest.mark.django_db


def _drawer_patch(api, activity, outcome):
    """The Edit activity drawer's PATCH on a campaign activity."""
    activity.refresh_from_db()
    return api.patch(f'/module-activities/{activity.id}/', {
        'title': activity.title,
        'activity_type': activity.activity_type,
        'call_to_action': activity.call_to_action,
        'description': activity.description,
        'outcome': outcome,
    }, format='json')


@pytest.fixture
def emailed(chain):
    """Step 1 COMPLETED with a non-final outcome; steps 2-3 still open."""
    from app_modules.activities.models import Activity
    s1 = chain(1, ActivityStatus.COMPLETED, _days(-2))
    chain(2, date=_days(1))
    chain(3, date=_days(4))
    _in_progress(s1)
    Activity.objects.filter(id=s1.id).update(outcome='FOLLOW_UP_NEEDED')
    return s1


def test_a_final_outcome_from_the_drawer_stops_the_sequence(authed_api_a, emailed):
    r = _drawer_patch(authed_api_a, emailed, 'SUCCESSFUL')
    assert r.status_code == 200, r.content
    emailed.refresh_from_db()
    assert emailed.outcome == 'SUCCESSFUL'
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'COMPLETED'


def test_a_terminal_outcome_from_the_drawer_stops_the_prospect(authed_api_a, emailed):
    r = _drawer_patch(authed_api_a, emailed, 'NOT_INTERESTED')
    assert r.status_code == 200, r.content
    assert _open_steps(emailed) == 0
    assert _contact_status(emailed) == 'STOPPED'


def test_changed_after_a_final_one_no_transition_no_500_logged(authed_api_a, emailed, caplog):
    assert _drawer_patch(authed_api_a, emailed, 'SUCCESSFUL').status_code == 200
    with caplog.at_level(logging.WARNING):
        r = _drawer_patch(authed_api_a, emailed, 'NOT_INTERESTED')
    assert r.status_code == 200, r.content
    emailed.refresh_from_db()
    assert emailed.outcome == 'NOT_INTERESTED'
    assert _contact_status(emailed) == 'COMPLETED'
    assert any(rec.getMessage() == 'campaign_final_outcome_changed_no_transition'
               for rec in caplog.records)


def test_a_non_final_outcome_keeps_the_sequence(authed_api_a, emailed):
    r = _drawer_patch(authed_api_a, emailed, 'NO_ANSWER')
    assert r.status_code == 200, r.content
    assert _open_steps(emailed) == 2
    assert _contact_status(emailed) == 'IN_PROGRESS'


def test_the_outcome_is_refused_on_a_planned_activity(authed_api_a, chain):
    s1 = chain(1, date=_days(0))
    r = _drawer_patch(authed_api_a, s1, 'SUCCESSFUL')
    assert r.status_code == 400, r.content
