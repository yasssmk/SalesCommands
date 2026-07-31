# backend/tests/campaigns/test_delete_keeps_activities.py
"""
Deleting a campaign (individual DELETE and bulk-delete, both modes) must never
delete activities. Activity.campaign is on_delete=SET_NULL, so the surviving
activities are detached automatically (campaign becomes None):

  - pending (PLANNED/ON_HOLD), no decision cycle -> CANCELLED, kept
  - linked to a decision cycle                    -> untouched, kept
  - already terminal (COMPLETED/CANCELLED)        -> untouched, kept

State is built directly with the standard save(user=, client_id=) pattern.
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
    Disabling throttling empties DEFAULT_THROTTLE_RATES, but the bulk view still
    forces BulkOperationThrottle, whose constructor raises on the missing 'bulk'
    rate (DRF binds THROTTLE_RATES at import, so a settings override is too
    late). Dropping the throttle class for the test mirrors the disabled-
    throttling intent without touching production code.
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
    plain = _activity(client, user, account, camp, ActivityStatus.PLANNED)
    linked = _activity(client, user, account, camp, ActivityStatus.PLANNED, decision_cycle=dc)
    done = _activity(client, user, account, camp, ActivityStatus.COMPLETED)
    return camp, dc, plain, linked, done


def _assert_survivors(dc, plain, linked, done):
    for a in (plain, linked, done):
        assert Activity.objects.filter(pk=a.pk).exists(), f"activity {a.pk} was deleted"
        a.refresh_from_db()
    # pending, no DC -> cancelled and detached
    assert plain.status == ActivityStatus.CANCELLED
    assert plain.campaign_id is None
    # linked to a DC -> untouched, detached, still linked to its cycle
    assert linked.status == ActivityStatus.PLANNED
    assert linked.campaign_id is None
    assert linked.decision_cycle_id == dc.id
    # already terminal -> untouched, detached
    assert done.status == ActivityStatus.COMPLETED
    assert done.campaign_id is None


@pytest.mark.django_db
def test_individual_delete_keeps_activities(authed_api_a, client_account_a, user_a, account):
    camp, dc, plain, linked, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(f'/campaigns/{camp.id}/')

    assert resp.status_code == 204, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_survivors(dc, plain, linked, done)


@pytest.mark.django_db
def test_bulk_strict_delete_keeps_activities(
    bulk_rate, authed_api_a, client_account_a, user_a, account
):
    camp, dc, plain, linked, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(
        BULK_DELETE_URL,
        data={'ids': [str(camp.id)], 'mode': 'strict'},
        format='json',
    )

    assert resp.status_code == 200, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_survivors(dc, plain, linked, done)


@pytest.mark.django_db
def test_bulk_partial_delete_keeps_activities(
    bulk_rate, authed_api_a, client_account_a, user_a, account
):
    camp, dc, plain, linked, done = _make_three(client_account_a, user_a, account)

    resp = authed_api_a.delete(
        BULK_DELETE_URL,
        data={'ids': [str(camp.id)], 'mode': 'partial'},
        format='json',
    )

    assert resp.status_code == 200, resp.content
    assert not Campaign.objects.filter(id=camp.id).exists()
    _assert_survivors(dc, plain, linked, done)
