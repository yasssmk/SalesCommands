# backend/tests/signals/test_signal_cycle_attachment.py
"""
Sprint « Cycle de vie des contacts », étape 2 -- an activity's signals take
its decision cycle when the activity is linked to one (ONE central point:
services/signal_cycle_attachment.py, triggered by the Activity post_save).

Before: SignalManager copied decision_cycle from the source activity at the
signal's CREATION only (signal_manager.py _propagate_activity_context), so
  * the signals of a campaign sequence never reached the cycle born from it
    (« Start Decision Cycle »: the cycle is put on the NEW activity, never on
    the campaign one);
  * the signals of an activity analysed BEFORE being linked to a cycle stayed
    outside it.

PO decisions:
  * the sequence = every activity of the same campaign_account (same
    campaign, same account), every prospect, every run;
  * PENDING and REJECTED signals join too; NextStepSignal is EXCLUDED (its
    born cycle is computed at read time, 5.14b);
  * decision_cycle only (no signal model has a decision_step column);
  * only a NULL decision_cycle is written: a signal already on another cycle
    stays there, counted, logged and returned by the service;
  * an activity that LEAVES its cycle: its signals keep their cycle;
  * idempotent.

Real paths: POST /module-activities/create-with-entities/ (conversion),
PATCH /module-activities/{id}/, GET /decision_cycles/{id}/people/.
"""

import datetime

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.signals.constants import (
    PeopleRole, ScopeLevel, SignalDimension, SignalSource, SignalStatus, SignalWhat,
)


pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


# =============================================================================
# HELPERS
# =============================================================================

def _campaign_account(account, user, name='Cold calling'):
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign, CampaignAccount
    campaign = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=user,
                        planned_start_date=TODAY,
                        planned_end_date=TODAY + datetime.timedelta(days=30))
    campaign.save(user=user, client_id=account.client_id)
    ca = CampaignAccount(campaign=campaign, account=account, status='IN_PROGRESS')
    ca.save(user=user, client_id=account.client_id)
    return ca


def _prospect_activity(ca, user, first_name, *, outcome=None, position=1):
    """A campaign activity of one prospect (its own CampaignContact)."""
    from app_modules.activities.models import Activity
    from app_modules.campaigns.models import CampaignContact
    from app_modules.contacts.models import Contact
    account = ca.account
    contact = Contact(account=account, first_name=first_name, last_name='Prospect')
    contact.save(user=user, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=contact, status='IN_PROGRESS')
    cc.save(user=user, client_id=account.client_id)
    a = Activity(title=f'Call {first_name}', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=outcome, account=account,
                 owner=user, campaign=ca.campaign, campaign_account=ca,
                 campaign_contact=cc, sequence_position=position, scheduled_date=TODAY)
    a.save(user=user, client_id=account.client_id)
    a.contacts.add(contact)
    a.prospect = contact
    return a


def _plain_activity(account, user, title='Discovery'):
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type=ActivityType.MEETING,
                 status=ActivityStatus.COMPLETED, account=account, owner=user,
                 scheduled_date=TODAY)
    a.save(user=user, client_id=account.client_id)
    return a


def _cycle(account, user, name='Deal'):
    from app_modules.decision_cycles.constants import PipelineStep
    from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
    dc = DecisionCycle(account=account, owner=user, name=name)
    dc.save(user=user, client_id=account.client_id)
    step = DecisionStep(cycle=dc, name='Qualification',
                        stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=user, client_id=account.client_id)
    dc.qualification = step
    return dc


def _people(activity, user, name, status=SignalStatus.PENDING, decision_cycle=None):
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=activity.account, source_activity=activity,
                     decision_cycle=decision_cycle, source=SignalSource.LLM_EXTRACTED,
                     role=PeopleRole.CHAMPION, full_name=name,
                     source_quote=f'{name} said so', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    if status != SignalStatus.PENDING:
        # An LLM signal is born PENDING; its review outcome, as the
        # validate / reject endpoints leave it.
        PeopleSignal.objects.filter(pk=p.pk).update(status=status)
    return p


def _pain(activity, user, decision_cycle=None):
    from app_modules.signals.models import PainSignal
    p = PainSignal(account=activity.account, source_activity=activity,
                   decision_cycle=decision_cycle, source=SignalSource.LLM_EXTRACTED,
                   what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
                   scope_level=ScopeLevel.BUSINESS, summary='we lose data',
                   source_quote='we lose data', confidence=0.8)
    p.save(user=user, client_id=activity.client_id)
    return p


