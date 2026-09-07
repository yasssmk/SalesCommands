# backend/tests/signals/test_objective_list_exposes_success_criteria_notes.py
"""
Verify the Objective LIST payload exposes success_criteria + notes.

The Activity detail drawer is fed by the aggregated (list) payload, which
maps objective -> ObjectiveSignalListSerializer. That serializer omitted
success_criteria / notes, so values saved through the objective update
serializer never reached the read drawer and looked "not saved".

These fields are read-only on the list payload (writes still go through
the update serializer); the list must simply surface them so the read
drawer can render what was saved.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import ObjectiveSignal


pytestmark = pytest.mark.django_db(transaction=True)


def _extract_results(response):
    body = response.json()
    results = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(results, dict):
        results = results.get('results', results)
    return results


class TestObjectiveListExposesSuccessCriteriaNotes:

    def test_objective_list_includes_success_criteria_and_notes(
        self, authed_api_a, account, activity, user_a,
    ):
        o = ObjectiveSignal(
            account=account, source_activity=activity,
            summary='cut reporting time', source=SignalSource.LLM_EXTRACTED,
            success_criteria='Reporting cycle under 2 days',
            notes='Sponsor confirmed in the QBR',
            what='OPS', dimension='TIME',
        )
        o.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:objective-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(o.id))
        assert row['success_criteria'] == 'Reporting cycle under 2 days'
        assert row['notes'] == 'Sponsor confirmed in the QBR'
