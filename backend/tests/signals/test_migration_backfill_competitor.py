# backend/tests/signals/test_migration_backfill_competitor.py
"""
Data-migration test for the is_competitor -> CompetitorSignal backfill
(Competitors sprint, sub-step 3).

There is no pre-existing migration-test harness in this project and
`django_test_migrations` is not installed, so this test drives Django's
own MigrationExecutor:

  * Prerequisite rows (account / activity / decision_cycle) are created via
    the real fixtures.
  * TechStackSignal source rows are created via the real model.
  * The migration's forwards()/reverse() functions are exercised against the
    HISTORICAL model state (executor.loader.project_state(...).apps), so the
    CompetitorSignal seen by the migration has NO custom save() -- proving
    the migration derives competitor_name_normalized itself rather than
    leaning on the concrete model (the whole reason a data migration must
    use apps.get_model).

Covers the frozen mapping + exclusions + reverse + idempotence.
"""

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


MIGRATION_MODULE = (
    'app_modules.signals.migrations.'
    '0031_backfill_competitor_from_techstack'
)

# Historical state to read the migration's model shapes from. The backfill is
# a pure data migration (no schema op) so the model shapes at 0030 == at 0031;
# 0030 already exists, and its CompetitorSignal carries no custom save().
HIST_STATE = ('module_signals', '0030_competitorsignal')


def _hist_apps():
    executor = MigrationExecutor(connection)
    return executor.loader.project_state(HIST_STATE).apps


def _migration():
    return importlib.import_module(MIGRATION_MODULE)


def _make_tech(account, user_a, *, tech_name, is_competitor,
               source_activity=None, decision_cycle=None,
               source_quote=None, status=SignalStatus.PENDING):
    """Create a TechStackSignal row via the real model (save() derives the
    normalised key). source=LLM_EXTRACTED so an arbitrary status (incl.
    REJECTED) is preserved at create (MANUAL would force VALIDATED)."""
    ts = TechStackSignal(
        account=account,
        source_activity=source_activity,
        decision_cycle=decision_cycle,
        tech_name=tech_name,
        is_competitor=is_competitor,
        source_quote=source_quote,
        source=SignalSource.LLM_EXTRACTED,
        status=status,
        confidence=0.9,
        is_inferred=False,
    )
    ts.save(user=user_a, client_id=account.client_id)
    return ts


@pytest.fixture
def seeded(account, activity, decision_cycle, user_a):
    """Seed the five source cases described in the sub-step brief."""
    a = _make_tech(
        account, user_a, tech_name='Intercom', is_competitor=True,
        source_activity=activity, decision_cycle=decision_cycle,
        source_quote='we are also evaluating Intercom instead of you',
        status=SignalStatus.PENDING,
    )
    b = _make_tech(
        account, user_a, tech_name='Zendesk', is_competitor=True,
        source_activity=activity, source_quote=None,
        status=SignalStatus.REJECTED,
    )
    c = _make_tech(
        account, user_a, tech_name='', is_competitor=True,
        source_activity=activity, source_quote='some quote',
    )
    d = _make_tech(
        account, user_a, tech_name='Okta', is_competitor=True,
        source_activity=None, source_quote='weighing Okta rather than you',
    )
    e = _make_tech(
        account, user_a, tech_name='Salesforce', is_competitor=False,
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
