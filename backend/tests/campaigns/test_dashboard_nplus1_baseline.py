# backend/tests/campaigns/test_dashboard_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil dashboard campagne (MESURE, aucun fix).

Measured on main AFTER the objectives-grouping fix is merged (so the objectives
loop is already bounded and NOT recounted here). What remains in
GET /campaigns/{id}/dashboard/ (CampaignAnalyticsService.get_dashboard,
campaign_analytics_service.py:57-82) is:

- N+1 EXECUTORS: get_executor_performance (:437-467) loops over
  [(owner,'OWNER'),(executor,'EXECUTOR')] (:440-443) and runs 5 .count() per
  non-null user (:448-452 total/completed/planned/on_hold/accounts_count). Each
  extra executor costs 6 queries: its 5 counts PLUS one lazy load of the
  campaign.executor User row (the retrieve does not select_related it).
- DUPLICATED COUNTs: total-accounts counted 3x (get_summary :90,
  get_accounts_breakdown :360, get_timeline_progress :410); total-activities
  counted 2x (get_summary :91, get_activities_breakdown :316).
- _count_meetings (:501-549) = one COUNT with two correlated Exists (an expensive
  single query, not an N+1), only when a MEETINGS objective is present.

This module GRAVES the cold dashboard query count and PROVES the executor slope
(+5 queries per executor). Cache neutralised (DummyCache) so we measure cold.
DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignType,
    ObjectiveType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignObjective

from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    user_a,
    authed_api_a,
)

TODAY = timezone.now().date()

_seq = 0


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca):
    global _seq
    _seq += 1
    acc = CompanyAccount(company_name=f"{name}{_seq}", has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _seed_campaign(owner, ca, *, executor):
    """Identical realistic campaign except for `executor`, so the ONLY query-count
    difference between the two is the extra executor's 5 .count() calls."""
    camp = Campaign(
        name="Dashboard", campaign_type=CampaignType.OUTBOUND, owner=owner,
        executor=executor, planned_start_date=TODAY,
        planned_end_date=TODAY + timedelta(days=30),
    )
    camp.save(user=owner, client_id=ca.id)

    # 5 accounts + CampaignAccounts across statuses.
    statuses = [
        CampaignAccountStatus.COMPLETED, CampaignAccountStatus.COMPLETED,
        CampaignAccountStatus.IN_PROGRESS, CampaignAccountStatus.PENDING,
        CampaignAccountStatus.STOPPED,
    ]
    accts = []
    for i, st in enumerate(statuses):
        acc = _mk_account(f"acc{i}-", owner, ca)
        CampaignAccount(campaign=camp, account=acc, status=st).save(user=owner, client_id=ca.id)
        accts.append(acc)

    # Activities owned by the OWNER across types/statuses (incl. a completed
    # MEETING so _count_meetings runs). Kept identical between the two campaigns.
    def _act(atype, status, acc, outcome=None):
        a = Activity(title="a", activity_type=atype, status=status, account=acc,
                     owner=owner, campaign=camp, scheduled_date=TODAY, outcome=outcome)
        a.save(user=owner, client_id=ca.id)

    _act(ActivityType.MEETING, ActivityStatus.COMPLETED, accts[0], outcome="SUCCESSFUL")
    _act(ActivityType.CALL, ActivityStatus.COMPLETED, accts[0])
    _act(ActivityType.CALL, ActivityStatus.PLANNED, accts[1])
    _act(ActivityType.EMAIL, ActivityStatus.PLANNED, accts[2])
    _act(ActivityType.CALL, ActivityStatus.ON_HOLD, accts[3])
    _act(ActivityType.EMAIL, ActivityStatus.COMPLETED, accts[4])

    # 3 objectives (already grouped by the merged fix — not the subject here).
    for idx, otype in enumerate(
        [ObjectiveType.MEETINGS, ObjectiveType.DECISION_CYCLES, ObjectiveType.CONTACTS_REACHED]
    ):
        CampaignObjective(campaign=camp, name=str(otype), objective_type=otype,
                          target_value=10, is_primary=(idx == 0)).save(user=owner, client_id=ca.id)

    return camp


def _measure_dashboard(authed_api_a, campaign_id):
    cache.clear()
    with CaptureQueriesContext(connection) as cap:
        resp = authed_api_a.get(f"/campaigns/{campaign_id}/dashboard/")
    assert resp.status_code == 200, resp.content
    return cap.captured_queries


def _count_table_counts(queries, table):
    """How many captured statements are a COUNT(*) over `table` — used to surface
    the duplicated total-accounts / total-activities counts."""
    return sum(1 for q in queries if "COUNT(*)" in q["sql"] and f'"{table}"' in q["sql"])


@pytest.mark.django_db
class TestDashboardNPlusOneRedBaseline:

    def test_dashboard_cold_query_count_and_executor_slope(
        self, authed_api_a, user_a, client_account_a, settings
    ):
        # CACHE NEUTRALISED: DummyCache -> the 30s dashboard cache never serves a
        # warm hit; every call recomputes (cold).
        settings.CACHES = {
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
        }

        executor = _mk_user("exec-a@a.test", client_account_a, user_a.role)

        # One executor (executor=None -> only OWNER processed) vs two (owner +
        # executor). Everything else identical.
        camp1 = _seed_campaign(user_a, client_account_a, executor=None)
        camp2 = _seed_campaign(user_a, client_account_a, executor=executor)

        q1 = _measure_dashboard(authed_api_a, camp1.id)
        q2 = _measure_dashboard(authed_api_a, camp2.id)
        n1, n2 = len(q1), len(q2)
        executor_slope = n2 - n1  # 1 executor -> 2 executors

        # Duplicated total counts in the 2-executor (realistic) trace.
        ca_counts = _count_table_counts(q2, "module_campaign_accounts")
        act_counts = _count_table_counts(q2, "module_activities")

        print("\n" + "=" * 66)
        print("RED BASELINE — GET /campaigns/{id}/dashboard/ SQL queries (cold)")
        print("=" * 66)
        print(f"  1 executor  (owner only)      : {n1} queries")
        print(f"  2 executors (owner + executor): {n2} queries")
        print(f"  executor slope                : {executor_slope} queries / executor")
        print(f"  COUNT(*) over campaign_accounts (dup total-accounts 3x): {ca_counts}")
        print(f"  COUNT(*) over module_activities (dup total-activities 2x): {act_counts}")
        print("=" * 66 + "\n")

        # ---- Executor N+1 proof: each executor adds 6 queries (its 5 .count()
        # calls + one lazy load of the executor User row, un-select_related'd).
        assert executor_slope == 6, f"executor slope expected 6, got {executor_slope}"
        # ---- Duplicated totals are present in the trace (>= the code-confirmed
        # 3x campaign-accounts and 2x activities bare counts, among other counts).
        assert ca_counts >= 3, f"expected >=3 campaign_accounts COUNTs, got {ca_counts}"
        assert act_counts >= 2, f"expected >=2 activities COUNTs, got {act_counts}"
        # ---- The cold dashboard is heavy (graved floor).
        assert n2 >= 20, f"dashboard cold baseline unexpectedly low: {n2}"
