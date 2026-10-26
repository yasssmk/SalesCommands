# backend/tests/activities/test_next_planned_step.py
"""
Sprint Next steps 5.1 -- `next_planned_step` on GET /module-activities/{id}/:
the ONE next step already planned, per the PO matrix (audit 5.0-bis, A3):

  (a) campaign activity without DC   -> the next step of the target's chain
                                        (source CAMPAIGN);
  (b) campaign activity that gave     -> the first open activity OF THAT DC
      birth to a DC                     (source BORN_DECISION_CYCLE, + the DC
                                        for "In decision cycle <name>");
  (c) DC activity, (d) DC activity    -> the first open activity of the DC in
      born from a campaign              the SERVER ranking (source
                                        DECISION_CYCLE), never the activity
                                        itself;
  nothing -> null (explicit empty state in the UI).

R13, server side: open = NON_TERMINAL_STATUSES (ON_HOLD included, shown with
its status); the phantom IN_PROGRESS status is gone; the server ranking (an
activity without date comes last) is the order.
"""

import datetime

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType


pytestmark = pytest.mark.django_db

TODAY = timezone.localdate()


def _days(n):
    return TODAY + datetime.timedelta(days=n)


def _get(authed_api, activity):
    response = authed_api.get(f'/module-activities/{activity.id}/')
    assert response.status_code == 200, response.content
    return response.json()['data']


def _activity(account, user, title, *, status=ActivityStatus.PLANNED, date=None, cycle=None,
              type_=ActivityType.CALL, **extra):
    from app_modules.activities.models import Activity
    a = Activity(title=title, activity_type=type_, status=status, account=account, owner=user,
                 decision_cycle=cycle, scheduled_date=date, **extra)
    a.save(user=user, client_id=account.client_id)
    return a


def _cycle(account, user, name='Deal Acme'):
    from app_modules.decision_cycles.models import DecisionCycle
    dc = DecisionCycle(account=account, owner=user, name=name, is_active=True)
    dc.save(user=user, client_id=account.client_id)
    return dc


@pytest.fixture
def chain(account, user_a):
    """A campaign target with its chain factory: step(position, status, date)."""
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
    from app_modules.contacts.models import Contact
    campaign = Campaign(name='Cold calling', campaign_type=CampaignType.OUTBOUND, owner=user_a,
                        planned_start_date=TODAY, planned_end_date=_days(30))
    campaign.save(user=user_a, client_id=account.client_id)
    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=user_a, client_id=account.client_id)
    contact = Contact(account=account, first_name='Jordan', last_name='Lee')
    contact.save(user=user_a, client_id=account.client_id)
    cc = CampaignContact(campaign_account=ca, contact=contact)
    cc.save(user=user_a, client_id=account.client_id)

    def step(position, status=ActivityStatus.PLANNED, date=None):
        return _activity(account, user_a, f'Step {position}', status=status, date=date,
                         campaign=campaign, campaign_account=ca, campaign_contact=cc,
                         sequence_position=position)
    return step


def _next(data):
    step = data['next_planned_step']
    return None if step is None else (step['source'], step['activity']['title'],
                                       step['activity']['status'],
                                       (step['decision_cycle'] or {}).get('name'))


# --- (a) campaign activity without DC -----------------------------------------

def test_a_completed_campaign_step_gives_the_next_step_of_the_chain(authed_api_a, chain):
    current = chain(1, ActivityStatus.COMPLETED, _days(-1))
    chain(2, date=_days(3))
    chain(3, date=_days(6))
    assert _next(_get(authed_api_a, current)) == ('CAMPAIGN', 'Step 2', 'PLANNED', None)


def test_a_planned_campaign_step_gives_the_step_after_it(authed_api_a, chain):
    chain(1, ActivityStatus.COMPLETED, _days(-1))
    current = chain(2, date=_days(3))
    chain(3, date=_days(6))
    assert _next(_get(authed_api_a, current)) == ('CAMPAIGN', 'Step 3', 'PLANNED', None)


# --- (b) campaign activity that gave birth to a DC -------------------------------

