# backend/tests/signals/test_activity_next_step_origins.py
"""
Sprint Next steps 5.9 -- PROVENANCE, widened (PO): an activity coming from
next steps shows the CONVERSATIONS they came from in its Context section, to
find quickly the transcripts that talk about this step. There may be SEVERAL:

  * the next step that CREATED it (Activity.next_step_signal);
  * the next steps LINKED to it afterwards (attached_next_step_signals);

each with its origin conversation (source_activity: id, title, date).

GET /module-activities/{id}/ -> data.next_step_origins:
    [{id, title, date}, ...]   one entry per CONVERSATION (two next steps from
    the same conversation -> one entry), sorted by conversation date (oldest
    first, undated last); a REJECTED next step is left out; [] without any.

Read through the real detail endpoint (lesson 4): its get_object() refetches
the row WITHOUT the retrieve select_related / prefetch -- direct reads.
next_step_signal_detail (2.5) is unchanged.
"""

import datetime

import pytest
from django.utils import timezone
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db


def _detail(authed_api, activity_id):
    response = authed_api.get(f'/module-activities/{activity_id}/')
    assert response.status_code == status.HTTP_200_OK, response.content
    return response.json()['data']


def _conversation(account, user, title, *, completed=None, scheduled=None):
    from app_modules.activities.models import Activity
    a = Activity(
        title=title, activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED if completed else ActivityStatus.PLANNED,
        account=account, owner=user, scheduled_date=scheduled,
        completed_at=(timezone.make_aware(datetime.datetime.combine(completed, datetime.time(14)))
                      if completed else None),
    )
    a.save(user=user, client_id=account.client_id)
    return a


def _next_step(account, conversation, user, title, *, status=SignalStatus.PENDING,
               attached_to=None):
    ns = NextStepSignal(
        account=account, source_activity=conversation, suggested_title=title,
        suggested_activity_type=ActivityType.MEETING,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user, client_id=account.client_id)
    if attached_to is not None or status != SignalStatus.PENDING:
        ns.attached_activity = attached_to
        ns.status = status
        ns.save(user=user, client_id=account.client_id)
    return ns


@pytest.fixture
def conversations(account, user_a):
    return {
        'atelier': _conversation(account, user_a, 'Atelier business case',
                                 completed=datetime.date(2026, 10, 20)),
        'kickoff': _conversation(account, user_a, 'Kick-off',
                                 completed=datetime.date(2026, 9, 15)),
        'rejected_only': _conversation(account, user_a, 'Call RSSI',
                                       completed=datetime.date(2026, 10, 1)),
        'undated': _conversation(account, user_a, 'Notes sans date'),
    }


def _created_from(authed_api, account, contact, ns):
    from app_modules.activities.models import Activity
    response = authed_api.post('/module-activities/', {
        'title': 'Revue sécurité', 'activity_type': 'MEETING',
        'account_id': str(account.id), 'contact_ids': [str(contact.id)],
        'scheduled_date': '2026-11-03', 'next_step_signal_id': str(ns.id),
    }, format='json')
    assert response.status_code == status.HTTP_201_CREATED, response.content
    return Activity.objects.get(next_step_signal=ns)


def _entry(conversation, date):
    return {'id': str(conversation.id), 'title': conversation.title, 'date': date}


def test_the_creating_and_the_linked_conversations_sorted_by_date(
    authed_api_a, account, contact, conversations, user_a,
):
    c = conversations
    creator = _next_step(account, c['atelier'], user_a, 'Revue sécurité avec le DSI')
    activity = _created_from(authed_api_a, account, contact, creator)
    # Linked afterwards: one from an older conversation, one more from the
    # same conversation as the creator (-> no duplicate), one REJECTED.
    _next_step(account, c['kickoff'], user_a, 'Valider le périmètre',
               status=SignalStatus.VALIDATED, attached_to=activity)
    _next_step(account, c['atelier'], user_a, 'Envoyer le DPA',
               status=SignalStatus.VALIDATED, attached_to=activity)
    _next_step(account, c['rejected_only'], user_a, 'Former Karim',
               status=SignalStatus.REJECTED, attached_to=activity)

    assert _detail(authed_api_a, activity.id)['next_step_origins'] == [
        _entry(c['kickoff'], '2026-09-15'),
        _entry(c['atelier'], '2026-10-20'),
    ]


def test_an_undated_conversation_comes_last(
    authed_api_a, account, contact, conversations, user_a,
):
    c = conversations
    creator = _next_step(account, c['undated'], user_a, 'Rappeler le DSI')
    activity = _created_from(authed_api_a, account, contact, creator)
    _next_step(account, c['kickoff'], user_a, 'Valider le périmètre',
               status=SignalStatus.VALIDATED, attached_to=activity)

    assert _detail(authed_api_a, activity.id)['next_step_origins'] == [
        _entry(c['kickoff'], '2026-09-15'),
        _entry(c['undated'], None),
    ]


def test_a_rejected_creating_next_step_is_left_out(
    authed_api_a, account, contact, conversations, user_a,
):
    c = conversations
    creator = _next_step(account, c['atelier'], user_a, 'Revue sécurité avec le DSI')
    activity = _created_from(authed_api_a, account, contact, creator)
    creator.refresh_from_db()
    creator.status = SignalStatus.REJECTED
    creator.save(user=user_a, client_id=account.client_id)

    assert _detail(authed_api_a, activity.id)['next_step_origins'] == []


def test_linked_only(authed_api_a, account, conversations, user_a):
    """An activity never created from a next step, only linked to one."""
    c = conversations
    activity = _conversation(account, user_a, 'Revue planifiée',
                             scheduled=datetime.date(2026, 11, 10))
    _next_step(account, c['atelier'], user_a, 'Revue sécurité avec le DSI',
               status=SignalStatus.VALIDATED, attached_to=activity)

    assert _detail(authed_api_a, activity.id)['next_step_origins'] == [
        _entry(c['atelier'], '2026-10-20'),
    ]


def test_empty_without_any_next_step(authed_api_a, conversations):
    assert _detail(authed_api_a, conversations['atelier'].id)['next_step_origins'] == []


def test_next_step_signal_detail_is_unchanged(
    authed_api_a, account, contact, conversations, user_a,
):
    creator = _next_step(account, conversations['atelier'], user_a, 'Revue sécurité avec le DSI')
    activity = _created_from(authed_api_a, account, contact, creator)
    assert _detail(authed_api_a, activity.id)['next_step_signal_detail']['id'] == str(creator.id)


def test_another_tenants_next_step_is_never_read(
    authed_api_a, account, conversations, user_a, other_tenant_account,
    other_tenant_activity, user_b,
):
    """Multi-tenant strict: a next step of tenant B pointing (by a corrupted
    FK) at tenant A's activity never shows."""
    activity = _conversation(account, user_a, 'Revue planifiée',
                             scheduled=datetime.date(2026, 11, 10))
    foreign = NextStepSignal(
        account=other_tenant_account, source_activity=other_tenant_activity,
        suggested_title='Globex follow-up', suggested_activity_type=ActivityType.MEETING,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    foreign.save(user=user_b, client_id=other_tenant_account.client_id)
    NextStepSignal.objects.filter(id=foreign.id).update(
        attached_activity=activity, status=SignalStatus.VALIDATED,
    )

    assert _detail(authed_api_a, activity.id)['next_step_origins'] == []
