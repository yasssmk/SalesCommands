# backend/tests/activities/test_create_with_entities_date_typing.py
"""
Regression: /module-activities/create-with-entities/ returned a 500 on any
activity carrying a due date.

``ActivityCreationService._create_activity`` builds the Activity in memory
straight from the request payload — ``due_date=activity_data.get('due_date')``
— and saves it. ``save()`` coerces on the way OUT to SQL, but Django never
re-reads the row, so the in-memory instance keeps the JSON **string**. The view
then serialises that same instance
(``ActivitySerializer``, whose ``is_overdue`` is a plain ``BooleanField``), and
``Activity.is_overdue`` runs::

    self.due_date < timezone.now().date()      # "2026-09-30" < date(...) -> TypeError

'<' not supported between instances of 'str' and 'datetime.date'. Because the
view is ``@transaction.atomic``, the TypeError escaping the block ROLLED BACK
everything — the activity, the inline cycle, its steps — so the user got a 500
and no trace of the operation.

``scheduled_date`` carried the same defect. It never crashed (``is_scheduled``
only null-checks it), so it was silently the wrong type instead.

The fix is at the ONE place the raw payload becomes an instance, not on
``is_overdue``: the service re-reads the saved row so everything downstream sees
DB-typed values. These tests therefore assert the TYPES on the persisted
instance, not just the absence of a 500 — a guard added to ``is_overdue`` alone
would leave ``scheduled_date`` wrong and would pass a crash-only test.

The standard create path (``ActivityViewSet.create``) goes through a serializer,
which coerces, and is covered here as a non-regression.

Harness mirrors tests/activities/test_create_with_entities_inline_cycle.py (same
endpoint, same authed client, same modal-shaped payload).
"""

from datetime import date, timedelta

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.contacts.models import Contact
from app_modules.decision_cycles.models import DecisionCycle


_URL = '/module-activities/create-with-entities/'
_STANDARD_URL = '/module-activities/'

TODAY = date.today()
PAST = TODAY - timedelta(days=7)
FUTURE = TODAY + timedelta(days=7)


def _payload(account, *, due_date=None, scheduled_date=None, title='Call',
             cycle_name='Cycle from modal'):
    """The exact shape ActivityModal posts when it creates a cycle inline."""
    activity = {
        'title': title,
        'activity_type': ActivityType.CALL,
        'status': ActivityStatus.PLANNED,
        'account_id': str(account.id),
        'contact_ids': [],
        'decision_step_id': None,
    }
    if due_date is not None:
        activity['due_date'] = due_date.isoformat()          # JSON -> a STRING
    if scheduled_date is not None:
        activity['scheduled_date'] = scheduled_date.isoformat()
    return {
        'activity': activity,
        'inline_cycle': {'name': cycle_name, 'description': None},
        'inline_step_stage': 'QUALIFICATION',
    }


@pytest.mark.django_db
class TestDueDateDoesNotCrashTheResponse:

    def test_an_activity_with_a_due_date_creates_and_serialises(
        self, authed_api_a, account,
    ):
        """THE crash: before the fix this raised
        TypeError: '<' not supported between instances of 'str' and
        'datetime.date' while building the response."""
        resp = authed_api_a.post(
            _URL, _payload(account, due_date=FUTURE), format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        body = resp.json()['data']['activity']
        assert body['due_date'] == FUTURE.isoformat()
        assert body['is_overdue'] is False

    def test_a_past_due_date_reports_overdue_true(self, authed_api_a, account):
        """The flag is not merely non-crashing — it is CORRECT. A guard that
        swallowed the bad type would return False here and pass a crash-only
        test."""
        resp = authed_api_a.post(
            _URL, _payload(account, due_date=PAST, title='Late call'),
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()['data']['activity']['is_overdue'] is True

    def test_the_persisted_instance_carries_real_date_objects(
        self, authed_api_a, account,
    ):
        """The TYPE is the fix, not the absence of a 500: scheduled_date never
        crashed (is_scheduled only null-checks it) but was equally a string."""
        resp = authed_api_a.post(
            _URL,
            _payload(account, due_date=FUTURE, scheduled_date=TODAY,
                     title='Typed call'),
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        activity = Activity.objects.get(id=resp.json()['data']['activity']['id'])
        assert activity.due_date == FUTURE
        assert activity.scheduled_date == TODAY
        # is_overdue must be computable on the freshly returned instance too.
        assert activity.is_overdue is False


@pytest.mark.django_db
class TestTheOperationPersists:
    """The view is @transaction.atomic, so the TypeError used to roll the whole
    operation back: the user saw a 500 AND nothing was created. These assert the
    entities survive."""

    def test_the_activity_and_the_inline_cycle_both_persist(
        self, authed_api_a, account,
    ):
        resp = authed_api_a.post(
            _URL,
            _payload(account, due_date=FUTURE, cycle_name='Persisted cycle'),
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        cycle = DecisionCycle.objects.get(account=account, name='Persisted cycle')
        activity = Activity.objects.get(id=resp.json()['data']['activity']['id'])
        assert activity.decision_cycle_id == cycle.id
        assert cycle.steps.filter(stage='QUALIFICATION').exists()


@pytest.mark.django_db
class TestUnchangedBehaviour:

    def test_the_standard_create_path_still_works(
        self, authed_api_a, account, client_account_a, user_a,
    ):
        """It goes through a serializer (which coerces), so it was never broken
        — pinned so the fix is not mistaken for the thing that made it work.

        Unlike the inline-entities endpoint, this one requires a contact."""
        contact = Contact(account=account, first_name='Std', last_name='Lead',
                          email='std@acme.test')
        contact.save(user=user_a, client_id=client_account_a.id)

        resp = authed_api_a.post(
            _STANDARD_URL,
            {
                'title': 'Standard call',
                'activity_type': ActivityType.CALL,
                'status': ActivityStatus.PLANNED,
                'account_id': str(account.id),
                'due_date': PAST.isoformat(),
                'contact_ids': [str(contact.id)],
            },
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()['data']['is_overdue'] is True

    def test_is_overdue_on_a_db_loaded_activity_is_unchanged(
        self, authed_api_a, account,
    ):
        """The model property itself is not the fix site and keeps its rules:
        a past due date is overdue, unless the activity is closed."""
        resp = authed_api_a.post(
            _URL, _payload(account, due_date=PAST, title='Closed later'),
            format='json',
        )
        activity = Activity.objects.get(id=resp.json()['data']['activity']['id'])

        assert activity.is_overdue is True

        activity.status = ActivityStatus.COMPLETED
        activity.save()
        assert activity.is_overdue is False

    def test_an_activity_without_any_date_is_not_overdue(
        self, authed_api_a, account,
    ):
        resp = authed_api_a.post(
            _URL, _payload(account, title='Undated'), format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()['data']['activity']['is_overdue'] is False
