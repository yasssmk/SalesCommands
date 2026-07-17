# backend/app_modules/territories/services/snapshot.py
"""
Lazy, read-refreshed coverage snapshots for the manager territory aggregate.

Territories have no stored membership (each ``filter_definition`` is a different
dynamic WHERE), so the manager's team aggregate can't be a single GROUP BY like
campaigns. Instead we materialise each territory's coverage counts onto the row
(the columns added in migration 0003) and GROUP BY those. This module keeps that
materialisation fresh — lazily, at read time:

  - a snapshot is STALE when it was never computed, is older than the TTL, or was
    computed for a different period (a FY25 snapshot is never served in FY26);
  - a read refreshes at most ``SNAPSHOT_REFRESH_BUDGET`` stale snapshots, oldest
    first, so no single Home load pays an unbounded recompute burst;
  - refreshes are ``FOR UPDATE ... OF self SKIP LOCKED`` so concurrent readers
    split the work and never block or double-compute — a reader that hits a
    locked row skips it and reads its existing (possibly stale) snapshot.

Deliberately NOT invalidated by account/activity writes: the 2h staleness is the
whole point (it trades a little freshness for O(1)-per-window recompute cost).
The counts themselves come from compute_territory_coverage_counts — the same core
the live per-territory KPI uses, never a copy.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q

from app_modules.territories.models import Territory

from .coverage import compute_territory_coverage_counts

logger = logging.getLogger(__name__)

# Read-TTL: a snapshot older than this is refreshed on the next read.
SNAPSHOT_TTL_SECONDS = 2 * 60 * 60  # 2h

# Burst guard: the most snapshots one read will recompute. Sized so steady state
# (a handful expiring per window) never hits it; it only splits a pathological
# cold-start / fiscal-rollover mass-staleness across a few reads.
SNAPSHOT_REFRESH_BUDGET = 50

_SNAPSHOT_FIELDS = [
    'coverage_numerator', 'coverage_denominator',
    'coverage_period_key', 'coverage_computed_at',
]


def period_key_for(period):
    """A stable string identifying the period a snapshot was computed for.

    A mismatch at read time forces a recompute, so a snapshot computed for one
    fiscal year is never silently served in the next — the FY25-read-in-FY26 bug
    is impossible by construction rather than guarded against.
    """
    if period is None:
        return 'all'
    start = period.start.isoformat() if period.start else ''
    end = period.end.isoformat() if period.end else ''
    return f'{start}:{end}'


def _stale_q(period_key, threshold):
    """Never computed, older than the TTL threshold, or a different period."""
    return (
        Q(coverage_computed_at__isnull=True)
        | Q(coverage_computed_at__lt=threshold)
        | ~Q(coverage_period_key=period_key)
    )


def refresh_stale_snapshots(territories, *, client_id, period, now,
                            budget=SNAPSHOT_REFRESH_BUDGET):
    """
    Refresh up to ``budget`` stale snapshots among ``territories`` (a Territory
    queryset the CALLER has already scoped). Returns the number refreshed.

    NULL and oldest ``computed_at`` first, so the most out-of-date rows go first
    and a fresh row is never recomputed (that is what the TTL buys). Stale rows
    are locked ``FOR UPDATE OF self SKIP LOCKED`` inside a transaction: a
    concurrent reader skips a locked row and reads its existing snapshot rather
    than blocking or recomputing it twice.

    Query cost is linear and bounded: 1 locked SELECT + 2 COUNTs per refreshed
    row + 1 bulk UPDATE — no per-territory UPDATE and no per-account N+1.
    """
    period_key = period_key_for(period)
    threshold = now - timedelta(seconds=SNAPSHOT_TTL_SECONDS)

    with transaction.atomic():
        # select_related('owner') so the coverage core reads territory.owner
        # without an extra query; of=('self',) locks ONLY the territory row, not
        # the joined user.
        locked = list(
            territories
            .filter(_stale_q(period_key, threshold))
            .select_related('owner')
            .select_for_update(skip_locked=True, of=('self',))
            .order_by(F('coverage_computed_at').asc(nulls_first=True))
            [:budget]
        )

        for terr in locked:
            num, den = compute_territory_coverage_counts(terr, client_id, period)
            terr.coverage_numerator = num
            terr.coverage_denominator = den
            terr.coverage_period_key = period_key
            terr.coverage_computed_at = now

        if locked:
            Territory.objects.bulk_update(locked, _SNAPSHOT_FIELDS)

    # Budget fully consumed -> there may be more stale rows a later read will
    # pick up. Logged (never silently dropped). This can over-report in the exact
    # boundary case (exactly `budget` stale, none left) — an INFO log, not a
    # decision, and detecting the boundary precisely would cost an extra query.
    if len(locked) >= budget:
        logger.info(
            "territory snapshot refresh hit the budget cap; "
            "some snapshots may remain stale for a later read",
            extra={'client_id': client_id, 'budget': budget,
                   'refreshed': len(locked)},
        )

    return len(locked)
