# app_modules/bi/periods.py
"""
Period helpers for the BI layer.

Resolves the default period window (the tenant's fiscal year) from the
ClientAccount fiscal config. Used by compute_fn KPIs that default to the
current fiscal year when the caller passes period=None.
"""

from __future__ import annotations

from typing import Optional

from .types import Period


def current_fiscal_year_period(client_id, *, cache=None) -> Optional[Period]:
    """Return the tenant's current fiscal-year window, or None if the tenant is
    unknown. One query.

    ``cache`` is an optional request-scoped dict {client_id: Period|None}. The
    batch endpoint passes one so N specs of the SAME tenant fetch the
    ClientAccount fiscal config ONCE instead of once per spec (the memoisation is
    pure — same value, fewer queries). Absent cache = compute fresh (the detail
    endpoint's single call).
    """
    if cache is not None and client_id in cache:
        return cache[client_id]

    from end_users.models import ClientAccount

    ca = ClientAccount.objects.filter(id=client_id).first()
    period = None if ca is None else Period(*ca.get_fiscal_year_dates())
    if cache is not None:
        cache[client_id] = period
    return period
