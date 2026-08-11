# backend/tests/campaigns/test_campaign_list_inactive.py
"""
is_inactive is exposed on the campaign LIST payload (GET /campaigns/) and the
DETAIL payload (GET /campaigns/{id}/), sourced from the set-based
with_inactivity() annotation.

The central guarantee is ANTI-N+1: the list marks every campaign from a single
annotated SELECT, so the endpoint's query count does NOT grow with the number
of campaigns. A per-instance computation (property / serializer query) would
add one query per campaign — the query-count comparison below would catch it.

Asserted on the HTTP responses (not serializers in isolation). Postgres 5432,
--reuse-db.
"""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.campaigns.constants import CampaignStatus, CampaignType

LIST_URL = '/campaigns/'


# ---------------------------------------------------------------------------
# Response unwrappers (list is enveloped + paginated; detail is enveloped)
# ---------------------------------------------------------------------------

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
    raise AssertionError(f'campaign {campaign_id} not in list payload')


def _detail_body(resp):
    body = resp.data
    return body['data'] if isinstance(body, dict) and 'data' in body else body


# ---------------------------------------------------------------------------
# Helper — an ACTIVE campaign with a controllable creation date
# ---------------------------------------------------------------------------

def _make_campaign(account, user, *, created_days_ago, name):
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name=name,
        campaign_type=CampaignType.OUTBOUND,
        status=CampaignStatus.ACTIVE,
        owner=user,
        planned_start_date=today - timedelta(days=90),
        planned_end_date=today + timedelta(days=90),
    )
    c.save(user=user, client_id=account.client_id)
    old = timezone.now() - timedelta(days=created_days_ago)
    Campaign.objects.filter(pk=c.pk).update(created_at=old)
    return c


# ---------------------------------------------------------------------------
# LIST exposes is_inactive with the correct value
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_list_exposes_is_inactive_flag(authed_api_a, account, user_a):
    stale = _make_campaign(account, user_a, created_days_ago=200, name='Stale')
    fresh = _make_campaign(account, user_a, created_days_ago=0, name='Fresh')

    resp = authed_api_a.get(LIST_URL)
    assert resp.status_code == 200

    assert _row_for(resp, stale.id)['is_inactive'] is True
    assert _row_for(resp, fresh.id)['is_inactive'] is False


# ---------------------------------------------------------------------------
# DETAIL exposes is_inactive (for the existing playlist banner)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_detail_exposes_is_inactive_flag(authed_api_a, account, user_a):
    stale = _make_campaign(account, user_a, created_days_ago=200, name='Stale')

    resp = authed_api_a.get(f'{LIST_URL}{stale.id}/')
    assert resp.status_code == 200
    assert _detail_body(resp)['is_inactive'] is True


# ---------------------------------------------------------------------------
# ANTI-N+1 — the list query count does NOT grow with the number of campaigns
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_list_is_inactive_has_no_nplus1(authed_api_a, account, user_a):
    def _list_query_count():
        cache.clear()  # list() is cached — force a real DB hit each measure
        with CaptureQueriesContext(connection) as ctx:
            resp = authed_api_a.get(LIST_URL)
            assert resp.status_code == 200
        return len(ctx)

    for i in range(3):
        _make_campaign(account, user_a, created_days_ago=200, name=f'S{i}')
    q_small = _list_query_count()

    for i in range(5):  # 3 -> 8 campaigns, all on the first page (size 10)
        _make_campaign(account, user_a, created_days_ago=200, name=f'M{i}')
    q_large = _list_query_count()

    assert q_large == q_small, (
        f'list query count grew with campaign count ({q_small} -> {q_large}): '
        f'is_inactive is being computed per campaign (N+1), not annotated'
    )
