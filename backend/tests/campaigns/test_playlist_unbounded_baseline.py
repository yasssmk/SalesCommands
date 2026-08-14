# backend/tests/campaigns/test_playlist_unbounded_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil playlist (MESURE, aucun fix).

GET /campaigns/{id}/playlist/ is UNBOUNDED: CampaignExecutionService.get_playlist
(services/campaign_execution_service.py:279-388) materialises EVERY PLANNED+ON_HOLD
activity of the campaign — `activities = list(queryset)` at :333, no LIMIT,
`total_count = len(activities)` at :334 — then buckets and priority-sorts them in
Python (:358-388, _calculate_priority :951-999). The `?limit=` is applied AFTER,
in Python, at the view: `result['activities'][:limit]` (campaign_views.py:1012),
and `total_count` stays the pre-slice total (:1019). The action is NOT cached
(no cache_get_set), so it always pays this cold.

This module GRAVES the non-bounded behaviour (rows fetched == all open activities,
NOT the requested limit) and CAPTURES the current ordering as the reference the
future (bounded) fix must preserve:
  today bucket (priority-sorted) -> upcoming (scheduled_date asc) -> on_hold last.

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignStatus, CampaignType
from app_modules.campaigns.models import Campaign
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)

from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    user_a,
    authed_api_a,
)

TODAY = timezone.now().date()

# Volume: far more open activities than the limit we request, so the Python slice
# is observable (all fetched, few returned). N_UPCOMING distinct future dates make
# the "upcoming" order deterministic.
N_UPCOMING = 210
N_TODAY = 20      # callbacks due today -> the TODAY bucket
N_ON_HOLD = 20    # always last
N_TOTAL = N_UPCOMING + N_TODAY + N_ON_HOLD   # 250 open activities
REQUEST_LIMIT = 20

_seq = 0


