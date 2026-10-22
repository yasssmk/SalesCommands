# backend/tests/signals/test_nextstep_conversion_defaults.py
"""
Sprint Next steps 2.2b — converting a next step fills the Activity from it,
ONLY where the create payload leaves the field empty (an explicit value
always wins). Central point: services/next_step_materialization.py, used by
both creation paths (POST /module-activities/ and create-with-entities).

  * description    ← suggested_topics
  * call_to_action ← suggested_objective + success criterion
  * decision_cycle ← the next step's cycle (same account), when none sent
  * decision_step  ← suggested_decision_step when it belongs to the cycle,
                     else the cycle's CURRENT step (computed, never stored)
  * dates (D6)     ← suggested_due_date: MEETING / CALL / DEMO →
                     scheduled_date, other types → due_date
The backend never adds a contact on its own.
"""

import datetime

import pytest
from rest_framework import status

from app_modules.activities.constants import (
    ActivityStatus,
    ActivityType,
    NEXT_STEP_SUCCESS_CRITERION_LABEL,
    NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR,
)
from app_modules.signals.constants import SignalSource
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db

URL = '/module-activities/'
URL_ENTITIES = '/module-activities/create-with-entities/'


def _step(cycle, user, order):
    from app_modules.decision_cycles.models import DecisionStep
    step = DecisionStep(cycle=cycle, name=f'Step {order}', order=order)
    step.save(user=user, client_id=cycle.client_id)
    return step


@pytest.fixture
def steps(decision_cycle, user_a):
    """Three ordered steps. Step 1 holds a COMPLETED activity and step 2 a
    PLANNED one, so step 1 is derived VALIDATED (all done + a later step has
    activities) and the CURRENT step is step 2 — not the first one."""
    from app_modules.activities.models import Activity
    s1, s2, s3 = (_step(decision_cycle, user_a, o) for o in (1, 2, 3))
    done = Activity(
        title='Done on step 1', activity_type=ActivityType.CALL,
        status=ActivityStatus.COMPLETED, account=decision_cycle.account,
        owner=user_a, decision_cycle=decision_cycle, decision_step=s1,
        scheduled_date=datetime.date(2026, 10, 1),
    )
    done.save(user=user_a, client_id=decision_cycle.client_id)
    planned = Activity(
        title='Planned on step 2', activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED, account=decision_cycle.account,
        owner=user_a, decision_cycle=decision_cycle, decision_step=s2,
        scheduled_date=datetime.date(2026, 12, 1),
    )
    planned.save(user=user_a, client_id=decision_cycle.client_id)
    return s1, s2, s3


def _next_step(account, activity, user, cycle=None, **fields):
    fields.setdefault('suggested_activity_type', ActivityType.MEETING)
    ns = NextStepSignal(
        account=account, source_activity=activity, decision_cycle=cycle,
        suggested_title='Revue sécurité avec le DSI',
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
        **fields,
    )
    ns.save(user=user, client_id=account.client_id)
    return ns


def _payload(account, contact, ns, **extra):
    payload = {
        'title': 'Revue sécurité avec le DSI',
        'activity_type': 'MEETING',
        'account_id': str(account.id),
        'contact_ids': [str(contact.id)],
        'next_step_signal_id': str(ns.id),
    }
    payload.update(extra)
    return {k: v for k, v in payload.items() if v is not None}


def _created(ns):
    from app_modules.activities.models import Activity
    return Activity.objects.get(next_step_signal=ns)


# =============================================================================
# Texts — description / objective + success criterion
# =============================================================================

