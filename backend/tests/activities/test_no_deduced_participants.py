# backend/tests/activities/test_no_deduced_participants.py
"""
Sprint Next steps 5.8c (PO rule: a next step neither creates nor describes any
person, it CITES names) -- the deduced participants (B2, 5.8a) are WITHDRAWN:
GET /module-activities/{id}/ carries no `participants`; the service and its
constant are gone. The activity's contacts (contacts_detail) are untouched.
The full_name of the DC People view (PeopleConsolidationService) is KEPT
(tests/decision_cycles/test_people_consolidation_full_name.py).
"""

import importlib.util

import pytest

from app_modules.activities import constants
from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db


def test_the_activity_detail_has_no_deduced_participants(authed_api_a, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.contacts.models import Contact
    contact = Contact(account=account, first_name='Thomas', last_name='Lefèvre')
    contact.save(user=user_a, client_id=account.client_id)
    activity = Activity(title='Security review', activity_type=ActivityType.MEETING,
                        status=ActivityStatus.PLANNED, account=account, owner=user_a)
    activity.save(user=user_a, client_id=account.client_id)
    activity.contacts.add(contact)

    data = authed_api_a.get(f'/module-activities/{activity.id}/').json()['data']
    assert 'participants' not in data
    assert [c['id'] for c in data['contacts_detail']] == [str(contact.id)]


def test_the_service_and_its_constant_are_gone():
    assert importlib.util.find_spec('app_modules.activities.services.activity_participants') is None
    assert not hasattr(constants, 'ParticipantSource')
