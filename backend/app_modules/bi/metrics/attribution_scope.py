# app_modules/bi/metrics/attribution_scope.py
"""
WHOSE number a metric is — declared ONCE, for the personal and team perimeters.

THE RULE (PO truth table, final)
--------------------------------
A deal belongs to a rep if ANY of three links holds:

    owner = them  OR  created_by = them  OR  account.account_owner = them

Not one field, three. The single-field rule this replaces (``owner`` alone)
made a whole role invisible: an SDR who opens a deal and hands it to an AE
owned nothing, so their pipeline read 0 while their work sat in someone else's
number. ``created_by`` is the SDR's link, ``account.account_owner`` is the
account manager's, ``owner`` is the AE's.

A CONSEQUENCE THE PO ACCEPTED EXPLICITLY: one deal can count for TWO people —
the SDR who created it and the AE who owns it — each at full value. Individual
attainments therefore do NOT partition the tenant's pipeline, and summing two
reps can exceed what the company has on the table. That is intended: an
attainment answers "did this person deliver", not "what share of the total is
theirs".

Counted ONCE per deal, though. The three links are all to-ONE foreign keys
(``owner`` and ``created_by`` are FKs on the row; ``account__account_owner``
is a FK on a FK), so the OR is evaluated on ONE joined row per cycle and no
branch can duplicate it — unlike the campaign case, where the union runs
through activities (to-many) and needs an ``Exists`` to stay flat
(campaigns/services/campaign_dc_attribution.py). A cycle matching all three
branches is still one row, so it is summed once.

THE COUNT-AN-ACT METRICS DO NOT USE THIS UNION
----------------------------------------------
MEETINGS and DECISION_CYCLES count an ACT — a meeting held, a deal opened — and
an act belongs to whoever performed it: ``created_by``, one link, no union (see
``creator_scope_q``, shared by both). The union above is for metrics that
measure a DEAL's value or outcome, where several people legitimately have a
claim on the same object.

Both used to read the wrong field. MEETINGS was credited through
``decision_step -> cycle -> owner``, which answered "who owns the deal this
meeting is attached to" and silently dropped every meeting logged without a
decision step. DECISION_CYCLES was credited to ``owner``, so an SDR who opened
ten deals and handed them to an AE had opened none, and the AE had opened ten
they had not yet touched.

THE TEAM FORM IS THE SAME RULE, WIDENED
---------------------------------------
Each ``*_for_teams`` function is its ``user`` twin with ``= user`` replaced by
``__team_id__in = <subtree>``. A manager's number is therefore the same
predicate evaluated over their whole subtree — not a second definition that
could drift from the personal one.

One consequence, arithmetic and unavoidable: a manager's total is the sum of
their members' ONLY while no deal links to two of them. A deal created by an
SDR and owned by an AE *in the same subtree* counts ONCE for the manager and
once for EACH of the two reps, so member-by-member figures add up to more than
the manager's. The dedup is the correct behaviour for a team total (the team
has one deal, not two); the double credit is the correct behaviour for two
attainments. They cannot both hold at once and the PO chose both, each where
it belongs.
"""

from __future__ import annotations

from django.db.models import Q, Subquery

from app_modules.decision_cycles.constants import CycleOutcome


# ---------------------------------------------------------------------------
# DecisionCycle-based metrics — PIPELINE_VALUE, REVENUE_WON
# ---------------------------------------------------------------------------

def cycle_scope_q(user):
    """The union, for ONE user, on a DecisionCycle queryset."""
    return (
        Q(owner=user)
        | Q(created_by=user)
        | Q(account__account_owner=user)
    )


def cycle_scope_q_for_teams(team_ids):
    """The same union widened to every user in ``team_ids``."""
    return (
        Q(owner__team_id__in=team_ids)
        | Q(created_by__team_id__in=team_ids)
        | Q(account__account_owner__team_id__in=team_ids)
    )


# ---------------------------------------------------------------------------
# The count-an-act metrics — MEETINGS (Activity) and DECISION_CYCLES (cycles)
# ---------------------------------------------------------------------------

def creator_scope_q(user):
    """Who an ACT belongs to: the person who performed it. One link, no union.

    ``created_by`` is the audit field ``ModuleBaseModel`` stamps from
    ``save(user=)``, so it is on every model here and means the same thing on
    each — which is why one pair of functions serves both metrics rather than
    two near-identical ones drifting apart.
    """
    return Q(created_by=user)


def creator_scope_q_for_teams(team_ids):
    return Q(created_by__team_id__in=team_ids)


# ---------------------------------------------------------------------------
# CompanyAccount-based metric — NEW_LOGOS
# ---------------------------------------------------------------------------

def _account_scope(direct_q, cycle_q):
    """``direct_q`` (the account's own links) OR "this account was turned into a
    client by a WON cycle that ``cycle_q`` selects".

    WHY THE CYCLE BRANCH EXISTS — the union names three ways a person is
    attached to a DEAL, and a new logo IS a deal outcome: ``became_client_at``
    is stamped on the first won cycle. Read on the account alone the union
    would lose exactly the case it was written for — the SDR who opened the
    deal on an account they neither own nor created still made the logo.

    WHY THE BASE STAYS ``CompanyAccount`` (V2 decision) — flipping the base to
    DecisionCycle would have to re-derive the population ("became a client")
    and the window (``became_client_at``) from cycles, and would silently
    change two settled rules: an account imported as CLIENT (NULL timestamp) is
    not a new logo, and an account won twice is one logo. Keeping the account
    as the row and reaching cycles through an isolated ``pk__in`` sub-query
    leaves both untouched, and keeps ONE ROW PER ACCOUNT — the sub-query is
    evaluated on its own, never joined, so an account won by several cycles
    cannot be counted twice. Same isolation idiom as the ``source_campaign``
    pivot filter right beside it in ``sales_metrics.new_logos``.
    """
    from app_modules.decision_cycles.models import DecisionCycle

    won_by_them = (
        DecisionCycle.objects
        .filter(outcome=CycleOutcome.WON)
        .filter(cycle_q)
    )
    return direct_q | Q(pk__in=Subquery(won_by_them.values('account')))


def account_scope_q(user):
    return _account_scope(
        Q(account_owner=user) | Q(created_by=user),
        cycle_scope_q(user),
    )


def account_scope_q_for_teams(team_ids):
    return _account_scope(
        Q(account_owner__team_id__in=team_ids) | Q(created_by__team_id__in=team_ids),
        cycle_scope_q_for_teams(team_ids),
    )
