# backend/tests/signals/test_migration_backfill_pain_impact_departments.py
"""
Data-migration test for the PainSignal / ImpactSignal target_department (FK)
-> target_departments (M2M) backfills (M2M scope sprint, sub-step 2a).

Mirrors the Constraint harness (test_migration_backfill_constraint_departments.py):
drives Django's MigrationExecutor and exercises the migration's module-level
backfill functions against a historical apps state.

Schema layout of this sub-step:
  * 0039_pain_impact_target_departments -- AddField M2M on both models (link
    tables created; the legacy FK target_department + scope_level stay).
  * 0040_backfill_pain_impact_target_departments -- two RunPython backfills
    (backfill_pain, backfill_impact) copying each row's single FK into the M2M.

The test rolls the module_signals schema back to 0039 (M2M tables present,
backfill NOT yet applied), seeds rows via the HISTORICAL models (which carry
both target_department and target_departments), exercises each backfill, and
asserts each row with a target_department gets exactly that one department in
the M2M, and a row WITHOUT a department gets an empty M2M. Then rolls forward
to the true HEAD so the rest of the suite runs on the final schema.
"""

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
    ImpactType,
)


# Real DDL (schema rollback) must run outside an atomic wrapper.
pytestmark = pytest.mark.django_db(transaction=True)


MIGRATION_MODULE = (
    'app_modules.signals.migrations.'
    '0040_backfill_pain_impact_target_departments'
)

# State right before the backfill runs: the M2M link tables exist (created by
# 0039) but no row has been copied yet.
BEFORE_BACKFILL = ('module_signals', '0039_pain_impact_target_departments')

# Historical state to read the migration's model shapes from. At 0040 both
# models carry BOTH target_department (FK) and target_departments (M2M).
HIST_STATE = ('module_signals', '0040_backfill_pain_impact_target_departments')


def _head_target():
    loader = MigrationExecutor(connection).loader
    leaves = [n for n in loader.graph.leaf_nodes() if n[0] == 'module_signals']
    return leaves[0]


def _hist_apps():
    return MigrationExecutor(connection).loader.project_state(HIST_STATE).apps


def _migration():
    return importlib.import_module(MIGRATION_MODULE)


@pytest.fixture
def before_backfill_schema():
    """Roll module_signals DDL back to 0039 (M2M present, backfill not run) for
    the duration of the test, then restore the true HEAD so the shared test DB
    is left exactly as the rest of the suite expects."""
    head = _head_target()
    MigrationExecutor(connection).migrate([BEFORE_BACKFILL])
    try:
        yield
    finally:
        MigrationExecutor(connection).migrate([head])


def _dept(hist, name):
    StandardDepartment = hist.get_model('core_modules', 'StandardDepartment')
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _make_pain(hist, account, user_a, *, summary, target_department=None,
               source_activity=None):
    PainSignal = hist.get_model('module_signals', 'PainSignal')
    return PainSignal.objects.create(
        account_id=account.id,
        client_id=account.client_id,
        source_activity_id=source_activity.id if source_activity else None,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.BUSINESS,
        summary=summary,
        canonical_key=None,
        target_department_id=target_department.id if target_department else None,
        source_quote='some quote',
        source=SignalSource.LLM_EXTRACTED,
        status=SignalStatus.PENDING,
        confidence=0.9,
        is_inferred=False,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )


def _make_impact(hist, account, user_a, *, summary, target_department=None,
                 source_activity=None):
    ImpactSignal = hist.get_model('module_signals', 'ImpactSignal')
    return ImpactSignal.objects.create(
        account_id=account.id,
        client_id=account.client_id,
        source_activity_id=source_activity.id if source_activity else None,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.BUSINESS,
        impact_type=ImpactType.FINANCIAL,
        summary=summary,
        canonical_key=None,
        target_department_id=target_department.id if target_department else None,
        source_quote='some quote',
        source=SignalSource.LLM_EXTRACTED,
        status=SignalStatus.PENDING,
        confidence=0.9,
        is_inferred=False,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )


