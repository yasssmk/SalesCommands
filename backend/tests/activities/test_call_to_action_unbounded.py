# backend/tests/activities/test_call_to_action_unbounded.py
"""
Sprint Next steps 2.2a (R3) — Activity.call_to_action (the "Objective") is
never truncated nor refused for its length.

It was a CharField(500) while every source that fills it is unbounded:
  * NextStepSignal.suggested_objective (TextField) — the conversion copies it
    (services/next_step_materialization.py), and 2.2b appends the success
    criterion;
  * Campaign.activity_objective / CampaignContact.objective (TextField) —
    campaign_execution_service._create_activity copies them.
A longer value was a 400 on the API and a database error on the copies.
"""

import datetime

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db

LONG_OBJECTIVE = ((
    'Valider l\'hébergement des données en Europe avec Laurent Petit (DSI) : '
    'DPA, rapport SOC 2, localisation Francfort / Paris, réversibilité. '
) * 12).strip()   # ~1 700 characters, far above the old 500 limit
# (strip: DRF trims surrounding whitespace — not a truncation)


@pytest.fixture
def contact(db, account, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name='Thomas', last_name='Lefèvre')
    c.save(user=user_a, client_id=account.client_id)
    return c


@pytest.fixture
def activity(db, account, user_a):
    from app_modules.activities.models import Activity
    a = Activity(
        title='Atelier business case', activity_type=ActivityType.MEETING,
        status=ActivityStatus.PLANNED, account=account, owner=user_a,
        scheduled_date=datetime.date(2026, 11, 3),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


def test_long_objective_is_accepted_and_stored_whole_on_patch(
    authed_api_a, activity,
):
    assert len(LONG_OBJECTIVE) > 500

    response = authed_api_a.patch(
        f'/module-activities/{activity.id}/',
        {'call_to_action': LONG_OBJECTIVE}, format='json',
    )

    assert response.status_code == status.HTTP_200_OK, response.content
    activity.refresh_from_db()
    assert activity.call_to_action == LONG_OBJECTIVE


def test_converting_a_next_step_keeps_its_long_objective_whole(
    authed_api_a, account, activity, contact, user_a,
):
    from app_modules.activities.models import Activity
    from app_modules.signals.constants import SignalSource
    from app_modules.signals.models import NextStepSignal

    ns = NextStepSignal(
        account=account, source_activity=activity,
        suggested_title='Revue sécurité avec le DSI',
        suggested_activity_type=ActivityType.MEETING,
        suggested_objective=LONG_OBJECTIVE,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user_a, client_id=account.client_id)

    response = authed_api_a.post('/module-activities/', {
        'title': 'Revue sécurité avec le DSI',
        'activity_type': 'MEETING',
        'account_id': str(account.id),
        'contact_ids': [str(contact.id)],
        'scheduled_date': '2026-11-03',
        'next_step_signal_id': str(ns.id),
    }, format='json')

    assert response.status_code == status.HTTP_201_CREATED, response.content
    created = Activity.objects.get(next_step_signal=ns)
    assert created.call_to_action == LONG_OBJECTIVE


# =============================================================================
# Migration 0023 — the reverse is refused while it would truncate
# =============================================================================

def _reverse_guard():
    import importlib
    migration = importlib.import_module(
        'app_modules.activities.migrations.0023_activity_call_to_action_text'
    )
    return migration.refuse_truncating_reverse


def test_reverse_guard_refuses_while_an_objective_is_longer_than_500(activity):
    from django.apps import apps

    activity.call_to_action = LONG_OBJECTIVE
    activity.save()

    with pytest.raises(RuntimeError, match='TRUNCATE'):
        _reverse_guard()(apps, None)
    activity.refresh_from_db()
    assert activity.call_to_action == LONG_OBJECTIVE   # nothing touched


def test_reverse_guard_lets_short_objectives_through(activity):
    from django.apps import apps

    activity.call_to_action = 'x' * 500
    activity.save()

    _reverse_guard()(apps, None)   # no error
