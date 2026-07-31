# backend/tests/campaigns/test_delete_activity_handling.py
"""
Deleting a campaign (individual DELETE and bulk-delete, both modes):

  - pending (PLANNED/ON_HOLD), no deal -> DELETED (it goes with the campaign)
  - linked to a decision cycle (deal)  -> kept, detached (campaign=None)
  - already terminal (COMPLETED/...)   -> kept, detached (campaign=None)

Activity.campaign is on_delete=SET_NULL, so the kept activities are detached
automatically. State is built directly with save(user=, client_id=).
Postgres 5432.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.models import Activity
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.campaigns.models import Campaign
from app_modules.campaigns.constants import CampaignType, CampaignStatus
from app_modules.decision_cycles.models import DecisionCycle

BULK_DELETE_URL = '/campaigns/bulk-delete/'


@pytest.fixture
def bulk_rate(monkeypatch):
    """
    Reach the bulk-delete endpoint in a test env where throttling is disabled.
    The bulk view forces BulkOperationThrottle, whose constructor raises on the
    missing 'bulk' rate (DRF binds THROTTLE_RATES at import). Dropping the
    throttle class for the test mirrors the disabled-throttling intent.
    """
    from app_modules.campaigns.views.campaign_bulk_views import CampaignBulkViewSet
    monkeypatch.setattr(CampaignBulkViewSet, 'throttle_classes', [])


def _campaign(client, user):
    today = timezone.now().date()
    c = Campaign(
        name='Outbound to delete',
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.ACTIVE,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user, client_id=client.id)
    return c


def _activity(client, user, account, campaign, status, decision_cycle=None):
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


def _make_three(client, user, account):
    dc = DecisionCycle(account=account, name='Deal', owner=user)
    dc.save(user=user, client_id=client.id)
    camp = _campaign(client, user)
    pending = _activity(client, user, account, camp, ActivityStatus.PLANNED)
    deal = _activity(client, user, account, camp, ActivityStatus.PLANNED, decision_cycle=dc)
    done = _activity(client, user, account, camp, ActivityStatus.COMPLETED)
    return camp, dc, pending, deal, done


def _assert_post_delete(dc, pending, deal, done):
    # pending non-deal: gone with the campaign
    assert not Activity.objects.filter(pk=pending.pk).exists(), "pending non-deal activity survived"
    # deal activity: kept, detached, cycle intact
    assert Activity.objects.filter(pk=deal.pk).exists(), "deal activity was deleted"
    deal.refresh_from_db()
    assert deal.status == ActivityStatus.PLANNED
    assert deal.campaign_id is None
    assert deal.decision_cycle_id == dc.id
    # completed non-deal: kept, detached
    assert Activity.objects.filter(pk=done.pk).exists(), "completed activity was deleted"
    done.refresh_from_db()
    assert done.status == ActivityStatus.COMPLETED
    assert done.campaign_id is None


@pytest.mark.django_db
def test_individual_delete_drops_only_pending_non_deal(authed_api_a, client_account_a, user_a, account):
    camp, dc, pending, deal, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(f'/campaigns/{camp.id}/')

    assert resp.status_code == 204, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_post_delete(dc, pending, deal, done)


@pytest.mark.django_db
def test_bulk_strict_delete_drops_only_pending_non_deal(
    bulk_rate, authed_api_a, client_account_a, user_a, account
):
    camp, dc, pending, deal, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(
        BULK_DELETE_URL,
        data={'ids': [str(camp.id)], 'mode': 'strict'},
        format='json',
    )

    assert resp.status_code == 200, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_post_delete(dc, pending, deal, done)


@pytest.mark.django_db
def test_bulk_partial_delete_drops_only_pending_non_deal(
    bulk_rate, authed_api_a, client_account_a, user_a, account
):
    camp, dc, pending, deal, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(
        BULK_DELETE_URL,
        data={'ids': [str(camp.id)], 'mode': 'partial'},
        format='json',
    )

    assert resp.status_code == 200, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_post_delete(dc, pending, deal, done)
