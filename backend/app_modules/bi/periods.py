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


def current_fiscal_year_period(client_id) -> Optional[Period]:
    """Return the tenant's current fiscal-year window, or None if the tenant is
    unknown. One query."""
    from end_users.models import ClientAccount

    ca = ClientAccount.objects.filter(id=client_id).first()
    if ca is None:
        return None
    start, end = ca.get_fiscal_year_dates()
    return Period(start=start, end=end)
