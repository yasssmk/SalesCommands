# backend/tests/signals/test_nextstep_link_candidates.py
"""
Sprint Next steps 2.3 — GET /module-signals/next-steps/{id}/link-candidates/

The existing activities a next step can be LINKED to ("Lier", D2): the OPEN
activities (NON_TERMINAL_STATUSES: PLANNED / ON_HOLD) of the SAME decision
cycle, same tenant — the next step's source activity (its conversation)
excepted. Ranked by NEXT_STEP_LINK_RANKING (signals/constants.py):

  1. people in common   — contacts of the next step's People (and its
                          suggested contacts) also on the activity (more first)
  2. same DC step       — activity step == the proposed step
  3. same type          — activity type == the proposed type
  4. closest date       — |activity date − next step date| (no date last)

The first candidate is the "link" proposal.
"""

import datetime

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import (
    NEXT_STEP_LINK_RANKING,
    PeopleRole,
    SignalSource,
)
from app_modules.signals.models import NextStepSignal, PeopleSignal


pytestmark = pytest.mark.django_db


def _url(pk):
    return reverse('module_signals:next-step-link-candidates', kwargs={'pk': pk})


def _step(cycle, user, order):
    from app_modules.decision_cycles.models import DecisionStep
    step = DecisionStep(cycle=cycle, name=f'Step {order}', order=order)
    step.save(user=user, client_id=cycle.client_id)
    return step


def _contact(account, user, last_name):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='X', last_name=last_name)
    c.save(user=user, client_id=account.client_id)
    return c


def _activity(account, user, title, *, cycle, step=None, type_=ActivityType.CALL,
              status_=ActivityStatus.PLANNED, date=None, contacts=()):
    from app_modules.activities.models import Activity
    a = Activity(
        title=title, activity_type=type_, status=status_, account=account,
        owner=user, decision_cycle=cycle, decision_step=step,
        scheduled_date=date,
    )
    a.save(user=user, client_id=account.client_id)
    if contacts:
        a.contacts.set(contacts)
    return a


@pytest.fixture
def setup(account, activity, decision_cycle, user_a):
    s1, s2 = _step(decision_cycle, user_a, 1), _step(decision_cycle, user_a, 2)
    laurent = _contact(account, user_a, 'Petit')
    people = PeopleSignal(
        account=account, source_activity=activity, full_name='Laurent Petit',
        role=PeopleRole.UNKNOWN, source=SignalSource.LLM_EXTRACTED,
        target_contact=laurent,
    )
    people.save(user=user_a, client_id=account.client_id)
    ns = NextStepSignal(
        account=account, source_activity=activity, decision_cycle=decision_cycle,
        suggested_title='Revue sécurité avec le DSI',
        suggested_activity_type=ActivityType.MEETING,
        suggested_due_date=datetime.date(2026, 11, 10),
        suggested_decision_step=s2,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user_a, client_id=account.client_id)
    ns.suggested_people.set([people])
    return {'ns': ns, 's1': s1, 's2': s2, 'laurent': laurent}


def _ids(response):
    return [c['id'] for c in response.json()['data']['candidates']]


