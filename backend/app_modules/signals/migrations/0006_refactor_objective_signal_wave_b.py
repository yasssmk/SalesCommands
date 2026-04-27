# app_modules/signals/migrations/0006_refactor_objective_signal_wave_b.py
"""
Wave B — Refactor ObjectiveSignal.

DESTRUCTIVE MIGRATION. The physical table module_signals_objective was
manually dropped prior to applying this migration (table was empty —
0 rows, validated by product).

What this migration does:
  1. Tell Django's ORM state that the legacy ObjectiveSignal no longer
     exists (DeleteModel via SeparateDatabaseAndState — state-only,
     no SQL emitted).

After this migration is applied, running `makemigrations signals` will
produce a clean CreateModel for the Wave B schema — no incremental
RemoveField/AddField guesswork, no interactive default prompts.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('module_signals', '0005_signalclusterarchival'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name='ObjectiveSignal'),
            ],
        ),
    ]