# backend/tests/signals/test_techstack_no_scope.py
"""
Sprint « Cycle de vie des contacts », étape 2c -- TechStackSignal has NO
scope (PO): a TechStack always describes the account ("which tool, who uses
it"); a tool evaluated on a deal is a CompetitorSignal. The 2b scope field
was removed (migration 0050); decision_cycle is routing to the DC only.

Guards that the scope does not come back: model, /all/ row, choices.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


def test_the_model_has_no_scope_field():
    assert 'scope' not in {f.name for f in TechStackSignal._meta.get_fields()}


def test_the_choices_endpoint_serves_no_tech_scopes(authed_api_a):
    r = authed_api_a.get(reverse('module_signals:choices'))
    assert r.status_code == status.HTTP_200_OK
    assert 'tech_scopes' not in r.json()['data']


def test_the_activity_row_carries_no_scope(authed_api_a, account, activity, user_a):
    sig = TechStackSignal(account=account, source_activity=activity,
                          source=SignalSource.LLM_EXTRACTED, tech_name='HubSpot',
                          source_quote='Sales lives in HubSpot.')
    sig.save(user=user_a, client_id=account.client_id)
    r = authed_api_a.get(reverse('module_signals:signal-all'),
                         {'activity_id': str(activity.id)})
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    row = next(x for x in body.get('results', body) if x['id'] == str(sig.id))
    assert 'scope' not in row
    assert 'scope_display' not in row
