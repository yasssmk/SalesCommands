# backend/tests/ai_pipelines/test_campaign_next_steps_extraction.py
"""
Sprint Next steps 5.14b -- PO rule: the goal of a campaign is to create
decision cycles; a campaign activity with a SUCCESSFUL outcome (the
SUCCESSFUL_OUTCOMES set: SUCCESSFUL, MEETING_SCHEDULED -- PO decision 3) can
create next steps. The extraction's guard (activity_extraction_view) reads
ONE shared predicate, next_steps_enabled(activity): a decision cycle, OR a
campaign activity with a successful outcome. Any other activity keeps the
silent skip. Without a decision cycle the AI proposes no step (PO decision
4: suggested_decision_step null, the step is chosen in the drawer).

Real endpoint, the LLM replaced by the fake provider (tests/ai_pipelines).
"""

import datetime

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.ai_pipelines.constants import AIPipelineType
from app_modules.ai_pipelines.models import AIPipelineRun

from .conftest import CANNED_REPLIES_HAPPY, CANNED_REPLY_NEXT_STEPS_HAPPY
from .test_activity_extraction_view import TRANSCRIPT, URL, _apply_patches, _bypass_redis


pytestmark = pytest.mark.django_db


def _campaign_activity(account, user, outcome, status=ActivityStatus.COMPLETED):
    from app_modules.activities.models import Activity
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
    from app_modules.contacts.models import Contact
    today = timezone.localdate()
    campaign = Campaign(name='Cold calling', campaign_type=CampaignType.OUTBOUND, owner=user,
                        planned_start_date=today, planned_end_date=today + datetime.timedelta(days=30))
    campaign.save(user=user, client_id=account.client_id)
    ca = CampaignAccount(campaign=campaign, account=account, status='IN_PROGRESS')
    ca.save(user=user, client_id=account.client_id)
    contact = Contact(account=account, first_name='Jordan', last_name='Lee')
    contact.save(user=user, client_id=account.client_id)
    # A prospect being chased (as a launched campaign has it).
    cc = CampaignContact(campaign_account=ca, contact=contact, status='IN_PROGRESS')
    cc.save(user=user, client_id=account.client_id)
    a = Activity(
        title='Cold call Jordan', activity_type=ActivityType.CALL, status=status,
        outcome=outcome, account=account, owner=user, decision_cycle=None,
        campaign=campaign, campaign_account=ca, campaign_contact=cc, sequence_position=1,
    )
    a.save(user=user, client_id=account.client_id)
    return a


def _extract(api, activity, fake_provider):
    fake_provider.replies = {**CANNED_REPLIES_HAPPY, 'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}
    with _apply_patches(_bypass_redis):
        resp = api.post(URL, {
            'activity_id': str(activity.id), 'transcript': TRANSCRIPT,
            'run_qualification': False, 'run_next_steps': True,
        }, format='json')
    return resp


def _next_steps_of(activity):
    from app_modules.signals.models import NextStepSignal
    return NextStepSignal.objects.filter(source_activity=activity)


@pytest.mark.parametrize('outcome', ['SUCCESSFUL', 'MEETING_SCHEDULED'])
def test_a_successful_campaign_activity_gets_next_steps(
    authed_api_a, account, user_a, patch_active_provider, fake_provider, outcome,
):
    activity = _campaign_activity(account, user_a, outcome)
    resp = _extract(authed_api_a, activity, fake_provider)
    assert resp.status_code == 200, resp.content
    assert AIPipelineRun.objects.filter(
        source_activity=activity, pipeline_type=AIPipelineType.NEXT_STEPS,
    ).count() == 1
    signals = _next_steps_of(activity)
    assert signals.count() >= 1
    # No decision cycle: the AI proposes no step (PO decision 4).
    assert all(s.suggested_decision_step_id is None for s in signals)
    assert all(s.decision_cycle_id is None for s in signals)


@pytest.mark.parametrize('outcome', ['NO_ANSWER', 'FOLLOW_UP_NEEDED', None])
def test_a_campaign_activity_without_a_successful_outcome_still_skips(
    authed_api_a, account, user_a, patch_active_provider, fake_provider, outcome,
):
    status = ActivityStatus.COMPLETED if outcome else ActivityStatus.PLANNED
    activity = _campaign_activity(account, user_a, outcome, status=status)
    resp = _extract(authed_api_a, activity, fake_provider)
    # Only next steps were asked: skipped -> nothing to run (the existing
    # NO_PIPELINE behaviour of a skipped next-steps-only request).
    assert _next_steps_of(activity).count() == 0
    assert AIPipelineRun.objects.filter(
        source_activity=activity, pipeline_type=AIPipelineType.NEXT_STEPS,
    ).count() == 0
    assert resp.status_code in (200, 400), resp.content


def test_the_shared_predicate():
    from types import SimpleNamespace
    from app_modules.activities.services.next_step_materialization import next_steps_enabled
    dc = SimpleNamespace(decision_cycle_id='dc', campaign_id=None, outcome=None)
    plain = SimpleNamespace(decision_cycle_id=None, campaign_id=None, outcome='SUCCESSFUL')
    won = SimpleNamespace(decision_cycle_id=None, campaign_id='c', outcome='SUCCESSFUL')
    meeting = SimpleNamespace(decision_cycle_id=None, campaign_id='c', outcome='MEETING_SCHEDULED')
    no_answer = SimpleNamespace(decision_cycle_id=None, campaign_id='c', outcome='NO_ANSWER')
    assert next_steps_enabled(dc) and next_steps_enabled(won) and next_steps_enabled(meeting)
    assert not next_steps_enabled(plain) and not next_steps_enabled(no_answer)


def test_successful_outcomes_live_in_the_campaigns_constants():
    from app_modules.activities.constants import ActivityOutcome
    from app_modules.campaigns import constants
    assert constants.SUCCESSFUL_OUTCOMES == frozenset({
        ActivityOutcome.SUCCESSFUL, ActivityOutcome.MEETING_SCHEDULED,
    })
