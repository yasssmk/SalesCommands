# backend/tests/campaigns/test_account_caps.py
"""
Per-campaign account cap = MAX_ACCOUNTS_PER_CAMPAIGN (50).

Two enforcement points, two counting rules (product-locked):

  * CREATION (OUTBOUND territory enrollment) — counted RAW: every account the
    territory resolves. A territory resolving 51 accounts is refused BEFORE any
    CampaignAccount is written (atomic create → zero partial enrollment). 50 is OK.

  * ADD TARGET (manual enroll-target) — counted on ACTIVE (non-terminal) accounts
    only. COMPLETED/STOPPED accounts do NOT count: a campaign holding 50 rows of
    which 10 are STOPPED (40 active) still accepts one more. A campaign with 50
    active rows refuses the next.

Fixtures reused from tests/campaigns/conftest.py (user_a, account, client_account_a,
authed_api_a). Postgres 5432; planned dates supplied NOT NULL.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from app_modules.campaigns.constants import (
    CampaignType,
    CampaignStatus,
    CampaignAccountStatus,
    MAX_ACCOUNTS_PER_CAMPAIGN,
)

ENROLL_URL = '/campaigns/accounts/enroll-target/'


# =============================================================================
# Helpers
# =============================================================================

def _make_accounts(n, user, client_id, start=0):
    """Create `n` fresh CompanyAccounts on the tenant (distinct company_name)."""
    from app_modules.accounts.models import CompanyAccount

    made = []
    for i in range(start, start + n):
        acc = CompanyAccount(company_name=f'Cap Co {i:04d}')
        acc.save(user=user, client_id=client_id)
        made.append(acc)
    return made


def _account_with_contact(user, client_id, tag):
    """A CompanyAccount holding one reachable contact (so enroll-target persists it)."""
    from app_modules.accounts.models import CompanyAccount
    from app_modules.contacts.models import Contact

    acc = CompanyAccount(company_name=f'Reachable Co {tag}')
    acc.save(user=user, client_id=client_id)
    ct = Contact(account=acc, first_name='Lead', last_name=tag, email=f'lead-{tag}@ex.com')
    ct.save(user=user, client_id=client_id)
    return acc


def _empty_territory(user, client_id):
    """A territory with an empty filter_definition → resolves ALL tenant accounts."""
    from app_modules.territories.models import Territory

    t = Territory(name='All Tenant', owner=user, filter_definition={})
    t.save(user=user, client_id=client_id)
    return t


def _active_targeted_campaign(user, client_id):
    """An ACTIVE TARGETED campaign owned by `user`."""
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name='Chasing',
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today,
    )
    c.save(user=user, client_id=client_id)
    return c


def _enroll_accounts_on(campaign, accounts, user, client_id, status=CampaignAccountStatus.PENDING):
    """Attach existing CompanyAccounts to a campaign at the given status."""
    from app_modules.campaigns.models import CampaignAccount

    rows = []
    for acc in accounts:
        ca = CampaignAccount(campaign=campaign, account=acc, status=status)
        ca.save(user=user, client_id=client_id)
        rows.append(ca)
    return rows


def _create_outbound(user, client_id, territory):
    from app_modules.campaigns.services.campaign_creation_service import CampaignCreationService

    today = timezone.now().date()
    service = CampaignCreationService(user=user, client_id=client_id)
    return service.create_campaign({
        'name': 'Territory Outbound',
        'campaign_type': CampaignType.OUTBOUND,
        'start_date': today,
        'end_date': today + timedelta(days=30),
        'territory_ids': [territory.id],
    })


# =============================================================================
# CREATION (OUTBOUND) — raw account count
# =============================================================================

@pytest.mark.django_db
def test_creation_outbound_51_accounts_refused_zero_created(user_a, client_account_a):
    """
    A territory resolving 51 accounts is refused. No Campaign and no CampaignAccount
    survive — the atomic create rolls back entirely (no partial enrollment).
    """
    from app_modules.campaigns.models import Campaign, CampaignAccount

    _make_accounts(51, user_a, client_account_a.id)
    territory = _empty_territory(user_a, client_account_a.id)

    with pytest.raises(StandardizedValidationError):
        _create_outbound(user_a, client_account_a.id, territory)

    # Rollback proof: nothing partially created.
    assert Campaign.objects.filter(campaign_type=CampaignType.OUTBOUND).count() == 0
    assert CampaignAccount.objects.count() == 0


@pytest.mark.django_db
def test_creation_outbound_exactly_50_accounts_ok(user_a, client_account_a):
    """The 50-account boundary is allowed and enrolls all 50 (non-vacuous)."""
    from app_modules.campaigns.models import CampaignAccount

    _make_accounts(50, user_a, client_account_a.id)
    territory = _empty_territory(user_a, client_account_a.id)

    result = _create_outbound(user_a, client_account_a.id, territory)

    assert result['accounts_enrolled'] == 50
    assert CampaignAccount.objects.filter(campaign=result['campaign']).count() == 50


# =============================================================================
# ADD TARGET (enroll-target) — active (non-terminal) count
# =============================================================================

@pytest.mark.django_db
def test_add_target_at_50_active_refused(authed_api_a, user_a, client_account_a):
    """Campaign already holding 50 ACTIVE accounts refuses the 51st (message, no row)."""
    from app_modules.campaigns.models import CampaignAccount

    campaign = _active_targeted_campaign(user_a, client_account_a.id)
    existing = _make_accounts(50, user_a, client_account_a.id)
    _enroll_accounts_on(campaign, existing, user_a, client_account_a.id)

    newcomer = _make_accounts(1, user_a, client_account_a.id, start=900)[0]

    resp = authed_api_a.post(
        ENROLL_URL,
        data={
            'campaign_id': str(campaign.id),
            'account_id': str(newcomer.id),
            'type': 'ACCOUNT',
        },
        format='json',
    )

    assert resp.status_code == 400, resp.data
    assert str(MAX_ACCOUNTS_PER_CAMPAIGN) in str(resp.data)
    # No new enrollment for the refused account.
    assert not CampaignAccount.objects.filter(campaign=campaign, account=newcomer).exists()
    assert CampaignAccount.objects.filter(campaign=campaign).count() == 50


@pytest.mark.django_db
def test_add_target_terminal_accounts_do_not_count(authed_api_a, user_a, client_account_a):
    """
    50 rows of which 10 are STOPPED → only 40 active. A 51st account is ACCEPTED,
    proving terminal accounts are excluded from the cap (non-vacuous: if all 50
    counted, this would be refused like the test above).
    """
    from app_modules.campaigns.models import CampaignAccount

    campaign = _active_targeted_campaign(user_a, client_account_a.id)
    accounts = _make_accounts(50, user_a, client_account_a.id)
    rows = _enroll_accounts_on(campaign, accounts, user_a, client_account_a.id)

    # Drive 10 to STOPPED via the real transition → 40 active remain.
    for ca in rows[:10]:
        ca.mark_stopped(user=user_a)
    assert CampaignAccount.objects.filter(
        campaign=campaign, status=CampaignAccountStatus.STOPPED
    ).count() == 10

    newcomer = _account_with_contact(user_a, client_account_a.id, 'terminal')

    resp = authed_api_a.post(
        ENROLL_URL,
        data={
            'campaign_id': str(campaign.id),
            'account_id': str(newcomer.id),
            'type': 'ACCOUNT',
        },
        format='json',
    )

    assert resp.status_code == 201, resp.data
    assert CampaignAccount.objects.filter(campaign=campaign, account=newcomer).exists()


@pytest.mark.django_db
def test_add_target_boundary_49_active_accepts_then_50_refuses(
    authed_api_a, user_a, client_account_a
):
    """Exact boundary: the 50th active add is accepted; the 51st is refused."""
    from app_modules.campaigns.models import CampaignAccount

    campaign = _active_targeted_campaign(user_a, client_account_a.id)
    existing = _make_accounts(49, user_a, client_account_a.id)
    _enroll_accounts_on(campaign, existing, user_a, client_account_a.id)

    fiftieth = _account_with_contact(user_a, client_account_a.id, 'fiftieth')
    fifty_first = _account_with_contact(user_a, client_account_a.id, 'fiftyfirst')

    ok = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(fiftieth.id), 'type': 'ACCOUNT'},
        format='json',
    )
    assert ok.status_code == 201, ok.data  # 49 → 50, allowed

    refused = authed_api_a.post(
        ENROLL_URL,
        data={'campaign_id': str(campaign.id), 'account_id': str(fifty_first.id), 'type': 'ACCOUNT'},
        format='json',
    )
    assert refused.status_code == 400, refused.data  # 50 → 51, blocked
