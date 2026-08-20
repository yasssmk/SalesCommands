# app_modules/campaigns/services/campaign_dc_attribution.py
"""
Which decision cycles a campaign's MONEY objectives may claim — declared ONCE.

PO rule, per KPI type:

* ``DECISION_CYCLES`` counts what the campaign CREATED — origin only
  (``DecisionCycle.source_campaign``). This module does not apply to it.
* ``PIPELINE_VALUE`` / ``REVENUE_WON`` count what the campaign **WORKED**: a
  cycle's value is claimed only once the campaign has at least one COMPLETED +
  SUCCESSFUL activity on that cycle.

BEING THE ORIGIN IS NOT A CLAIM ON THE MONEY (PO, final rule). A cycle born from
a campaign that nobody has worked yet contributes NOTHING to that campaign's
pipeline — the campaign gets credit for the value when it has actually moved the
deal, not for having opened it. The count above is where creation is rewarded;
these two are where work is.

That single condition also closes two reported symptoms at once, without
touching any write path: a deal used to enter a campaign's pipeline the moment
an activity was CREATED (before completion), and to stay there after that
activity was CANCELLED. Both arrived through the born-from branch, which no
longer contributes on its own; ``status=COMPLETED`` settles the rest.

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

HOW AN ACTIVITY BELONGS TO A CAMPAIGN
-------------------------------------
Two edges, both taken from ``CampaignAnalyticsService._count_meetings``, which
unions them because neither field alone is enough (``Activity.campaign`` and
``source_activity`` are both nullable):

1. ``Activity.campaign``                 — a campaign activity logged on the cycle;
2. ``Activity.source_activity.campaign`` — a follow-up born from a campaign
   activity. This is the pre-existing-deal case: the modal sets the cycle but
   leaves ``Activity.campaign`` None.

``DecisionCycle.source_campaign`` was a third edge here until the rule above made
work, not origin, the condition for money. It still decides DECISION_CYCLES.

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
stays one row per cycle.
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

    Both campaign edges are tested here; the cycle's own ``source_campaign`` is
    not one of them (see the module docstring).
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
    """Narrow a DecisionCycle queryset to the cycles ``campaign_id`` may claim
    the VALUE of: those carrying at least one COMPLETED + SUCCESSFUL activity of
    the campaign.

    Being the cycle's ``source_campaign`` is deliberately NOT sufficient — see
    the module docstring. Origin decides DECISION_CYCLES, work decides the money.

    Returns a queryset with ONE ROW PER CYCLE — safe to aggregate over, and safe
    to combine with the deal_products join, because the predicate is a scalar
    subquery, not a join.

    THE single declaration of the rule: the campaign LIST path
    (campaign_objective_progress), the campaign DETAIL path and the campaign
    DASHBOARD all call this, so they cannot drift — and a parity test asserts
    they agree on every objective type.
    """
    return (
        queryset
        .annotate(**{TOUCHED_BY_ALIAS: successful_campaign_activity(campaign_id)})
        .filter(**{TOUCHED_BY_ALIAS: True})
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
