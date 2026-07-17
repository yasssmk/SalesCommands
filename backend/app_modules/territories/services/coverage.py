# backend/app_modules/territories/services/coverage.py
"""
The SHARED coverage core for a territory.

`compute_territory_coverage_counts` is the ONE place that turns a territory +
period into (numerator, denominator). Both consumers call it so they can never
drift apart:
  - the per-territory KPI (bi.definitions.territory._territory_coverage), used
    live on the rep Home;
  - the manager aggregate snapshot refresh (territories.services.snapshot),
    which materialises these counts onto the Territory row.

Same discipline as CAMPAIGN_DONE_Q / build_todo_population: extract the shared
predicate so two call sites can't encode two different definitions of the same
thing.
"""

from app_modules.accounts.models import CompanyAccount
from app_modules.accounts.services.filter_service import AccountFilterService


def compute_territory_coverage_counts(territory, client_id, period):
    """
    Return (numerator, denominator) for a territory over a period.

    - denominator: accounts in the territory — its dynamic ``filter_definition``
      evaluated ONCE, tenant-scoped so isolation holds regardless of the filter.
    - numerator: of those, how many were touched with a response (an Activity
      carrying an outcome) within the period window.

    EXACTLY two queries (the two COUNTs): ``apply_filters`` returns a lazy
    queryset and its FK filters are ``Exists`` subqueries, so there is no
    per-account N+1. ``period`` is a ``Period`` (or None for all-time); its
    ``start``/``end`` bounds are applied only when set.
    """
    base = CompanyAccount.objects.filter(client_id=client_id)
    accounts = AccountFilterService.apply_filters(
        base, territory.filter_definition or {},
        client_id=client_id, user=territory.owner,
    )
    denominator = accounts.count()

    touched = accounts.filter(activities__outcome__isnull=False)
    if period and period.start is not None:
        touched = touched.filter(activities__scheduled_date__gte=period.start)
    if period and period.end is not None:
        touched = touched.filter(activities__scheduled_date__lte=period.end)
    numerator = touched.distinct().count()

    return numerator, denominator
