# backend/tests/ai_pipelines/test_prep_call_campaign_context.py
"""
Sprint 2 Game Plan — sub-step G8: the light campaign diagnostic's DATA — a
campaign activity WITHOUT a decision cycle.

Before: the prep call read no campaign data at all — an activity of a
sequence (cold calls, NO_ANSWER attempts) got a brief with neither the
campaign's objective, nor the contact's, nor what happened at the previous
steps.

Now the pack carries `campaign` (None for an activity inside a cycle: the DC
path stays the only one — the two never add up):
  * the campaign's name / type and its activity_objective;
  * the CampaignContact's objective and status;
  * the activity's call_to_action is in `activity` (G7) — the stored result
    of the objective copy (campaign_execution_service._create_activity,
    step config -> campaign objective -> contact objective): read, never
    recomputed;
  * the sequence: position / total and the next open steps —
    ActivitySequenceService.get_sequence_context(activity,
    SequenceScope.CAMPAIGN), reused;
  * the history and results of the sequence: the COMPLETED steps with their
    outcome and notes — the `previous_activities` block (G7: same cycle OR
    same sequence), not read twice.
The v1 prompt prints a CAMPAIGN block and the PREVIOUS CONVERSATIONS. The
campaign block enters the dedup hash v2. The campaign_diagnostic section of
the output schema comes with G10; no freshness banner here (G14).
No N+1: the cost does not grow with the length of the sequence.

Real path: POST /module-ai-pipelines/prep-call/run/ (real view and
pipeline; the fake provider records the prompt). The campaign, its contact
and the sequence's activities are seeded through the ORM.

DB: Postgres.
"""

import datetime
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.activities.constants import ActivityOutcome, ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.pipelines.prep_call import PrepCallPipeline
from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
    PrepInputPackAssembler,
)

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import TODAY, _campaign_account, _cycle


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'
CAMPAIGN_OBJECTIVE = 'Book a discovery meeting with the finance lead.'
CONTACT_OBJECTIVE = 'Learn which reporting tool they use today.'


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _step(ca, cc, user, position, *, status=ActivityStatus.COMPLETED, outcome=None,
          notes='', days_ago=0, cycle=None):
    a = Activity(title=f'Step {position}', activity_type=ActivityType.CALL, status=status,
                 outcome=outcome, outcome_notes=notes, account=ca.account, owner=user,
                 campaign=ca.campaign, campaign_account=ca, campaign_contact=cc,
                 sequence_position=position, decision_cycle=cycle,
                 decision_step=cycle.qualification if cycle else None,
                 scheduled_date=TODAY - datetime.timedelta(days=days_ago),
                 completed_at=(timezone.now() - datetime.timedelta(days=days_ago)
                               if status == ActivityStatus.COMPLETED else None),
                 call_to_action=CAMPAIGN_OBJECTIVE)
    a.save(user=user, client_id=ca.account.client_id)
    a.contacts.add(cc.contact)
    return a


@pytest.fixture
def sequence(account, user_a):
    """A cold-calling sequence: two NO_ANSWER steps done, the 3rd planned
    (the one prepared), a 4th to come. No decision cycle."""
    from app_modules.campaigns.models import CampaignContact
    from app_modules.contacts.models import Contact
    ca = _campaign_account(account, user_a)
    ca.campaign.activity_objective = CAMPAIGN_OBJECTIVE
    ca.campaign.save(user=user_a)
    prospect = Contact(account=account, first_name='Claire', last_name='Prospect')
    prospect.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=prospect, status='IN_PROGRESS',
                         objective=CONTACT_OBJECTIVE)
    cc.save(user=user_a, client_id=account.client_id)
    _step(ca, cc, user_a, 1, outcome=ActivityOutcome.NO_ANSWER, notes='Voicemail left.', days_ago=6)
    _step(ca, cc, user_a, 2, outcome=ActivityOutcome.NO_ANSWER, notes='Rang twice, no answer.',
          days_ago=3)
    current = _step(ca, cc, user_a, 3, status=ActivityStatus.PLANNED)
    _step(ca, cc, user_a, 4, status=ActivityStatus.PLANNED)
    return {'ca': ca, 'cc': cc, 'current': current, 'user': user_a}


