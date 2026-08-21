# app_modules/bi/metrics/sales_metrics.py
"""
Canonical Sales metric formulas — ONE source of truth per metric.

These are PURE functions: no cache, no HTTP, no ``request``, no scope
resolution. Each takes a ``base_queryset`` that the CALLER has already bounded
to the tenant and to the caller's role scope (mine/team/client); the function
only NARROWS it further (owner / period / source_campaign). It never widens or
bypasses the scope the caller applied.

Common signature:

    def <metric>(base_queryset, *, user=None, period=None, source_campaign=None)

- base_queryset : the starting queryset (DecisionCycle, Activity or
  CompanyAccount depending on the metric), already tenant+scope bounded.
- user          : filter to the rows that BELONG to that user when provided
  (None = no user filter). "Belong" is not one rule for all five: it is declared
  once in ``attribution_scope`` — owner OR created_by OR account owner for the
  metrics that measure a DEAL (PIPELINE_VALUE, REVENUE_WON, NEW_LOGOS), and
  ``created_by`` alone for the metrics that count an ACT (DECISION_CYCLES,
  MEETINGS). See that module for both rules and their consequences.
- period        : a ``(date_start, date_end)`` couple filtered on the metric's
  OWN anchor date (see each function). None = no time bound. Either bound may be
  None to make the window half-open.
- source_campaign : filter by campaign of origin when provided.

Returns a scalar: ``int`` for counts, ``float`` for monetary sums (float to
match the existing campaign-objective service, the living parity reference).

Design rules honoured here (mirror of the S7c patterns in
decision_cycles/services/derivation_sql.py and campaigns/views/campaign_views.py):
- Every to-many traversal (NEW_LOGOS via the campaign pivot, PIPELINE_VALUE via
  the deal lines) uses an ISOLATED correlated sub-query (Exists / Subquery),
  never a Count/Sum over a deep join that fan-outs and double-counts.
- Nullable FK traversals are written in positive form; the join itself drops the
  null rows (documented at each call site).
- Outcome sets are imported from where the business already declares them
  (``SUCCESSFUL_OUTCOMES``), never re-listed as literals here.

RECONCILIATION NOTE (PO decision): where the current BI and the campaign
objectives diverge (the campaign service computes WITHOUT a date filter), the
canonical definition is the DATED one. Callers that want the campaign's
undated numbers simply pass ``period=None``.
"""

from __future__ import annotations

from django.db.models import OuterRef, Subquery, Sum

from app_modules.activities.constants import ActivityStatus
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.services.close_date_sql import (
    CLOSE_DATE_ALIAS,
    annotate_effective_close_date,
)
from app_modules.decision_cycles.services.deal_value_sql import (
    DEAL_VALUE_ALIAS,
    annotate_deal_value,
)

from .attribution_scope import account_scope_q, creator_scope_q, cycle_scope_q


# ---------------------------------------------------------------------------
# Small internal helpers (no side effects, no DB access here)
# ---------------------------------------------------------------------------

def _between(queryset, field, period, *, is_datetime=False):
    """Filter ``queryset`` to ``period = (start, end)`` on ``field``.

    ``None`` period is a no-op. A ``None`` bound makes the window half-open.
    A DateTimeField anchor (``created_at``, ``completed_at``,
    ``became_client_at``) MUST pass ``is_datetime=True``: the bounds are then
    compared at DATE granularity (``__date``) so an ``end`` bound includes the
    whole day. Without it, ``<= end`` compares against MIDNIGHT and silently
    drops everything recorded later on the closing day — a real bug that shipped
    on NEW_LOGOS. DateField anchors (outcome_date, expected_close_date) compare
    directly and must NOT pass it.
    """
    if period is None:
        return queryset
    start, end = period
    lookup = f'{field}__date' if is_datetime else field
    if start is not None:
        queryset = queryset.filter(**{f'{lookup}__gte': start})
    if end is not None:
        queryset = queryset.filter(**{f'{lookup}__lte': end})
    return queryset


def _amount(value):
    """Normalise a nullable Sum() result to a float amount (0.0 when None).

    float mirrors the campaign-objective service (the living parity reference),
    which returns ``float(result['total'] or 0)``.
    """
    return float(value or 0)


# ---------------------------------------------------------------------------
# The five canonical metrics
# ---------------------------------------------------------------------------

