# app_modules/decision_cycles/migrations/0022_remove_decisioncycle_closed_at.py
"""
Drop DecisionCycle.closed_at — converged onto the single close date.

``closed_at`` was added by 0021 earlier in this same branch as a WON-only
timestamp for windowing won amounts. It is redundant with ``outcome_date``,
which every closed cycle has carried since 0009: outcome_date is set on every
close (views/views.py:735) and cleared on reopen (:839), giving one field and
one invariant instead of two overlapping ones.

0021 is NOT rewritten or deleted — it is already applied on the test database,
so the column is removed forward, by this migration, depending on it.

Nothing is lost: no reader outside the two quota windows ever read closed_at,
and both now select WON by status and window on outcome_date.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('decision_cycles', '0021_decisioncycle_closed_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='decisioncycle',
            name='closed_at',
        ),
    ]
