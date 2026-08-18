# app_modules/bi/metrics/keys.py
"""
Canonical metric vocabulary — the SINGLE source of truth for the six metric
identifiers, shared by every consumer (BI KPIs, sales quotas/objectives,
campaign objectives).

``MetricKey`` is a Django ``TextChoices`` so a model field can use it directly
(``choices=MetricKey.choices``) without re-declaring a parallel list. Each key
maps 1:1 to the pure formula of the same concept in ``sales_metrics`` via
``METRIC_FUNCTIONS`` — the calculation binding a later sub-step will use.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import sales_metrics


class MetricKey(models.TextChoices):
    """The six canonical Sales metrics. Values are stable identifiers."""

    DECISION_CYCLES = 'DECISION_CYCLES', _('Decision cycles')
    LEADS = 'LEADS', _('Leads')
    MEETINGS = 'MEETINGS', _('Meetings')
    NEW_LOGOS = 'NEW_LOGOS', _('New logos')
    PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline value')
    REVENUE_WON = 'REVENUE_WON', _('Won value')      # TD-127 — display label; key unchanged


# key -> the pure formula that computes it (see sales_metrics for signatures).
# Kept beside the enum so the vocabulary and the calculation never drift apart.
METRIC_FUNCTIONS = {
    MetricKey.DECISION_CYCLES: sales_metrics.decision_cycles,
    MetricKey.LEADS: sales_metrics.leads,
    MetricKey.MEETINGS: sales_metrics.meetings,
    MetricKey.NEW_LOGOS: sales_metrics.new_logos,
    MetricKey.PIPELINE_VALUE: sales_metrics.pipeline_value,
    MetricKey.REVENUE_WON: sales_metrics.revenue_won,
}
