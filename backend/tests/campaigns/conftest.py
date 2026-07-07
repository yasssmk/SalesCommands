# backend/tests/campaigns/conftest.py
"""
Pytest fixtures for the campaigns module tests.

This conftest COMPLEMENTS the fixtures declared in
backend/tests/signals/conftest.py. We re-export the tenant / user /
account / contact fixtures and add campaign-specific ones: an OUTBOUND
campaign, a CampaignAccount, and a callable factory that builds a
CampaignContact in a given status.

Re-exported from tests/signals/conftest.py (same pattern as
tests/decision_cycles/conftest.py):
    pytest_configure, _jwt_only_no_csrf,
    tenant_a_id, client_account_a, role_individual_a, user_a,
    account, contact

New fixtures (campaigns-specific):
    campaign              -- OUTBOUND DRAFT campaign on tenant A
    campaign_account      -- CampaignAccount linking campaign + account
    make_campaign_contact -- factory(status=...) -> CampaignContact
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    account,
    contact,
    contact_extra,
)


# =============================================================================
# CAMPAIGN — OUTBOUND draft campaign on tenant A
# =============================================================================

@pytest.fixture
def campaign(db, account, user_a):
    """
    OUTBOUND campaign owned by the tenant-A rep.

    Uses the project's standard save(user=, client_id=) pattern so that
    ModuleBaseModel audit fields and ClientScopeManager scoping are
    populated identically to production.
    """
    from app_modules.campaigns.models import Campaign
    from app_modules.campaigns.constants import CampaignType

    today = timezone.now().date()
    c = Campaign(
        name='Q3 Outbound',
        campaign_type=CampaignType.OUTBOUND,
        owner=user_a,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


# =============================================================================
# CAMPAIGN ACCOUNT — links the campaign to the tracked account
# =============================================================================

@pytest.fixture
def campaign_account(db, campaign, account, user_a):
    from app_modules.campaigns.models import CampaignAccount

    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=user_a, client_id=account.client_id)
    return ca


# =============================================================================
# CAMPAIGN CONTACT — factory building a contact in an arbitrary status
# =============================================================================

@pytest.fixture
def make_campaign_contact(db, campaign_account, contact, user_a):
    """
    Callable factory: make_campaign_contact(status=...) -> CampaignContact.

    Defaults to PENDING. Persists the contact directly in the requested
    status so terminal-state transition rules can be exercised without
    driving the full sequence lifecycle.
    """
    from app_modules.campaigns.models import CampaignContact
    from app_modules.campaigns.constants import CampaignContactStatus

    def _factory(status=CampaignContactStatus.PENDING, **overrides):
        cc = CampaignContact(
            campaign_account=campaign_account,
            contact=contact,
            status=status,
            **overrides,
        )
        cc.save(user=user_a, client_id=campaign_account.client_id)
        return cc

    return _factory
