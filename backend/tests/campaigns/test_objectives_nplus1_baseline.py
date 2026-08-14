# backend/tests/campaigns/test_objectives_nplus1_baseline.py
"""
RED BASELINE — Sprint Timeout / Fil objectifs (MESURE, aucun fix).

Le calcul de progression des objectifs de campagne est un 1+N : UNE requete SQL
par CampaignObjective, emise par la MEME fonction partagee
``CampaignAnalyticsService._calculate_objective_value``
(``campaign_analytics_service.py:409``) sur les TROIS chemins qui exposent la
progression des objectifs :

  (a) GET /campaigns/{id}/dashboard/
      -> ``CampaignAnalyticsService.get_objectives_progress``
         (fetch ``campaign_analytics_service.py:189`` + boucle ``:192-193`` ->
         ``_calculate_objective_value:409``)

  (b) GET /campaigns/{id}/  (detail)
      -> ``CampaignDetailSerializer.get_objectives``
         (``campaign_serializer.py:394-398``) -> le MEME
         ``get_objectives_progress`` (rejoue car ``get_object`` de la mixin
         court-circuite le queryset annote/prefetch, ``permissions/mixins.py``)

  (c) compute du KPI ``campaign_progress``
      -> ``bi/definitions/campaigns.py:114-115`` ``obj.get_current_value()``
         -> ``campaign_objective.py:110-112`` -> le MEME
         ``_calculate_objective_value:409``

GARDE-FOU POST-FIX. Le calcul des objectifs est desormais GROUPE PAR SOURCE au
point partage ``CampaignAnalyticsService.calculate_objective_values`` : une seule
requete par SOURCE de donnees presente (famille DecisionCycle collapsee en 1
agregat conditionnel ; MEETINGS / CONTACTS_REACHED / NEW_LOGOS, 1 chacune),
plafonnee a 4 quelle que soit la quantite d'objectifs. Ce module VERROUILLE les
nombres verts et la pente reduite.

ROUGE (avant fix, commit f1827e9) -> VERT (apres regroupement) :
  (a) GET dashboard : 30 / 34  -> 30 / 32
  (b) GET detail    : 11 / 15  -> 11 / 13
  (c) KPI           :  5 /  9  ->  5 /  7
Pente : +1 requete/objectif  -> +0,5/objectif (2 sources irreductibles ajoutees
entre 2 et 6 objectifs : CONTACTS_REACHED et NEW_LOGOS ; la famille DecisionCycle
DECISION_CYCLES/PIPELINE_VALUE/REVENUE_WON ne coute qu'UNE requete). Casser le
regroupement (ex. 3 requetes DecisionCycle separees) fait REMONTER ces nombres et
echouer ce test — c'est sa non-vacuite.

CACHE NEUTRALISE : on force le backend ``DummyCache`` pendant la mesure, donc
chaque appel est FROID (jamais un hit Redis). On mesure le cout reel du calcul.

Le chemin (c) est mesure via ``cached_run(campaign_progress, ...)`` : c'est
EXACTEMENT le compute que l'endpoint ``/bi/kpi/<key>/`` invoque
(``bi/views.py:111``), sans l'auth/serialisation — lesquelles sont
independantes du nombre d'objectifs et n'entrent donc pas dans la pente.

DB : Postgres.
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
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions.campaigns import campaign_progress
from app_modules.campaigns.constants import (
    CampaignAccountStatus,
    CampaignType,
    ObjectiveType,
)
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignObjective
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from permissions.compat import AuthContext

TODAY = timezone.now().date()

# A campaign holds at most one objective per type (unique (campaign,
# objective_type)), so 6 is the business maximum. Fixed order so the
# 2-objective campaign is a strict prefix of the 6-objective one: the 4 added
# types (CONTACTS_REACHED, PIPELINE_VALUE, REVENUE_WON, NEW_LOGOS) each add
# exactly one query, hence a slope of +4.
OBJECTIVE_TYPES = [
    ObjectiveType.MEETINGS,
    ObjectiveType.DECISION_CYCLES,
    ObjectiveType.CONTACTS_REACHED,
    ObjectiveType.PIPELINE_VALUE,
    ObjectiveType.REVENUE_WON,
    ObjectiveType.NEW_LOGOS,
]


# ---------------------------------------------------------------------------
# Realistic seed — IDENTICAL for every campaign except the objective count, so
# the ONLY query-count difference between the 2- and 6-objective campaigns is
# the objectives loop.
# ---------------------------------------------------------------------------

def _seed_campaign(user, ca, n_objectives):
    camp = Campaign(
        name=f"RedBaseline-{n_objectives}",
        campaign_type=CampaignType.OUTBOUND,
        owner=user,
        executor=user,
        planned_start_date=TODAY,
        planned_end_date=TODAY + timedelta(days=30),
    )
    camp.save(user=user, client_id=ca.id)

    # 3 accounts + 3 CampaignAccounts (2 COMPLETED, 1 PENDING).
    accts = []
    for i in range(3):
        a = CompanyAccount(
            company_name=f"Acc{n_objectives}-{i}",
            has_buying_decision=True,
            account_owner=user,
        )
        a.save(user=user, client_id=ca.id)
        accts.append(a)
    for acc, status in (
        (accts[0], CampaignAccountStatus.COMPLETED),
        (accts[1], CampaignAccountStatus.COMPLETED),
        (accts[2], CampaignAccountStatus.PENDING),
    ):
        CampaignAccount(campaign=camp, account=acc, status=status).save(
            user=user, client_id=ca.id
        )

    # 2 completed campaign meetings (feed MEETINGS / CONTACTS_REACHED).
    for i in range(2):
        Activity(
            title=f"M{i}",
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
            outcome="SUCCESSFUL",
            account=accts[0],
            owner=user,
            campaign=camp,
            scheduled_date=TODAY,
        ).save(user=user, client_id=ca.id)

    # 2 decision cycles of origin (feed DECISION_CYCLES / PIPELINE_VALUE /
    # REVENUE_WON): one open, one won.
    DecisionCycle(
        account=accts[1],
        owner=user,
        name="dc-open",
        source_campaign=camp,
        estimated_value=1500,
    ).save(user=user, client_id=ca.id)
    DecisionCycle(
        account=accts[2],
        owner=user,
        name="dc-won",
        source_campaign=camp,
        estimated_value=900,
        outcome=CycleOutcome.WON,
        outcome_date=TODAY,
    ).save(user=user, client_id=ca.id)

    # Objectives — the first n types, exactly one per type; MEETINGS is primary.
    for idx, otype in enumerate(OBJECTIVE_TYPES[:n_objectives]):
        CampaignObjective(
            campaign=camp,
            name=str(otype),
            objective_type=otype,
            target_value=10,
            is_primary=(idx == 0),
        ).save(user=user, client_id=ca.id)

    return camp


def _measure(fn):
    """Count SQL queries emitted by fn(), cache cleared first (cold)."""
    cache.clear()  # explicit cold intent (a no-op under DummyCache).
    with CaptureQueriesContext(connection) as cap:
        fn()
    return len(cap.captured_queries)


def _get_ok(api, url):
    resp = api.get(url)
    assert resp.status_code == 200, (
        f"{url} -> {resp.status_code}: {getattr(resp, 'data', None)}"
    )
    return resp


# ---------------------------------------------------------------------------
# THE RED — measured query counts (cold cache) + the 1+N slope.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestObjectivesNPlusOneRedBaseline:
    """Measures, does not fix. Prints the starting numbers and locks the slope."""

    def test_baseline_and_slope(self, settings, authed_api_a, user_a, client_account_a):
        # CACHE NEUTRALISED: force DummyCache so every call is COLD (never a warm
        # Redis/locmem hit) — we measure the real compute cost, not a cache hit.
        settings.CACHES = {
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
        }

        # Two identical campaigns except objective count: 2 (business min useful)
        # vs 6 (business max — one per ObjectiveType).
        camp2 = _seed_campaign(user_a, client_account_a, n_objectives=2)
        camp6 = _seed_campaign(user_a, client_account_a, n_objectives=6)

        ctx = AuthContext(
            user_id=str(user_a.id),
            client_id=str(client_account_a.id),
            is_authenticated=True,
        )

        # (a) dashboard endpoint
        dash2 = _measure(
            lambda: _get_ok(authed_api_a, f"/campaigns/{camp2.id}/dashboard/")
        )
        dash6 = _measure(
            lambda: _get_ok(authed_api_a, f"/campaigns/{camp6.id}/dashboard/")
        )

        # (b) detail endpoint
        det2 = _measure(lambda: _get_ok(authed_api_a, f"/campaigns/{camp2.id}/"))
        det6 = _measure(lambda: _get_ok(authed_api_a, f"/campaigns/{camp6.id}/"))

        # (c) KPI campaign_progress compute (the exact producer bi/views.py:111
        # calls, minus objective-independent auth/serialize).
        kpi2 = _measure(
            lambda: cached_run(
                campaign_progress, ctx, scope="mine",
                params={"campaign_id": str(camp2.id)},
            ).value
        )
        kpi6 = _measure(
            lambda: cached_run(
                campaign_progress, ctx, scope="mine",
                params={"campaign_id": str(camp6.id)},
            ).value
        )

        # ---- THE NUMBERS (printed; run with `pytest -s` to see it) ----
        print("\n" + "=" * 66)
        print("OBJECTIVES SQL COST — grouped guard (cold cache, DummyCache)")
        print("=" * 66)
        print(f"{'path':<28}{'2 obj':>8}{'6 obj':>8}{'slope/obj':>12}")
        print("-" * 66)
        print(f"{'(a) GET dashboard':<28}{dash2:>8}{dash6:>8}{(dash6 - dash2) / 4:>12.2f}")
        print(f"{'(b) GET detail':<28}{det2:>8}{det6:>8}{(det6 - det2) / 4:>12.2f}")
        print(f"{'(c) KPI campaign_progress':<28}{kpi2:>8}{kpi6:>8}{(kpi6 - kpi2) / 4:>12.2f}")
        print("=" * 66)
        print(
            "Workspace opens (a)+(b) together -> the objectives loop runs TWICE "
            f"per open: {dash6} + {det6} = {dash6 + det6} queries at 6 objectives.\n"
        )

        # ---- Grouped slope: +4 objectives (types) -> +2 queries on EVERY path.
        # Between 2 and 6 objectives the test adds CONTACTS_REACHED and NEW_LOGOS
        # (two irreducible sources) plus PIPELINE_VALUE/REVENUE_WON, which fold
        # into the already-present DecisionCycle aggregate for free. So +2, not
        # +4. Break the DecisionCycle collapse and this jumps back to +4. ----
        assert dash6 - dash2 == 2, f"dashboard slope regressed: {dash2} -> {dash6}"
        assert det6 - det2 == 2, f"detail slope regressed: {det2} -> {det6}"
        assert kpi6 - kpi2 == 2, f"kpi slope regressed: {kpi2} -> {kpi6}"

        # ---- KPI absolute: campaign + accounts agg + objectives load + one
        # query per SOURCE present. 2 obj (MEETINGS + DECISION_CYCLES) = 3 + 2 = 5;
        # 6 obj (all types, DC family folded) = 3 + 4 sources = 7 (was 9). ----
        assert kpi2 == 5, f"KPI at 2 objectives expected 5, got {kpi2}"
        assert kpi6 == 7, f"KPI at 6 objectives expected 7, got {kpi6}"

        # ---- Endpoints carry a large constant baseline ON TOP of the loop. ----
        assert dash2 >= 10, f"dashboard baseline unexpectedly low: {dash2}"
        assert det2 >= 5, f"detail baseline unexpectedly low: {det2}"
