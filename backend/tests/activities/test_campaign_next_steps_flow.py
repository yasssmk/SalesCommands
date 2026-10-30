# backend/tests/activities/test_campaign_next_steps_flow.py
"""
Sprint Next steps 5.14b -- a SUCCESSFUL campaign activity's next steps, by
the real endpoints:
  * ✓ (Create) without a DC born yet: a NEW decision cycle created inline
    from the next step (create-with-entities: next_step_signal_id +
    inline_cycle + source_activity_id) -- the next step validated, the cycle
    stamped with its source_campaign, the campaign activity now "born";
  * the 2nd ✓ goes INTO that born cycle: a creation from the next step with
    no decision_cycle_id defaults to the born cycle (next_step_cycle_default
    reads born_decision_cycle -- the ONE helper, computed at read time, PO:
    never stored on the signal);
  * Link: the candidates are the open activities of the born cycle only;
    none while no cycle is born.
"""

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal
from tests.activities.test_next_planned_step import _activity, _cycle, _get


pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


@pytest.fixture
def won_call(account, user_a):
    """A campaign call logged SUCCESSFUL (the prospect being chased)."""
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
    from app_modules.contacts.models import Contact
    campaign = Campaign(name='Cold calling', campaign_type=CampaignType.OUTBOUND, owner=user_a,
                        planned_start_date=TODAY, planned_end_date=TODAY + datetime.timedelta(days=30))
    campaign.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=campaign, account=account, status='IN_PROGRESS')
    ca.save(user=user_a, client_id=account.client_id)
    contact = Contact(account=account, first_name='Jordan', last_name='Lee')
    contact.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=contact, status='IN_PROGRESS')
    cc.save(user=user_a, client_id=account.client_id)
    a = Activity(title='Cold call Jordan', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome='SUCCESSFUL', account=account,
                 owner=user_a, campaign=campaign, campaign_account=ca, campaign_contact=cc,
                 sequence_position=1, scheduled_date=TODAY)
    a.save(user=user_a, client_id=account.client_id)
    a.contacts.add(contact)
    a.jordan = contact
    return a


def _next_step(activity, user, title):
    ns = NextStepSignal(account=activity.account, source_activity=activity, suggested_title=title,
                        suggested_activity_type=ActivityType.MEETING,
                        source=SignalSource.LLM_EXTRACTED, confidence=0.8)
    ns.save(user=user, client_id=activity.client_id)
    return ns


def _convert(api, won_call, ns, cycle_name='Deal Jordan'):
    r = api.post('/module-activities/create-with-entities/', {
        'activity': {
            'title': ns.suggested_title, 'activity_type': 'MEETING', 'status': 'PLANNED',
            'account_id': str(won_call.account_id), 'contact_ids': [str(won_call.jordan.id)],
            'scheduled_date': str(TODAY + datetime.timedelta(days=7)),
            'source_activity_id': str(won_call.id), 'next_step_signal_id': str(ns.id),
        },
        'inline_contact': None, 'inline_cycle': {'name': cycle_name},
        'inline_step_stage': 'TECHNICAL_FIT',
    }, format='json')
    assert r.status_code in (200, 201), r.content
    from app_modules.activities.models import Activity
    return Activity.objects.get(next_step_signal=ns)


def _candidates(api, ns):
    r = api.get(reverse('module_signals:next-step-link-candidates', kwargs={'pk': ns.id}))
    assert r.status_code == 200, r.content
    return [c['id'] for c in r.json()['data']['candidates']]


def test_first_validation_creates_a_new_cycle_born_from_the_campaign_activity(
    authed_api_a, won_call, user_a,
):
    ns = _next_step(won_call, user_a, 'Discovery meeting')
    created = _convert(authed_api_a, won_call, ns)
    ns.refresh_from_db()
    assert ns.status == SignalStatus.VALIDATED
    assert created.decision_cycle is not None
    assert created.decision_cycle.source_campaign_id == won_call.campaign_id
    assert created.decision_step.stage == 'TECHNICAL_FIT'
    born = _get(authed_api_a, won_call)['next_planned_step']
    assert born['source'] == 'BORN_DECISION_CYCLE'
    assert born['decision_cycle']['id'] == str(created.decision_cycle_id)


def test_the_second_validation_goes_into_the_born_cycle(authed_api_a, won_call, user_a):
    first = _next_step(won_call, user_a, 'Discovery meeting')
    second = _next_step(won_call, user_a, 'Send the security questionnaire')
    born = _convert(authed_api_a, won_call, first).decision_cycle
    r = authed_api_a.post('/module-activities/', {
        'title': second.suggested_title, 'activity_type': 'MEETING',
        'account_id': str(won_call.account_id), 'contact_ids': [str(won_call.jordan.id)],
        'scheduled_date': str(TODAY + datetime.timedelta(days=10)),
        'next_step_signal_id': str(second.id),
    }, format='json')
    assert r.status_code == 201, r.content
    from app_modules.activities.models import Activity
    created = Activity.objects.get(next_step_signal=second)
    assert created.decision_cycle_id == born.id
    assert created.decision_step_id is not None
    from app_modules.decision_cycles.models import DecisionCycle
    assert DecisionCycle.objects.filter(account_id=won_call.account_id).count() == 1


def test_link_no_candidate_while_no_cycle_is_born(authed_api_a, won_call, account, user_a):
    other = _cycle(account, user_a, 'Another deal')
    _activity(account, user_a, 'Unrelated open meeting', date=TODAY, cycle=other)
    ns = _next_step(won_call, user_a, 'Discovery meeting')
    assert _candidates(authed_api_a, ns) == []


def test_link_candidates_are_the_born_cycle_open_activities_only(
    authed_api_a, won_call, account, user_a,
):
    other = _cycle(account, user_a, 'Another deal')
    unrelated = _activity(account, user_a, 'Unrelated open meeting', date=TODAY, cycle=other)
    first = _next_step(won_call, user_a, 'Discovery meeting')
    second = _next_step(won_call, user_a, 'Security review')
    born_activity = _convert(authed_api_a, won_call, first)
    ids = _candidates(authed_api_a, second)
    assert ids == [str(born_activity.id)]
    assert str(unrelated.id) not in ids


def test_the_born_cycle_helper_is_shared(won_call, authed_api_a, user_a):
    from app_modules.activities.services.activity_sequence_service import born_decision_cycle
    assert born_decision_cycle(won_call) is None
    ns = _next_step(won_call, user_a, 'Discovery meeting')
    created = _convert(authed_api_a, won_call, ns)
    assert born_decision_cycle(won_call) == created.decision_cycle
