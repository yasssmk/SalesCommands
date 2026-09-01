# app_modules/signals/migrations/0040_backfill_pain_impact_target_departments.py
"""
Backfill PainSignal.target_departments and ImpactSignal.target_departments
(M2M) from the legacy target_department (FK).

Sub-step 2a/… of the "Signal scope (department)" sprint. Migration 0039 added
the two M2Ms; this data migration preserves the existing scope by copying each
row's single target_department into the corresponding M2M as its (only) entry.
Same shape as the Constraint backfill (migration 0037).

Two INDEPENDENT backfills — one per model, each its own RunPython operation so
Pain and Impact are provable separately:

  * backfill_pain / reverse_pain  — PainSignal
  * backfill_impact / reverse_impact — ImpactSignal

forwards: for every signal whose target_department FK is set, add that
department to target_departments. Idempotent — re-running adds no duplicate
(M2M .add of an existing link is a no-op).
reverse: clear target_departments for the rows that carry a target_department
(the exact set forwards touched). The legacy FK is left untouched either way —
this migration only writes the M2M.

Uses apps.get_model (historical model state), never a direct import.
"""

from django.db import migrations


def backfill_pain(apps, schema_editor):
    PainSignal = apps.get_model("module_signals", "PainSignal")
    for signal in PainSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.add(signal.target_department_id)


def reverse_pain(apps, schema_editor):
    PainSignal = apps.get_model("module_signals", "PainSignal")
    for signal in PainSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.clear()


def backfill_impact(apps, schema_editor):
    ImpactSignal = apps.get_model("module_signals", "ImpactSignal")
    for signal in ImpactSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.add(signal.target_department_id)


def reverse_impact(apps, schema_editor):
    ImpactSignal = apps.get_model("module_signals", "ImpactSignal")
    for signal in ImpactSignal.objects.filter(
        target_department__isnull=False
    ).iterator():
        signal.target_departments.clear()


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0039_pain_impact_target_departments"),
    ]

    operations = [
        migrations.RunPython(backfill_pain, reverse_pain),
        migrations.RunPython(backfill_impact, reverse_impact),
    ]
