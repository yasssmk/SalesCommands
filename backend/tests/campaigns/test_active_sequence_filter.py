# backend/tests/campaigns/test_active_sequence_filter.py
"""
The opt-in `active_sequence` filter on the activities endpoint.

The playlist "completed" accordion must hide completed activities whose target
sequence is OVER (its CampaignContact is COMPLETED/STOPPED) and keep the rest.
This pins the three cases plus the opt-in guarantee:

    GET /module-activities/?campaign={id}&status=COMPLETED&active_sequence=true

    (a) CampaignContact COMPLETED/STOPPED  -> EXCLUDED
    (b) CampaignContact non-final          -> INCLUDED
    (c) campaign_contact = None            -> STILL INCLUDED   <- the NULL trap

Case (c) is the reason the filter is written with the positive (non-final) set
plus an explicit isnull branch instead of exclude(): exclude() across the
nullable campaign_contact FK would silently drop the null rows. The 4th test
proves the filter is opt-in — without the param, all three come back.

Mirrors tests/campaigns/conftest.py (campaign / campaign_account /
make_campaign_contact / make_campaign_activity) and the unwrap style of
test_campaign_list_attribution.py. Postgres 5432; planned dates NOT NULL via
the conftest campaign fixture.
"""

import pytest
from django.utils import timezone

from app_modules.campaigns.constants import CampaignContactStatus

URL = "/module-activities/"


def _ids(resp):
    """Set of activity ids in the (enveloped, paginated) list payload."""
    body = resp.data
    data = body["data"] if isinstance(body, dict) and "data" in body else body
    results = (
        data["results"] if isinstance(data, dict) and "results" in data else data
    )
    return {str(r["id"]) for r in results}


def _completed_campaign_activity(
    campaign, campaign_account, account, user_a, campaign_contact
):
    """A COMPLETED activity on the campaign, optionally without a CampaignContact."""
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title="Chased",
        activity_type=ActivityType.CALL,
        status=ActivityStatus.COMPLETED,
        account=account,
        owner=user_a,
        campaign=campaign,
        campaign_account=campaign_account,
        campaign_contact=campaign_contact,
        scheduled_date=timezone.now().date(),
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.mark.django_db
def test_active_sequence_excludes_finished_keeps_active_and_orphan(
    authed_api_a, campaign, campaign_account, account, user_a, make_campaign_contact
):
    cc_final = make_campaign_contact(status=CampaignContactStatus.COMPLETED)
    cc_active = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)

    a_final = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, cc_final
    )
    a_active = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, cc_active
    )
    # (c) The trap: a completed activity with NO campaign_contact at all.
    a_orphan = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, None
    )

    resp = authed_api_a.get(
        f"{URL}?campaign={campaign.id}&status=COMPLETED&active_sequence=true"
    )
    assert resp.status_code == 200
    ids = _ids(resp)

    # (a) finished sequence excluded.
    assert str(a_final.id) not in ids
    # (b) active sequence included.
    assert str(a_active.id) in ids
    # (c) orphan (campaign_contact=None) STILL included — the NULL-safe branch.
    assert str(a_orphan.id) in ids


@pytest.mark.django_db
def test_without_param_returns_all_three(
    authed_api_a, campaign, campaign_account, account, user_a, make_campaign_contact
):
    """The filter is opt-in: absent the param, nothing is excluded."""
    cc_final = make_campaign_contact(status=CampaignContactStatus.STOPPED)
    cc_active = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)

    a_final = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, cc_final
    )
    a_active = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, cc_active
    )
    a_orphan = _completed_campaign_activity(
        campaign, campaign_account, account, user_a, None
    )

    resp = authed_api_a.get(f"{URL}?campaign={campaign.id}&status=COMPLETED")
    assert resp.status_code == 200
    ids = _ids(resp)

    assert {str(a_final.id), str(a_active.id), str(a_orphan.id)} <= ids
