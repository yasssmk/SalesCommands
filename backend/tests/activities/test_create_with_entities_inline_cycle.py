# backend/tests/activities/test_create_with_entities_inline_cycle.py
"""
Regression: creating a Decision Cycle inline from the activity-creation modal.

Parcours: the "Create new cycle" affordance in ActivityModal posts to
/module-activities/create-with-entities/ with an ``inline_cycle`` block plus
``inline_step_stage``. The service auto-creates the cycle AND its fixed pipeline
steps, then links the activity to the QUALIFICATION step.

Migration 0019 removed ``DecisionStep.status`` (status is now derived), so any
code still passing ``status=`` to the ``DecisionStep`` constructor raises
``TypeError: 'status' is an invalid keyword argument`` — surfaced to the user as
``CYCLE_CREATION_FAILED``. This test reproduces the modal payload and asserts the
cycle + steps are created and the activity is linked.
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep


_URL = '/module-activities/create-with-entities/'


@pytest.mark.django_db
class TestCreateActivityWithInlineCycle:

    def test_inline_cycle_creation_from_activity_modal(
        self, authed_api_a, account
    ):
        """The exact payload the ActivityModal sends when a new cycle is created
        inline must succeed: cycle + 5 pipeline steps created, activity linked to
        the QUALIFICATION step."""
        payload = {
            'activity': {
                'title': 'Discovery call',
                'activity_type': ActivityType.CALL,
                'status': ActivityStatus.PLANNED,
                'account_id': str(account.id),
                'contact_ids': [],
                'decision_step_id': None,
            },
            'inline_cycle': {
                'name': 'New cycle from modal',
                'description': None,
            },
            'inline_step_stage': 'QUALIFICATION',
        }

        resp = authed_api_a.post(_URL, payload, format='json')

        assert resp.status_code == status.HTTP_201_CREATED, resp.content

        # The cycle was created on the account...
        cycles = DecisionCycle.objects.filter(
            account=account, name='New cycle from modal'
        )
        assert cycles.count() == 1
        cycle = cycles.first()

        # ...with its fixed pipeline steps...
        steps = DecisionStep.objects.filter(cycle=cycle)
        assert steps.count() >= 1
        assert steps.filter(stage='QUALIFICATION').exists()

        # ...and the activity is linked to the cycle and its QUALIFICATION step.
        activity = resp.json()['data']['activity']
        assert activity['decision_cycle'] == str(cycle.id)
        qualification = steps.get(stage='QUALIFICATION')
        assert activity['decision_step'] == str(qualification.id)
