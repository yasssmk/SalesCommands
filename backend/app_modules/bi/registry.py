# app_modules/bi/registry.py
"""
Declarative KPI registry.

A KPI is DECLARED, not coded: you build a `KPIDefinition` (source queryset +
DB-level aggregation + scope + period + optional decoupled target + output
shape + cache wiring) and `register()` it. The compute layer (palier 1c)
reads these definitions and runs them; there is NO per-KPI compute code.

This module is pure Python (no DB access at import time) so the registry can
be introspected and unit-tested without a database. `aggregation` and
`source` hold Django objects but are never evaluated here — they are opaque
to the registry and only used by the compute layer.

Design notes:
- `target` is DECOUPLED from `aggregation` (a separate optional resolver).
  A sales_plan / milestone V2 can later point at a KPI `key` and read its
  value without any change here — the target is not baked into the metric.
- `cache_tags` / `invalidation_sources` declare the cache wiring; the cache
  (1d) and invalidation (1e) paliers consume them. Declaring them now keeps
  the definition the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import OutputShape

# The role scopes a KPI may be computed under (see permissions.scope_filter).
VALID_SCOPES = frozenset({'mine', 'team', 'client'})


@dataclass(frozen=True)
class KPIDefinition:
    """Declarative definition of one KPI.

    Fields:
        key:      stable unique identifier (e.g. 'dc_pipeline_value').
        label:    human-readable name.
        source:   zero-arg callable returning the BASE queryset (before tenant,
                  scope and period filtering — the compute layer applies those).
        aggregation: a Django DB-level aggregation expression (e.g.
                  Count('id'), Sum('estimated_value')). Opaque here; evaluated
                  by the compute layer via .aggregate()/.annotate(). NEVER a
                  Python-side loop.
        scope_module: OWNERSHIP_MAP key passed to
                  permissions.scope_filter.apply_role_scope (reuses the exact
                  same mine/team/client + C6 logic as the viewsets).
        period_field: the model date field used to filter/bucket by period.
        output_shape: SCALAR | BREAKDOWN | TIMESERIES.
        allowed_scopes: which scopes this KPI may be requested under.
        dimension: group-by field name; REQUIRED for BREAKDOWN, ignored
                  otherwise.
        default_period: default period window when the caller doesn't specify
                  one ('fiscal_year' by default — resolved against the tenant's
                  fiscal config by the compute layer).
        target:   OPTIONAL, DECOUPLED target resolver. None = no target. When
                  present, a callable the compute layer invokes to obtain the
                  target value for a given (auth context, period). Kept
                  separate from `aggregation` so V2 plans/milestones can attach
                  targets without touching the metric.
        cache_tags: tag namespaces this KPI's cached value is keyed under.
        invalidation_sources: model labels (e.g. 'module_activities.Activity')
                  whose writes must bust this KPI's cache.
    """

    key: str
    label: str
    scope_module: str
    # Standard-pipeline fields (required UNLESS compute_fn is set — see below).
    source: Optional[Callable[[], Any]] = None
    aggregation: Any = None
    period_field: Optional[str] = None
    output_shape: Optional[OutputShape] = None
    allowed_scopes: Tuple[str, ...] = ('mine', 'team', 'client')
    dimension: Optional[str] = None
    default_period: str = 'fiscal_year'
    target: Optional[Callable[..., Any]] = None
    cache_tags: Tuple[str, ...] = ()
    invalidation_sources: Tuple[str, ...] = ()
    # Escape hatch for KPIs that are NOT a single aggregate over a scoped
    # queryset (ratios, parameterized/per-entity metrics — e.g. coverage %,
    # quota attainment). When set, compute.run() delegates to it instead of the
    # standard pipeline: compute_fn(definition, auth_ctx, scope, period, params)
    # -> KPIResult. It is a CALCULATION escape hatch, NOT a security one: it
    # MUST still scope via permissions.scope_filter.apply_role_scope and MUST
    # be query-bounded (no N+1).
    compute_fn: Optional[Callable[..., Any]] = None
    # Optional resolver mapping the raw breakdown keys (FK ids, ALREADY
    # scope-filtered by apply_role_scope) of a BREAKDOWN result to
    # human-readable labels, in ONE query. Used by owner-dimensioned KPIs so
    # the API can return names (e.g. {user_id: 'First Last'}) without the
    # client resolving N ids — and without ever widening the query beyond the
    # ids present in the (already scoped) breakdown.
    # Signature: dimension_labels(ids: list) -> dict[id, str]. None = no labels.
    dimension_labels: Optional[Callable[..., Any]] = None

    def __post_init__(self):
        if not self.key:
            raise ValueError("KPIDefinition.key must be a non-empty string")
        if not self.label:
            raise ValueError(f"KPIDefinition '{self.key}': label must be non-empty")
        if not self.scope_module:
            raise ValueError(f"KPIDefinition '{self.key}': scope_module must be non-empty")

        if self.compute_fn is not None:
            if not callable(self.compute_fn):
                raise TypeError(
                    f"KPIDefinition '{self.key}': compute_fn must be callable or None"
                )
        else:
            # Standard-pipeline requirements (only when there is no custom compute).
            if not callable(self.source):
                raise TypeError(f"KPIDefinition '{self.key}': source must be callable")
            if self.aggregation is None:
                raise ValueError(f"KPIDefinition '{self.key}': aggregation is required")
            if not self.period_field:
                raise ValueError(f"KPIDefinition '{self.key}': period_field is required")
            if not isinstance(self.output_shape, OutputShape):
                raise TypeError(
                    f"KPIDefinition '{self.key}': output_shape must be an OutputShape"
                )
            if self.output_shape is OutputShape.BREAKDOWN and not self.dimension:
                raise ValueError(
                    f"KPIDefinition '{self.key}': BREAKDOWN output requires a "
                    f"`dimension` (group-by field)"
                )

        if not self.allowed_scopes:
            raise ValueError(
                f"KPIDefinition '{self.key}': allowed_scopes must not be empty"
            )
        invalid = set(self.allowed_scopes) - VALID_SCOPES
        if invalid:
            raise ValueError(
                f"KPIDefinition '{self.key}': invalid allowed_scopes "
                f"{sorted(invalid)} (valid: {sorted(VALID_SCOPES)})"
            )
        if self.target is not None and not callable(self.target):
            raise TypeError(
                f"KPIDefinition '{self.key}': target must be callable or None"
            )
        if self.dimension_labels is not None and not callable(self.dimension_labels):
            raise TypeError(
                f"KPIDefinition '{self.key}': dimension_labels must be callable or None"
            )


# =============================================================================
# Registry — module-level, introspectable
# =============================================================================

_REGISTRY: Dict[str, KPIDefinition] = {}


def register(definition: KPIDefinition) -> KPIDefinition:
    """Register a KPI. Raises on a duplicate key. Returns the definition so it
    can be used as an expression."""
    if not isinstance(definition, KPIDefinition):
        raise TypeError("register() expects a KPIDefinition")
    if definition.key in _REGISTRY:
        raise ValueError(f"KPI '{definition.key}' is already registered")
    _REGISTRY[definition.key] = definition
    return definition


def get(key: str) -> KPIDefinition:
    """Return the definition for `key`. Raises KeyError if unknown."""
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(f"No KPI registered under '{key}'")


def all_kpis() -> List[KPIDefinition]:
    """Return all registered definitions (list, order of registration)."""
    return list(_REGISTRY.values())


def keys() -> List[str]:
    """Return all registered KPI keys."""
    return list(_REGISTRY.keys())


def is_registered(key: str) -> bool:
    return key in _REGISTRY


def clear() -> None:
    """Empty the registry. Test helper — not for production use."""
    _REGISTRY.clear()