def _mk_account(owner, ca):
    global _seq
    _seq += 1
    acc = CompanyAccount(company_name=f"Acc{_seq}", has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


@pytest.fixture
def big_campaign(db, client_account_a, user_a):
    ca, owner = client_account_a, user_a
    camp = Campaign(name="Playlist", campaign_type=CampaignType.OUTBOUND, owner=owner,
                    status=CampaignStatus.ACTIVE, planned_start_date=TODAY,
                    planned_end_date=TODAY + timedelta(days=60))
    camp.save(user=owner, client_id=ca.id)

    accounts = [_mk_account(owner, ca) for _ in range(10)]

    def _act(status, scheduled, *, callback=False, seq=1):
        a = Activity(
            title="a", activity_type=ActivityType.CALL, status=status,
            account=accounts[_seq % 10], owner=owner, campaign=camp,
            scheduled_date=scheduled, sequence_position=seq, is_callback_followup=callback,
        )
        a.save(user=owner, client_id=ca.id)

    # UPCOMING: PLANNED, future dates (no campaign_contact -> not "first planned" ->
    # upcoming), distinct dates for a deterministic ascending order.
    for i in range(N_UPCOMING):
        _act(ActivityStatus.PLANNED, TODAY + timedelta(days=i + 1))
    # TODAY: callbacks due today -> eligible for the TODAY bucket.
    for _ in range(N_TODAY):
        _act(ActivityStatus.PLANNED, TODAY, callback=True)
    # ON_HOLD: always at the end.
    for _ in range(N_ON_HOLD):
        _act(ActivityStatus.ON_HOLD, TODAY)

    return camp


def _get_playlist(authed_api_a, campaign_id, limit):
    resp = authed_api_a.get(f"/campaigns/{campaign_id}/playlist/?limit={limit}")
    assert resp.status_code == 200, resp.content
    return resp.data["data"]


@pytest.mark.django_db
class TestPlaylistUnboundedRedBaseline:

    def test_fetches_everything_regardless_of_limit(self, big_campaign, authed_api_a):
        camp = big_campaign

        with CaptureQueriesContext(connection) as cap:
            data = _get_playlist(authed_api_a, camp.id, REQUEST_LIMIT)

        total_count = data["total_count"]
        returned = len(data["results"])

        # The MAIN playlist fetch = the module_activities query filtering the two
        # open statuses. (A separate LIMIT 1 probe over module_activities exists —
        # the campaign's is_inactive check — and is not the playlist fetch.)
        main_fetch = [
            q for q in cap.captured_queries
            if '"module_activities"' in q["sql"]
            and "PLANNED" in q["sql"] and "ON_HOLD" in q["sql"]
        ]
        main_fetch_limited = [q for q in main_fetch if " LIMIT " in q["sql"].upper()]

        print("\n" + "=" * 62)
        print("RED BASELINE — GET /campaigns/{id}/playlist/ (unbounded)")
        print("=" * 62)
        print(f"  open activities (PLANNED+ON_HOLD)     : {N_TOTAL}")
        print(f"  ?limit= requested                     : {REQUEST_LIMIT}")
        print(f"  total_count (rows the service loaded) : {total_count}")
        print(f"  results returned (Python slice)       : {returned}")
        print(f"  main playlist fetch has a LIMIT       : {bool(main_fetch_limited)}")
        print("=" * 62 + "\n")

        # ---- THE RED: the service loads ALL open activities, not the limit. ----
        assert total_count == N_TOTAL, f"total_count expected {N_TOTAL}, got {total_count}"
        assert returned == REQUEST_LIMIT, f"returned expected {REQUEST_LIMIT}, got {returned}"
        # The main fetch exists and carries NO LIMIT: the full set is fetched and
        # sliced in Python.
        assert len(main_fetch) >= 1, "could not identify the playlist fetch query"
        assert len(main_fetch_limited) == 0, "the playlist fetch is DB-limited (unexpected)"

    def test_order_is_deterministic_and_follows_the_documented_buckets(
        self, big_campaign, authed_api_a
    ):
        """Capture the CURRENT order as the reference a bounded fix must reproduce:
        deterministic across calls, TODAY bucket first, ON_HOLD last, UPCOMING
        sorted by scheduled_date ascending."""
        camp = big_campaign

        # Determinism (via the real endpoint): two calls -> identical id order.
        ids_1 = [r["id"] for r in _get_playlist(authed_api_a, camp.id, 500)["results"]]
        ids_2 = [r["id"] for r in _get_playlist(authed_api_a, camp.id, 500)["results"]]
        assert ids_1 == ids_2, "playlist order is not deterministic"
        assert len(ids_1) == N_TOTAL

        # Structure reference (via the service, which returns the ordered objects):
        service = CampaignExecutionService(user=camp.owner, client_id=camp.client_id)
        ordered = service.get_playlist(camp)["activities"]
        assert [str(a.id) for a in ordered] == ids_1  # endpoint order == service order

        statuses = [a.status for a in ordered]
        # ON_HOLD is a contiguous block at the very end.
        first_on_hold = next(i for i, s in enumerate(statuses) if s == ActivityStatus.ON_HOLD)
        assert all(s == ActivityStatus.ON_HOLD for s in statuses[first_on_hold:]), \
            "ON_HOLD activities are not all at the end"
        assert statuses[:first_on_hold].count(ActivityStatus.ON_HOLD) == 0

        # The UPCOMING tail (PLANNED after the TODAY callbacks) is scheduled asc.
        planned = [a for a in ordered if a.status == ActivityStatus.PLANNED]
        upcoming = [a for a in planned if not a.is_callback_followup]
        upcoming_dates = [a.scheduled_date for a in upcoming]
        assert upcoming_dates == sorted(upcoming_dates), "UPCOMING not sorted by date asc"

        # TODAY bucket (the callbacks) leads, before any upcoming.
        first_upcoming_idx = statuses.index(ActivityStatus.PLANNED) if not ordered[0].is_callback_followup else 0
        assert ordered[0].is_callback_followup, "TODAY (callback) bucket does not lead"
