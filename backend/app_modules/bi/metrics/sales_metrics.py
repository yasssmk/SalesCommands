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
- user          : filter by owner when provided (None = no owner filter).
- period        : a ``(date_start, date_end)`` couple filtered on the metric's
  OWN anchor date (see each function). None = no time bound. Either bound may be
  None to make the window half-open.
- source_campaign : filter by campaign of origin when provided.

Returns a scalar: ``int`` for counts, ``float`` for monetary sums (float to
match the existing campaign-objective service, the living parity reference).

Design rules honoured here (mirror of the S7c patterns in
decision_cycles/services/derivation_sql.py and campaigns/views/campaign_views.py):
- Every to-many traversal (LEADS via activities, PIPELINE_VALUE via steps) uses
  an ISOLATED correlated sub-query (Exists / Subquery), never a Count/Sum over a
  deep join that fan-outs and double-counts.
- Nullable FK traversals are written in positive form; the join itself drops the
  null rows (documented at each call site).
- CANCELLED activities are excluded from activity-based counts, consistent with
  the existing status derivation.
- ``ActivityOutcome.MEETING_SCHEDULED`` is imported, never hardcoded as a literal.

RECONCILIATION NOTE (PO decision): where the current BI and the campaign
objectives diverge (the campaign service computes WITHOUT a date filter), the
canonical definition is the DATED one. Callers that want the campaign's
undated numbers simply pass ``period=None``.
"""

from __future__ import annotations

from django.db.models import OuterRef, Subquery, Sum

from app_modules.activities.constants import ActivityOutcome, ActivityStatus
from app_modules.activities.models import Activity
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.services.close_date_sql import (
    CLOSE_DATE_ALIAS,
    annotate_effective_close_date,
)
from app_modules.decision_cycles.services.deal_value_sql import (
    DEAL_VALUE_ALIAS,
    annotate_deal_value,
)


# ---------------------------------------------------------------------------
# Small internal helpers (no side effects, no DB access here)
# ---------------------------------------------------------------------------

def _between(queryset, field, period, *, is_datetime=False):
    """Filter ``queryset`` to ``period = (start, end)`` on ``field``.

    ``None`` period is a no-op. A ``None`` bound makes the window half-open.
    For a DateTimeField anchor (``created_at``) the bounds are compared at DATE
    granularity (``__date``) so an ``end`` bound includes the whole day — a
    plain ``<= end`` would drop everything on ``end`` after 00:00. DateField
    anchors (scheduled_date, outcome_date, the steps' expected_end) compare
    directly.
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
# The six canonical metrics
# ---------------------------------------------------------------------------

def decision_cycles(base_queryset, *, user=None, period=None, source_campaign=None):
    """DECISION_CYCLES — count of decision cycles.

    Anchor: the DC creation date (``created_at``).
    Campaign attribution: ``source_campaign`` on the DC.
    Owner: the DC ``owner``.

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    qs = base_queryset
    if user is not None:
        qs = qs.filter(owner=user)
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = _between(qs, 'created_at', period, is_datetime=True)
    return qs.count()


def leads(base_queryset, *, user=None, period=None, source_campaign=None):
    """LEADS — count of decision cycles that have at least one activity whose
    outcome is MEETING_SCHEDULED.

    Anchor: the DC creation date (``created_at``).
    Campaign attribution: ``source_campaign`` on the DC.
    Owner: the DC ``owner``.

    The "has a scheduled-meeting activity" test is an ISOLATED correlated
    EXISTS on Activity (not a join+count), so a DC with several such activities
    is still counted once — no fan-out. CANCELLED activities are excluded.

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    has_meeting = (
        Activity.objects
        .filter(
            decision_cycle=OuterRef('pk'),
            outcome=ActivityOutcome.MEETING_SCHEDULED,
        )
        .exclude(status=ActivityStatus.CANCELLED)
    )
    qs = base_queryset.filter(pk__in=Subquery(has_meeting.values('decision_cycle')))
    if user is not None:
        qs = qs.filter(owner=user)
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = _between(qs, 'created_at', period, is_datetime=True)
    return qs.count()


def meetings(base_queryset, *, user=None, period=None, source_campaign=None):
    """MEETINGS — count of activities whose outcome is MEETING_SCHEDULED.

    Anchor: the activity date (``scheduled_date``).
    Campaign attribution: via the activity's decision cycle
    (``decision_step -> cycle -> source_campaign``).
    Owner: the owner of the activity's cycle
    (``decision_step -> cycle -> owner``).

    CANCELLED activities are excluded. The owner / campaign filters traverse the
    nullable ``decision_step`` FK in positive form: an activity with no
    decision_step has no cycle owner/campaign, so the inner join drops it — the
    intended semantics (it cannot be attributed to a cycle owner or a campaign
    of origin). The step->cycle->owner/campaign path is entirely to-ONE, so
    counting activities does not fan out.

    ``base_queryset`` is a (tenant+scope bounded) Activity queryset.
    """
    qs = (
        base_queryset
        .filter(outcome=ActivityOutcome.MEETING_SCHEDULED)
        .exclude(status=ActivityStatus.CANCELLED)
    )
    if user is not None:
        # positive form; drops activities whose decision_step (nullable) is null.
        qs = qs.filter(decision_step__cycle__owner=user)
    if source_campaign is not None:
        # positive form; drops activities without a cycle of origin.
        qs = qs.filter(decision_step__cycle__source_campaign=source_campaign)
    qs = _between(qs, 'scheduled_date', period)
    return qs.count()


def new_logos(base_queryset, *, user=None, period=None, source_campaign=None):
    """NEW_LOGOS — count of accounts that became a client.

    Anchor: ``became_client_at`` on the account. Having a non-null
    ``became_client_at`` IS the definition of "became a client": an account
    imported as CLIENT (null timestamp) is never a new logo, so it is excluded
    regardless of the period.
    Owner: the account owner (``account_owner``).
    Campaign attribution: the account was worked in the campaign (isolated
    EXISTS on the CampaignAccount pivot).

    ``became_client_at`` is set by the system on the first won decision cycle
    (see the close hook). This function only READS it.

    ``base_queryset`` is a (tenant+scope bounded) CompanyAccount queryset.
    """
    qs = base_queryset.filter(became_client_at__isnull=False)
    if user is not None:
        qs = qs.filter(account_owner=user)
    if source_campaign is not None:
        # deferred import to avoid a module-load cycle through campaigns.
        from app_modules.campaigns.models.campaign_account import CampaignAccount
        worked_in_campaign = CampaignAccount.objects.filter(
            account=OuterRef('pk'), campaign=source_campaign
        )
        qs = qs.filter(pk__in=Subquery(worked_in_campaign.values('account')))
    # Anchor on became_client_at (sub-step 3 field).
    qs = _between(qs, 'became_client_at', period)
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
    Owner: the DC ``owner``.
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
        qs = qs.filter(owner=user)
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
    Owner: the DC ``owner``.
    Amount: the DERIVED product roll-up (see PIPELINE_VALUE — TD-75).

    ``base_queryset`` is a (tenant+scope bounded) DecisionCycle queryset.
    """
    qs = base_queryset.filter(outcome=CycleOutcome.WON)
    if user is not None:
        qs = qs.filter(owner=user)
    if source_campaign is not None:
        qs = qs.filter(source_campaign=source_campaign)
    qs = _between(qs, 'outcome_date', period)
    return _amount(
        annotate_deal_value(qs).aggregate(total=Sum(DEAL_VALUE_ALIAS))['total']
    )
