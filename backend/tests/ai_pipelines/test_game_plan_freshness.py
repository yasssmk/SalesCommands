# backend/tests/ai_pipelines/test_game_plan_freshness.py
"""
Sprint 2 Game Plan — sub-step G14: the banner predicate (backend only; the
display comes with the Activity UI step).

Before: GET /module-ai-pipelines/prep-call/by-activity/<id>/ answered
{data: null} for an activity without Game Plan — nothing told the rep that
the deal health had new information to analyse before the first Game Plan.

Now, with data null (no Game Plan yet) only: `game_plan_freshness` =
services/game_plan_freshness.game_plan_freshness(activity) — the deal
health's freshness of the activity's cycle, NO second logic (THE predicate
of S7, DealHealthEvidenceBuilder.new_info_reasons, through
deal_health_freshness): the same applies (open cycle, step >=
TECHNICAL_FIT), the same reasons. None for a campaign activity without
cycle. Not served once a Game Plan exists.
Invariant: banner on (applies and has_new_info) => a deal-health re-run is
accepted (a dedicated test).

Real path: the real GET, the real POST deal-health/run/ (fake LLM provider).

DB: Postgres.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines.services.deal_health_freshness import deal_health_freshness
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
    five_steps,
    planned_activity_on_step,
    completed_activity_on_step,
)


pytestmark = pytest.mark.django_db

BY_ACTIVITY_URL = '/module-ai-pipelines/prep-call/by-activity/{id}/'
PREP_RUN_URL = '/module-ai-pipelines/prep-call/run/'
DH_RUN_URL = '/module-ai-pipelines/deal-health/run/'


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def technical_fit(cycle, five_steps, planned_activity_on_step, completed_activity_on_step):
    """Qualification done, Technical Fit current: a planned meeting to prepare."""
    completed_activity_on_step(five_steps[0])
    meeting = planned_activity_on_step(five_steps[1])
    return {'cycle': cycle, 'steps': five_steps, 'meeting': meeting}


def _by_activity(api, activity):
    resp = api.get(BY_ACTIVITY_URL.format(id=activity.id))
    assert resp.status_code == 200, resp.content
    return resp.json()


def _deal_health_run(api, cycle):
    return api.post(DH_RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')


def _new_signal(cycle, user):
    from app_modules.signals.constants import SignalSource, SignalStatus
    from app_modules.signals.models import PainSignal
    PainSignal(account=cycle.account, decision_cycle=cycle, source=SignalSource.MANUAL,
               status=SignalStatus.VALIDATED, summary='Plans rebuilt by hand', what='OPS',
               dimension='TIME', source_quote='we rebuild the plans by hand',
               ).save(user=user, client_id=cycle.client_id)


# =============================================================================
# THE REPRO — before the first Game Plan, the banner predicate is served
# =============================================================================

def test_before_the_first_game_plan_the_banner_predicate_is_served(
    authed_api_a, technical_fit, provider,
):
    body = _by_activity(authed_api_a, technical_fit['meeting'])

    assert body['data'] is None
    assert body['game_plan_freshness'] == {
        'applies': True, 'has_new_info': True,
        'last_analysis_at': None, 'reasons': ['NO_ANALYSIS_YET'],
    }


def test_it_is_the_deal_health_freshness_no_second_logic(
    authed_api_a, technical_fit, provider, user_a,
):
    cycle = technical_fit['cycle']
    assert _deal_health_run(authed_api_a, cycle).status_code == 201
    _new_signal(cycle, user_a)

    served = _by_activity(authed_api_a, technical_fit['meeting'])['game_plan_freshness']

    assert served == deal_health_freshness(DecisionCycle.objects.get(pk=cycle.pk))
    assert served['reasons'] == ['NEW_SOURCES']


def test_once_a_game_plan_exists_the_banner_is_not_served(authed_api_a, technical_fit, provider):
    meeting = technical_fit['meeting']
    assert authed_api_a.post(PREP_RUN_URL, {'activity_id': str(meeting.id)},
                             format='json').status_code == 201

    body = _by_activity(authed_api_a, meeting)

    assert body['data'] is not None
    assert 'game_plan_freshness' not in body


# =============================================================================
# THE SAME applies AS THE DEAL HEALTH — and nothing for a campaign without DC
# =============================================================================

def test_before_technical_fit_it_does_not_apply(authed_api_a, cycle, five_steps,
                                                planned_activity_on_step, provider):
    qualification = planned_activity_on_step(five_steps[0])

    fresh = _by_activity(authed_api_a, qualification)['game_plan_freshness']

    assert fresh['applies'] is False and fresh['has_new_info'] is False


def test_a_closed_cycle_does_not_apply(authed_api_a, technical_fit, provider):
    DecisionCycle.objects.filter(pk=technical_fit['cycle'].pk).update(outcome=CycleOutcome.LOST)

    fresh = _by_activity(authed_api_a, technical_fit['meeting'])['game_plan_freshness']

    assert fresh['applies'] is False


def test_nothing_for_a_campaign_activity_without_cycle(authed_api_a, account, user_a):
    from tests.ai_pipelines.test_prep_call_campaign_context import _step
    from tests.signals.test_signal_cycle_attachment import _campaign_account
    from app_modules.activities.constants import ActivityStatus
    from app_modules.campaigns.models import CampaignContact
    from app_modules.contacts.models import Contact
    ca = _campaign_account(account, user_a)
    prospect = Contact(account=account, first_name='Elena', last_name='Prospect')
    prospect.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=prospect, status='IN_PROGRESS')
    cc.save(user=user_a, client_id=account.client_id)
    call = _step(ca, cc, user_a, 1, status=ActivityStatus.PLANNED)

    body = _by_activity(authed_api_a, call)

    assert body['data'] is None
    assert body['game_plan_freshness'] is None


# =============================================================================
# THE INVARIANT — banner on => a deal-health re-run is accepted
# =============================================================================

@pytest.mark.parametrize('scene', ['no analysis yet', 'a new source', 'nothing new'])
def test_banner_on_means_a_deal_health_rerun_is_accepted(
    authed_api_a, technical_fit, provider, user_a, scene,
):
    cycle, meeting = technical_fit['cycle'], technical_fit['meeting']
    if scene != 'no analysis yet':
        assert _deal_health_run(authed_api_a, cycle).status_code == 201
    if scene == 'a new source':
        _new_signal(cycle, user_a)

    fresh = _by_activity(authed_api_a, meeting)['game_plan_freshness']
    banner_on = fresh['applies'] and fresh['has_new_info']
    rerun = _deal_health_run(authed_api_a, cycle)

    accepted = rerun.status_code == 201
    assert banner_on == (scene != 'nothing new')            # each scene is what it says
    assert accepted == banner_on, (scene, fresh, rerun.content)