def _tech_stack(activity, user, decision_cycle=None):
    from app_modules.signals.models import TechStackSignal
    t = TechStackSignal(account=activity.account, source_activity=activity,
                        decision_cycle=decision_cycle, source=SignalSource.LLM_EXTRACTED,
                        tech_name='Salesforce', source_quote='we use Salesforce',
                        confidence=0.8)
    t.save(user=user, client_id=activity.client_id)
    return t


def _next_step(activity, user):
    from app_modules.signals.models import NextStepSignal
    ns = NextStepSignal(account=activity.account, source_activity=activity,
                        suggested_title='Demo', suggested_activity_type=ActivityType.MEETING,
                        source=SignalSource.LLM_EXTRACTED, confidence=0.8)
    ns.save(user=user, client_id=activity.client_id)
    return ns


def _cycle_of(signal):
    signal.refresh_from_db()
    return signal.decision_cycle_id


def _start_decision_cycle(api, campaign_activity):
    """« Start Decision Cycle » (5.13): create-with-entities, a NEW inline
    cycle, source_activity_id = the campaign activity."""
    from app_modules.activities.models import Activity
    r = api.post('/module-activities/create-with-entities/', {
        'activity': {
            'title': 'Discovery meeting', 'activity_type': 'MEETING', 'status': 'PLANNED',
            'account_id': str(campaign_activity.account_id),
            'contact_ids': [str(campaign_activity.prospect.id)],
            'scheduled_date': str(TODAY + datetime.timedelta(days=7)),
            'source_activity_id': str(campaign_activity.id),
        },
        'inline_contact': None, 'inline_cycle': {'name': 'Deal born'},
        'inline_step_stage': 'QUALIFICATION',
    }, format='json')
    assert r.status_code in (200, 201), r.content
    return Activity.objects.get(source_activity=campaign_activity).decision_cycle


def _patch_cycle(api, activity, cycle):
    step_id = cycle.steps.order_by('order').first().id if cycle else None
    r = api.patch(f'/module-activities/{activity.id}/', {
        'decision_cycle_id': str(cycle.id) if cycle else None,
        'decision_step_id': str(step_id) if step_id else None,
    }, format='json')
    assert r.status_code == 200, r.content


# =============================================================================
# (a) « Start Decision Cycle »: the whole campaign_account sequence joins
# =============================================================================

def test_start_decision_cycle_brings_the_signals_of_the_whole_campaign_account(
    authed_api_a, account, user_a,
):
    ca = _campaign_account(account, user_a)
    won = _prospect_activity(ca, user_a, 'Jordan', outcome='SUCCESSFUL', position=2)
    other_prospect = _prospect_activity(ca, user_a, 'Kim', position=1)

    pending_on_won = _people(won, user_a, 'Jordan Prospect')
    pain_on_won = _pain(won, user_a)
    validated_on_other = _people(other_prospect, user_a, 'Kim Prospect',
                                 status=SignalStatus.VALIDATED)
    rejected_on_other = _people(other_prospect, user_a, 'Alex Nobody',
                                status=SignalStatus.REJECTED)
    next_step_on_won = _next_step(won, user_a)

    # Another campaign on the same account: NOT the sequence.
    other_ca = _campaign_account(account, user_a, name='Other campaign')
    foreign = _people(_prospect_activity(other_ca, user_a, 'Sam'), user_a, 'Sam Prospect')

    born = _start_decision_cycle(authed_api_a, won)

    assert _cycle_of(pending_on_won) == born.id
    assert _cycle_of(pain_on_won) == born.id
    assert _cycle_of(validated_on_other) == born.id
    assert _cycle_of(rejected_on_other) == born.id
    assert _cycle_of(next_step_on_won) is None      # 5.14b: computed at read time
    assert _cycle_of(foreign) is None               # other campaign_account

    # Visible where it matters: the born cycle's People view.
    r = authed_api_a.get(f'/decision_cycles/{born.id}/people/')
    assert r.status_code == 200, r.content
    names = {q['full_name'] for q in r.json()['data']['qualified']}
    assert 'Kim Prospect' in names


# =============================================================================
# (b) PATCH: an analysed activity linked to a cycle afterwards
# =============================================================================

