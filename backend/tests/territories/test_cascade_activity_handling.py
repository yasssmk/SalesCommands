# backend/tests/territories/test_cascade_activity_handling.py
"""
Territory cascade (delete a sole-territory NON-active OUTBOUND campaign):

  - pending (PLANNED/ON_HOLD), no deal -> DELETED (goes with the campaign)
  - already terminal (COMPLETED/...)    -> kept, detached (campaign=None)
  - linked to a decision cycle (deal)   -> kept (already spared today)

Real endpoint, Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityType, ActivityStatus
from app_modules.campaigns.constants import CampaignType, CampaignStatus


def _url(tid):
    return f'/territories/{tid}/'


def _territory(client, user, name='SoleTerr'):
    from app_modules.territories.models import Territory
    t = Territory(name=name, owner=user, filter_definition={})
    t.save(user=user, client_id=client.id)
    return t


def _campaign(client, user, territories):
    from app_modules.campaigns.models import Campaign
    today = timezone.now().date()
    c = Campaign(
        name='Draft-solo',
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.DRAFT,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user, client_id=client.id)
    c.territories.set(territories)
    return c


def _account(client, user):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name='Acme', has_buying_decision=True)
    a.save(user=user, client_id=client.id)
    return a


def _activity(client, user, campaign, account, status, decision_cycle=None):
    a = Activity(
        title='act',
        activity_type=ActivityType.CALL,
        status=status,
        account=account,
        owner=user,
        campaign=campaign,
        decision_cycle=decision_cycle,
    )
    a.save(user=user, client_id=client.id)
    return a


@pytest.mark.django_db
def test_cascade_deletes_pending_non_deal_activity(authed_api_a, user_a, client_account_a):
    from app_modules.campaigns.models import Campaign

    terr = _territory(client_account_a, user_a)
    camp = _campaign(client_account_a, user_a, [terr])
    acc = _account(client_account_a, user_a)
    act = _activity(client_account_a, user_a, camp, acc, ActivityStatus.PLANNED)

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Campaign.objects.filter(id=camp.id).exists()
    assert not Activity.objects.filter(id=act.id).exists(), "pending non-deal activity survived"


@pytest.mark.django_db
def test_cascade_keeps_completed_activity_detached(authed_api_a, user_a, client_account_a):
    from app_modules.campaigns.models import Campaign

    terr = _territory(client_account_a, user_a)
    camp = _campaign(client_account_a, user_a, [terr])
    acc = _account(client_account_a, user_a)
    act = _activity(client_account_a, user_a, camp, acc, ActivityStatus.COMPLETED)

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Campaign.objects.filter(id=camp.id).exists()
    assert Activity.objects.filter(id=act.id).exists(), "completed activity was deleted"
    act.refresh_from_db()
    assert act.status == ActivityStatus.COMPLETED
    assert act.campaign_id is None


@pytest.mark.django_db
def test_cascade_keeps_deal_activity(authed_api_a, user_a, client_account_a):
    from app_modules.campaigns.models import Campaign
    from app_modules.decision_cycles.models import DecisionCycle

    terr = _territory(client_account_a, user_a)
    camp = _campaign(client_account_a, user_a, [terr])
    acc = _account(client_account_a, user_a)
    dc = DecisionCycle(account=acc, name='Deal', owner=user_a)
    dc.save(user=user_a, client_id=client_account_a.id)
    act = _activity(client_account_a, user_a, camp, acc, ActivityStatus.PLANNED, decision_cycle=dc)

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Campaign.objects.filter(id=camp.id).exists()
    assert Activity.objects.filter(id=act.id).exists(), "deal activity was deleted"
    act.refresh_from_db()
    assert act.status == ActivityStatus.PLANNED
    assert act.campaign_id is None
    assert act.decision_cycle_id == dc.id
