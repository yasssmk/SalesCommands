# backend/tests/signals/test_activity_next_step_provenance.py
"""
Sprint Next steps 2.5 (D11) — provenance of an activity CREATED from a next
step, for the "From next step" line of the Context section.

GET /module-activities/{id}/ → data.next_step_signal_detail:
    {id, title, source_activity: {id, title, date}}   (null otherwise)

Read through the real detail endpoint: its get_object()
(permissions/mixins.py) refetches the row with model.objects.get(), WITHOUT
the retrieve select_related / prefetch — the field must not depend on them.
"""

import datetime

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import SignalSource
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db


def _detail(authed_api, activity_id):
    response = authed_api.get(f'/module-activities/{activity_id}/')
    assert response.status_code == status.HTTP_200_OK, response.content
    return response.json()['data']


@pytest.fixture
def conversation(account, user_a):
    """The conversation the next step was extracted from (completed)."""
    from app_modules.activities.models import Activity
    a = Activity(
        title='Atelier business case', activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED, account=account, owner=user_a,
        scheduled_date=datetime.date(2026, 10, 19),
        completed_at=timezone.make_aware(datetime.datetime(2026, 10, 20, 14, 0)),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


def _converted(authed_api, account, contact, conversation, user):
    from app_modules.activities.models import Activity
    ns = NextStepSignal(
        account=account, source_activity=conversation,
        suggested_title='Revue sécurité avec le DSI',
        suggested_activity_type=ActivityType.MEETING,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user, client_id=account.client_id)
    response = authed_api.post('/module-activities/', {
        'title': 'Revue sécurité', 'activity_type': 'MEETING',
        'account_id': str(account.id), 'contact_ids': [str(contact.id)],
        'scheduled_date': '2026-11-03', 'next_step_signal_id': str(ns.id),
    }, format='json')
    assert response.status_code == status.HTTP_201_CREATED, response.content
    return ns, Activity.objects.get(next_step_signal=ns)


def test_detail_of_an_activity_created_from_a_next_step(
    authed_api_a, account, contact, conversation, user_a,
):
    ns, created = _converted(authed_api_a, account, contact, conversation, user_a)

    data = _detail(authed_api_a, created.id)

    assert data['next_step_signal_detail'] == {
        'id': str(ns.id),
        'title': 'Revue sécurité avec le DSI',
        'source_activity': {
            'id': str(conversation.id),
            'title': 'Atelier business case',
            'date': '2026-10-20',          # completed_at wins over scheduled_date
        },
    }


def test_source_date_falls_back_to_the_planned_date(
    authed_api_a, account, contact, conversation, user_a,
):
    conversation.completed_at = None
    conversation.save(user=user_a)
    _ns, created = _converted(authed_api_a, account, contact, conversation, user_a)

    data = _detail(authed_api_a, created.id)

    assert data['next_step_signal_detail']['source_activity']['date'] == '2026-10-19'


def test_null_without_an_origin_next_step(authed_api_a, conversation):
    assert _detail(authed_api_a, conversation.id)['next_step_signal_detail'] is None


def test_null_once_the_next_step_is_deleted(
    authed_api_a, account, contact, conversation, user_a,
):
    ns, created = _converted(authed_api_a, account, contact, conversation, user_a)
    ns.delete()   # Activity.next_step_signal is SET_NULL

    assert _detail(authed_api_a, created.id)['next_step_signal_detail'] is None