def _pack(activity):
    activity.refresh_from_db()
    return PrepInputPackAssembler().build(activity=activity)


def _hash(activity):
    return PrepCallPipeline._compute_idempotence_hash(
        input_pack=_pack(activity), target_contact=None,
    )


# =============================================================================
# THE REPRO — the campaign's data reach the prompt
# =============================================================================

def test_the_campaign_objective_and_the_sequence_history_reach_the_prompt(
    authed_api_a, sequence, provider,
):
    resp = authed_api_a.post(RUN_URL, {'activity_id': str(sequence['current'].id)}, format='json')
    assert resp.status_code == 201, resp.content
    [prompt] = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']

    assert 'CAMPAIGN' in prompt
    assert CAMPAIGN_OBJECTIVE in prompt
    assert CONTACT_OBJECTIVE in prompt
    assert 'step 3 of 4' in prompt
    assert prompt.count('No Answer') >= 2
    assert 'Voicemail left.' in prompt and 'Rang twice, no answer.' in prompt


# =============================================================================
# THE PACK BLOCK — only without a cycle
# =============================================================================

def test_the_campaign_block(sequence):
    campaign = _pack(sequence['current'])['campaign']

    assert campaign['objective'] == CAMPAIGN_OBJECTIVE
    assert campaign['contact_objective'] == CONTACT_OBJECTIVE
    assert campaign['contact_status'] == 'IN_PROGRESS'
    assert campaign['name'] == sequence['ca'].campaign.name
    assert campaign['sequence']['position'] == 3 and campaign['sequence']['total'] == 4
    assert [s['status'] for s in campaign['sequence']['next_steps']] == [ActivityStatus.PLANNED]
    # The history is the previous_activities block (G7), not read twice.
    history = _pack(sequence['current'])['previous_activities']
    assert [h['outcome'] for h in history] == ['No Answer', 'No Answer']


def test_a_campaign_activity_inside_a_cycle_keeps_the_dc_path(sequence, account, user_a):
    cycle = _cycle(account, user_a)
    in_cycle = _step(sequence['ca'], sequence['cc'], user_a, 5, status=ActivityStatus.PLANNED,
                     cycle=cycle)

    pack = _pack(in_cycle)

    assert pack['campaign'] is None
    assert pack['deal'] is not None


# =============================================================================
# THE HASH v2 — the campaign block moves it
# =============================================================================

def test_the_campaign_objective_moves_the_hash(sequence):
    before = _hash(sequence['current'])
    campaign = sequence['ca'].campaign
    campaign.activity_objective = 'Another objective.'
    campaign.save(user=sequence['user'])

    assert _hash(sequence['current']) != before


def test_the_contact_objective_moves_the_hash(sequence):
    before = _hash(sequence['current'])
    cc = sequence['cc']
    cc.objective = 'Another contact objective.'
    cc.save(user=sequence['user'])

    assert _hash(sequence['current']) != before


# =============================================================================
# NO N+1 — the cost does not grow with the length of the sequence
# =============================================================================

def test_the_pack_cost_does_not_grow_with_the_sequence(sequence):
    def count():
        current = Activity.objects.get(pk=sequence['current'].pk)
        with CaptureQueriesContext(connection) as ctx:
            PrepInputPackAssembler().build(activity=current)
        return len(ctx.captured_queries)

    few = count()
    for position in (5, 6, 7, 8):
        _step(sequence['ca'], sequence['cc'], sequence['user'], position, status=ActivityStatus.PLANNED)
    for position, days_ago in ((10, 9), (11, 8)):
        _step(sequence['ca'], sequence['cc'], sequence['user'], position,
              outcome=ActivityOutcome.NO_ANSWER, days_ago=days_ago)
    many = count()

    assert many == few, (few, many)
