# backend/tests/campaigns/test_active_campaign_caps.py
"""
Per-user caps on simultaneously ACTIVE campaigns (product-locked):

  * OUTBOUND active  <= MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER (10)
  * TARGETED active  <= MAX_ACTIVE_TARGETED_CAMPAIGNS_PER_USER (1)

The two caps are INDEPENDENT (a user may hold 10 active outbound AND 1 active
targeted at once). Only ACTIVE campaigns count — DRAFT and final-state
campaigns are ignored. "Per user" = the campaign owner.

OUTBOUND is enforced at activation (CampaignLifecycleService.start), the real
DRAFT -> ACTIVE path the /start/ endpoint delegates to. TARGETED's 1-active
guarantee is structural: the singleton is born ACTIVE and
unique_targeted_campaign_per_user keeps it unique per user; get_or_create is
idempotent (no IntegrityError) and manual TARGETED creation is refused with a
validation error, not a 500 — both proven here.

Postgres 5432; planned dates supplied NOT NULL.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from app_modules.campaigns.constants import (
    CampaignType,
    CampaignStatus,
    MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER,
)
from app_modules.campaigns.services.campaign_lifecycle_service import (
    CampaignLifecycleService,
)

CREATE_URL = '/campaigns/'


# =============================================================================
# Helpers
# =============================================================================

def _mk_campaign(client, user, name, status, ctype=CampaignType.OUTBOUND):
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=ctype,
        status=status,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today if status == CampaignStatus.ACTIVE else None,
    )
    c.save(user=user, client_id=client.id)
    return c


def _mk_active_outbound(client, user, n):
    return [
        _mk_campaign(client, user, f'active-out-{i}', CampaignStatus.ACTIVE)
        for i in range(n)
    ]


def _startable_draft_outbound(client, user, account, name='to-start'):
    """A DRAFT OUTBOUND with one CampaignAccount, so start() reaches activation."""
    from app_modules.campaigns.models import CampaignAccount

    c = _mk_campaign(client, user, name, CampaignStatus.DRAFT)
    ca = CampaignAccount(campaign=c, account=account)
    ca.save(user=user, client_id=client.id)
    return c


def _start(user, client, campaign):
    return CampaignLifecycleService(user=user, client_id=client.id).start(campaign)


# =============================================================================
# OUTBOUND active cap (10)
# =============================================================================

@pytest.mark.django_db
def test_eleventh_active_outbound_refused(account, user_a, client_account_a):
    """With 10 active outbound campaigns, starting an 11th is refused; it stays DRAFT."""
    _mk_active_outbound(client_account_a, user_a, MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER)
    to_start = _startable_draft_outbound(client_account_a, user_a, account)

    with pytest.raises(StandardizedValidationError):
        _start(user_a, client_account_a, to_start)

    to_start.refresh_from_db()
    assert to_start.status == CampaignStatus.DRAFT


@pytest.mark.django_db
def test_tenth_active_outbound_allowed(account, user_a, client_account_a):
    """With only 9 active outbound campaigns, the 10th starts (non-vacuous)."""
    _mk_active_outbound(client_account_a, user_a, MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER - 1)
    to_start = _startable_draft_outbound(client_account_a, user_a, account)

    _start(user_a, client_account_a, to_start)

    to_start.refresh_from_db()
    assert to_start.status == CampaignStatus.ACTIVE


@pytest.mark.django_db
def test_draft_and_final_campaigns_do_not_count(account, user_a, client_account_a):
    """
    Only ACTIVE campaigns count. A user with 3 active + a pile of DRAFT/COMPLETED/
    CANCELLED outbound campaigns can still start another (would be refused if
    DRAFT/final counted).
    """
    _mk_active_outbound(client_account_a, user_a, 3)
    for i in range(15):
        _mk_campaign(client_account_a, user_a, f'draft-{i}', CampaignStatus.DRAFT)
    for i in range(5):
        _mk_campaign(client_account_a, user_a, f'done-{i}', CampaignStatus.COMPLETED)
        _mk_campaign(client_account_a, user_a, f'cancel-{i}', CampaignStatus.CANCELLED)

    to_start = _startable_draft_outbound(client_account_a, user_a, account)
    _start(user_a, client_account_a, to_start)

    to_start.refresh_from_db()
    assert to_start.status == CampaignStatus.ACTIVE


# =============================================================================
# Independence of the two caps
# =============================================================================

@pytest.mark.django_db
def test_targeted_does_not_consume_outbound_budget(account, user_a, client_account_a):
    """
    An active TARGETED campaign does not count against the OUTBOUND cap: with
    9 active outbound + 1 active targeted, the 10th outbound still starts.
    """
    _mk_campaign(client_account_a, user_a, 'my-targeted', CampaignStatus.ACTIVE,
                 ctype=CampaignType.TARGETED)
    _mk_active_outbound(client_account_a, user_a, MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER - 1)

    to_start = _startable_draft_outbound(client_account_a, user_a, account)
    _start(user_a, client_account_a, to_start)

    to_start.refresh_from_db()
    assert to_start.status == CampaignStatus.ACTIVE


@pytest.mark.django_db
def test_ten_outbound_and_one_targeted_coexist(user_a, client_account_a):
    """10 active outbound and 1 active targeted can be held by the same user at once."""
    from app_modules.campaigns.models import Campaign

    _mk_active_outbound(client_account_a, user_a, MAX_ACTIVE_OUTBOUND_CAMPAIGNS_PER_USER)
    _mk_campaign(client_account_a, user_a, 'my-targeted', CampaignStatus.ACTIVE,
                 ctype=CampaignType.TARGETED)

    active = Campaign.objects.filter(owner=user_a, status=CampaignStatus.ACTIVE)
    assert active.filter(campaign_type=CampaignType.OUTBOUND).count() == 10
    assert active.filter(campaign_type=CampaignType.TARGETED).count() == 1


# =============================================================================
# TARGETED 1-active guarantee — idempotent, elegant (no IntegrityError)
# =============================================================================

@pytest.mark.django_db
def test_targeted_singleton_idempotent_no_integrityerror(user_a, client_account_a):
    """
    Requesting the TARGETED campaign twice returns the same one (created False the
    second time) — the unique constraint guarantees 1 active per user without a
    raw IntegrityError bubbling up.
    """
    from app_modules.campaigns.services.campaign_creation_service import (
        CampaignCreationService,
    )
    from app_modules.campaigns.models import Campaign

    service = CampaignCreationService(user=user_a, client_id=client_account_a.id)

    c1, created1 = service.get_or_create_targeted(sequence_type='TARGETED')
    c2, created2 = service.get_or_create_targeted(sequence_type='TARGETED')

    assert created1 is True
    assert created2 is False
    assert c1.id == c2.id
    assert c1.status == CampaignStatus.ACTIVE
    assert Campaign.objects.filter(
        owner=user_a,
        campaign_type=CampaignType.TARGETED,
        status=CampaignStatus.ACTIVE,
    ).count() == 1


@pytest.mark.django_db
def test_manual_targeted_creation_refused_elegantly(authed_api_a):
    """Creating a TARGETED campaign via the API is refused with a 400, not a 500."""
    today = timezone.now().date()
    resp = authed_api_a.post(
        CREATE_URL,
        data={
            'name': 'Hand-rolled Targeted',
            'campaign_type': CampaignType.TARGETED,
            'planned_start_date': str(today),
            'planned_end_date': str(today + timedelta(days=30)),
        },
        format='json',
    )
    assert resp.status_code == 400, resp.data
