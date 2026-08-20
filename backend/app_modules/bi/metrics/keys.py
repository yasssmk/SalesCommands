# app_modules/bi/metrics/keys.py
"""
Canonical metric vocabulary — the SINGLE source of truth for the six metric
identifiers, shared by every consumer (BI KPIs, sales quotas/objectives,
campaign objectives).

``MetricKey`` is a Django ``TextChoices`` so a model field can use it directly
(``choices=MetricKey.choices``) without re-declaring a parallel list. Each key
maps 1:1 to the pure formula of the same concept in ``sales_metrics`` via
``METRIC_FUNCTIONS`` — the calculation binding a later sub-step will use.

There were six. LEADS was removed (PO): it counted decision cycles carrying at
least one MEETING_SCHEDULED activity — neither a cycle count nor a meeting
count, but a third population nobody set an objective on. Its absence is
asserted in tests/quotas/test_leads_metric_removed.py, at every layer it could
have survived in. Unrelated namesake, deliberately untouched:
``bi/definitions/leads.py`` declares two BI DASHBOARD KPIs
(``leads_dc_created``, ``leads_activities_created``) in the separate
``bi.registry`` namespace.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from . import sales_metrics


class MetricKey(models.TextChoices):
    """The five canonical Sales metrics. Values are stable identifiers."""

    DECISION_CYCLES = 'DECISION_CYCLES', _('Decision cycles')
    MEETINGS = 'MEETINGS', _('Meetings')
    NEW_LOGOS = 'NEW_LOGOS', _('New logos')
    PIPELINE_VALUE = 'PIPELINE_VALUE', _('Pipeline value')
    REVENUE_WON = 'REVENUE_WON', _('Won value')      # TD-127 — display label; key unchanged


# key -> the pure formula that computes it (see sales_metrics for signatures).
# Kept beside the enum so the vocabulary and the calculation never drift apart.
METRIC_FUNCTIONS = {
    MetricKey.DECISION_CYCLES: sales_metrics.decision_cycles,
    MetricKey.MEETINGS: sales_metrics.meetings,
    MetricKey.NEW_LOGOS: sales_metrics.new_logos,
    MetricKey.PIPELINE_VALUE: sales_metrics.pipeline_value,
    MetricKey.REVENUE_WON: sales_metrics.revenue_won,
}
