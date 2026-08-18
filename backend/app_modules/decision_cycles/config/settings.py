# app_modules/decision_cycles/config/settings.py
"""
Centralized decision-cycles module configuration.

Single source of truth for the DC list's default ordering, orderable fields and
search fields — the DecisionCycleViewSet reads these, nothing is hard-coded in
the view. Mirrors the campaigns module CONFIG singleton
(app_modules/campaigns/config/settings.py).

Usage:
    from app_modules.decision_cycles.config import CONFIG

    ordering = CONFIG.filters.default_dc_ordering
"""

from dataclasses import dataclass, field
from typing import List

from ..services.deal_value_sql import DEAL_VALUE_ALIAS
from ..services.derivation_sql import (
    CURRENT_STEP_STAGE_ALIAS,
    CYCLE_STATUS_ALIAS,
)


@dataclass(frozen=True)
class FilterConfig:
    """List filtering / ordering / search configuration for decision cycles."""

    # Default list order: the single displayed cycle per account first, then
    # most-recently-updated. Both are FLAT model fields, so no branch of the
    # queryset needs an annotation for the default order (only the `list`
    # action, which carries the cycle-state annotations, exposes the annotated
    # ordering fields below).
    default_dc_ordering: List[str] = field(
        default_factory=lambda: ['-is_active', '-updated_at']
    )

    # The eight orderable columns. Flat fields and FK traversals order directly;
    # stage and status order on the 1b cycle-state annotations, and Amount on
    # the deal-value annotation — all three present on the list queryset.
    # Amount orders on the DERIVED roll-up, not on estimated_value: that manual
    # field is never populated, so sorting by it sorted nothing (TD-75). Clients send these exact terms (DRF OrderingFilter passes
    # the term straight to order_by — it does not alias).
    dc_ordering_fields: List[str] = field(
        default_factory=lambda: [
            'name',
            'account__company_name',
            CURRENT_STEP_STAGE_ALIAS,    # current-step stage (annotation)
            CYCLE_STATUS_ALIAS,          # effective status (annotation)
            DEAL_VALUE_ALIAS,            # Amount column — the product roll-up
            'owner__first_name',         # owner (name)
            'owner__team__name',         # team name
            'updated_at',
        ]
    )

    # Search fields — cycle name + account + owner + team only. `description`
    # is intentionally NOT searchable.
    dc_search_fields: List[str] = field(
        default_factory=lambda: [
            'name',
            'account__company_name',
            'owner__first_name',
            'owner__last_name',
            'owner__team__name',
        ]
    )


@dataclass(frozen=True)
class DecisionCycleModuleConfig:
    """Decision-cycles module configuration singleton."""

    filters: FilterConfig = field(default_factory=FilterConfig)


CONFIG = DecisionCycleModuleConfig()
