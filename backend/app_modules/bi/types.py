# app_modules/bi/types.py
"""
Value types for the BI aggregation layer.

`OutputShape` describes how a KPI's value is shaped; `KPIResult` is the
container the compute layer (palier 1c) returns. This module is pure Python
— no Django, no DB — so it is cheap to import and trivial to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, NamedTuple, Optional


class Period(NamedTuple):
    """A closed date window [start, end] used to filter/bucket a KPI.

    Either bound may be None (open-ended). The compute layer resolves the
    default window (e.g. the tenant's fiscal year) when the caller passes
    period=None and the KPIDefinition declares default_period='fiscal_year'.
    """

    start: Optional[date] = None
    end: Optional[date] = None


class OutputShape(str, Enum):
    """How a KPI value is shaped.

    - SCALAR:     a single number (e.g. "$ pipeline", "count of open cycles").
    - BREAKDOWN:  a mapping dimension -> number (e.g. cycles grouped by
                  outcome). The grouping field is declared on the
                  KPIDefinition (`dimension`).
    - TIMESERIES: an ordered list of {period, value} points bucketed over the
                  period field (e.g. leads created per month).
    """

    SCALAR = 'scalar'
    BREAKDOWN = 'breakdown'
    TIMESERIES = 'timeseries'


@dataclass
class KPIResult:
    """The computed result of a single KPI, for one (tenant, scope, period).

    The compute layer (1c) fills this; the registry/types (1b) only define the
    shape. `value` is typed by `shape`:
      - SCALAR     -> a number (int | Decimal | float)
      - BREAKDOWN  -> dict[str, number]
      - TIMESERIES -> list[dict] (e.g. [{'period': '2026-01', 'value': 12}, ...])

    `target` / `attainment` are populated only when the KPIDefinition declares
    a (decoupled) target and the compute layer resolves it — otherwise None.
    `meta` is an open bag for compute-time context (cache hit, generated_at
    stamped by the caller, applied scope, etc.).
    """

    key: str
    shape: OutputShape
    value: Any
    scope: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    target: Optional[Any] = None
    attainment: Optional[float] = None
    meta: dict = field(default_factory=dict)
