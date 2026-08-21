# app_modules/campaigns/services/campaign_dc_attribution.py
"""
Which decision cycles a campaign's MONEY objectives may claim — declared ONCE.

PO rule, final: a cycle counts for a campaign's ``PIPELINE_VALUE`` /
``REVENUE_WON`` / ``NEW_LOGOS`` if EITHER branch holds —

* BORN-FROM — the campaign OPENED the cycle (``DecisionCycle.source_campaign``).
  UNCONDITIONAL: it counts from the moment the deal exists, with nothing logged
  on it. A deal a campaign opened is that campaign's deal.
* TOUCHED-BY — the campaign has at least one COMPLETED + SUCCESSFUL activity on
  the cycle. GATED, because a deal the campaign did not open has to be earned.

The two branches are gated differently ON PURPOSE, and that asymmetry is the
whole content of this module. ``DECISION_CYCLES`` is not covered here: it is
origin-only and counts creation, which is a narrower question.

WHY BORN-FROM WAS GATED FOR A WHILE, AND WHY IT IS NOT ANY MORE
---------------------------------------------------------------
Two symptoms were reported: a deal entered a campaign's pipeline as soon as an
activity was CREATED (before completion), and stayed there after that activity
was CANCELLED. Both were the same bug — an UNVALIDATED activity attributing —
and requiring ``status=COMPLETED`` on the touched-by branch is what fixes them.
Gating born-from as well was a wrong diagnosis of the same symptom: it made a
campaign's own freshly opened deals invisible to it. Reversed (PO, final);
``status=COMPLETED`` stays exactly where it belongs.

A cycle may be claimed by SEVERAL campaigns, and campaign values are NOT additive
across campaigns. That is intended: the campaign that opened a deal and the
campaign that closed it each carried the whole deal, not a share of it.

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

HOW AN ACTIVITY BELONGS TO A CAMPAIGN (the touched-by branch)
------------------------------------------------------------
Two edges, both taken from ``CampaignAnalyticsService._count_meetings``, which
unions them because neither field alone is enough (``Activity.campaign`` and
``source_activity`` are both nullable):

1. ``Activity.campaign``                 — a campaign activity logged on the cycle;
2. ``Activity.source_activity.campaign`` — a follow-up born from a campaign
   activity. This is the pre-existing-deal case: the modal sets the cycle but
   leaves ``Activity.campaign`` None.

``DecisionCycle.source_campaign`` is the THIRD edge, on the cycle itself — the
born-from branch, which needs no activity at all.

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

from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Sum

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

    This is the TOUCHED-BY branch only — both ACTIVITY edges. The cycle's own
    ``source_campaign`` is the separate born-from branch, applied by
    ``attributed_cycles``, and it carries no activity condition.
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
    those it OPENED (born-from, unconditional) plus those it has WORKED
    (touched-by, a COMPLETED + SUCCESSFUL activity).

    The two branches are ORed, and only the second carries a condition — see the
    module docstring for why the asymmetry is deliberate.

    ONE ROW PER CYCLE whichever branch matches, and whichever matches BOTH: the
    born-from side is a column comparison on the cycle itself and the touched-by
    side is a scalar ``Exists``, so neither can duplicate a row. That is what
    makes the result safe to aggregate over and safe to combine with the
    deal_products join.

    THE single declaration of the rule: the campaign LIST path
    (campaign_objective_progress), the campaign DETAIL path and the campaign
    DASHBOARD all call this, so they cannot drift — and a parity test asserts
    they agree on every objective type.
    """
    return (
        queryset
        .annotate(**{TOUCHED_BY_ALIAS: successful_campaign_activity(campaign_id)})
        .filter(
            Q(**{TOUCHED_BY_ALIAS: True})
            | Q(source_campaign_id=campaign_id)
        )
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


# Annotation alias for the first-win date. Underscored, same convention as above.
FIRST_WIN_ALIAS = '_account_first_win'


def _transition_cycles(client_id):
    """The won cycles that turned a PROSPECT into a CLIENT — one per converted
    account, before any campaign filter.

    TWO CONDITIONS, and the pair is the definition of a new logo:

    * the ACCOUNT really transitioned. ``became_client_at`` is the marker: the
      close hook stamps it once, on the first win of a PROSPECT account
      (decision_cycles/views/views.py:779-788), and never for an account imported
      as CLIENT. Winning a deal on an existing client is revenue, not a logo;
    * the CYCLE is the one that triggered it. Nothing records WHICH cycle set the
      stamp — it is a bare timestamp, with no link back — so the triggering cycle
      is derived as the account's EARLIEST win by ``outcome_date``, which is what
      "stamped on the first win" means. ``outcome_date`` is a DateField, so two
      cycles won on the SAME DAY both qualify; a campaign carrying either earns
      the logo. That tie is pinned in the tests rather than hidden.

    Cycles with no ``outcome_date`` are excluded: a win with no close date cannot
    be ordered against the others, and every real close sets it
    (decision_cycles/views/views.py:735).
    """
    won = DecisionCycle.objects.filter(
        client_id=client_id,
        outcome=CycleOutcome.WON,
        outcome_date__isnull=False,
    )
    earliest_win = (
        won.filter(account_id=OuterRef('account_id'))
        .order_by('outcome_date')
        .values('outcome_date')[:1]
    )
    return (
        won
        .filter(account__became_client_at__isnull=False)
        .annotate(**{FIRST_WIN_ALIAS: Subquery(earliest_win)})
        .filter(outcome_date=F(FIRST_WIN_ALIAS))
    )


def campaign_new_logos(campaign_id, client_id):
    """How many accounts became clients through a deal ``campaign_id`` carried.

    THE canonical campaign new-logo calculation — the list card, the detail
    serializer and the workspace dashboard all call it, exactly as they all call
    ``campaign_money``.

    It replaces an MVP proxy that counted ``CampaignAccount(status=COMPLETED,
    account__type='CLIENT')``: every account the campaign finished working that
    is CURRENTLY typed client, consulting no decision cycle at all. An account
    imported as a client and enrolled in the campaign was a "new logo" under it.

    Counted per ACCOUNT, once. ``Count(distinct=True)`` over the transition
    cycles is what collapses an account won twice on the same day, and
    ``attributed_cycles`` keeps its own two branches flat, so neither several
    wins nor several successful activities can inflate a logo into two.

    No period filter: campaign metrics are all-time by rule.
    """
    return attributed_cycles(
        _transition_cycles(client_id), campaign_id,
    ).aggregate(
        logos=Count('account', distinct=True)
    )['logos']