def decision_cycles(base_queryset, *, user=None, period=None, source_campaign=None):
    """DECISION_CYCLES — count of decision cycles a rep OPENED.

    Anchor: the DC creation date (``created_at``), compared at DATE granularity.
    Campaign attribution: ``source_campaign`` on the DC.
    Owner: ``attribution_scope.creator_scope_q`` — ``created_by``, the person
    who opened the deal.

    It scoped on ``owner`` before, which reads a different question: who runs
    the deal NOW. The two diverge exactly where this metric matters — an SDR
    opens a deal and hands it to an AE, and under the old rule the SDR had
    opened nothing while the AE had opened a deal they had not yet touched.
    Ownership is what the VALUE metrics are attributed by (a wider union, see
    attribution_scope); opening is an act, and an act belongs to whoever
    performed it.

    Deliberately NOT the three-branch union: this counts deals opened, and
    exactly one person opens a deal. Widening it would make one deal a
    "cycle opened" for three people.

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    qs = base_queryset
    if user is not None:
        qs = qs.filter(creator_scope_q(user))
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = _between(qs, 'created_at', period, is_datetime=True)
    return qs.count()


def meetings(base_queryset, *, user=None, period=None, source_campaign=None):
    """MEETINGS — count of meetings actually HELD and gone well.

    Population: ``status=COMPLETED`` AND ``outcome in SUCCESSFUL_OUTCOMES``.
    Anchor: ``completed_at`` — when the meeting was marked done.
    Owner: ``created_by`` — the person who logged it (attribution_scope).
    Campaign attribution: via the activity's cycle of origin
    (``decision_step -> cycle -> source_campaign``), unchanged.

    THREE RULES CHANGED HERE, all in the same direction — from "a meeting was
    planned somewhere on a deal" to "this person held a meeting and it worked":

    * the POPULATION was ``outcome=MEETING_SCHEDULED`` minus CANCELLED, which
      counted an intention. A row planned for next month, or completed with a
      NO_ANSWER, was a meeting. Now completion is required and the outcome must
      be one the business calls a success — the SAME set the campaign
      progression uses to close a contact, ``SUCCESSFUL_OUTCOMES``, not a second
      opinion about what "successful" means. Pairing it with ``status`` matters:
      ``Activity.outcome`` is only meaningful once completed, so a PLANNED row
      carrying a stray outcome must not count. CANCELLED needs no explicit
      exclusion any more — it is not COMPLETED.
    * the OWNER was ``decision_step -> cycle -> owner``, which answered a
      different question ("who owns the deal this meeting hangs off") and, being
      a positive traversal of a NULLABLE FK, silently dropped every meeting
      logged without a decision step — most of them. An SDR's meetings landed in
      the AE's number, or in nobody's.
    * the ANCHOR was ``scheduled_date``, the date the meeting was booked FOR.
      A meeting booked in March and held in April counted in March. It now
      anchors on ``completed_at``, a DateTimeField, so the window is compared at
      DATE granularity (``is_datetime=True``) exactly as ``created_at`` is.

    ``completed_at`` is an accepted PROXY for the moment the outcome became
    successful (PO): nothing records that transition on its own, and the two
    coincide in the normal flow — a rep completes the activity and sets its
    outcome in the same action. A row completed first and re-qualified as
    successful days later is anchored on the completion, not the re-qualification.

    No traversal here fans out: the campaign path is to-ONE, and the population
    filters are on the row itself, so counting activities counts rows.

    ``base_queryset`` is a (tenant+scope bounded) Activity queryset.
    """
    # Deferred import: campaigns imports bi.metrics, so this cannot be top-level
    # (same reason as the CampaignAccount import in new_logos below).
    from app_modules.campaigns.services.campaign_execution_service import (
        SUCCESSFUL_OUTCOMES,
    )

    qs = base_queryset.filter(
        status=ActivityStatus.COMPLETED,
        outcome__in=SUCCESSFUL_OUTCOMES,
    )
    if user is not None:
        qs = qs.filter(creator_scope_q(user))
    if source_campaign is not None:
        # positive form; drops activities without a cycle of origin.
        qs = qs.filter(decision_step__cycle__source_campaign=source_campaign)
    qs = _between(qs, 'completed_at', period, is_datetime=True)
    return qs.count()


def new_logos(base_queryset, *, user=None, period=None, source_campaign=None):
    """NEW_LOGOS — count of accounts that became a client.

    Anchor: ``became_client_at`` on the account. Having a non-null
    ``became_client_at`` IS the definition of "became a client": an account
    imported as CLIENT (null timestamp) is never a new logo, so it is excluded
    regardless of the period.
    Owner: ``attribution_scope.account_scope_q`` — the account's own owner or
    creator, OR anyone attached to the WON cycle that made it a client. The
    account-only rule that preceded it credited the logo to the account manager
    and to nobody else, while the deal metrics beside it credited the whole
    union; the logo now follows the same rule as the deal that produced it.
    Campaign attribution: the account was worked in the campaign (isolated
    EXISTS on the CampaignAccount pivot).

    ``became_client_at`` is set by the system on the first won decision cycle
    (see the close hook). This function only READS it.

    ``base_queryset`` is a (tenant+scope bounded) CompanyAccount queryset.
    """
    qs = base_queryset.filter(became_client_at__isnull=False)
    if user is not None:
        qs = qs.filter(account_scope_q(user))
    if source_campaign is not None:
        # deferred import to avoid a module-load cycle through campaigns.
        from app_modules.campaigns.models.campaign_account import CampaignAccount
        worked_in_campaign = CampaignAccount.objects.filter(
            account=OuterRef('pk'), campaign=source_campaign
        )
        qs = qs.filter(pk__in=Subquery(worked_in_campaign.values('account')))
    # Anchor on became_client_at. It is a DateTimeField, so the window is
    # compared at DATE granularity (``is_datetime=True``) exactly as ``created_at``
    # and ``completed_at`` are: a bare ``<= end`` compares against MIDNIGHT on the
    # closing day and silently drops every account converted later that day.
    qs = _between(qs, 'became_client_at', period, is_datetime=True)
    return qs.count()


def pipeline_value(base_queryset, *, user=None, period=None, source_campaign=None):
    """PIPELINE_VALUE — Σ deal value of OPEN decision cycles (outcome empty).

    Anchor: the cycle's EFFECTIVE CLOSE DATE —
    ``decision_cycles/services/close_date_sql.py``, where the rule is declared
    once: the manual ``expected_close_date`` when the rep set one, else the date
    of the CLOSING step's last activity, else NULL. This metric states no date
    rule of its own; it consumes that one, exactly as it consumes
    ``annotate_deal_value`` for the money.

    It previously anchored on ``Max(steps.expected_end)``, which is NULL on
    every freshly created cycle — step auto-creation sets ``expected_end=None``
    on all five steps — so a normally used deal fell out of every windowed read
    and a personal pipeline objective showed 0.

    Campaign attribution: ``source_campaign`` on the DC.
    Owner: ``attribution_scope.cycle_scope_q`` — owner OR created_by OR the
    account's owner, one row per cycle (all three links are to-ONE).
    Amount: the DERIVED product roll-up — ``total_deal_value``, summed through
    the ``annotate_deal_value`` SQL annotation (TD-75). The manual
    ``estimated_value`` field is no longer read here: no runtime path ever
    populated it, which is why this metric was stuck at 0.

    Pipeline is EXCLUSIVE: only ``outcome IS NULL`` counts, so a WON or LOST
    cycle has left the pipeline (ON_HOLD too — it carries an outcome).

    Every to-many traversal stays isolated: the close date is a correlated
    Subquery over the closing step's activities and the amount is a correlated
    per-cycle Subquery over ``deal_products``, so neither fans out over the
    other (a ``.annotate(Max('steps__...'))`` join would). A cycle with NO
    effective close date has a NULL anchor and therefore falls OUTSIDE any given
    period window — now meaning "nobody stated when this closes", which the rep
    can fix by setting the date; with ``period=None`` every open cycle is summed,
    which is how the CAMPAIGN paths call it (they are deliberately unwindowed,
    so this anchor never affects a campaign number).

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    qs = base_queryset.filter(outcome__isnull=True)
    if user is not None:
        qs = qs.filter(cycle_scope_q(user))
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = annotate_effective_close_date(qs)
    qs = _between(qs, CLOSE_DATE_ALIAS, period)
    return _amount(
        annotate_deal_value(qs).aggregate(total=Sum(DEAL_VALUE_ALIAS))['total']
    )


