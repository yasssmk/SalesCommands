# app_modules/signals/migrations/0006_refactor_objective_signal_wave_b.py
"""
Wave B — Refactor ObjectiveSignal.

Same architectural pattern as the StandardDepartment retirement: the
original migration relied on a manual DROP TABLE pre-step in production
("table was empty — 0 rows, validated by product"). The state-only
SeparateDatabaseAndState that followed only removed the model from the
migration state, not from the database.

That design works for incremental production upgrades but breaks fresh-
database replays (CI / new dev environments / pytest with --create-db):
0001_initial creates `module_signals_objective`, this migration removes
it from state only, and the next migration (0007_objectivesignal) tries
to CREATE TABLE on top of the still-present physical table and crashes
with `relation "module_signals_objective" already exists`.

Resolution (Sprint chore PR #7, chore/fix-pre-existing-migration-drifts):

  * Replace SeparateDatabaseAndState(database_operations=[]) with a
    plain DeleteModel('ObjectiveSignal'). The default DeleteModel
    performs BOTH state and database deletion — i.e. DROP TABLE
    module_signals_objective is now issued by this migration itself.

  * Behavior on production databases (this migration already applied):
    Django never replays applied migrations, so the change is invisible.
    The historical manual DROP + state-only delete leaves the same end
    state as the new full DeleteModel would have produced.

  * Behavior on fresh databases: the migration drops the table itself,
    and 0007_objectivesignal recreates it cleanly. No --no-migrations
    flag required for tests.

The next migration (0007_objectivesignal) emits a clean CreateModel for
the Wave B schema as originally intended.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module_signals', '0005_signalclusterarchival'),
    ]

    operations = [
        # Full DeleteModel — drops the table from state AND from the DB.
        # See module docstring: the original state-only SeparateDatabaseAndState
        # assumed a manual DROP TABLE pre-step in production, which is not
        # available on fresh databases.
        migrations.DeleteModel(name='ObjectiveSignal'),
    ]
