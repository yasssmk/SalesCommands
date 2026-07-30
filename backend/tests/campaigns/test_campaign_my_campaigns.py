# backend/tests/campaigns/test_campaign_my_campaigns.py
"""
GET /campaigns/my-campaigns/ — regression + parity with the main list.

my-campaigns serializes with CampaignListSerializer and calls filter_queryset,
so DRF OrderingFilter applies the campaign default ordering
(['_status_priority', '-created_at']). The _status_priority annotation was only
added to the `list` branch of get_queryset, while my-campaigns fell into the
`else` branch — so the endpoint 400s with
"Cannot resolve keyword '_status_priority' into field". These tests are the
coverage that was missing (only GET /campaigns/ was tested).

They also pin the pre-existing degradation the else branch carried: without the
list annotations, accounts_count fell back to a per-row count and targets_total
serialized as None. After the fix (folding my-campaigns into the list branch)
both are annotated.

Mirrors test_campaign_list_ordering.py + test_campaign_list_attribution.py
(URL + row-unwrap helpers, builders). Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import (
    CampaignStatus,
    CampaignType,
    CampaignContactStatus,
)

URL = '/campaigns/my-campaigns/'


def _rows(resp):
    """Unwrap the (possibly double-enveloped, paginated) list payload."""
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _row_for(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    raise AssertionError(f'campaign {campaign_id} not found in my-campaigns payload')


def _mk_campaign(client_account, user, name, status, created_days_ago):
    """OUTBOUND campaign in a given status with a controlled created_at.

    Planned dates supplied like the conftest `campaign` fixture (NOT NULL).
    created_at is auto_now_add -> forced afterwards via .update(). Status set
    directly (test data), not via the lifecycle transitions.
    """
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=CampaignType.OUTBOUND,
        owner=user,
        status=status,
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user, client_id=client_account.id)
    Campaign.objects.filter(pk=c.pk).update(
        created_at=timezone.now() - timedelta(days=created_days_ago),
    )
    return c


def _mk_account(client_account, user, name):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name=name, has_buying_decision=True)
    a.save(user=user, client_id=client_account.id)
    return a


def _mk_campaign_account(campaign, account, client_account, user):
    from app_modules.campaigns.models import CampaignAccount
    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=user, client_id=client_account.id)
    return ca


def _enroll(campaign_account, account, client_account, user, statuses):
    from app_modules.campaigns.models import CampaignContact
    from app_modules.contacts.models import Contact
    for i, status in enumerate(statuses):
        contact = Contact(account=account, first_name=f'C{i}', last_name='T')
        contact.save(user=user, client_id=client_account.id)
        cc = CampaignContact(
            campaign_account=campaign_account, contact=contact, status=status,
        )
        cc.save(user=user, client_id=client_account.id)


@pytest.mark.django_db
def test_my_campaigns_home_call_returns_200(authed_api_a, user_a, client_account_a):
    """The exact Home request must not 400 (the reported regression)."""
    _mk_campaign(client_account_a, user_a, 'active', CampaignStatus.ACTIVE, 1)

    resp = authed_api_a.get(URL, {'status': 'ACTIVE', 'page_size': 50, 'page': 1})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_my_campaigns_status_priority_then_recency(
    authed_api_a, user_a, client_account_a
):
    """my-campaigns follows the same order as the main list: status groups
    (ACTIVE -> PAUSED -> DRAFT -> COMPLETED -> CANCELLED), created_at DESC within
    a group. Two DRAFT with different created_at prove the secondary sort. The
    relative order of the created campaigns is asserted (TARGETED singleton
    ignored) so the test is not fragile."""
    cancelled = _mk_campaign(client_account_a, user_a, 'cancelled', CampaignStatus.CANCELLED, 4)
    draft_old = _mk_campaign(client_account_a, user_a, 'draft-old', CampaignStatus.DRAFT, 5)
    active = _mk_campaign(client_account_a, user_a, 'active', CampaignStatus.ACTIVE, 10)
    completed = _mk_campaign(client_account_a, user_a, 'completed', CampaignStatus.COMPLETED, 1)
    draft_new = _mk_campaign(client_account_a, user_a, 'draft-new', CampaignStatus.DRAFT, 2)
    paused = _mk_campaign(client_account_a, user_a, 'paused', CampaignStatus.PAUSED, 3)

    resp = authed_api_a.get(URL, {'page_size': 100})
    assert resp.status_code == 200

    order = [str(r['id']) for r in _rows(resp)]
    mine = {str(c.pk) for c in (cancelled, draft_old, active, completed, draft_new, paused)}
    got = [cid for cid in order if cid in mine]

    assert got == [
        str(active.pk),
        str(paused.pk),
        str(draft_new.pk),
        str(draft_old.pk),
        str(completed.pk),
        str(cancelled.pk),
    ]
    assert got.index(str(draft_new.pk)) < got.index(str(draft_old.pk))


@pytest.mark.django_db
def test_my_campaigns_carries_accounts_and_targets_counts(
    authed_api_a, user_a, client_account_a
):
    """Fixed degradation: the else branch lacked the list annotations, so
    accounts_count fell back to a per-row count and targets_total was None.
    After the fix both are annotated and correct: 2 accounts, each holding at
    least one contact (4 enrolled contacts total) -> accounts_count == 2,
    targets_total == 4. Both accounts carry contacts so accounts_count counts
    them under the orphans-excluded definition."""
    camp = _mk_campaign(client_account_a, user_a, 'counts', CampaignStatus.ACTIVE, 1)
    acc1 = _mk_account(client_account_a, user_a, 'A1')
    acc2 = _mk_account(client_account_a, user_a, 'A2')
    ca1 = _mk_campaign_account(camp, acc1, client_account_a, user_a)
    ca2 = _mk_campaign_account(camp, acc2, client_account_a, user_a)
    _enroll(ca1, acc1, client_account_a, user_a,
            [CampaignContactStatus.COMPLETED, CampaignContactStatus.PENDING,
             CampaignContactStatus.IN_PROGRESS])
    # acc2 must hold a contact too — otherwise it is an orphan and no longer
    # counts toward accounts_count (orphans-excluded definition).
    _enroll(ca2, acc2, client_account_a, user_a,
            [CampaignContactStatus.PENDING])

    resp = authed_api_a.get(URL, {'page_size': 100})
    assert resp.status_code == 200
    row = _row_for(resp, camp.id)

    assert row['accounts_count'] == 2
    assert row['targets_total'] == 4  # not None — annotation present after the fix
