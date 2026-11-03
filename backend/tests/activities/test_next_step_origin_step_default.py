# backend/tests/activities/test_next_step_origin_step_default.py
"""
Sprint « Cycle de vie des contacts », étape 7c -- the DC step of an activity
created from a next step, when none is sent (next_step_step_default, mirror of
the drawer):
  1. the step the next step suggests, when it belongs to the cycle (existing
     rule, next_step_materialization.py);
  2. else the step of the ORIGIN activity (the next step's conversation), when
     it belongs to the cycle -- was: the cycle's current step;
  3. else the cycle's current step.

Real path: POST /module-activities/ with next_step_signal_id and
decision_cycle_id, no decision_step_id.
"""

import pytest
from rest_framework import status

from app_modules.signals.constants import SignalSource


pytestmark = pytest.mark.django_db


def _contact(account, user):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='Pat', last_name='Participant')
    c.save(user=user, client_id=account.client_id)
    return c


def _conversation_on(authed_api, account, user, stage):
    """A cycle (auto-created steps) and its conversation on `stage`."""
    contact = _contact(account, user)
    r = authed_api.post('/module-activities/create-with-entities/', {
        'activity': {'title': 'Atelier', 'activity_type': 'MEETING', 'status': 'PLANNED',
                     'account_id': str(account.id), 'scheduled_date': '2026-11-10',
                     'contact_ids': [str(contact.id)]},
        'inline_contact': None, 'inline_cycle': {'name': 'Deal'}, 'inline_step_stage': stage,
    }, format='json')
    assert r.status_code in (200, 201), r.content
    from app_modules.activities.models import Activity
    a = Activity.objects.get(title='Atelier')
    return a, a.decision_cycle, contact


def _next_step(conversation, user, suggested_step=None):
    from app_modules.signals.models import NextStepSignal
    ns = NextStepSignal(account=conversation.account, source_activity=conversation,
                        decision_cycle=conversation.decision_cycle, suggested_title='Follow-up',
                        suggested_activity_type='TASK', source=SignalSource.LLM_EXTRACTED,
                        confidence=0.8, suggested_decision_step=suggested_step)
    ns.save(user=user, client_id=conversation.client_id)
    return ns


def _create_from(authed_api, ns, cycle, account):
    r = authed_api.post('/module-activities/', {
        'title': 'Follow-up', 'activity_type': 'TASK', 'status': 'PLANNED',
        'account_id': str(account.id), 'due_date': '2026-11-30',
        'decision_cycle_id': str(cycle.id), 'next_step_signal_id': str(ns.id),
    }, format='json')
    assert r.status_code == status.HTTP_201_CREATED, r.content
    from app_modules.activities.models import Activity
    return Activity.objects.get(next_step_signal=ns)


def test_without_a_suggested_step_the_origin_step(authed_api_a, account, user_a):
    conversation, cycle, _ = _conversation_on(authed_api_a, account, user_a, 'BUSINESS_CASE')
    created = _create_from(authed_api_a, _next_step(conversation, user_a), cycle, account)
    assert created.decision_step.stage == 'BUSINESS_CASE'      # not the current (Qualification)


def test_the_suggested_step_of_the_cycle_wins(authed_api_a, account, user_a):
    conversation, cycle, _ = _conversation_on(authed_api_a, account, user_a, 'BUSINESS_CASE')
    closing = cycle.steps.get(stage='CLOSING')
    created = _create_from(authed_api_a, _next_step(conversation, user_a, closing), cycle, account)
    assert created.decision_step_id == closing.id
