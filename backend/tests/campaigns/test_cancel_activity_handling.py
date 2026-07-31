# backend/tests/campaigns/test_cancel_activity_handling.py
"""
Cancelling a campaign (CampaignLifecycleService.cancel):

  - pending (PLANNED/ON_HOLD), no deal -> CANCELLED, kept, still linked
  - pending, linked to a decision cycle (deal) -> untouched, kept
  - already terminal (COMPLETED/CANCELLED) -> untouched, kept

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
from app_modules.campaigns.services.campaign_lifecycle_service import (
    CampaignLifecycleService,
)
from app_modules.decision_cycles.models import DecisionCycle


def _campaign(client, user):
    today = timezone.now().date()
    c = Campaign(
        name='Outbound to cancel',
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


@pytest.mark.django_db
def test_cancel_marks_pending_non_deal_activity_cancelled_and_keeps_it(
    client_account_a, user_a, account
):
    camp = _campaign(client_account_a, user_a)
    act = _activity(client_account_a, user_a, account, camp, ActivityStatus.PLANNED)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(camp)

    assert Activity.objects.filter(pk=act.pk).exists(), "pending activity was deleted"
    act.refresh_from_db()
    assert act.status == ActivityStatus.CANCELLED


@pytest.mark.django_db
def test_cancel_leaves_deal_activity_untouched(client_account_a, user_a, account):
    dc = DecisionCycle(account=account, name='Deal', owner=user_a)
    dc.save(user=user_a, client_id=client_account_a.id)
    camp = _campaign(client_account_a, user_a)
    act = _activity(
        client_account_a, user_a, account, camp,
        ActivityStatus.PLANNED, decision_cycle=dc,
    )

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(camp)

    assert Activity.objects.filter(pk=act.pk).exists(), "deal activity was deleted"
    act.refresh_from_db()
    assert act.status == ActivityStatus.PLANNED
    assert act.decision_cycle_id == dc.id
    assert act.campaign_id == camp.id


@pytest.mark.django_db
def test_cancel_keeps_completed_activity_untouched(client_account_a, user_a, account):
    camp = _campaign(client_account_a, user_a)
    act = _activity(client_account_a, user_a, account, camp, ActivityStatus.COMPLETED)

    CampaignLifecycleService(user=user_a, client_id=client_account_a.id).cancel(camp)

    assert Activity.objects.filter(pk=act.pk).exists(), "completed activity was deleted"
    act.refresh_from_db()
    assert act.status == ActivityStatus.COMPLETED