def test_patch_linking_an_analysed_activity_to_a_cycle_brings_its_signals(
    authed_api_a, account, user_a,
):
    activity = _plain_activity(account, user_a)
    people = _people(activity, user_a, 'Marie Curie')
    pain = _pain(activity, user_a)
    cycle = _cycle(account, user_a)

    _patch_cycle(authed_api_a, activity, cycle)

    assert _cycle_of(people) == cycle.id
    assert _cycle_of(pain) == cycle.id


# =============================================================================
# (c) guard: a signal on ANOTHER cycle is never moved, and is reported
# =============================================================================

def test_moving_an_activity_from_x_to_y_leaves_its_signals_on_x(
    authed_api_a, account, user_a,
):
    x = _cycle(account, user_a, name='X')
    y = _cycle(account, user_a, name='Y')
    activity = _plain_activity(account, user_a)
    _patch_cycle(authed_api_a, activity, x)
    on_x = _people(activity, user_a, 'Marie Curie', decision_cycle=x)
    orphan = _pain(activity, user_a)
    from app_modules.signals.models import PainSignal
    PainSignal.objects.filter(pk=orphan.pk).update(decision_cycle=None)

    _patch_cycle(authed_api_a, activity, y)

    assert _cycle_of(on_x) == x.id          # never moved
    assert _cycle_of(orphan) == y.id        # a NULL one takes Y


def test_the_service_reports_the_signals_left_on_another_cycle(account, user_a):
    from app_modules.signals.services.signal_cycle_attachment import (
        attach_signals_to_activity_cycle,
    )
    x = _cycle(account, user_a, name='X')
    y = _cycle(account, user_a, name='Y')
    activity = _plain_activity(account, user_a)
    _people(activity, user_a, 'Marie Curie', decision_cycle=x)
    _pain(activity, user_a)
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(decision_cycle=y)
    activity.refresh_from_db()

    result = attach_signals_to_activity_cycle(activity)

    assert result.attached == {'pain': 1}
    assert result.kept_on_other_cycle == {'people': 1}


def test_an_activity_leaving_its_cycle_keeps_its_signals_cycle(
    authed_api_a, account, user_a,
):
    cycle = _cycle(account, user_a)
    activity = _plain_activity(account, user_a)
    _patch_cycle(authed_api_a, activity, cycle)
    people = _people(activity, user_a, 'Marie Curie', decision_cycle=cycle)

    _patch_cycle(authed_api_a, activity, None)

    assert _cycle_of(people) == cycle.id


# =============================================================================
# 2b (3) / 2c -- TechStackSignal RE-INCLUDED: a TechStack always describes
# the account; its decision_cycle is routing to the DC only (no "in place /
# evaluated" meaning -- a tool evaluated on a deal is a CompetitorSignal), so
# it goes up through the DC like every signal. (2a had excluded it
# temporarily; the 2b scope field was removed in 2c, PO.)
# =============================================================================

def test_a_tech_stack_of_an_activity_linked_to_a_cycle_takes_the_cycle(
    authed_api_a, account, user_a,
):
    activity = _plain_activity(account, user_a)
    tech = _tech_stack(activity, user_a)
    pain = _pain(activity, user_a)
    cycle = _cycle(account, user_a)

    _patch_cycle(authed_api_a, activity, cycle)

    assert _cycle_of(pain) == cycle.id
    assert _cycle_of(tech) == cycle.id


def test_start_decision_cycle_brings_the_sequence_tech_stack(
    authed_api_a, account, user_a,
):
    ca = _campaign_account(account, user_a)
    won = _prospect_activity(ca, user_a, 'Jordan', outcome='SUCCESSFUL')
    tech = _tech_stack(_prospect_activity(ca, user_a, 'Kim'), user_a)

    born = _start_decision_cycle(authed_api_a, won)

    assert _cycle_of(tech) == born.id


def test_idempotent_a_second_run_attaches_nothing(account, user_a):
    from app_modules.signals.services.signal_cycle_attachment import (
        attach_signals_to_activity_cycle,
    )
    activity = _plain_activity(account, user_a)
    _pain(activity, user_a)
    cycle = _cycle(account, user_a)
    from app_modules.activities.models import Activity
    Activity.objects.filter(pk=activity.pk).update(decision_cycle=cycle)
    activity.refresh_from_db()

    first = attach_signals_to_activity_cycle(activity)
    second = attach_signals_to_activity_cycle(activity)

    assert first.attached == {'pain': 1}
    assert second.attached == {}
