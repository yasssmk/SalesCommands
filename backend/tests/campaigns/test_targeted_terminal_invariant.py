# backend/tests/campaigns/test_targeted_terminal_invariant.py
"""
C3 — "a TARGETED campaign never reaches a terminal state" is now enforced at the
MODEL level, not only at the view/signal frontiers.

Campaign.complete() / Campaign.cancel() raise StandardizedValidationError (an
elegant 4xx, never a raw 500) when the campaign is TARGETED, so a direct model
call — a future service, script, or management command bypassing the views —
cannot break the invariant. OUTBOUND campaigns are strictly unchanged, and the
existing view guard (_assert_not_targeted) still fires on the lifecycle routes.

Real journeys / direct model calls. Postgres 5432.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.exceptions import StandardizedValidationError
from app_modules.campaigns.constants import (
    CampaignType,
    CampaignStatus,
)


def _mk_campaign(client_account, user, ctype, status):
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name=f'{ctype}-{status}',
        campaign_type=ctype,
        status=status,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
        actual_start_date=today if status == CampaignStatus.ACTIVE else None,
    )
    c.save(user=user, client_id=client_account.id)
    return c


# =============================================================================
# MODEL GUARD — TARGETED cannot be completed / cancelled (direct model call)
# =============================================================================

@pytest.mark.django_db
def test_targeted_complete_raises_and_status_unchanged(user_a, client_account_a):
    """Direct Campaign.complete() on a TARGETED raises; status stays ACTIVE."""
    camp = _mk_campaign(client_account_a, user_a, CampaignType.TARGETED, CampaignStatus.ACTIVE)

    with pytest.raises(StandardizedValidationError):
        camp.complete(user=user_a)

    camp.refresh_from_db()
    assert camp.status == CampaignStatus.ACTIVE


@pytest.mark.django_db
def test_targeted_cancel_raises_and_status_unchanged(user_a, client_account_a):
    """Direct Campaign.cancel() on a TARGETED raises; status stays ACTIVE."""
    camp = _mk_campaign(client_account_a, user_a, CampaignType.TARGETED, CampaignStatus.ACTIVE)

    with pytest.raises(StandardizedValidationError):
        camp.cancel(user=user_a)

    camp.refresh_from_db()
    assert camp.status == CampaignStatus.ACTIVE


# =============================================================================
# OUTBOUND UNAFFECTED — complete / cancel still work
# =============================================================================

@pytest.mark.django_db
def test_outbound_complete_succeeds(user_a, client_account_a):
    """OUTBOUND ACTIVE → complete() transitions to COMPLETED (non-vacuity)."""
    camp = _mk_campaign(client_account_a, user_a, CampaignType.OUTBOUND, CampaignStatus.ACTIVE)

    camp.complete(user=user_a)

    camp.refresh_from_db()
    assert camp.status == CampaignStatus.COMPLETED


@pytest.mark.django_db
def test_outbound_cancel_succeeds(user_a, client_account_a):
    """OUTBOUND ACTIVE → cancel() transitions to CANCELLED (non-vacuity)."""
    camp = _mk_campaign(client_account_a, user_a, CampaignType.OUTBOUND, CampaignStatus.ACTIVE)

    camp.cancel(user=user_a)

    camp.refresh_from_db()
    assert camp.status == CampaignStatus.CANCELLED


# =============================================================================
# FRONTIER COHERENCE — the view guard still returns a clean 4xx (not 500)
# =============================================================================

@pytest.mark.django_db
def test_view_complete_on_targeted_still_4xx(authed_api_a, user_a, client_account_a):
    """
    The lifecycle route on a TARGETED campaign still fails cleanly (4xx, not a
    500). The model guard backs up the view guard — no double-exception mishap.
    """
    camp = _mk_campaign(client_account_a, user_a, CampaignType.TARGETED, CampaignStatus.ACTIVE)

    resp = authed_api_a.post(f'/campaigns/{camp.id}/complete/', data={}, format='json')

    assert 400 <= resp.status_code < 500, resp.status_code
    camp.refresh_from_db()
    assert camp.status == CampaignStatus.ACTIVE
