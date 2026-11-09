# backend/tests/activities/test_conversion_into_existing_cycle.py
"""
Sprint « Cycle de vie des contacts », 8c-3 (PO, revises 5.13 « always a new
DC ») — the conversion (« Start Decision Cycle », ✓ Create / « + Add next
step » on a campaign activity without a born DC) may target an EXISTING open
DC of the account: POST /module-activities/create-with-entities/ with
activity.decision_cycle_id (+ its step) + source_activity_id, no inline_cycle:
  * the activity is created in that DC, from the campaign activity;
  * born_decision_cycle detects it (next_planned_step BORN_DECISION_CYCLE: the
    « Start Decision Cycle » CTA disappears);
  * the sequence's signals take the DC (étape 2) and its VALIDATED People
    join stakeholders (8c-0);
  * source_campaign is NOT set (the DC was not born from the campaign).
New cycle: unchanged (source_campaign set).
Helpers reused from tests/signals/test_signal_cycle_attachment.py.
"""

import datetime

import pytest

from app_modules.signals.constants import SignalStatus
from tests.signals.test_signal_cycle_attachment import (
    TODAY,
    _campaign_account,
    _cycle,
    _pain,
    _people,
    _prospect_activity,
    _start_decision_cycle,
)


pytestmark = pytest.mark.django_db


def _convert_into(api, campaign_activity, cycle):
    """The drawer's conversion payload for an EXISTING cycle."""
    from app_modules.activities.models import Activity
    r = api.post('/module-activities/create-with-entities/', {
        'activity': {
            'title': 'Discovery meeting', 'activity_type': 'MEETING', 'status': 'PLANNED',
            'account_id': str(campaign_activity.account_id),
            'contact_ids': [str(campaign_activity.prospect.id)],
            'scheduled_date': str(TODAY + datetime.timedelta(days=7)),
            'decision_cycle_id': str(cycle.id),
            'decision_step_id': str(cycle.qualification.id),
            'source_activity_id': str(campaign_activity.id),
        },
        'inline_contact': None, 'inline_cycle': None, 'inline_step_stage': None,
    }, format='json')
    assert r.status_code in (200, 201), r.content
    return Activity.objects.get(source_activity=campaign_activity)


def test_converting_into_an_existing_open_cycle(authed_api_a, account, user_a):
    from app_modules.decision_cycles.models import DecisionCycle, Stakeholder
    ca = _campaign_account(account, user_a)
    call = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL')
    second = _prospect_activity(ca, user_a, 'Hugo')
    pain = _pain(second, user_a)
    marc = _people(call, user_a, 'Marc', status=SignalStatus.VALIDATED)
    existing = _cycle(account, user_a, name='Existing deal')

    created = _convert_into(authed_api_a, call, existing)

    assert created.decision_cycle_id == existing.id
    assert created.source_activity_id == call.id
    # born_decision_cycle detects it: the CTA disappears
    r = authed_api_a.get(f'/module-activities/{call.id}/')
    body = r.json().get('data', r.json())
    assert body['next_planned_step']['source'] == 'BORN_DECISION_CYCLE'
    assert body['next_planned_step']['decision_cycle']['id'] == str(existing.id)
    # the sequence's signals take the DC; the VALIDATED People joins a stakeholder
    pain.refresh_from_db(); marc.refresh_from_db()
    assert pain.decision_cycle_id == existing.id
    assert marc.decision_cycle_id == existing.id
    assert Stakeholder.objects.get(pk=marc.stakeholder_id).decision_cycle_id == existing.id
    # source_campaign NOT set: the DC was not born from the campaign
    assert DecisionCycle.objects.get(pk=existing.pk).source_campaign_id is None


def test_a_new_cycle_is_unchanged_source_campaign_set(authed_api_a, account, user_a):
    ca = _campaign_account(account, user_a)
    call = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL')
    born = _start_decision_cycle(authed_api_a, call)
    assert born.source_campaign_id == ca.campaign_id