class TestPainBackfill:

    @pytest.fixture
    def seeded(self, before_backfill_schema, account, activity, user_a):
        hist = _hist_apps()
        fin, it = _dept(hist, 'Finance'), _dept(hist, 'IT')
        a = _make_pain(hist, account, user_a, summary='Finance pain',
                       target_department=fin, source_activity=activity)
        b = _make_pain(hist, account, user_a, summary='IT pain',
                       target_department=it, source_activity=activity)
        c = _make_pain(hist, account, user_a, summary='Company-wide pain',
                       target_department=None, source_activity=activity)
        return {'a': a, 'b': b, 'c': c, 'fin': fin, 'it': it}

    def test_forwards_copies_fk_into_m2m(self, seeded):
        hist = _hist_apps()
        Pain = hist.get_model('module_signals', 'PainSignal')
        for s in Pain.objects.all():
            assert list(s.target_departments.all()) == []

        _migration().backfill_pain(hist, None)

        assert [d.id for d in Pain.objects.get(pk=seeded['a'].pk).target_departments.all()] == [seeded['fin'].id]
        assert [d.id for d in Pain.objects.get(pk=seeded['b'].pk).target_departments.all()] == [seeded['it'].id]
        assert list(Pain.objects.get(pk=seeded['c'].pk).target_departments.all()) == []
        # legacy FK untouched
        assert Pain.objects.get(pk=seeded['a'].pk).target_department_id == seeded['fin'].id

    def test_reverse_empties(self, seeded):
        hist = _hist_apps()
        Pain = hist.get_model('module_signals', 'PainSignal')
        _migration().backfill_pain(hist, None)
        assert Pain.objects.get(pk=seeded['a'].pk).target_departments.count() == 1
        _migration().reverse_pain(hist, None)
        for s in Pain.objects.all():
            assert list(s.target_departments.all()) == []

    def test_forwards_idempotent(self, seeded):
        hist = _hist_apps()
        Pain = hist.get_model('module_signals', 'PainSignal')
        _migration().backfill_pain(hist, None)
        _migration().backfill_pain(hist, None)
        assert [d.id for d in Pain.objects.get(pk=seeded['a'].pk).target_departments.all()] == [seeded['fin'].id]


class TestImpactBackfill:

    @pytest.fixture
    def seeded(self, before_backfill_schema, account, activity, user_a):
        hist = _hist_apps()
        fin, it = _dept(hist, 'Finance'), _dept(hist, 'IT')
        a = _make_impact(hist, account, user_a, summary='Finance impact',
                         target_department=fin, source_activity=activity)
        b = _make_impact(hist, account, user_a, summary='IT impact',
                         target_department=it, source_activity=activity)
        c = _make_impact(hist, account, user_a, summary='Company-wide impact',
                         target_department=None, source_activity=activity)
        return {'a': a, 'b': b, 'c': c, 'fin': fin, 'it': it}

    def test_forwards_copies_fk_into_m2m(self, seeded):
        hist = _hist_apps()
        Impact = hist.get_model('module_signals', 'ImpactSignal')
        for s in Impact.objects.all():
            assert list(s.target_departments.all()) == []

        _migration().backfill_impact(hist, None)

        assert [d.id for d in Impact.objects.get(pk=seeded['a'].pk).target_departments.all()] == [seeded['fin'].id]
        assert [d.id for d in Impact.objects.get(pk=seeded['b'].pk).target_departments.all()] == [seeded['it'].id]
        assert list(Impact.objects.get(pk=seeded['c'].pk).target_departments.all()) == []
        assert Impact.objects.get(pk=seeded['a'].pk).target_department_id == seeded['fin'].id

    def test_reverse_empties(self, seeded):
        hist = _hist_apps()
        Impact = hist.get_model('module_signals', 'ImpactSignal')
        _migration().backfill_impact(hist, None)
        assert Impact.objects.get(pk=seeded['a'].pk).target_departments.count() == 1
        _migration().reverse_impact(hist, None)
        for s in Impact.objects.all():
            assert list(s.target_departments.all()) == []

    def test_forwards_idempotent(self, seeded):
        hist = _hist_apps()
        Impact = hist.get_model('module_signals', 'ImpactSignal')
        _migration().backfill_impact(hist, None)
        _migration().backfill_impact(hist, None)
        assert [d.id for d in Impact.objects.get(pk=seeded['a'].pk).target_departments.all()] == [seeded['fin'].id]