class TestLinkCandidates:

    def test_ranking_people_then_step_then_type_then_date(
        self, authed_api_a, account, decision_cycle, user_a, setup,
    ):
        s1, s2, far = setup['s1'], setup['s2'], datetime.date(2027, 3, 1)
        kw = dict(cycle=decision_cycle)
        date_far = _activity(account, user_a, 'date far', step=s1,
                             date=datetime.date(2026, 12, 30), **kw)
        date_close = _activity(account, user_a, 'date close', step=s1,
                               date=datetime.date(2026, 11, 11), **kw)
        same_type = _activity(account, user_a, 'same type', step=s1,
                              type_=ActivityType.MEETING, date=far, **kw)
        same_step = _activity(account, user_a, 'same step', step=s2, date=far, **kw)
        shared = _activity(account, user_a, 'people in common', step=s1, date=far,
                           contacts=[setup['laurent']], **kw)

        response = authed_api_a.get(_url(setup['ns'].id))

        assert response.status_code == status.HTTP_200_OK, response.content
        assert _ids(response) == [
            str(a.id) for a in (shared, same_step, same_type, date_close, date_far)
        ]
        data = response.json()['data']
        assert data['proposed_activity_id'] == str(shared.id)
        first = data['candidates'][0]
        assert first['shared_people_count'] == 1
        assert first['title'] == 'people in common'

    def test_only_open_activities_of_the_same_cycle(
        self, authed_api_a, account, activity, decision_cycle, user_a, setup,
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        other_cycle = DecisionCycle(account=account, owner=user_a, name='Other',
                                    is_active=True)
        other_cycle.save(user=user_a, client_id=account.client_id)
        kw = dict(step=setup['s1'], date=datetime.date(2026, 11, 20))
        planned = _activity(account, user_a, 'planned', cycle=decision_cycle, **kw)
        on_hold = _activity(account, user_a, 'on hold', cycle=decision_cycle,
                            status_=ActivityStatus.ON_HOLD, **kw)
        _activity(account, user_a, 'completed', cycle=decision_cycle,
                  status_=ActivityStatus.COMPLETED, **kw)
        _activity(account, user_a, 'cancelled', cycle=decision_cycle,
                  status_=ActivityStatus.CANCELLED, **kw)
        _activity(account, user_a, 'other cycle', cycle=other_cycle, **kw)
        _activity(account, user_a, 'no cycle', cycle=None, **kw)
        # The next step's own conversation is never a candidate.
        activity.decision_cycle = decision_cycle
        activity.status = ActivityStatus.PLANNED
        activity.save()

        response = authed_api_a.get(_url(setup['ns'].id))

        assert response.status_code == status.HTTP_200_OK, response.content
        assert set(_ids(response)) == {str(planned.id), str(on_hold.id)}

    def test_an_activity_without_date_comes_after_dated_ones(
        self, authed_api_a, account, decision_cycle, user_a, setup,
    ):
        kw = dict(cycle=decision_cycle, step=setup['s1'])
        undated = _activity(account, user_a, 'no date', **kw)
        dated = _activity(account, user_a, 'far date',
                          date=datetime.date(2027, 6, 1), **kw)

        response = authed_api_a.get(_url(setup['ns'].id))

        assert response.status_code == status.HTTP_200_OK, response.content
        assert _ids(response) == [str(dated.id), str(undated.id)]
        assert response.json()['data']['candidates'][1]['date_distance_days'] is None

    def test_no_candidate_gives_no_proposal(self, authed_api_a, setup):
        response = authed_api_a.get(_url(setup['ns'].id))

        assert response.status_code == status.HTTP_200_OK, response.content
        assert response.json()['data'] == {'proposed_activity_id': None, 'candidates': []}

    def test_a_next_step_without_cycle_has_no_candidate(
        self, authed_api_a, account, activity, decision_cycle, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='hors DC', suggested_activity_type=ActivityType.CALL,
            source=SignalSource.LLM_EXTRACTED,
        )
        ns.save(user=user_a, client_id=account.client_id)
        _activity(account, user_a, 'dc activity', cycle=decision_cycle,
                  date=datetime.date(2026, 11, 20))

        response = authed_api_a.get(_url(ns.id))

        assert response.status_code == status.HTTP_200_OK, response.content
        assert _ids(response) == []

    def test_another_tenant_cannot_read_the_candidates(self, authed_api_b, setup):
        response = authed_api_b.get(_url(setup['ns'].id))

        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_ranking_order_is_a_constant():
    assert NEXT_STEP_LINK_RANKING == (
        'shared_people', 'same_step', 'same_type', 'closest_date',
    )


def test_without_next_step_date_the_reference_is_the_project_local_date(
    authed_api_a, account, activity, decision_cycle, user_a, monkeypatch,
):
    """'Today' is the project's local date (timezone.localdate), not the
    server clock's date (date.today)."""
    from django.utils import timezone

    monkeypatch.setattr(timezone, 'localdate', lambda *a, **k: datetime.date(2030, 1, 1))
    ns = NextStepSignal(
        account=account, source_activity=activity, decision_cycle=decision_cycle,
        suggested_title='sans date', suggested_activity_type=ActivityType.CALL,
        source=SignalSource.LLM_EXTRACTED,
    )
    ns.save(user=user_a, client_id=account.client_id)
    _activity(account, user_a, 'dated', cycle=decision_cycle,
              date=datetime.date(2030, 1, 11))

    response = authed_api_a.get(_url(ns.id))

    assert response.status_code == status.HTTP_200_OK, response.content
    assert response.json()['data']['candidates'][0]['date_distance_days'] == 10