class TestTextsFromTheNextStep:

    def test_topics_and_objective_with_criterion_fill_the_empty_fields(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _next_step(
            account, activity, user_a,
            suggested_topics='Hébergement UE, DPA, SOC 2',
            suggested_objective='Lever le blocage sécurité',
            suggested_success_criterion='Le DSI valide l\'hébergement',
        )

        response = authed_api_a.post(
            URL, _payload(account, contact, ns, scheduled_date='2026-11-03'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.description == 'Hébergement UE, DPA, SOC 2'
        assert created.call_to_action == (
            'Lever le blocage sécurité'
            + NEXT_STEP_OBJECTIVE_PARTS_SEPARATOR
            + NEXT_STEP_SUCCESS_CRITERION_LABEL
            + 'Le DSI valide l\'hébergement'
        )

    def test_success_criterion_alone_becomes_the_objective(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _next_step(account, activity, user_a,
                        suggested_success_criterion='Budget validé')

        response = authed_api_a.post(
            URL, _payload(account, contact, ns, scheduled_date='2026-11-03'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert _created(ns).call_to_action == (
            NEXT_STEP_SUCCESS_CRITERION_LABEL + 'Budget validé'
        )

    def test_values_sent_by_the_rep_win(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _next_step(
            account, activity, user_a, suggested_topics='topics',
            suggested_objective='objective', suggested_success_criterion='crit',
        )

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
            description='Rep description', call_to_action='Rep objective',
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.description == 'Rep description'
        assert created.call_to_action == 'Rep objective'


# =============================================================================
# Dates — D6
# =============================================================================

class TestDateFromTheNextStep:

    @pytest.mark.parametrize('activity_type', ['MEETING', 'CALL', 'DEMO'])
    def test_meeting_like_types_are_scheduled(
        self, authed_api_a, account, activity, contact, user_a, activity_type,
    ):
        ns = _next_step(account, activity, user_a,
                        suggested_due_date=datetime.date(2026, 11, 3))

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, activity_type=activity_type,
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.scheduled_date == datetime.date(2026, 11, 3)
        assert created.due_date is None

    @pytest.mark.parametrize('activity_type', ['EMAIL', 'TASK', 'LINKEDIN', 'OTHER'])
    def test_other_types_are_due(
        self, authed_api_a, account, activity, contact, user_a, activity_type,
    ):
        ns = _next_step(account, activity, user_a,
                        suggested_due_date=datetime.date(2026, 10, 23))

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, activity_type=activity_type,
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.due_date == datetime.date(2026, 10, 23)
        assert created.scheduled_date is None

    def test_a_date_sent_by_the_rep_wins(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _next_step(account, activity, user_a,
                        suggested_due_date=datetime.date(2026, 11, 3))

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, due_date='2026-12-24',
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.due_date == datetime.date(2026, 12, 24)
        assert created.scheduled_date is None


# =============================================================================
# DC step — proposed, else the current one (computed, never stored)
# =============================================================================

class TestDecisionStepFromTheNextStep:

    def test_the_proposed_step_is_used(
        self, authed_api_a, account, activity, contact, decision_cycle, steps, user_a,
    ):
        s1, _s2, s3 = steps
        ns = _next_step(account, activity, user_a, cycle=decision_cycle,
                        suggested_decision_step=s3)

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
            decision_cycle_id=str(decision_cycle.id),
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert _created(ns).decision_step == s3

    def test_without_proposal_the_current_step_is_used_and_not_stored(
        self, authed_api_a, account, activity, contact, decision_cycle, steps, user_a,
    ):
        _s1, s2, _s3 = steps
        ns = _next_step(account, activity, user_a, cycle=decision_cycle)

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
            decision_cycle_id=str(decision_cycle.id),
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert _created(ns).decision_step == s2   # current, not the first
        ns.refresh_from_db()
        assert ns.suggested_decision_step is None   # never stored

    def test_without_cycle_in_the_payload_the_next_step_cycle_is_used(
        self, authed_api_a, account, activity, contact, decision_cycle, steps, user_a,
    ):
        _s1, s2, _s3 = steps
        ns = _next_step(account, activity, user_a, cycle=decision_cycle)

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = _created(ns)
        assert created.decision_cycle == decision_cycle
        assert created.decision_step == s2

    def test_a_proposed_step_of_another_cycle_falls_back_to_the_current_one(
        self, authed_api_a, account, activity, contact, decision_cycle, steps, user_a,
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        _s1, s2, _s3 = steps
        other = DecisionCycle(account=account, owner=user_a, name='Other', is_active=True)
        other.save(user=user_a, client_id=account.client_id)
        foreign_step = _step(other, user_a, 1)
        ns = _next_step(account, activity, user_a, cycle=decision_cycle,
                        suggested_decision_step=foreign_step)

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
            decision_cycle_id=str(decision_cycle.id),
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert _created(ns).decision_step == s2

    def test_a_step_sent_by_the_rep_wins(
        self, authed_api_a, account, activity, contact, decision_cycle, steps, user_a,
    ):
        s1, _s2, s3 = steps
        ns = _next_step(account, activity, user_a, cycle=decision_cycle,
                        suggested_decision_step=s3)

        response = authed_api_a.post(URL, _payload(
            account, contact, ns, scheduled_date='2026-11-03',
            decision_cycle_id=str(decision_cycle.id), decision_step_id=str(s1.id),
        ), format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert _created(ns).decision_step == s1


# =============================================================================
# Same rules on the create-with-entities path; no contact added by the server
# =============================================================================

class TestCreateWithEntitiesUsesTheSameDefaults:

    def test_inline_contact_conversion_gets_the_same_defaults(
        self, authed_api_a, account, activity, decision_cycle, steps, user_a,
    ):
        _s1, s2, _s3 = steps
        ns = _next_step(
            account, activity, user_a, cycle=decision_cycle,
            suggested_topics='Hébergement UE',
            suggested_objective='Lever le blocage',
            suggested_due_date=datetime.date(2026, 10, 23),
            suggested_activity_type=ActivityType.EMAIL,
        )

        response = authed_api_a.post(URL_ENTITIES, {
            'activity': {
                'title': 'Envoyer le DPA', 'activity_type': 'EMAIL',
                'account_id': str(account.id),
                'next_step_signal_id': str(ns.id),
            },
            'inline_contact': {'first_name': 'Thomas', 'last_name': 'Lefèvre'},
        }, format='json')

        assert response.status_code in (200, 201), response.content
        created = _created(ns)
        assert created.description == 'Hébergement UE'
        assert created.call_to_action == 'Lever le blocage'
        assert created.due_date == datetime.date(2026, 10, 23)
        assert created.scheduled_date is None
        assert created.decision_cycle == decision_cycle
        assert created.decision_step == s2
        # Only the inline contact — the server adds none from the next step.
        assert [c.last_name for c in created.contacts.all()] == ['Lefèvre']
