# backend/tests/campaigns/test_campaign_targets_progress.py
"""
Campaign list progress annotations: targets_total + targets_worked.

The card's progress bar needs, per campaign, the total number of enrolled
targets (CampaignContact rows) and how many are "worked" (in a final state,
COMPLETED / STOPPED). These are annotated on the list queryset via SEPARATE
correlated subqueries so they never join campaign_accounts — the fan-out this
commit exists to avoid.

THE test of the commit: one campaign with 3 accounts and 10 contacts total must
report accounts_count == 3 AND targets_total == 10 (NOT 30). If a deeper Count
were used on campaign_accounts__campaign_contacts in the same annotate, the
accounts×contacts LEFT JOIN would multiply rows and the counts would be wrong.

Mirrors test_campaign_list_attribution.py (same URL + row-unwrap helpers).
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.signals.conftest import (  # noqa: F401 — tenant-B fixtures for isolation
    tenant_b_id,
    client_account_b,
    role_individual_b,
    user_b,
)

from app_modules.campaigns.constants import CampaignContactStatus, CampaignType

URL = '/campaigns/'

# Worked = final target states.
COMPLETED = CampaignContactStatus.COMPLETED
STOPPED = CampaignContactStatus.STOPPED
IN_PROGRESS = CampaignContactStatus.IN_PROGRESS
PENDING = CampaignContactStatus.PENDING
ON_HOLD = CampaignContactStatus.ON_HOLD
CALLBACK = CampaignContactStatus.CALLBACK_PENDING


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


def _row_or_none(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    return None


# ---------------------------------------------------------------------------
# Builders (client-scoped save pattern, as in the fixtures)
# ---------------------------------------------------------------------------

def _mk_account(client_account, user, name):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name=name, has_buying_decision=True)
    a.save(user=user, client_id=client_account.id)
    return a


def _mk_campaign(client_account, user, name):
    # Mirror the conftest `campaign` fixture (tests/campaigns/conftest.py:49-70):
    # planned_start_date / planned_end_date are NOT NULL on Campaign, so they
    # must be supplied here too (the fixture-built tenant-A campaign has them).
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
    made = []
    for i, status in enumerate(statuses):
        contact = Contact(account=account, first_name=f'C{i}', last_name='T')
        contact.save(user=user, client_id=client_account.id)
        cc = CampaignContact(
            campaign_account=campaign_account, contact=contact, status=status,
        )
        cc.save(user=user, client_id=client_account.id)
        made.append(cc)
    return made


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_targets_counts_no_fanout(
    authed_api_a, user_a, client_account_a, account, campaign
):
    """3 accounts / 10 contacts total → accounts_count==3, targets_total==10
    (NOT 30), targets_worked == number in COMPLETED/STOPPED. This is THE
    fan-out proof."""
    # Account 1 (the fixture account): 4 contacts — 2 COMPLETED, 1 STOPPED, 1 IN_PROGRESS
    ca1 = _mk_campaign_account(campaign, account, client_account_a, user_a)
    _enroll(ca1, account, client_account_a, user_a,
            [COMPLETED, COMPLETED, STOPPED, IN_PROGRESS])

    # Account 2: 3 contacts — 1 COMPLETED, 2 PENDING
    acc2 = _mk_account(client_account_a, user_a, 'Acc Two')
    ca2 = _mk_campaign_account(campaign, acc2, client_account_a, user_a)
    _enroll(ca2, acc2, client_account_a, user_a, [COMPLETED, PENDING, PENDING])

    # Account 3: 3 contacts — 1 STOPPED, 1 ON_HOLD, 1 CALLBACK_PENDING
    acc3 = _mk_account(client_account_a, user_a, 'Acc Three')
    ca3 = _mk_campaign_account(campaign, acc3, client_account_a, user_a)
    _enroll(ca3, acc3, client_account_a, user_a, [STOPPED, ON_HOLD, CALLBACK])

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    # 3 accounts, 10 contacts — NOT 30 (would be the accounts×contacts fan-out).
    assert row['accounts_count'] == 3
    assert row['targets_total'] == 10
    # worked = final states: (2 COMPLETED + 1 STOPPED) + 1 COMPLETED + 1 STOPPED = 5
    assert row['targets_worked'] == 5


@pytest.mark.django_db
def test_targets_total_zero_no_contacts(authed_api_a, campaign):
    """A campaign with no enrolled contacts → 0 via Coalesce, not null."""
    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    assert row['targets_total'] == 0
    assert row['targets_worked'] == 0


@pytest.mark.django_db
def test_cross_tenant_contacts_not_counted(
    authed_api_a, user_a, client_account_a, account, campaign,
    client_account_b, user_b,
):
    """Contacts enrolled in another tenant's campaign never inflate this
    campaign's counts, and the other tenant's campaign is not in the list."""
    # Tenant A: 2 contacts on the campaign (1 COMPLETED, 1 PENDING).
    ca = _mk_campaign_account(campaign, account, client_account_a, user_a)
    _enroll(ca, account, client_account_a, user_a, [COMPLETED, PENDING])

    # Tenant B: its own campaign with 5 contacts.
    acc_b = _mk_account(client_account_b, user_b, 'B Account')
    camp_b = _mk_campaign(client_account_b, user_b, 'B Campaign')
    ca_b = _mk_campaign_account(camp_b, acc_b, client_account_b, user_b)
    _enroll(ca_b, acc_b, client_account_b, user_b,
            [COMPLETED, COMPLETED, STOPPED, PENDING, IN_PROGRESS])

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200

    row = _row_for(resp, campaign.id)
    assert row['targets_total'] == 2  # only tenant-A contacts, not 7
    assert row['targets_worked'] == 1

    # Tenant B's campaign is not visible to tenant A at all.
    assert _row_or_none(resp, camp_b.id) is None
