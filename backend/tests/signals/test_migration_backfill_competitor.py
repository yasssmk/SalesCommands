# backend/tests/signals/test_migration_backfill_competitor.py
"""
Data-migration test for the is_competitor -> CompetitorSignal backfill
(Competitors sprint, sub-step 3; re-tooled in sub-step 8b).

There is no pre-existing migration-test harness in this project and
`django_test_migrations` is not installed, so this test drives Django's own
MigrationExecutor.

Sub-step 8b dropped the `is_competitor` COLUMN (migration 0033). The backfill
migration 0031 reads `TechStackSignal.objects.filter(is_competitor=True)` —
real SQL that needs the column to physically exist. So this test rolls the
module_signals schema back to 0032 (the state right before the drop, where the
column is still present), exercises 0031 against controlled data, then rolls
forward to HEAD (0033, column dropped) so the rest of the suite runs on the
final schema.

  * The DB schema is moved with MigrationExecutor.migrate (needs transaction=True
    so real DDL runs outside the test's atomic wrapper).
  * TechStackSignal source rows are created via the HISTORICAL model
    (apps.get_model at 0031, which still carries is_competitor) — NOT the
    current model, which no longer declares the field.
  * The migration's forwards()/reverse() are exercised against the historical
    model state, so the CompetitorSignal seen by the migration has NO custom
    save() -- proving the migration derives competitor_name_normalized itself.

Covers the frozen mapping + exclusions + reverse + idempotence.
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
    '0031_backfill_competitor_from_techstack'
)

# The state right before the is_competitor drop — the column still exists here.
BEFORE_DROP = ('module_signals', '0032_alter_signalclusterarchival_signal_type')

# Historical state to read the migration's model shapes from. At 0031 the
# TechStackSignal model still carries is_competitor and CompetitorSignal has no
# custom save().
HIST_STATE = ('module_signals', '0031_backfill_competitor_from_techstack')


def _head_target():
    """The current leaf migration of module_signals — the real HEAD, computed
    dynamically so later schema drops don't leave this test restoring to a
    stale node (which would corrupt the shared test DB for later tests)."""
    loader = MigrationExecutor(connection).loader
    leaves = [n for n in loader.graph.leaf_nodes() if n[0] == 'module_signals']
    return leaves[0]


def _hist_apps():
    return MigrationExecutor(connection).loader.project_state(HIST_STATE).apps


def _migration():
    return importlib.import_module(MIGRATION_MODULE)


@pytest.fixture
def before_drop_schema():
    """Roll module_signals DDL back to 0032 (is_competitor present) for the
    duration of the test, then restore the true HEAD so the shared test DB is
    left exactly as the rest of the suite expects."""
    head = _head_target()
    MigrationExecutor(connection).migrate([BEFORE_DROP])
    try:
        yield
    finally:
        MigrationExecutor(connection).migrate([head])


def _make_tech(hist, account, user_a, *, tech_name, is_competitor,
               source_activity=None, decision_cycle=None,
               source_quote=None, status=SignalStatus.PENDING):
    """Create a TechStackSignal row via the HISTORICAL model (0031 state, which
    still declares is_competitor). The historical model has no save(), so
    tech_name_normalized is set explicitly (the backfill does not read it) and
    source=LLM_EXTRACTED so an arbitrary status (incl. REJECTED) is preserved."""
    TechStackSignal = hist.get_model('module_signals', 'TechStackSignal')
    normalized = ' '.join((tech_name or '').lower().split())
    return TechStackSignal.objects.create(
        account_id=account.id,
        client_id=account.client_id,
        source_activity_id=source_activity.id if source_activity else None,
        decision_cycle_id=decision_cycle.id if decision_cycle else None,
        tech_name=tech_name,
        tech_name_normalized=normalized,
        is_competitor=is_competitor,
        source_quote=source_quote,
        source=SignalSource.LLM_EXTRACTED,
        status=status,
        confidence=0.9,
        is_inferred=False,
        created_by_id=user_a.id,
        updated_by_id=user_a.id,
    )


@pytest.fixture
def seeded(before_drop_schema, account, activity, decision_cycle, user_a):
    """Seed the five source cases described in the sub-step brief, via the
    historical model at the rolled-back (0032) schema."""
    hist = _hist_apps()
    a = _make_tech(
        hist, account, user_a, tech_name='Intercom', is_competitor=True,
        source_activity=activity, decision_cycle=decision_cycle,
        source_quote='we are also evaluating Intercom instead of you',
        status=SignalStatus.PENDING,
    )
    b = _make_tech(
        hist, account, user_a, tech_name='Zendesk', is_competitor=True,
        source_activity=activity, source_quote=None,
        status=SignalStatus.REJECTED,
    )
    c = _make_tech(
        hist, account, user_a, tech_name='', is_competitor=True,
        source_activity=activity, source_quote='some quote',
    )
    d = _make_tech(
        hist, account, user_a, tech_name='Okta', is_competitor=True,
        source_activity=None, source_quote='weighing Okta rather than you',
    )
    e = _make_tech(
        hist, account, user_a, tech_name='Salesforce', is_competitor=False,
        source_activity=activity, source_quote='we run on Salesforce',
    )
    return {'a': a, 'b': b, 'c': c, 'd': d, 'e': e,
            'account': account, 'activity': activity,
            'decision_cycle': decision_cycle}


class TestBackfillForwards:

    def test_forwards_creates_mirror_competitors(self, seeded):
        hist = _hist_apps()
        Competitor = hist.get_model('module_signals', 'CompetitorSignal')

        # BEFORE: no competitor rows exist.
        assert Competitor.objects.count() == 0

        _migration().forwards(hist, None)

        # AFTER: a, b, d migrated; c excluded (blank name); e excluded (not competitor).
        assert Competitor.objects.count() == 3

        acct = seeded['account']
        # (a) full mapping
        ca = Competitor.objects.get(competitor_name='Intercom')
        assert ca.competitor_name_normalized == 'intercom'
        assert ca.summary == 'Competitor: Intercom'
        assert ca.status == SignalStatus.PENDING
        assert ca.decision_cycle_id == seeded['decision_cycle'].id
        assert ca.source_activity_id == seeded['activity'].id
        assert ca.account_id == acct.id
        assert str(ca.client_id) == str(acct.client_id)
        assert ca.source_quote == 'we are also evaluating Intercom instead of you'
        assert ca.metadata['backfilled_from'] == 'techstack_is_competitor'
        assert ca.canonical_key is None
        # campaign copied from source_activity.
        assert ca.campaign_id == seeded['activity'].campaign_id

        # (b) REJECTED status preserved, source_quote NULL tolerated
        cb = Competitor.objects.get(competitor_name='Zendesk')
        assert cb.status == SignalStatus.REJECTED
        assert cb.source_quote is None

        # (d) source_activity NULL -> campaign NULL
        cd = Competitor.objects.get(competitor_name='Okta')
        assert cd.source_activity_id is None
        assert cd.campaign_id is None
        assert cd.competitor_name_normalized == 'okta'

        # (c) blank name and (e) non-competitor never produced a row.
        assert not Competitor.objects.filter(competitor_name='').exists()
        assert not Competitor.objects.filter(competitor_name='Salesforce').exists()

    def test_reverse_deletes_only_backfilled(self, seeded):
        hist = _hist_apps()
        Competitor = hist.get_model('module_signals', 'CompetitorSignal')

        _migration().forwards(hist, None)
        assert Competitor.objects.count() == 3

        _migration().reverse(hist, None)
        assert Competitor.objects.count() == 0

    def test_forwards_is_idempotent(self, seeded):
        hist = _hist_apps()
        Competitor = hist.get_model('module_signals', 'CompetitorSignal')

        _migration().forwards(hist, None)
        assert Competitor.objects.count() == 3

        # Second pass must create no duplicates.
        _migration().forwards(hist, None)
        assert Competitor.objects.count() == 3