def test_b_a_campaign_activity_that_gave_birth_to_a_dc_follows_that_dc(
    authed_api_a, account, user_a, chain,
):
    call = chain(1, ActivityStatus.COMPLETED, _days(-2))
    chain(2, date=_days(1))          # a leftover chain step (TD-156): the DC wins
    dc = _cycle(account, user_a, 'Deal Logistix')
    _activity(account, user_a, 'Discovery meeting', date=_days(10), cycle=dc,
              type_=ActivityType.MEETING, source_activity=call)
    _activity(account, user_a, 'Send pricing', date=_days(5), cycle=dc)
    assert _next(_get(authed_api_a, call)) == (
        'BORN_DECISION_CYCLE', 'Send pricing', 'PLANNED', 'Deal Logistix')


# --- (c) DC activity / (d) DC activity born from a campaign ---------------------

def test_c_the_first_open_activity_of_the_dc_in_the_server_ranking_never_itself(
    authed_api_a, account, user_a,
):
    dc = _cycle(account, user_a)
    current = _activity(account, user_a, 'This call', date=_days(1), cycle=dc)
    _activity(account, user_a, 'Future meeting', date=_days(4), cycle=dc)
    _activity(account, user_a, 'Overdue task', date=_days(-3), cycle=dc)   # overdue first
    _activity(account, user_a, 'Done', status=ActivityStatus.COMPLETED, date=_days(-5), cycle=dc)
    assert _next(_get(authed_api_a, current)) == (
        'DECISION_CYCLE', 'Overdue task', 'PLANNED', 'Deal Acme')


def test_d_a_dc_activity_born_from_a_campaign_follows_its_dc_not_the_chain(
    authed_api_a, account, user_a, chain,
):
    call = chain(1, ActivityStatus.COMPLETED, _days(-2))
    chain(2, date=_days(1))
    dc = _cycle(account, user_a)
    current = _activity(account, user_a, 'Discovery meeting', status=ActivityStatus.COMPLETED,
                        date=_days(-1), cycle=dc, source_activity=call)
    _activity(account, user_a, 'Demo', date=_days(7), cycle=dc)
    assert _next(_get(authed_api_a, current)) == ('DECISION_CYCLE', 'Demo', 'PLANNED', 'Deal Acme')


# --- R13: undated, ON_HOLD, never itself, nothing --------------------------------

def test_an_activity_without_date_comes_after_a_dated_one(authed_api_a, account, user_a):
    dc = _cycle(account, user_a)
    current = _activity(account, user_a, 'This call', status=ActivityStatus.COMPLETED,
                        date=_days(-1), cycle=dc)
    _activity(account, user_a, 'Undated task', cycle=dc)
    _activity(account, user_a, 'Dated task', date=_days(20), cycle=dc)
    assert _next(_get(authed_api_a, current))[1] == 'Dated task'


def test_an_on_hold_activity_is_a_next_step_with_its_status(authed_api_a, account, user_a, chain):
    current = chain(1, ActivityStatus.COMPLETED, _days(-1))
    chain(2, ActivityStatus.ON_HOLD, _days(3))     # the campaign is paused
    assert _next(_get(authed_api_a, current)) == ('CAMPAIGN', 'Step 2', 'ON_HOLD', None)


def test_the_conversation_itself_is_never_returned(authed_api_a, account, user_a):
    dc = _cycle(account, user_a)
    current = _activity(account, user_a, 'Only open one', date=_days(2), cycle=dc)
    _activity(account, user_a, 'Cancelled', status=ActivityStatus.CANCELLED, date=_days(3), cycle=dc)
    assert _get(authed_api_a, current)['next_planned_step'] is None


def test_nothing_planned_is_null(authed_api_a, account, user_a):
    alone = _activity(account, user_a, 'No sequence', date=_days(2))
    assert _get(authed_api_a, alone)['next_planned_step'] is None


def test_r13_the_sequence_context_counts_on_hold_activities(authed_api_a, account, user_a):
    """The existing sequence_context.next_activities follows the same open
    statuses (NON_TERMINAL_STATUSES): an ON_HOLD activity is listed."""
    dc = _cycle(account, user_a)
    current = _activity(account, user_a, 'This call', status=ActivityStatus.COMPLETED,
                        date=_days(-1), cycle=dc)
    _activity(account, user_a, 'Paused', status=ActivityStatus.ON_HOLD, date=_days(2), cycle=dc)
    titles = [a['title'] for a in _get(authed_api_a, current)['sequence_context']['next_activities']]
    assert titles == ['Paused']


def test_in_progress_is_gone_from_the_sequence_service():
    import inspect
    from app_modules.activities.services import activity_sequence_service
    assert 'IN_PROGRESS' not in inspect.getsource(activity_sequence_service)
