# app_modules/decision_cycles/migrations/0021_decisioncycle_closed_at.py
"""
Add DecisionCycle.closed_at — the timestamp of the latest transition to WON.

SCHEMA ONLY, nullable, no backfill (PO decision): cycles already WON keep
``closed_at = NULL``. Consequence to keep in mind when reading the numbers — a
WON-amount read that is WINDOWED on a period cannot see those historic wins
until they are re-won; unwindowed reads (period=None, the campaign objectives)
are unaffected.

The value is stamped by DecisionCycle.save() on the outcome transition, never by
a default or a DB trigger.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('decision_cycles', '0020_dealproduct_discount_percent_bounds'),
    ]

    operations = [
        migrations.AddField(
            model_name='decisioncycle',
            name='closed_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                editable=False,
                help_text=(
                    'Timestamp of the LATEST transition to WON, stamped '
                    'automatically by save() — the anchor won amounts are '
                    'windowed on. Re-winning a reopened cycle overwrites it; '
                    'reopening leaves it untouched (it is only ever read for a '
                    'cycle whose outcome IS WON). Null on a cycle that has never '
                    'been won, and on cycles won before this field existed (no '
                    'backfill, PO decision).'
                ),
                verbose_name='Closed At (won)',
            ),
        ),
    ]
