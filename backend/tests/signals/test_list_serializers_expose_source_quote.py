# backend/tests/signals/test_list_serializers_expose_source_quote.py
"""
Verify that list endpoints expose source_quote and metadata fields.

These fields were promoted from BaseSignalDetailSerializer to
BaseSignalListSerializer so that Flat view cards can render quotes
and tech metadata without a per-signal retrieve call.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import (
    BlockerSignal,
    PainSignal,
    ObjectiveSignal,
    ImpactSignal,
    TechStackSignal,
    NextStepSignal,
)


pytestmark = pytest.mark.django_db(transaction=True)


def _extract_results(response):
    body = response.json()
    results = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(results, dict):
        results = results.get('results', results)
    return results


class TestListSerializersExposeSourceQuote:

    def test_pain_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        p = PainSignal(
            account=account, source_activity=activity,
            summary='pain with quote', source=SignalSource.LLM_EXTRACTED,
            source_quote='We lose 5h/week on consolidation',
            what='OPS', dimension='TIME',
        )
        p.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:pain-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(p.id))
        assert row['source_quote'] == 'We lose 5h/week on consolidation'
        assert 'metadata' in row

    def test_objective_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        o = ObjectiveSignal(
            account=account, source_activity=activity,
            summary='objective with quote', source=SignalSource.LLM_EXTRACTED,
            source_quote='We want to cut reporting time by 50%',
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
        assert row['source_quote'] == 'We want to cut reporting time by 50%'
        assert 'metadata' in row

    def test_impact_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        i = ImpactSignal(
            account=account, source_activity=activity,
            summary='impact with quote', source=SignalSource.LLM_EXTRACTED,
            source_quote='This costs us 200k per year',
            what='OPS', dimension='TIME',
        )
        i.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:impact-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(i.id))
        assert row['source_quote'] == 'This costs us 200k per year'
        assert 'metadata' in row

    def test_techstack_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        t = TechStackSignal(
            account=account, source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
            source_quote='We use Salesforce for CRM',
            metadata={'pending_tech_name': 'Salesforce'},
        )
        t.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:tech-stack-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(t.id))
        assert row['source_quote'] == 'We use Salesforce for CRM'
        assert row['metadata']['pending_tech_name'] == 'Salesforce'

    def test_blocker_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='blocker with quote', source=SignalSource.LLM_EXTRACTED,
            source_quote='Budget is frozen until Q2',
        )
        b.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:blocker-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(b.id))
        assert row['source_quote'] == 'Budget is frozen until Q2'
        assert 'metadata' in row

    def test_nextstep_list_includes_source_quote_and_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            summary='next step with quote', source=SignalSource.LLM_EXTRACTED,
            source_quote='Let us schedule a follow-up next week',
        )
        ns.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            reverse('module_signals:next-step-list'),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        results = _extract_results(response)
        row = next(r for r in results if r['id'] == str(ns.id))
        assert row['source_quote'] == 'Let us schedule a follow-up next week'
        assert 'metadata' in row
