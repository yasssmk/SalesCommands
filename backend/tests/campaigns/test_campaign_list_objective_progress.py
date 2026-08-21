# backend/tests/campaigns/test_campaign_list_objective_progress.py
"""
The campaign LIST payload exposes the primary objective's advancement.

The detail serializer already returned current_value + progress_percentage; the
list serializer (which feeds the card) returned only target_value, so the card's
objective bar had no value to render. These tests lock:

- REPRO: the list's ``primary_objective`` now carries current_value +
  progress_percentage (absent before the fix).
- PARITY: those numbers equal the detail serializer's, and equal the
  per-campaign CampaignAnalyticsService calculation (no drift between the batch
  used for the list and the single-campaign calc used for the detail).
- ANTI-N+1: the batch computes a whole page in a query count that does NOT grow
  with the number of campaigns.
- MEETINGS: the MEETINGS objective's current_value is correct (regression probe
  requested in the ticket).

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType, ObjectiveType
from app_modules.campaigns.models import Campaign, CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from tests.deal_value_helpers import give_deal_value

TODAY = timezone.now().date()
LIST_URL = '/campaigns/'


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _mk_campaign(owner, ca, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_objective(campaign, owner, ca, objective_type, target, is_primary=True):
    o = CampaignObjective(campaign=campaign, name=str(objective_type),
                          objective_type=objective_type, target_value=target,
                          is_primary=is_primary)
    o.save(user=owner, client_id=ca.id)
    return o


def _mk_cycle(owner, account, ca, *, source_campaign, estimated_value=None,
              outcome=None, outcome_date=None, name='dc'):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign, outcome=outcome,
                       outcome_date=outcome_date)
    dc.save(user=owner, client_id=ca.id)
    # TD-75: the campaign money objectives sum the DERIVED product roll-up, so
    # the amount is seeded as a real product line (parameter name unchanged so
    # the call sites read the same); `estimated_value` is never set.
    give_deal_value(dc, estimated_value, user=owner)
    return dc


def _mk_worked(campaign, account, owner, ca, cycle):
    """A completed + SUCCESSFUL campaign activity on ``cycle``.

    Since the PO's final rule, a campaign claims a deal's VALUE only once it has
    worked it — being the deal's ``source_campaign`` is not enough (that decides
    DECISION_CYCLES). The money builders below therefore attach one of these.
    """
    a = Activity(title='worked', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome='SUCCESSFUL',
                 account=account, owner=owner, campaign=campaign,
                 decision_cycle=cycle, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _mk_meeting(campaign, account, owner, ca):
    a = Activity(title='m', activity_type=ActivityType.MEETING,
                 status=ActivityStatus.COMPLETED, outcome='SUCCESSFUL',
                 account=account, owner=owner, campaign=campaign,
                 scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _rows(resp):
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _row_for(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    raise AssertionError(f'campaign {campaign_id} not in list payload')


# ---------------------------------------------------------------------------
# REPRO + list/detail parity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestListExposesProgress:

    def test_primary_objective_has_current_and_progress(
            self, authed_api_a, user_a, client_account_a, account):
        camp = _mk_campaign(user_a, client_account_a)
        _mk_objective(camp, user_a, client_account_a,
                      ObjectiveType.DECISION_CYCLES, target=4)
        _mk_cycle(user_a, account, client_account_a, source_campaign=camp)
        _mk_cycle(user_a, account, client_account_a, source_campaign=camp, name='dc2')

        resp = authed_api_a.get(LIST_URL)
        assert resp.status_code == 200
        primary = _row_for(resp, camp.id)['primary_objective']

        # The two keys that were ABSENT before the fix.
        assert 'current_value' in primary
        assert 'progress_percentage' in primary
        assert primary['current_value'] == 2.0
        assert primary['progress_percentage'] == 50.0   # 2 / 4
        assert primary['target_value'] == 4.0

    def test_list_matches_detail(
            self, authed_api_a, user_a, client_account_a, account):
        camp = _mk_campaign(user_a, client_account_a)
        _mk_objective(camp, user_a, client_account_a,
                      ObjectiveType.PIPELINE_VALUE, target=5000)
        cycle = _mk_cycle(user_a, account, client_account_a, source_campaign=camp,
                          estimated_value=1500)
        # The campaign must have WORKED the deal to claim its value (creation
        # alone counts only for DECISION_CYCLES).
        _mk_worked(camp, account, user_a, client_account_a, cycle)

        list_primary = _row_for(authed_api_a.get(LIST_URL), camp.id)['primary_objective']
        detail = authed_api_a.get(f'{LIST_URL}{camp.id}/')
        detail_objs = detail.data['data']['objectives']
        detail_primary = next(o for o in detail_objs if o['is_primary'])

        assert list_primary['current_value'] == detail_primary['current_value'] == 1500.0
        assert list_primary['progress_percentage'] == detail_primary['progress_percentage'] == 30.0


# ---------------------------------------------------------------------------
# PARITY GUARD — batch == per-campaign calculation, every objective type
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBatchParityWithService:
    """Each grouped batch value must equal CampaignAnalyticsService's
    per-campaign _calculate_objective_value, so the list and detail can never
    show different numbers."""

    def _one(self, owner, ca, account, objective_type, build):
        camp = _mk_campaign(owner, ca, name=str(objective_type))
        obj = _mk_objective(camp, owner, ca, objective_type, target=10)
        build(camp)
        svc = CampaignAnalyticsService(client_id=ca.id)
        expected = float(svc._calculate_objective_value(camp, obj) or 0)
        batch = compute_primary_objective_progress_batch([camp], ca.id)
        assert batch[camp.id]['current_value'] == expected
        return expected

    def test_decision_cycles(self, user_a, client_account_a, account):
        exp = self._one(user_a, client_account_a, account, ObjectiveType.DECISION_CYCLES,
                        lambda camp: _mk_cycle(user_a, account, client_account_a,
                                               source_campaign=camp))
        assert exp == 1.0

    def test_pipeline_value(self, user_a, client_account_a, account):
        exp = self._one(
            user_a, client_account_a, account, ObjectiveType.PIPELINE_VALUE,
            lambda camp: _mk_worked(
                camp, account, user_a, client_account_a,
                _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp, estimated_value=900)))
        assert exp == 900.0

    def test_revenue_won(self, user_a, client_account_a, account):
        exp = self._one(
            user_a, client_account_a, account, ObjectiveType.REVENUE_WON,
            lambda camp: _mk_worked(
                camp, account, user_a, client_account_a,
                _mk_cycle(user_a, account, client_account_a,
                          source_campaign=camp, estimated_value=700,
                          outcome=CycleOutcome.WON, outcome_date=TODAY)))
        assert exp == 700.0

    def test_meetings(self, user_a, client_account_a, account):
        exp = self._one(user_a, client_account_a, account, ObjectiveType.MEETINGS,
                        lambda camp: _mk_meeting(camp, account, user_a, client_account_a))
        assert exp == 1.0


# ---------------------------------------------------------------------------
# MEETINGS — the detail current_value is correct (ticket probe)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_meetings_detail_current_value_correct(
        authed_api_a, user_a, client_account_a, account):
    camp = _mk_campaign(user_a, client_account_a)
    _mk_objective(camp, user_a, client_account_a, ObjectiveType.MEETINGS, target=2)
    _mk_meeting(camp, account, user_a, client_account_a)

    detail = authed_api_a.get(f'{LIST_URL}{camp.id}/')
    primary = next(o for o in detail.data['data']['objectives'] if o['is_primary'])
    assert primary['current_value'] == 1.0          # the completed campaign meeting
    assert primary['progress_percentage'] == 50.0   # 1 / 2

    list_primary = _row_for(authed_api_a.get(LIST_URL), camp.id)['primary_objective']
    assert list_primary['current_value'] == 1.0


# ---------------------------------------------------------------------------
# ANTI-N+1 — batch query count does NOT grow with the number of campaigns
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBatchQueryBounded:

    def _campaigns(self, owner, ca, account, n, tag):
        camps = []
        for i in range(n):
            c = _mk_campaign(owner, ca, name=f'C{tag}{i}')
            _mk_objective(c, owner, ca, ObjectiveType.DECISION_CYCLES, target=5)
            _mk_cycle(owner, account, ca, source_campaign=c, name=f'dc{tag}{i}')
            camps.append(c)
        return camps

    def test_query_count_constant_regardless_of_n(
            self, django_assert_num_queries, user_a, client_account_a, account):
        few = self._campaigns(user_a, client_account_a, account, 2, tag='a')
        many = self._campaigns(user_a, client_account_a, account, 6, tag='b')

        # One query for the primary objectives + one grouped aggregate for the
        # single objective_type present = 2 queries, for 2 OR 6 campaigns.
        with django_assert_num_queries(2):
            compute_primary_objective_progress_batch(few, client_account_a.id)
        with django_assert_num_queries(2):
            compute_primary_objective_progress_batch(many, client_account_a.id)
