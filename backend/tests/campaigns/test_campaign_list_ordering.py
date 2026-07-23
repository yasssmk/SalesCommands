# backend/tests/campaigns/test_campaign_list_ordering.py
"""
Default ordering of the campaign list, asserted end-to-end on the HTTP response.

The list opens on what to work on now, so campaigns are grouped by status
priority — ACTIVE -> PAUSED -> DRAFT -> COMPLETED -> CANCELLED — and newest-first
(created_at DESC) within each group.

This MUST be an endpoint test, not a queryset unit test: the ordering is applied
by DRF OrderingFilter (default ['_status_priority', '-created_at']) AFTER
get_queryset, so only GET /campaigns/ -> viewset -> OrderingFilter -> serializer
-> paginated response proves the order actually reaches the client.

Mirrors test_campaign_list_attribution.py (URL + row-unwrap helpers). Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType

URL = '/campaigns/'


def _rows(resp):
    """Unwrap the (possibly double-enveloped, paginated) list payload."""
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _mk_campaign(client_account, user, name, status, created_days_ago):
    """Create an OUTBOUND campaign in a given status with a controlled created_at.

    Mirrors the conftest `campaign` fixture for the NOT NULL planned dates
    (today / today+30). created_at is auto_now_add so it cannot be set on
    create — force it afterwards via .update() (which also bypasses auto_now).
    Status is set directly (test data), not via the lifecycle transitions.
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


@pytest.mark.django_db
def test_list_default_order_status_groups_then_recency(
    authed_api_a, user_a, client_account_a
):
    """Groups in status-priority order, created_at DESC within a group.

    Two DRAFT campaigns with different created_at prove the secondary sort, not
    just the grouping. The relative order of the created campaigns is asserted
    (ignoring the auto-created TARGETED singleton) so the test is not fragile.
    """
    # Created in a deliberately scrambled order; created_days_ago controls recency.
    cancelled = _mk_campaign(client_account_a, user_a, 'cancelled', CampaignStatus.CANCELLED, 4)
    draft_old = _mk_campaign(client_account_a, user_a, 'draft-old', CampaignStatus.DRAFT, 5)
    active = _mk_campaign(client_account_a, user_a, 'active', CampaignStatus.ACTIVE, 10)
    completed = _mk_campaign(client_account_a, user_a, 'completed', CampaignStatus.COMPLETED, 1)
    draft_new = _mk_campaign(client_account_a, user_a, 'draft-new', CampaignStatus.DRAFT, 2)
    paused = _mk_campaign(client_account_a, user_a, 'paused', CampaignStatus.PAUSED, 3)

    # page_size large enough that all rows land on one page (no pagination cut).
    resp = authed_api_a.get(URL, {'page_size': 100})
    assert resp.status_code == 200

    order = [str(r['id']) for r in _rows(resp)]
    mine = {str(c.pk) for c in (cancelled, draft_old, active, completed, draft_new, paused)}
    got = [cid for cid in order if cid in mine]

    expected = [
        str(active.pk),      # ACTIVE group
        str(paused.pk),      # PAUSED group
        str(draft_new.pk),   # DRAFT group, newest first...
        str(draft_old.pk),   # ...then older
        str(completed.pk),   # COMPLETED group
        str(cancelled.pk),   # CANCELLED group
    ]
    assert got == expected

    # Explicit secondary-sort assertion within the DRAFT group.
    assert got.index(str(draft_new.pk)) < got.index(str(draft_old.pk))
