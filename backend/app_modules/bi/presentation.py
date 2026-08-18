# app_modules/bi/presentation.py
"""
API-facing helpers for the BI endpoint.

Keeps the view thin: scope authorization (the KPI scope becomes a USER INPUT
at the API boundary, so it must be bounded by the caller's role), period
parsing, and KPIResult -> envelope serialization (including id->name label
enrichment for owner-dimensioned breakdowns).

Nothing here computes a KPI; it wraps registry + compute/cache.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from permissions.checks import check_permission

from .periods import current_fiscal_year_period
from .types import OutputShape, Period

logger = logging.getLogger(__name__)

# Scope authorization ---------------------------------------------------------
# mine ⊂ team ⊂ client. A requested scope is allowed only if it does not exceed
# the maximum scope the caller's role grants for the KPI's scope_module (the
# same registry used by the viewsets — single source of truth for role->scope).
_SCOPE_RANK = {'mine': 1, 'team': 2, 'client': 3}

# Query params reserved by the endpoint itself; everything else is forwarded to
# the KPI as compute_fn params (e.g. cycle_id, campaign_id, territory_id).
RESERVED_QUERY_PARAMS = frozenset({'scope', 'period', 'period_start', 'period_end'})

DEFAULT_SCOPE = 'mine'


def resolve_max_scope(request, scope_module: str) -> Optional[str]:
    """Maximum READ scope the caller's role grants on ``scope_module``.

    Returns 'client' | 'team' | 'mine', or None when the role has no read
    access to that module at all.
    """
    return check_permission(request, scope_module, 'read')


def scope_within(requested: str, max_scope: Optional[str]) -> bool:
    """True if ``requested`` does not exceed ``max_scope`` (mine ⊂ team ⊂ client)."""
    if max_scope is None or max_scope == 'none':
        return False
    return _SCOPE_RANK.get(requested, 99) <= _SCOPE_RANK.get(max_scope, 0)


# Period parsing --------------------------------------------------------------
def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD), got {value!r}")


def resolve_period(
    period_name: Optional[str],
    period_start: Optional[str],
    period_end: Optional[str],
    definition,
    client_id,
    fiscal_cache=None,
) -> Optional[Period]:
    """Translate the ``period`` request parameter into a ``Period`` or None.

    - absent / 'default' -> the KPI's default_period ('fiscal_year' -> the
      tenant's current fiscal-year window; anything else -> None).
    - 'fiscal_year'      -> the tenant's current fiscal-year window.
    - 'all' / 'none'     -> None (no period filter).
    - 'custom'           -> Period(period_start, period_end), both ISO dates.

    Raises ValueError on an unknown name or malformed custom dates.
    """
    name = (period_name or 'default').lower()

    if name in ('all', 'none'):
        return None

    if name == 'custom':
        if not period_start or not period_end:
            raise ValueError("custom period requires period_start and period_end")
        start = _parse_iso_date(period_start, 'period_start')
        end = _parse_iso_date(period_end, 'period_end')
        if start > end:
            raise ValueError("period_start must be on or before period_end")
        return Period(start=start, end=end)

    if name == 'fiscal_year' or (name == 'default' and definition.default_period == 'fiscal_year'):
        return current_fiscal_year_period(client_id, cache=fiscal_cache)

    if name == 'default':
        # KPI default_period is not a fiscal window -> no period filter; the
        # compute layer (or the compute_fn) applies its own natural default.
        return None

    raise ValueError(f"unknown period '{period_name}'")


# Serialization ---------------------------------------------------------------
def serialize_result(result, definition, client_id=None) -> dict:
    """KPIResult -> plain dict for the {success, data} envelope.

    BREAKDOWN keys are FK ids; JSON object keys must be strings, so they are
    stringified. When the KPI declares a `dimension_labels` resolver, the raw
    (already scope-filtered) ids are resolved to names in ONE query and placed
    under meta['labels'] — value keeps its {id: number} shape.

    A MONETARY KPI (``definition.unit == 'currency'``) also carries `currency`:
    the tenant's single currency, resolved from `client_id` (core.currency). The
    amount itself is untouched — no conversion happens anywhere — this only says
    what unit it is in. Non-monetary KPIs get `currency: None`.
    """
    value = result.value
    meta = dict(result.meta or {})
    shape = result.shape

    if shape is OutputShape.BREAKDOWN and isinstance(value, dict):
        raw_keys = list(value.keys())
        value = {str(k): v for k, v in value.items()}
        if definition.dimension_labels and raw_keys:
            try:
                labels = definition.dimension_labels(raw_keys)
                meta['labels'] = {str(k): v for k, v in (labels or {}).items()}
            except Exception:  # labels are best-effort — never break the metric
                logger.warning(
                    "bi_dimension_labels_failed",
                    extra={'kpi': result.key, 'event': 'bi_labels'},
                    exc_info=True,
                )

    currency = None
    if getattr(definition, 'unit', None) == 'currency':
        from core.currency import tenant_currency

        currency = tenant_currency(client_id)

    return {
        'key': result.key,
        'shape': shape.value if hasattr(shape, 'value') else shape,
        'value': value,
        'currency': currency,
        'scope': result.scope,
        'period_start': result.period_start,
        'period_end': result.period_end,
        'target': result.target,
        'attainment': result.attainment,
        'meta': meta,
    }
