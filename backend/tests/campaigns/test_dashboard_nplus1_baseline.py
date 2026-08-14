# backend/tests/campaigns/test_dashboard_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil dashboard campagne (MESURE, aucun fix).

GARDE-FOU POST-FIX. Le dashboard groupe désormais les stats exécuteurs en UNE
agrégation conditionnelle (get_executor_performance) et déduplique les COUNT en
partageant un GROUP BY par statut (comptes + activités) calculé une seule fois
dans get_dashboard. Valeurs métier inchangées (voir test_dashboard_equivalence).

ROUGE (avant fix, commit 8d5d5c55) -> VERT :
- 1 exécuteur  : 25 -> 14
- 2 exécuteurs : 31 -> 15
- pente exécuteur : 6 -> 1

La pente résiduelle de 1 n'est PLUS le N+1 exécuteurs (le bloc perf est O(1) via
l'agrégat + in_bulk des noms) : c'est le chargement paresseux de campaign.executor
que get_summary fait pour SA sortie (bloc 'executor'), un load unique constant.
Les COUNT(*) « nus » sur module_campaign_accounts passent de 6 à 0 (tous les
totaux/statuts dérivent du GROUP BY partagé). Casser un regroupement fait remonter
ces nombres et échouer ce test.

Cache neutralisé (DummyCache) = cold. DB: Postgres.
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
        print("DASHBOARD SQL queries — grouped guard (cold)")
        print("=" * 66)
        print(f"  1 executor  (owner only)      : {n1} queries")
        print(f"  2 executors (owner + executor): {n2} queries")
        print(f"  executor slope                : {executor_slope} queries / executor")
        print(f"  COUNT(*) over campaign_accounts (dup total-accounts 3x): {ca_counts}")
        print(f"  COUNT(*) over module_activities (dup total-activities 2x): {act_counts}")
        print("=" * 66 + "\n")

        # ---- Executor block is now O(1): the slope collapsed from 6 to 1, and the
        # residual 1 is get_summary's own campaign.executor load (not the N+1).
        assert executor_slope == 1, f"executor slope expected 1, got {executor_slope}"
        assert n1 == 14, f"1-executor dashboard expected 14 queries, got {n1}"
        assert n2 == 15, f"2-executor dashboard expected 15 queries, got {n2}"
        # ---- Dedup complete: no bare COUNT(*) over campaign_accounts remains (all
        # totals/statuses derive from the shared GROUP BY). Breaking the reuse makes
        # these climb back.
        assert ca_counts == 0, f"expected 0 bare campaign_accounts COUNT(*), got {ca_counts}"
