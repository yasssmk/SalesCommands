# app_modules/signals/migrations/0037_backfill_constraint_target_departments.py
"""
Backfill ConstraintSignal.target_departments (M2M) from the legacy
target_department (FK).

Sub-step 1a/… of the "Signal scope (department)" sprint. Migration 0036
added the M2M; this data migration preserves the existing scope by copying
each row's single target_department into the new M2M as its (only) entry.
Contrast with the TechStack precedent (migration 0027) which had NOTHING to
backfill — here real rows carry a target_department that must survive the
FK→M2M transition.

  * forwards: for every ConstraintSignal whose target_department FK is set,
    add that department to target_departments. Idempotent — re-running adds
    no duplicate (M2M .add of an existing link is a no-op).
  * reverse: clear target_departments for the rows that carry a
    target_department (the exact set forwards touched). The legacy FK is left
    untouched either way — this migration only writes the M2M.

Uses apps.get_model (historical model state), never a direct import, so the
migration runs against the schema as it was at this point in history.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    ConstraintSignal = apps.get_model("module_signals", "ConstraintSignal")
    for signal in ConstraintSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.add(signal.target_department_id)


def reverse(apps, schema_editor):
    ConstraintSignal = apps.get_model("module_signals", "ConstraintSignal")
    for signal in ConstraintSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.clear()


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0036_constraintsignal_target_departments"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
