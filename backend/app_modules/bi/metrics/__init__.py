# app_modules/bi/metrics/__init__.py
"""
Canonical Sales metric definitions.

ONE pure formula per metric, the single source of calculation that the three
consumers (BI KPIs, sales quotas, campaign objectives) will call in later
sub-steps. This sub-step delivers the formulas and their parity guard ONLY — it
wires NO consumer.

See ``sales_metrics`` for the shared signature and the per-metric anchors.
"""

from .sales_metrics import (
    decision_cycles,
    leads,
    meetings,
    new_logos,
    pipeline_value,
    revenue_won,
)

__all__ = [
    'decision_cycles',
    'leads',
    'meetings',
    'new_logos',
    'pipeline_value',
    'revenue_won',
]
