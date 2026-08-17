# backend/tests/signals/test_activity_objective_from_signal.py
"""
S13 sub-step 5/6 — Decision Cycle "Activity Objective" support.

Two ways a DC-linked activity carries an objective (reusing Activity.call_to_action):

1. MANUAL: a rep sets/edits call_to_action on a DC activity (create + PATCH).
   This already works — the tests here are guards.

2. SIGNAL: when a NextStepSignal materialises into an Activity, a
   `suggested_objective` carried on the signal populates the new activity's
   call_to_action — unless the create payload sets call_to_action explicitly
   (explicit wins). The prompt that fills suggested_objective is out of scope.

Real path: POST /module-activities/ (ActivityCreateSerializer.create ->
NextStepSignal materialisation). Postgres.

Mirrors tests/signals/test_activity_create_next_step.py for the materialisation
setup.
"""
from datetime import date

import pytest

from app_modules.activities.models import Activity

URL = '/module-activities/'


def _signal(account, activity, user_a, *, suggested_objective=None):
    from app_modules.signals.models import NextStepSignal
    from app_modules.signals.constants import SignalSource
    sig = NextStepSignal(
        account=account,
        source_activity=activity,
        suggested_title='Follow up on pricing',
        suggested_activity_type='CALL',
        suggested_due_date=date(2026, 6, 15),
        source_quote='We should discuss this next week',
        source=SignalSource.LLM_EXTRACTED,
        suggested_objective=suggested_objective,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


def _payload(account, contact, **extra):
    data = {
        'title': 'Follow up call',
        'activity_type': 'CALL',
        'account_id': str(account.id),
        'contact_ids': [str(contact.id)],
        'scheduled_date': '2026-06-15',
    }
    data.update(extra)
    return data


# ---------------------------------------------------------------------------
# RED repro — signal.suggested_objective → activity.call_to_action
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_signal_objective_maps_to_call_to_action(authed_api_a, account, contact, activity, user_a):
    sig = _signal(account, activity, user_a,
                  suggested_objective='Follow up on security review')

    resp = authed_api_a.post(
        URL, _payload(account, contact, next_step_signal_id=str(sig.id)), format='json',
    )
    assert resp.status_code == 201, resp.data

    act = Activity.objects.get(next_step_signal=sig)
    assert act.call_to_action == 'Follow up on security review'


# ---------------------------------------------------------------------------
# signal WITHOUT objective → call_to_action None (no crash)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_signal_without_objective_leaves_cta_none(authed_api_a, account, contact, activity, user_a):
    sig = _signal(account, activity, user_a, suggested_objective=None)

    resp = authed_api_a.post(
        URL, _payload(account, contact, next_step_signal_id=str(sig.id)), format='json',
    )
    assert resp.status_code == 201, resp.data

    act = Activity.objects.get(next_step_signal=sig)
    assert act.call_to_action is None


# ---------------------------------------------------------------------------
# explicit payload call_to_action wins over signal default
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_explicit_call_to_action_wins_over_signal(authed_api_a, account, contact, activity, user_a):
    sig = _signal(account, activity, user_a, suggested_objective='Signal objective')

    resp = authed_api_a.post(
        URL,
        _payload(account, contact,
                 next_step_signal_id=str(sig.id),
                 call_to_action='Explicit objective'),
        format='json',
    )
    assert resp.status_code == 201, resp.data

    act = Activity.objects.get(next_step_signal=sig)
    assert act.call_to_action == 'Explicit objective'


# ---------------------------------------------------------------------------
# MANUAL — DC-linked activity objective: create + PATCH (guard, already works)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_manual_dc_activity_objective_create_and_patch(authed_api_a, account, contact, user_a):
    from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
    from app_modules.decision_cycles.constants import PipelineStep

    dc = DecisionCycle(account=account, name='Cycle A', owner=user_a)
    dc.save(user=user_a, client_id=account.client_id)
    step = DecisionStep(cycle=dc, name='Qualification',
                        stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=user_a, client_id=account.client_id)

    # Create a DC-linked activity with an objective (call_to_action).
    resp = authed_api_a.post(
        URL,
        _payload(account, contact,
                 decision_cycle_id=str(dc.id),
                 decision_step_id=str(step.id),
                 call_to_action='Prepare pricing proposal'),
        format='json',
    )
    assert resp.status_code == 201, resp.data
    act_id = resp.data['data']['id']

    act = Activity.objects.get(id=act_id)
    assert act.decision_cycle_id == dc.id
    assert act.call_to_action == 'Prepare pricing proposal'

    # PATCH the objective.
    patch = authed_api_a.patch(
        f'{URL}{act_id}/', {'call_to_action': 'Send revised quote'}, format='json',
    )
    assert patch.status_code in (200, 202), patch.data

    act.refresh_from_db()
    assert act.call_to_action == 'Send revised quote'
