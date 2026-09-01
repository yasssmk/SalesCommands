# backend/tests/signals/test_migration_backfill_constraint_departments.py
"""
Data-migration test for the ConstraintSignal.target_department (FK) ->
target_departments (M2M) backfill (M2M scope sprint, sub-step 1a).

Mirrors the harness of test_migration_backfill_competitor.py: there is no
`django_test_migrations` in this project, so the test drives Django's own
MigrationExecutor and exercises the migration's module-level forwards()/
reverse() against a historical apps state.

Schema layout of this sub-step:
  * 0036_constraintsignal_target_departments -- AddField M2M (link table
    created; the legacy FK target_department stays in place, drop is 1d).
  * 0037_backfill_constraint_target_departments -- RunPython copying each
    row's single target_department FK into the new M2M as its first entry.

The test rolls the module_signals schema back to 0036 (M2M table present,
backfill NOT yet applied), seeds ConstraintSignal rows via the HISTORICAL
model (which has both target_department and target_departments), exercises
0037.forwards(), asserts each row with a target_department gets exactly that
one department in the M2M, and a row WITHOUT a department gets an empty M2M.
Then rolls forward to the true HEAD so the rest of the suite runs on the
final schema.

  * The DB schema is moved with MigrationExecutor.migrate (transaction=True
    so real DDL runs outside the test's atomic wrapper).
  * ConstraintSignal + StandardDepartment source rows are created via the
    HISTORICAL models (apps.get_model at 0037), NOT the current models.
  * Covers the copy + the no-department case + reverse + idempotence.
"""

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from app_modules.signals.constants import SignalSource, SignalStatus


# Real DDL (schema rollback) must run outside an atomic wrapper.
pytestmark = pytest.mark.django_db(transaction=True)


MIGRATION_MODULE = (
    'app_modules.signals.migrations.'
    '0037_backfill_constraint_target_departments'
)

# State right before the backfill runs: the M2M link table exists (created by
# 0036) but no row has been copied yet.
BEFORE_BACKFILL = ('module_signals', '0036_constraintsignal_target_departments')

# Historical state to read the migration's model shapes from. At 0037 the
# ConstraintSignal model carries BOTH target_department (FK) and
# target_departments (M2M).
HIST_STATE = ('module_signals', '0037_backfill_constraint_target_departments')


def _head_target():
    """The current leaf migration of module_signals — computed dynamically so
    later nodes don't leave this test restoring to a stale node (which would
    corrupt the shared test DB for later tests)."""
    loader = MigrationExecutor(connection).loader
    leaves = [n for n in loader.graph.leaf_nodes() if n[0] == 'module_signals']
    return leaves[0]


def _hist_apps():
    return MigrationExecutor(connection).loader.project_state(HIST_STATE).apps


def _migration():
    return importlib.import_module(MIGRATION_MODULE)


@pytest.fixture
def before_backfill_schema():
    """Roll module_signals DDL back to 0036 (M2M present, backfill not run) for
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


def _make_constraint(hist, account, user_a, *, summary, target_department=None,
                     source_activity=None, status=SignalStatus.PENDING):
    """Create a ConstraintSignal row via the HISTORICAL model (0037 state). The
    historical model has no save(), so canonical_key is set to None explicitly
    and source=LLM_EXTRACTED so an arbitrary status is preserved."""
    ConstraintSignal = hist.get_model('module_signals', 'ConstraintSignal')
    return ConstraintSignal.objects.create(
        account_id=account.id,
        client_id=account.client_id,
        source_activity_id=source_activity.id if source_activity else None,
        summary=summary,
        nature='TECHNICAL',
        rigidity='FIRM',
        canonical_key=None,
        target_department_id=target_department.id if target_department else None,
        source_quote='some quote',
        source=SignalSource.LLM_EXTRACTED,
        status=status,
        confidence=0.9,
        is_inferred=False,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )


@pytest.fixture
def seeded(before_backfill_schema, account, activity, user_a):
    """Seed three ConstraintSignal rows via the historical model at the
    rolled-back (0036) schema: two with a target_department, one without."""
    hist = _hist_apps()
    finance = _dept(hist, 'Finance')
    it = _dept(hist, 'IT')
    a = _make_constraint(
        hist, account, user_a, summary='Budget owned by Finance',
        target_department=finance, source_activity=activity,
    )
    b = _make_constraint(
        hist, account, user_a, summary='IT owns the SAP integration',
        target_department=it, source_activity=activity,
        status=SignalStatus.REJECTED,
    )
    c = _make_constraint(
        hist, account, user_a, summary='Company-wide encryption requirement',
        target_department=None, source_activity=activity,
    )
    return {'a': a, 'b': b, 'c': c,
            'finance': finance, 'it': it, 'account': account}


class TestBackfillForwards:

    def test_forwards_copies_fk_into_m2m(self, seeded):
        hist = _hist_apps()
        Constraint = hist.get_model('module_signals', 'ConstraintSignal')

        # BEFORE: no row has any M2M entry yet.
        for s in Constraint.objects.all():
            assert list(s.target_departments.all()) == []

        _migration().forwards(hist, None)

        # AFTER: (a) and (b) each carry exactly their old department; (c) empty.
        ca = Constraint.objects.get(pk=seeded['a'].pk)
        assert [d.id for d in ca.target_departments.all()] == [seeded['finance'].id]

        cb = Constraint.objects.get(pk=seeded['b'].pk)
        assert [d.id for d in cb.target_departments.all()] == [seeded['it'].id]
        # the legacy FK is untouched by this sub-step
        assert cb.target_department_id == seeded['it'].id

        cc = Constraint.objects.get(pk=seeded['c'].pk)
        assert list(cc.target_departments.all()) == []

    def test_reverse_empties_only_backfilled(self, seeded):
        hist = _hist_apps()
        Constraint = hist.get_model('module_signals', 'ConstraintSignal')

        _migration().forwards(hist, None)
        assert Constraint.objects.get(pk=seeded['a'].pk).target_departments.count() == 1

        _migration().reverse(hist, None)
        for s in Constraint.objects.all():
            assert list(s.target_departments.all()) == []
        # the legacy FK survives the reverse (only the M2M is cleared)
        assert Constraint.objects.get(pk=seeded['a'].pk).target_department_id == seeded['finance'].id

    def test_forwards_is_idempotent(self, seeded):
        hist = _hist_apps()
        Constraint = hist.get_model('module_signals', 'ConstraintSignal')

        _migration().forwards(hist, None)
        _migration().forwards(hist, None)

        ca = Constraint.objects.get(pk=seeded['a'].pk)
        assert [d.id for d in ca.target_departments.all()] == [seeded['finance'].id]
