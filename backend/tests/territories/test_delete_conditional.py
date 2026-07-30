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


@pytest.mark.django_db
def test_delete_sole_territory_nonactive_blocked_for_now(authed_api_a, user_a, client_account_a):
    """
    Territory that is the ONLY territory of a NON-active campaign → destructive
    cascade needed → blocked in this step (Commit 2 turns this into a cascade).
    """
    from app_modules.territories.models import Territory
    from app_modules.campaigns.models import Campaign

    terr = _territory(client_account_a, user_a, 'SoleTerr')
    camp = _campaign(client_account_a, user_a, 'Draft-solo', CampaignStatus.DRAFT, [terr])

    resp = authed_api_a.delete(_url(terr.id))

    assert 400 <= resp.status_code < 500, resp.status_code
    assert Territory.objects.filter(id=terr.id).exists()
    assert Campaign.objects.filter(id=camp.id).exists()
