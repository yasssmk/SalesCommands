# backend/tests/campaigns/test_campaign_list_channel.py
"""
CampaignListSerializer exposes channel_override so the card can show the
Email Only channel strategy.

Asserted on the HTTP response of GET /campaigns/ (not the serializer in
isolation): 'AUTO' on a default campaign, 'EMAIL_ONLY' when created with the
option.

Mirrors test_campaign_list_attribution.py (URL + row-unwrap helpers). Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignType

URL = '/campaigns/'


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
    raise AssertionError(f'campaign {campaign_id} not found in list payload')


def _mk_email_only(client_account, user):
    """OUTBOUND campaign created with channel_override='EMAIL_ONLY'.

    Planned dates supplied like the conftest `campaign` fixture (NOT NULL).
    """
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    c = Campaign(
        name='Email Only Campaign',
        campaign_type=CampaignType.OUTBOUND,
        owner=user,
        channel_override='EMAIL_ONLY',
        planned_start_date=today,
        planned_end_date=today + timedelta(days=30),
    )
    c.save(user=user, client_id=client_account.id)
    return c


@pytest.mark.django_db
def test_default_campaign_reports_auto(authed_api_a, campaign):
    """A campaign created without the option reports channel_override 'AUTO'."""
    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)
    assert row['channel_override'] == 'AUTO'


@pytest.mark.django_db
def test_email_only_campaign_reports_email_only(
    authed_api_a, user_a, client_account_a
):
    """A campaign created with the option reports channel_override 'EMAIL_ONLY'."""
    camp = _mk_email_only(client_account_a, user_a)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, camp.id)
    assert row['channel_override'] == 'EMAIL_ONLY'
