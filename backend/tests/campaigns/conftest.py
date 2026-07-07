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
    api,
    authenticate,
    authed_api_a,
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
def make_campaign_contact(db, campaign_account, account, user_a):
    """
    Callable factory: make_campaign_contact(status=...) -> CampaignContact.

    Each call creates a fresh Contact (unique per call, so the factory can be
    invoked several times without hitting the (campaign_account, contact)
    uniqueness constraint) and enrolls it in the requested status.
    """
    from app_modules.campaigns.models import CampaignContact
    from app_modules.campaigns.constants import CampaignContactStatus
    from app_modules.contacts.models import Contact

    counter = {'n': 0}

    def _factory(status=CampaignContactStatus.PENDING, **overrides):
        counter['n'] += 1
        c = Contact(
            account=account,
            first_name=f'Contact{counter["n"]}',
            last_name='Test',
        )
        c.save(user=user_a, client_id=account.client_id)

        cc = CampaignContact(
            campaign_account=campaign_account,
            contact=c,
            status=status,
            **overrides,
        )
        cc.save(user=user_a, client_id=campaign_account.client_id)
        return cc

    return _factory


# =============================================================================
# CAMPAIGN ACTIVITY — factory for PLANNED sequence activities
# =============================================================================

@pytest.fixture
def make_campaign_activity(db, campaign, campaign_account, account, user_a):
    """
    Callable factory building an Activity attached to the campaign chain:
    make_campaign_activity(campaign_contact, scheduled_date, sequence_position=1, ...).
    """
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    def _factory(
        campaign_contact,
        scheduled_date,
        sequence_position=1,
        status=ActivityStatus.PLANNED,
        is_callback_followup=False,
        min_delay_days=0,
        **overrides,
    ):
        a = Activity(
            title=f'Step {sequence_position}',
            activity_type=ActivityType.CALL,
            status=status,
            account=account,
            owner=user_a,
            campaign=campaign,
            campaign_account=campaign_account,
            campaign_contact=campaign_contact,
            scheduled_date=scheduled_date,
            sequence_position=sequence_position,
            is_callback_followup=is_callback_followup,
            min_delay_days=min_delay_days,
            **overrides,
        )
        a.save(user=user_a, client_id=account.client_id)
        return a

    return _factory
