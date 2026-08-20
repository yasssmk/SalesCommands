# backend/tests/quotas/test_leads_metric_removed.py
"""
LEADS is gone from the canonical metric vocabulary — proved, not assumed.

PO decision: the LEADS metric is dead. It counted "decision cycles carrying at
least one MEETING_SCHEDULED activity", which is neither a decision-cycle count
nor a meeting count but a third thing nobody set an objective on.

A deletion is the one change a test suite cannot catch by running the code that
is left — nothing fails when a dead branch is merely orphaned. So this module
asserts the ABSENCE at each layer it could survive in: the enum a Quota's
``metric`` column validates against, the key -> formula binding, the module's
public surface, and the per-metric wiring the quota progress service dispatches
on. A half-removal — key gone but formula left, or the reverse — fails here.

NOT IN SCOPE, and deliberately left standing: ``bi/definitions/leads.py``
declares ``leads_dc_created`` and ``leads_activities_created``, two BI DASHBOARD
KPIs in the separate ``bi.registry`` namespace, served over /bi/kpi/<key>/.
They share a word with the deleted metric and nothing else — different registry,
different keys, not an objective or campaign metric. Their coverage lives in
tests/bi/test_kpi_leads.py.

DB: not needed — this is a vocabulary assertion, no query.
"""

import pytest

from app_modules.bi import metrics
from app_modules.bi.metrics import METRIC_FUNCTIONS, MetricKey
from app_modules.quotas.models import Quota
from app_modules.quotas.services import progress as P


class TestLeadsIsAbsentEverywhere:

    def test_the_enum_no_longer_offers_it(self):
        assert not hasattr(MetricKey, 'LEADS')
        assert 'LEADS' not in MetricKey.values
        assert 'LEADS' not in dict(MetricKey.choices)

    def test_the_quota_column_no_longer_validates_it(self):
        """``Quota.metric`` takes its choices straight from the enum, so the
        field and the vocabulary cannot drift — asserted through the field, not
        by re-listing the values."""
        field = Quota._meta.get_field('metric')
        assert 'LEADS' not in [value for value, _label in field.choices]

    def test_no_formula_is_bound_to_it(self):
        assert not any(str(key) == 'LEADS' for key in METRIC_FUNCTIONS)

    def test_the_metrics_module_exposes_no_leads_function(self):
        """The formula itself is gone, not merely unreferenced."""
        assert not hasattr(metrics, 'leads')
        assert 'leads' not in metrics.__all__

    def test_the_quota_dispatch_has_no_entry_for_it(self):
        assert not any(str(key) == 'LEADS' for key in P._SPEC)

    def test_every_remaining_key_is_fully_wired(self):
        """The other half of a clean deletion: nothing ELSE went missing with
        it. Every surviving key still has a formula and a dispatch entry."""
        for key in MetricKey:
            assert key in METRIC_FUNCTIONS, key
            assert key in P._SPEC, key
        assert set(MetricKey.values) == {
            'DECISION_CYCLES', 'MEETINGS', 'NEW_LOGOS',
            'PIPELINE_VALUE', 'REVENUE_WON',
        }


class TestAStoredUnknownMetricDoesNotCrashTheRead:
    """A quota row stored under a metric the vocabulary no longer knows.

    ``Quota.metric`` is a plain CharField — ``choices`` is validated on write,
    never enforced by the database — so a row written before the deletion
    survives it. The progress service dispatches on that stored string
    (``_SPEC[metric]``), which would raise KeyError and take down the whole
    objectives list, not just the dead row.

    It now reports 0 — and therefore 0% of its target — so one dead row cannot
    hide every live objective on the page. Nothing is deleted here: what to do
    with such a row is the PO's call, and this keeps it visible instead of
    fatal."""

    @pytest.mark.django_db
    def test_it_reports_zero_instead_of_raising(self, client_account_a):
        from datetime import date, timedelta
        from decimal import Decimal

        from end_users.models import User, UserRole

        role = UserRole.objects.create(
            client_account=client_account_a, name='Ind', is_individual=True,
            read=True, write=True, modify=True, can_delete=True,
        )
        owner = User.objects.create(email='stale@a.test',
                                    client_account=client_account_a,
                                    role=role, is_active=True)
        today = date.today()
        quota = Quota(owner=owner, metric=MetricKey.DECISION_CYCLES,
                      target_value=Decimal('10'),
                      period_start=today - timedelta(days=15),
                      period_end=today + timedelta(days=15))
        quota.save(user=owner, client_id=client_account_a.id)
        # bypass validation the way a pre-deletion row reaches us: straight
        # through the column.
        Quota.objects.filter(pk=quota.pk).update(metric='LEADS')
        quota.refresh_from_db()

        result = P.compute_progress(quota)

        assert result.current_value == 0
        assert result.ratio == 0.0          # 0 of a live target, not undefined
        assert result.target_value == 10.0  # the row is intact, only unmeasurable
