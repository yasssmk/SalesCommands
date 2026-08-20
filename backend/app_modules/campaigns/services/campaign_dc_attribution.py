# app_modules/campaigns/services/campaign_dc_attribution.py
"""
Which decision cycles a campaign's MONEY objectives may claim — declared ONCE.

PO rule, per KPI type:

* ``DECISION_CYCLES`` counts what the campaign CREATED — origin only
  (``DecisionCycle.source_campaign``). This module does not apply to it.
* ``PIPELINE_VALUE`` / ``REVENUE_WON`` count what the campaign CREATED **or**
  **WORKED**: a cycle's value is claimed when the cycle is born from the
  campaign OR carries a SUCCESSFUL activity of it.

A cycle may therefore be claimed by SEVERAL campaigns, and campaign values are
NOT additive across campaigns. That is intended: two campaigns that both moved a
deal each did so on the whole deal, not on a share of it.

WHY THIS LIVES IN THE CAMPAIGN LAYER
------------------------------------
``bi/metrics/sales_metrics.pipeline_value`` / ``revenue_won`` are the CANONICAL
formulas, shared with personal quotas and the team/admin perimeters
(quotas/services/progress.py). Widening their ``source_campaign`` filter would
change attribution for every one of those callers. So the union is expressed
HERE, on the queryset, ABOVE the canonical functions — the campaign paths hand
them an already-attributed set (or aggregate directly), and nothing personal
moves.

"SUCCESSFUL" IS NOT REDEFINED
-----------------------------
It is ``campaign_execution_service.SUCCESSFUL_OUTCOMES`` — the set the campaign
progression already uses to complete a contact — paired with
``status=COMPLETED``: ``Activity.outcome`` is documented as meaningful "only when
completed", so the pairing keeps a PLANNED row with a stray outcome from
attributing.

THREE EDGES, THE SAME THREE AS MEETINGS
---------------------------------------
Mirrors ``CampaignAnalyticsService._count_meetings``, which already unions them
because no single field is enough (``Activity.decision_cycle`` and
``source_activity`` are both nullable):

1. ``Activity.campaign``                 — a campaign activity logged on the cycle;
2. ``DecisionCycle.source_campaign``     — the born-from branch (a field of the
   cycle itself, so it is a plain filter here rather than an activity edge);
3. ``Activity.source_activity.campaign`` — a follow-up born from a campaign
   activity, on a cycle that never got ``source_campaign``. This is the
   pre-existing-deal case: the modal sets the cycle but leaves
   ``Activity.campaign`` None.

ONCE PER CAMPAIGN — THE CORRECTNESS RISK
----------------------------------------
The money must count a cycle ONCE per campaign however many successful
activities it carries. Reaching cycles through their activities is a to-many
traversal, and ``DEAL_VALUE_SUM`` is itself a join over ``deal_products``
(deal_value_sql.py warns that combining it with ANY other to-many join
multiplies rows). A join-based union would inflate by activities AND by lines,
silently and plausibly.

``Exists`` is what makes that impossible: it is a correlated BOOLEAN subquery, so
three matching activities and one give the same answer, and the outer row set
stays one row per cycle. The born-from branch ORs into the same predicate, so a
cycle that is both born-from and touched-by is still a single row.
"""

from django.db.models import Exists, OuterRef, Q, Sum

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.services.deal_value_sql import (
    DEAL_VALUE_ALIAS,
    annotate_deal_value,
)

from .campaign_execution_service import SUCCESSFUL_OUTCOMES


# Annotation alias for the touched-by test. Underscored so it can never clash
# with a model field or a serializer output key (same convention as
# deal_value_sql.py / derivation_sql.py).
TOUCHED_BY_ALIAS = '_touched_by_campaign'


def successful_campaign_activity(campaign_id):
    """``Exists`` — this cycle carries at least ONE successful activity of
    ``campaign_id``.

    Correlated on the OUTER cycle's pk, so it is evaluated per cycle and returns
    a boolean: the number of matching activities never reaches the outer row set,
    which is precisely what keeps the money from multiplying.

    Edges 1 and 3 of the union (edge 2, born-from, is a field of the cycle and is
    applied by ``attributed_cycles`` below).
    """
    return Exists(
        Activity.objects
        .filter(
            decision_cycle_id=OuterRef('pk'),
            status=ActivityStatus.COMPLETED,
            outcome__in=SUCCESSFUL_OUTCOMES,
        )
        .filter(
            Q(campaign_id=campaign_id)
            | Q(source_activity__campaign_id=campaign_id)
        )
    )


def attributed_cycles(queryset, campaign_id):
    """Narrow a DecisionCycle queryset to the cycles ``campaign_id`` may claim:
    born from it OR carrying a successful activity of it.

    Returns a queryset with ONE ROW PER CYCLE — safe to aggregate
    ``DEAL_VALUE_SUM`` over, and safe to combine with the deal_products join
    because the added predicate is a scalar subquery, not a join.

    THE single declaration of the rule: both the campaign LIST path
    (campaign_objective_progress) and the campaign DETAIL path
    (CampaignAnalyticsService) call this, so they cannot drift — and a parity
    test asserts they agree on every objective type.
    """
    return (
        queryset
        .annotate(**{TOUCHED_BY_ALIAS: successful_campaign_activity(campaign_id)})
        .filter(Q(source_campaign_id=campaign_id) | Q(**{TOUCHED_BY_ALIAS: True}))
    )


# A campaign reports a RESULT, not a state (PO): a deal the campaign produced does
# not vanish from its pipeline the moment it is won. So campaign PIPELINE covers
# OPEN **or** WON, and campaign WON covers WON — the same won deal counts in both,
# and that overlap is intended. This is the ONE place the two populations differ
# from the personal metrics, where pipeline is exclusive (a won deal leaves it):
# a rep's pipeline answers "what is still to close", a campaign's answers "what
# did this campaign put on the table". LOST / ON_HOLD / NOT_QUALIFIED are in
# neither: the campaign produced nothing there.
_CAMPAIGN_PIPELINE_STATES = Q(outcome__isnull=True) | Q(outcome=CycleOutcome.WON)
_CAMPAIGN_WON_STATES = Q(outcome=CycleOutcome.WON)


def campaign_money(campaign_id, client_id):
    """``{'pipeline': float, 'won': float}`` for ONE campaign.

    THE canonical campaign money calculation. Every campaign surface calls this
    — the list card, the detail serializer and the workspace dashboard — so the
    three cannot show different numbers. Before it existed they each had their
    own aggregate, and the dashboard's was still origin-only.

    Both figures come from ONE query over the attributed set:

    * ``annotate_deal_value`` gives each cycle its roll-up as a correlated
      SUBQUERY, so summing it with two different filters cannot fan out — a
      ``DEAL_VALUE_SUM`` join would multiply each cycle by its line count and
      make the two sums disagree with the row set they came from;
    * ``attributed_cycles`` adds the born-from OR successful-activity predicate
      as an ``Exists``, keeping one row per cycle whatever its activity count.

    No period filter: campaign metrics are all-time by rule.
    """
    agg = attributed_cycles(
        annotate_deal_value(DecisionCycle.objects.filter(client_id=client_id)),
        campaign_id,
    ).aggregate(
        pipeline=Sum(DEAL_VALUE_ALIAS, filter=_CAMPAIGN_PIPELINE_STATES),
        won=Sum(DEAL_VALUE_ALIAS, filter=_CAMPAIGN_WON_STATES),
    )
    return {
        'pipeline': float(agg['pipeline'] or 0),
        'won': float(agg['won'] or 0),
    }
