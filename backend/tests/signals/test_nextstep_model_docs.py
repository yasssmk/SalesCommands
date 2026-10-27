# backend/tests/signals/test_nextstep_model_docs.py
"""
Sprint Next steps 5.8h (5) -- the NextStepSignal model documents the REAL
conversion: the server adds NO contact when an activity is created from a
next step (services/next_step_materialization.py). The activity's contacts
are what the rep sends; the creation form PRE-FILLS them from the persons the
next step cites (front, activityDefaultsFromNextStep: MEETING / CALL / EMAIL
only, a REJECTED People never used).

Before 5.8h, suggested_people's help_text said "their contacts become the
activity contacts at conversion" -- false (inventory People <-> Contact,
inconsistency 16).
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.signals.constants import PeopleRole, SignalSource
from app_modules.signals.models import NextStepSignal, PeopleSignal


pytestmark = pytest.mark.django_db


def _help_text(field):
    return str(NextStepSignal._meta.get_field(field).help_text)


def test_suggested_people_help_text_states_no_contact_is_added():
    text = _help_text('suggested_people')
    assert 'become the activity contacts' not in text
    assert 'adds no contact' in text
    assert 'pre-fill' in text


def test_the_model_docstring_states_no_contact_is_added():
    assert 'The server adds NO contact at conversion' in NextStepSignal.__doc__


def test_the_behaviour_documented_no_contact_is_added(
    authed_api_a, account, activity, contact, user_a,
):
    """The documented behaviour, by the real endpoint: a People of the next
    step is linked to ANOTHER contact -- the activity gets only the sent one."""
    from app_modules.contacts.models import Contact
    linked = Contact(account=account, first_name='Laurent', last_name='Dubois', job_title='')
    linked.save(user=user_a, client_id=account.client_id)
    people = PeopleSignal(account=account, source_activity=activity, full_name='Laurent Dubois',
                          role=PeopleRole.CHAMPION, source=SignalSource.LLM_EXTRACTED,
                          target_contact=linked)
    people.save(user=user_a, client_id=account.client_id)
    ns = NextStepSignal(account=account, source_activity=activity,
                        suggested_title='Security review',
                        suggested_activity_type=ActivityType.MEETING,
                        source=SignalSource.LLM_EXTRACTED, confidence=0.8)
    ns.save(user=user_a, client_id=account.client_id)
    ns.suggested_people.set([people])

    response = authed_api_a.post('/module-activities/', {
        'title': 'Security review', 'activity_type': 'MEETING',
        'account_id': str(account.id), 'scheduled_date': '2026-11-03',
        'contact_ids': [str(contact.id)], 'next_step_signal_id': str(ns.id),
    }, format='json')

    assert response.status_code == status.HTTP_201_CREATED, response.content
    created = Activity.objects.get(next_step_signal=ns)
    assert list(created.contacts.values_list('id', flat=True)) == [contact.id]
