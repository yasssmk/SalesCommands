# backend/tests/signals/test_techstack_scope.py
"""
Sprint « Cycle de vie des contacts », étape 2b (1) -- the SCOPE of a
TechStack is an explicit field, TechStackSignal.scope (TechScope ACCOUNT /
DEAL), NOT NULL, default ACCOUNT. The decision cycle no longer carries it.

PO rule: every piece of information comes from an activity and always goes
up through the DC; its scope is either the deal (a tool evaluated on this
deal) or the account (a tool in place, valid for the account, DC included).

Real paths: POST / PATCH /module-signals/tech-stack/, the /all/ row the
Activity drawer reads, and the extraction persist_stage (default ACCOUNT,
documented -- the prompt does not tell the scope, TD).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


def _post(api, account, activity, **extra):
    body = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'tech_name': 'Salesforce',
        'source_quote': 'We run the whole pipeline in Salesforce',
        **extra,
    }
    return api.post(reverse('module_signals:tech-stack-list'), body, format='json')


def _tech(account, activity, user):
    sig = TechStackSignal(account=account, source_activity=activity,
                          source=SignalSource.LLM_EXTRACTED, tech_name='HubSpot',
                          source_quote='Sales lives in HubSpot.')
    sig.save(user=user, client_id=account.client_id)
    return sig


def test_constant_values():
    from app_modules.signals.constants import TechScope
    assert list(TechScope.values) == ['ACCOUNT', 'DEAL']


def test_the_choices_endpoint_serves_the_scope_labels(authed_api_a):
    """Étape 2b (2): the Activity UI reads the « Account-wide » / « This
    deal » labels from GET /signals/choices/ (tech_scopes)."""
    r = authed_api_a.get(reverse('module_signals:choices'))
    assert r.status_code == status.HTTP_200_OK
    assert r.json()['data']['tech_scopes'] == [
        {'value': 'ACCOUNT', 'label': 'Account-wide'},
        {'value': 'DEAL',    'label': 'This deal'},
    ]


def test_a_tech_stack_defaults_to_account(account, activity, user_a):
    sig = _tech(account, activity, user_a)
    sig.refresh_from_db()
    assert sig.scope == 'ACCOUNT'


def test_create_without_scope_is_account(authed_api_a, account, activity):
    r = _post(authed_api_a, account, activity)
    assert r.status_code == status.HTTP_201_CREATED, r.content
    assert TechStackSignal.objects.get(tech_name='Salesforce').scope == 'ACCOUNT'


def test_create_accepts_deal(authed_api_a, account, activity):
    r = _post(authed_api_a, account, activity, scope='DEAL')
    assert r.status_code == status.HTTP_201_CREATED, r.content
    assert TechStackSignal.objects.get(tech_name='Salesforce').scope == 'DEAL'


def test_create_refuses_an_unknown_scope(authed_api_a, account, activity):
    r = _post(authed_api_a, account, activity, scope='WORLD')
    assert r.status_code == status.HTTP_400_BAD_REQUEST, r.content


def test_update_changes_the_scope(authed_api_a, account, activity, user_a):
    sig = _tech(account, activity, user_a)
    r = authed_api_a.patch(
        reverse('module_signals:tech-stack-detail', kwargs={'pk': sig.id}),
        {'scope': 'DEAL'}, format='json',
    )
    assert r.status_code == status.HTTP_200_OK, r.content
    sig.refresh_from_db()
    assert sig.scope == 'DEAL'


def test_the_activity_row_exposes_the_scope(authed_api_a, account, activity, user_a):
    sig = _tech(account, activity, user_a)
    r = authed_api_a.get(reverse('module_signals:signal-all'),
                         {'activity_id': str(activity.id)})
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    row = next(x for x in body.get('results', body) if x['id'] == str(sig.id))
    assert row['scope'] == 'ACCOUNT'
    assert row['scope_display'] == 'Account-wide'


def test_extraction_writes_account_even_inside_a_decision_cycle(
    account, activity, user_a,
):
    """The DC no longer carries the scope: a tool extracted from an activity
    of a DC is ACCOUNT (default, documented) while it still takes the DC."""
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user_a, name='Deal')
    dc.save(user=user_a, client_id=account.client_id)
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(decision_cycle=dc)
    activity.refresh_from_db()

    TranscriptSignalExtractor().persist_stage(
        stage='techstack',
        raw_signals=[{
            'tech_name': 'Zendesk', 'usage_scope': 'COMPANY',
            'source_quote': 'We use Zendesk across the company',
            'confidence': 0.9, 'is_inferred': False,
        }],
        activity=activity, user=user_a, client_id=account.client_id,
        confidence_min=0.5, drop_inferred=True,
    )

    sig = TechStackSignal.objects.get(tech_name='Zendesk')
    assert sig.decision_cycle_id == dc.id
    assert sig.scope == 'ACCOUNT'
