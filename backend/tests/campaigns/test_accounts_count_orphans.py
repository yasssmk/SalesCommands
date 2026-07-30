# backend/tests/campaigns/test_accounts_count_orphans.py
"""
C2 — `accounts_count` counts only CampaignAccounts holding at least one contact.

Orphan accounts (0 CampaignContact — residue that maps to no real worked account)
are excluded. Terminal accounts (STOPPED/COMPLETED) that DO hold contacts still
count — the exclusion is about "has a contact", not about status.

This is distinct from, and non-contradictory with, the 50-account cap (which uses
a dedicated ACTIVE count that excludes terminal accounts): a STOPPED-with-contacts
account counts here but not toward the cap.

Real list endpoint (`/campaigns/`, where the _accounts_count annotation applies).
Postgres 5432.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignType, CampaignContactStatus

URL = '/campaigns/'


def _rows(resp):
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _row_for(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    raise AssertionError(f'campaign {campaign_id} not found in list payload')


def _mk_account(client_account, user, name):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name=name, has_buying_decision=True)
    a.save(user=user, client_id=client_account.id)
    return a


def _mk_campaign(client_account, user, name):
    from app_modules.campaigns.models import Campaign
    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=CampaignType.OUTBOUND,
        owner=user,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user, client_id=client_account.id)
    return c


def _mk_campaign_account(campaign, account, client_account, user):
    from app_modules.campaigns.models import CampaignAccount
    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=user, client_id=client_account.id)
    return ca


def _enroll(campaign_account, account, client_account, user, statuses):
    """Create one Contact per status and enroll it in campaign_account."""
    from app_modules.campaigns.models import CampaignContact
    from app_modules.contacts.models import Contact
    for i, status in enumerate(statuses):
        contact = Contact(account=account, first_name=f'C{i}', last_name='T')
        contact.save(user=user, client_id=client_account.id)
        CampaignContact(
            campaign_account=campaign_account, contact=contact, status=status,
        ).save(user=user, client_id=client_account.id)


@pytest.mark.django_db
def test_orphan_account_excluded_from_accounts_count(
    authed_api_a, user_a, client_account_a
):
    """
    3 CampaignAccounts, one with ZERO contacts (orphan) → accounts_count == 2.
    RED on the old definition (Count of all campaign_accounts → 3).
    """
    from app_modules.campaigns.models import CampaignAccount

    camp = _mk_campaign(client_account_a, user_a, 'orphan-mix')
    acc1 = _mk_account(client_account_a, user_a, 'A1')
    acc2 = _mk_account(client_account_a, user_a, 'A2')
    acc3 = _mk_account(client_account_a, user_a, 'A3-orphan')
    ca1 = _mk_campaign_account(camp, acc1, client_account_a, user_a)
    ca2 = _mk_campaign_account(camp, acc2, client_account_a, user_a)
    _mk_campaign_account(camp, acc3, client_account_a, user_a)  # orphan: no _enroll

    _enroll(ca1, acc1, client_account_a, user_a, [CampaignContactStatus.IN_PROGRESS])
    _enroll(ca2, acc2, client_account_a, user_a,
            [CampaignContactStatus.PENDING, CampaignContactStatus.COMPLETED])

    # Non-vacuity: the orphan row really exists in the DB — it is excluded from
    # the count, not simply absent.
    assert CampaignAccount.objects.filter(campaign=camp).count() == 3

    resp = authed_api_a.get(URL, {'page_size': 100})
    assert resp.status_code == 200
    row = _row_for(resp, camp.id)
    assert row['accounts_count'] == 2  # orphan A3 excluded


@pytest.mark.django_db
def test_terminal_account_with_contacts_still_counted(
    authed_api_a, user_a, client_account_a
):
    """
    An account whose only contact is STOPPED (terminal) still counts — the rule
    excludes orphans (0 contacts), NOT terminal-with-contacts accounts. Proves
    accounts_count is 'has a contact', not 'active only'.
    """
    camp = _mk_campaign(client_account_a, user_a, 'terminal-with-contact')
    acc = _mk_account(client_account_a, user_a, 'A-stopped')
    ca = _mk_campaign_account(camp, acc, client_account_a, user_a)
    _enroll(ca, acc, client_account_a, user_a, [CampaignContactStatus.STOPPED])

    resp = authed_api_a.get(URL, {'page_size': 100})
    assert resp.status_code == 200
    row = _row_for(resp, camp.id)
    assert row['accounts_count'] == 1  # terminal, but has a contact → counted
