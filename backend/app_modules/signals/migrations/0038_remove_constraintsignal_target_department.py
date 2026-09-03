# app_modules/signals/migrations/0038_remove_constraintsignal_target_department.py
"""
Drop the legacy single-FK target_department from ConstraintSignal.

Sub-step 1d of the "Signal scope (department)" sprint — the finition of the
constraint FK→M2M move:

  * 0036 added the multi-department M2M target_departments;
  * 0037 backfilled it from the single FK;
  * 1b recabled every reader (serializer, clustering, prep_call, deal_health,
    aggregated endpoint) onto the M2M and 1c moved extraction onto it, so the
    FK target_department has NO remaining reader or writer in live code
    (verified by audit — only historical migrations 0036/0037 reference it,
    which read the FK against their own historical model state and are
    unaffected).

  * RemoveField target_department — reversible: reversing re-adds the nullable
    FK from the historical state carried by 0037, restoring the (empty) column.
    No data-migration step: the M2M already carries the departments.

Only ConstraintSignal is touched. Pain/Impact/Objective/People keep their own
target_department FK.

Scope note: the unrelated signalclusterarchival.signal_type choices drift that
makemigrations proposes alongside is intentionally NOT included — it is a
pre-existing, choices-only (no-DDL) drift left by the People sprint and belongs
to a dedicated sanitization migration, not to this scope-M2M sub-step. Same
stance as migrations 0027/0028/0031/0036. This migration is hand-written so it
carries ONLY the RemoveField.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0037_backfill_constraint_target_departments"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="constraintsignal",
            name="target_department",
        ),
    ]
