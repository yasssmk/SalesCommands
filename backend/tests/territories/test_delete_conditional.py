# backend/tests/territories/test_delete_conditional.py
"""
Lot 1 — conditional territory deletion (non-destructive).

Campaign→Territory is a M2M (Campaign.territories, reverse 'campaigns').
DELETE /territories/{id}/ now behaves as:
  - >=1 ACTIVE campaign linked        -> blocked (4xx, "active campaigns" message)
  - only NON-active SOLE-territory     -> blocked for now (destructive cascade is
                                          the next step)
  - only NON-active MULTI-territory    -> detached from those campaigns, deleted
  - no campaign                        -> simple delete

No campaign is deleted in this step. Real endpoint. Postgres 5432.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignType, CampaignStatus


def _url(tid):
    return f'/territories/{tid}/'


def _territory(client_account, user, name):
    from app_modules.territories.models import Territory
    t = Territory(name=name, owner=user, filter_definition={})
    t.save(user=user, client_id=client_account.id)
    return t


def _campaign(client_account, user, name, status, territories):
    from app_modules.campaigns.models import Campaign
    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=CampaignType.OUTBOUND,
        status=status,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today if status == CampaignStatus.ACTIVE else None,
    )
    c.save(user=user, client_id=client_account.id)
    c.territories.set(territories)
    return c


@pytest.mark.django_db
def test_delete_blocked_by_active_campaign(authed_api_a, user_a, client_account_a):
    """Territory used by an ACTIVE campaign → 4xx, nothing deleted."""
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign

    terr = _territory(client_account_a, user_a, 'Active-linked')
    camp = _campaign(client_account_a, user_a, 'Live', CampaignStatus.ACTIVE, [terr])

    resp = authed_api_a.delete(_url(terr.id))

    assert 400 <= resp.status_code < 500, resp.status_code
    # Non-vacuity vs the old debug throw: the message names active campaigns.
    assert 'active' in str(resp.data).lower()
    assert Territory.objects.filter(id=terr.id).exists()
    assert Campaign.objects.filter(id=camp.id).exists()


@pytest.mark.django_db
def test_delete_simple_no_campaign(authed_api_a, user_a, client_account_a):
    """Territory linked to no campaign → deleted (200)."""
    from app_modules.territories.models import Territory

    terr = _territory(client_account_a, user_a, 'Lonely')

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Territory.objects.filter(id=terr.id).exists()


@pytest.mark.django_db
def test_delete_detaches_multi_territory_nonactive(authed_api_a, user_a, client_account_a):
    """
    Territory used only by a NON-active MULTI-territory campaign → territory is
    removed from that campaign and deleted; the campaign survives with its other
    territory.
    """
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign

    terr = _territory(client_account_a, user_a, 'ToRemove')
    other = _territory(client_account_a, user_a, 'Keeper')
    camp = _campaign(client_account_a, user_a, 'Draft-multi', CampaignStatus.DRAFT, [terr, other])

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Territory.objects.filter(id=terr.id).exists()
    camp.refresh_from_db()
    assert Campaign.objects.filter(id=camp.id).exists()
    remaining = set(camp.territories.values_list('id', flat=True))
    assert remaining == {other.id}


def _account(client_account, user, name='Acme'):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name=name, has_buying_decision=True)
    a.save(user=user, client_id=client_account.id)
    return a


def _activity(client_account, user, campaign, ca, title, decision_cycle=None):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title=title, activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
        account=ca.account, owner=user, campaign=campaign, campaign_account=ca,
        decision_cycle=decision_cycle,
    )
    a.save(user=user, client_id=client_account.id)
    return a


@pytest.mark.django_db
def test_delete_sole_territory_cascades_campaign(authed_api_a, user_a, client_account_a):
    """
    Territory that is the ONLY territory of a NON-active OUTBOUND campaign →
    territory deleted, campaign cascade-deleted with its CampaignAccount and
    NON-DC activities.
    """
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign, CampaignAccount
    from app_modules.activities.models import Activity

    terr = _territory(client_account_a, user_a, 'SoleTerr')
    camp = _campaign(client_account_a, user_a, 'Draft-solo', CampaignStatus.DRAFT, [terr])
    acc = _account(client_account_a, user_a)
    ca = CampaignAccount(campaign=camp, account=acc)
    ca.save(user=user_a, client_id=client_account_a.id)
    non_dc = _activity(client_account_a, user_a, camp, ca, 'plain call')

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Territory.objects.filter(id=terr.id).exists()
    assert not Campaign.objects.filter(id=camp.id).exists()
    assert not CampaignAccount.objects.filter(id=ca.id).exists()
    assert not Activity.objects.filter(id=non_dc.id).exists()  # non-DC deleted


@pytest.mark.django_db
def test_cascade_preserves_decision_cycle_activity(authed_api_a, user_a, client_account_a):
    """
    RED-RULE guard: a DC-linked activity of a cascaded campaign SURVIVES
    (detached, not deleted), its decision cycle intact; a sibling NON-DC
    activity is deleted.
    """
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign, CampaignAccount
    from app_modules.activities.models import Activity
    from app_modules.decision_cycles.models import DecisionCycle

    terr = _territory(client_account_a, user_a, 'SoleTerrDC')
    camp = _campaign(client_account_a, user_a, 'Draft-dc', CampaignStatus.DRAFT, [terr])
    acc = _account(client_account_a, user_a)
    ca = CampaignAccount(campaign=camp, account=acc)
    ca.save(user=user_a, client_id=client_account_a.id)

    dc = DecisionCycle(account=acc, name='Deal', owner=user_a)
    dc.save(user=user_a, client_id=client_account_a.id)
    dc_act = _activity(client_account_a, user_a, camp, ca, 'dc call', decision_cycle=dc)
    non_dc = _activity(client_account_a, user_a, camp, ca, 'plain call')

    resp = authed_api_a.delete(_url(terr.id))

    assert resp.status_code == 200, resp.data
    assert not Campaign.objects.filter(id=camp.id).exists()
    assert not Activity.objects.filter(id=non_dc.id).exists()          # non-DC deleted
    # DC activity preserved, detached from the campaign, DC intact.
    dc_act.refresh_from_db()
    assert dc_act.campaign_id is None
    assert dc_act.decision_cycle_id == dc.id
    assert DecisionCycle.objects.filter(id=dc.id).exists()


@pytest.mark.django_db
def test_cascade_is_atomic_on_failure(authed_api_a, user_a, client_account_a):
    """
    If the delete fails mid-way, everything rolls back — no half-deleted state.
    We force the final Territory.delete() to raise after the campaign cascade
    ran; the transaction must restore campaign + activity + territory.
    """
    from unittest.mock import patch
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign, CampaignAccount
    from app_modules.activities.models import Activity

    terr = _territory(client_account_a, user_a, 'AtomTerr')
    camp = _campaign(client_account_a, user_a, 'Draft-atom', CampaignStatus.DRAFT, [terr])
    acc = _account(client_account_a, user_a)
    ca = CampaignAccount(campaign=camp, account=acc)
    ca.save(user=user_a, client_id=client_account_a.id)
    non_dc = _activity(client_account_a, user_a, camp, ca, 'plain call')

    with patch(
        'app_modules.territories.models.Territory.delete',
        side_effect=RuntimeError('boom'),
    ):
        try:
            authed_api_a.delete(_url(terr.id))
        except RuntimeError:
            pass  # DRF test client may re-raise the unhandled exception

    # Full rollback: nothing was deleted.
    assert Territory.objects.filter(id=terr.id).exists()
    assert Campaign.objects.filter(id=camp.id).exists()
    assert CampaignAccount.objects.filter(id=ca.id).exists()
    assert Activity.objects.filter(id=non_dc.id).exists()