def revenue_won(base_queryset, *, user=None, period=None, source_campaign=None):
    """REVENUE_WON — Σ deal value of WON decision cycles.

    Anchor: ``outcome_date`` — the single close date of a decision cycle, set on
    every close (views/views.py:735) and cleared on reopen (:839). It carries no
    won-specific meaning on its own, which is why the WON population is selected
    by STATUS first (``outcome=WON``) and only then windowed: a lost or on-hold
    cycle has an ``outcome_date`` too, and never reaches this filter.
    Consequences of that pairing, both intended: a cycle won and then REOPENED
    leaves this metric (it is no longer WON, and its date is cleared), and a
    cycle re-won later carries the newer close date. Every closed cycle has
    carried the field since migration 0009, so historic wins are visible in a
    window — there is no dark period.
    Campaign attribution: ``source_campaign`` on the DC.
    Owner: ``attribution_scope.cycle_scope_q`` — the same union as
    PIPELINE_VALUE, so a deal does not change hands when it is won.
    Amount: the DERIVED product roll-up (see PIPELINE_VALUE — TD-75).

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    qs = base_queryset.filter(outcome=CycleOutcome.WON)
    if user is not None:
        qs = qs.filter(cycle_scope_q(user))
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = _between(qs, 'outcome_date', period)
    return _amount(
        annotate_deal_value(qs).aggregate(total=Sum(DEAL_VALUE_ALIAS))['total']
    )
